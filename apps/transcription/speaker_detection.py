"""
Speaker detection service integration.

Enables calling a 3rd party service that integrates the speaker detected identification in the transcription.
"""

import logging
import requests
import tempfile
import os
import json
from django.conf import settings
from typing import Optional, Dict, Any
from apps.core.exceptions import TranscriptionError

logger = logging.getLogger(__name__)


def _save_debug_data(audio_file, payload: Dict[str, Any]) -> None:
    """
    Save audio file and transcription data for debugging purposes.

    Args:
        audio_file: Django audio file object
        payload: Dictionary containing transcription data
    """
    try:
        # Create debug directory if it doesn't exist
        debug_dir = os.path.join(settings.MEDIA_ROOT, 'detection_debug')
        os.makedirs(debug_dir, exist_ok=True)

        # Generate filename based on original audio filename
        base_name = os.path.splitext(audio_file.original_filename)[0]
        timestamp = str(int(audio_file.created_at.timestamp())) if hasattr(audio_file, 'created_at') else 'unknown'

        # Save audio file copy using a new file handle
        audio_debug_path = os.path.join(debug_dir, f"{base_name}_{timestamp}.mp3")
        try:
            # Open the Django file with a fresh context manager
            with audio_file.file.open('rb') as source_file:
                with open(audio_debug_path, 'wb') as debug_audio:
                    debug_audio.write(source_file.read())
        except Exception as file_error:
            logger.warning(f"Could not save debug audio file: {str(file_error)}")

        # Save transcription data as JSON
        json_debug_path = os.path.join(debug_dir, f"{base_name}_{timestamp}.json")
        with open(json_debug_path, 'w', encoding='utf-8') as debug_json:
            json.dump(payload, debug_json, indent=2, ensure_ascii=False)

        logger.info(f"Debug data saved: {audio_debug_path} and {json_debug_path}")

    except Exception as err:
        logger.warning(f"Failed to save debug data: {str(err)}")


class SpeakerDetectionService:
    """Service for integrating with external speaker detection API."""

    def __init__(self):
        self.host = getattr(settings, 'SPEAKER_DETECTION_HOST', '')
        self.port = getattr(settings, 'SPEAKER_DETECTION_PORT', '')
        self.enabled = bool(self.host and self.port)
        self.base_url = f"http://{self.host}:{self.port}" if self.enabled else None
        self.timeout = 300  # 5 minutes timeout for speaker detection
        
    def is_enabled(self) -> bool:
        """Check if speaker detection service is enabled."""
        return self.enabled
    
    def check_health(self) -> bool:
        """
        Check if the speaker detection service is available.
        
        Returns:
            bool: True if service is healthy, False otherwise
        """
        if not self.enabled:
            return False
            
        try:
            logger.info(f"Checking speaker detection service health at {self.base_url}/healthcheck")
            response = requests.get(
                f"{self.base_url}/healthcheck",
                timeout=10
            )
            
            is_healthy = response.status_code == 200
            if is_healthy:
                logger.info("✅ Speaker detection service is healthy")
            else:
                logger.warning(f"❌ Speaker detection service health check failed: HTTP {response.status_code}")
                
            return is_healthy
            
        except requests.exceptions.RequestException as err:
            logger.warning(f"❌ Speaker detection service health check failed: {str(err)}")
            return False
    
    def detect_speakers(self, audio_file, transcription_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Send audio file and transcription to speaker detection service.
        
        Args:
            audio_file: Django audio file object
            transcription_data: Dictionary containing transcription text and word timestamps
            
        Returns:
            Dict containing speaker-separated transcription data, or None if failed
        """
        if not self.enabled:
            logger.debug("Speaker detection service not enabled")
            return None
            
        try:
            logger.info(f"Sending transcription to speaker detection service for {audio_file.original_filename}")
            
            # Log timestamp information being sent
            word_count = len(transcription_data.get('words', []))
            segment_count = len(transcription_data.get('segments', []))
            logger.info(f"Sending {word_count} words and {segment_count} segments with timestamps")
            
            # Prepare the transcription payload with detailed timestamps
            payload = {
                'text': transcription_data.get('text', ''),
                'language': transcription_data.get('language', 'en'),
                'confidence_score': transcription_data.get('confidence_score', 0.95),
                'processing_time': transcription_data.get('processing_time', 0.0),
                'words': transcription_data.get('words', []),
                'segments': transcription_data.get('segments', [])
            }

            with audio_file.file.open('rb') as f:
                stored_filename = audio_file.file.name
                stored_extension = stored_filename.split('.')[-1].lower()
                mime_type = 'audio/mpeg' if stored_extension == 'mp3' else 'audio/mpeg'

                files = {
                    'audio': (
                        audio_file.original_filename,
                        f.read(),
                        mime_type
                    )
                }

                data = {
                    'transcription_data': json.dumps(payload)  # ✅ Convert to string for form data
                }

                response = requests.post(
                    f"{self.base_url}/speaker-identification",
                    files=files,
                    data=data,  # ✅ Use data instead of json - clean multipart/form-data
                    timeout=self.timeout
                )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Speaker detection completed for {audio_file.original_filename}")
                logger.debug(f"Detected {len(result.get('speakers', []))} speakers")
                return result
            else:
                logger.error(f"Speaker detection API error: HTTP {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Speaker detection request timed out after {self.timeout}s")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Speaker detection request failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in speaker detection: {str(e)}")
            return None
    
    def update_transcription_with_speakers(self, transcription, speaker_data: Dict[str, Any]) -> bool:
        """
        Update transcription with speaker-separated data.
        
        Args:
            transcription: Transcription model instance
            speaker_data: Speaker detection response data
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            if not speaker_data or 'speakers' not in speaker_data:
                logger.warning("No speaker data to process")
                return False
            
            from .models import TranscriptionSegment, TranscriptionWord, Speaker
            
            # Create Speaker records
            transcription.speakers.all().delete()  # Clear existing speakers
            speakers_created = []
            
            for speaker_info in speaker_data.get('speakers', []):
                speaker = Speaker.objects.create(
                    transcription=transcription,
                    speaker_id=speaker_info.get('speaker_id', ''),
                    speaker_label=speaker_info.get('speaker_label', ''),
                    confidence_score=speaker_info.get('confidence', 0.95),
                    total_speaking_time=speaker_info.get('total_speaking_time', 0.0),
                    word_count=speaker_info.get('word_count', 0)
                )
                speakers_created.append(speaker)
            
            logger.info(f"Created {len(speakers_created)} speaker records")
            
            # Update segments with speaker information if available
            if 'speaker_segments' in speaker_data:
                # Clear existing segments
                TranscriptionSegment.objects.filter(transcription=transcription).delete()
                
                # Create new segments with speaker information
                for segment_data in speaker_data['speaker_segments']:
                    TranscriptionSegment.objects.create(
                        transcription=transcription,
                        start_time=segment_data.get('start_time', 0.0),
                        end_time=segment_data.get('end_time', 0.0),
                        text=segment_data.get('text', ''),
                        confidence_score=segment_data.get('confidence', 0.95),
                        speaker_id=segment_data.get('speaker_id'),
                        speaker_label=segment_data.get('speaker_label')
                    )
                
                logger.info(f"Created {len(speaker_data['speaker_segments'])} speaker-aware segments")
            
            # Update word-level data with speaker information if available
            if 'speaker_words' in speaker_data:
                # Update existing words with speaker information
                for word_data in speaker_data['speaker_words']:
                    word_index = word_data.get('word_index')
                    speaker_id = word_data.get('speaker_id')
                    
                    if word_index is not None and speaker_id is not None:
                        TranscriptionWord.objects.filter(
                            transcription=transcription,
                            word_index=word_index
                        ).update(speaker_id=speaker_id)
            
            # Generate and save speaker-separated text
            transcription.speaker_separated_text = transcription.generate_speaker_separated_text()
            
            # Update main transcription text if provided (optional, preserves original)
            if 'speaker_separated_text' in speaker_data:
                transcription.speaker_separated_text = speaker_data['speaker_separated_text']
            
            transcription.save()
            logger.info(f"Updated transcription with {len(speakers_created)} speakers and speaker-separated text")
            return True
            
        except Exception as e:
            logger.error(f"Error updating transcription with speaker data: {str(e)}")
            return False


# Global instance
speaker_detection_service = SpeakerDetectionService()