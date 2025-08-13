"""
Services for transcription processing.
"""
import logging
import time
from openai import OpenAI
from django.conf import settings
from .models import AudioFile, Transcription, TranscriptionSegment
from apps.core.exceptions import TranscriptionError

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for handling audio transcription using OpenAI Whisper."""
    
    def __init__(self):
        self.use_mock = not settings.OPENAI_API_KEY
        if not self.use_mock:
            self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def transcribe_audio(self, audio_file_id, language='auto'):
        """
        Transcribe an audio file using OpenAI Whisper API or mock service.
        """
        start_time = time.time()
        
        try:
            audio_file = AudioFile.objects.get(id=audio_file_id)
            audio_file.status = 'processing'
            audio_file.save()
            
            logger.info(f"Starting transcription for audio file {audio_file_id}")
            
            if self.use_mock:
                # Use mock transcription for testing
                transcription_text = f"This is a mock transcription for the file '{audio_file.original_filename}'. " \
                                   f"In a real implementation, this would be the actual transcribed text from the audio file. " \
                                   f"The transcription service would process the audio and return the spoken content. " \
                                   f"This mock shows how the system would work with real transcription data."
                detected_language = language if language != 'auto' else 'en'
                processing_time = time.time() - start_time
                
                # Simulate some processing time
                time.sleep(1)
                
            else:
                # Use real OpenAI Whisper API
                with audio_file.file.open('rb') as file:
                    transcription_response = self.client.audio.transcriptions.create(
                        file=(audio_file.original_filename, file, 'audio/mpeg'),
                        model="whisper-1",
                        response_format="verbose_json",
                        timestamp_granularities=["word"],
                        language=None if language == 'auto' else language
                    )
                
                processing_time = time.time() - start_time
                transcription_text = transcription_response.text
                detected_language = getattr(transcription_response, 'language', language)
            
            # Create transcription record
            transcription = Transcription.objects.create(
                audio_file=audio_file,
                text=transcription_text,
                language=detected_language,
                confidence_score=self._calculate_average_confidence(transcription_response if not self.use_mock else None),
                processing_time=processing_time
            )
            
            # Create segments from word-level timestamps
            if self.use_mock:
                self._create_sentence_segments(transcription)
            else:
                self._create_segments_from_words(transcription, transcription_response)
            
            audio_file.status = 'completed'
            audio_file.save()
            
            logger.info(f"Successfully transcribed audio file {audio_file_id} in {processing_time:.2f}s")
            return transcription
            
        except AudioFile.DoesNotExist:
            raise TranscriptionError(f"Audio file with id {audio_file_id} not found")
        except Exception as e:
            logger.error(f"Error transcribing audio file {audio_file_id}: {str(e)}")
            if 'audio_file' in locals():
                audio_file.status = 'failed'
                audio_file.save()
            raise TranscriptionError(f"Transcription failed: {str(e)}")
    
    def _calculate_average_confidence(self, transcription_response):
        """Calculate average confidence from word-level data if available."""
        if transcription_response is None:
            return 0.95  # Default confidence for mock
            
        try:
            if hasattr(transcription_response, 'words') and transcription_response.words:
                confidences = [word.get('confidence', 1.0) for word in transcription_response.words]
                return sum(confidences) / len(confidences)
        except (AttributeError, KeyError):
            pass
        return 0.95  # Default confidence if not available
    
    def _create_segments_from_words(self, transcription, transcription_response):
        """Create segments from word-level timestamps."""
        try:
            if not hasattr(transcription_response, 'words') or not transcription_response.words:
                # Fallback to sentence-based segments if words not available
                self._create_sentence_segments(transcription)
                return
            
            words = transcription_response.words
            segment_duration = 30.0  # Group words into 30-second segments
            current_segment_words = []
            segment_start = None
            
            for word in words:
                word_start = word.get('start', 0.0)
                word_end = word.get('end', 0.0)
                word_text = word.get('word', '')
                
                if segment_start is None:
                    segment_start = word_start
                
                current_segment_words.append(word_text)
                
                # Create segment if duration exceeded or it's the last word
                if (word_end - segment_start >= segment_duration) or (word == words[-1]):
                    segment_text = ' '.join(current_segment_words).strip()
                    if segment_text:
                        TranscriptionSegment.objects.create(
                            transcription=transcription,
                            start_time=segment_start,
                            end_time=word_end,
                            text=segment_text,
                            confidence_score=self._calculate_segment_confidence(current_segment_words, words)
                        )
                    
                    # Reset for next segment
                    current_segment_words = []
                    segment_start = None
                    
        except Exception as e:
            logger.warning(f"Error creating word-based segments: {str(e)}, falling back to sentence segments")
            self._create_sentence_segments(transcription)
    
    def _create_sentence_segments(self, transcription):
        """Fallback method to create sentence-based segments."""
        text = transcription.text
        sentences = text.split('. ')
        duration_per_char = 0.1  # Rough estimate
        current_time = 0.0
        
        for sentence in sentences:
            if sentence.strip():
                sentence = sentence.strip() + ('.' if not sentence.endswith('.') else '')
                segment_duration = len(sentence) * duration_per_char
                
                TranscriptionSegment.objects.create(
                    transcription=transcription,
                    start_time=current_time,
                    end_time=current_time + segment_duration,
                    text=sentence,
                    confidence_score=transcription.confidence_score or 0.95
                )
                
                current_time += segment_duration
    
    def _calculate_segment_confidence(self, segment_words, all_words):
        """Calculate confidence for a segment based on its words."""
        try:
            word_confidences = []
            for word_text in segment_words:
                for word_data in all_words:
                    if word_data.get('word', '').strip() == word_text.strip():
                        word_confidences.append(word_data.get('confidence', 1.0))
                        break
            
            if word_confidences:
                return sum(word_confidences) / len(word_confidences)
        except Exception:
            pass
        return 0.95