"""
Services for transcription processing.
"""

import logging
import time
import tempfile
import os
import numpy as np
import librosa
from openai import OpenAI
from django.conf import settings
from django.core.files.base import ContentFile
from pydub import AudioSegment
from .models import AudioFile, Transcription, TranscriptionSegment, TranscriptionWord
from apps.core.exceptions import TranscriptionError

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for handling audio transcription using OpenAI Whisper."""

    def __init__(self, max_segment_duration: int = 480, max_segment_size: int = 20 * 1024 * 1024):
        """
        Initialize the service.

            max_segment_duration: max duration in seconds (default: 480 = 8 minutes)
            max_segment_size: max file size in bytes (default: 20MB)
        """
        self.use_mock = not settings.OPENAI_API_KEY
        if not self.use_mock:
            self.client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=getattr(settings, 'OPENAI_CALL_TIMEOUT', 600)
            )
        self.max_segment_duration = max_segment_duration
        self.max_segment_size = max_segment_size
        
        # Formats that OpenAI Whisper supports natively
        self.openai_native_formats = ['mp3', 'mp4', 'mpeg', 'mpga', 'm4a', 'webm']

    def transcribe_audio(self, audio_file_id, language="auto"):
        """
        Transcribe an audio file using OpenAI Whisper API or mock service.
        """
        start_time = time.time()

        try:
            audio_file = AudioFile.objects.get(id=audio_file_id)
            audio_file.status = "processing"
            audio_file.save()

            logger.info(f"Starting transcription for audio file {audio_file_id}")
            
            # Check if audio needs segmentation
            duration = self._get_audio_duration(audio_file)
            if duration:
                audio_file.duration = duration
                audio_file.save()
                logger.info(f"Audio file duration: {duration:.2f}s")
            
            if self.use_mock:
                # Use mock transcription for testing
                transcription_text = (
                    f"This is a mock transcription for the file '{audio_file.original_filename}'. "
                    f"In a real implementation, this would be the actual transcribed text from the audio file. "
                    f"The transcription service would process the audio and return the spoken content. "
                    f"This mock shows how the system would work with real transcription data."
                )
                detected_language = language if language != "auto" else "en"
                processing_time = time.time() - start_time

                # Simulate some processing time
                time.sleep(1)

            else:
                # Use real OpenAI Whisper API with segmentation for long files
                segments = self._segment_audio(audio_file)
                
                all_transcriptions = []
                all_words = []
                detected_language = language
                
                for segment_idx, (audio_segment, segment_start_time) in enumerate(segments):
                    logger.info(f"Transcribing segment {segment_idx + 1}/{len(segments)} (start: {segment_start_time:.2f}s)")
                    
                    # Export segment to temporary file for OpenAI API (always as MP3)
                    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
                        try:
                            # Ensure segment is in the right format for OpenAI (MP3, optimized for speech)
                            optimized_segment = audio_segment.set_frame_rate(16000).set_channels(1)
                            optimized_segment.export(
                                temp_file.name, 
                                format="mp3",
                                bitrate="128k",
                                parameters=['-q:a', '2']
                            )
                            
                            with open(temp_file.name, "rb") as segment_file:
                                segment_response = self.client.audio.transcriptions.create(
                                    file=(f"{audio_file.original_filename}_segment_{segment_idx + 1}.mp3", segment_file, "audio/mpeg"),
                                    model="whisper-1",
                                    response_format="verbose_json",
                                    timestamp_granularities=["word"],
                                    language=None if language == "auto" else language,
                                )
                            
                            # Store segment transcription
                            all_transcriptions.append(segment_response.text)
                            
                            # Adjust word timestamps to match the full audio timeline
                            if hasattr(segment_response, 'words') and segment_response.words:
                                for word in segment_response.words:
                                    adjusted_word = {
                                        'word': word.word if hasattr(word, 'word') else word.get('word', ''),
                                        'start': (word.start if hasattr(word, 'start') else word.get('start', 0.0)) + segment_start_time,
                                        'end': (word.end if hasattr(word, 'end') else word.get('end', 0.0)) + segment_start_time,
                                        'confidence': word.confidence if hasattr(word, 'confidence') else word.get('confidence', 1.0)
                                    }
                                    all_words.append(adjusted_word)
                            
                            # Get language from first segment
                            if segment_idx == 0:
                                detected_language = getattr(segment_response, "language", language)
                                
                        finally:
                            # Clean up temporary file
                            if os.path.exists(temp_file.name):
                                os.unlink(temp_file.name)
                
                processing_time = time.time() - start_time
                transcription_text = " ".join(all_transcriptions)
                
                # Create a mock response object with combined words
                class CombinedResponse:
                    def __init__(self, text, words, language):
                        self.text = text
                        self.words = words
                        self.language = language
                
                transcription_response = CombinedResponse(transcription_text, all_words, detected_language)

            # Create transcription record
            transcription = Transcription.objects.create(
                audio_file=audio_file,
                text=transcription_text,
                language=detected_language,
                confidence_score=self._calculate_average_confidence(
                    transcription_response if not self.use_mock else None
                ),
                processing_time=processing_time,
            )

            # Create segments and word timestamps
            if self.use_mock:
                self._create_sentence_segments(transcription)
                self._create_mock_word_timestamps(transcription)
            else:
                self._create_segments_from_words(transcription, transcription_response)
                self._create_word_timestamps(transcription, transcription_response)

            audio_file.status = "completed"
            audio_file.save()

            logger.info(
                f"Successfully transcribed audio file {audio_file_id} in {processing_time:.2f}s"
            )
            return transcription

        except AudioFile.DoesNotExist:
            raise TranscriptionError(f"Audio file with id {audio_file_id} not found")
        except Exception as e:
            logger.error(f"Error transcribing audio file {audio_file_id}: {str(e)}")
            if "audio_file" in locals():
                audio_file.status = "failed"
                audio_file.save()
            raise TranscriptionError(f"Transcription failed: {str(e)}")

    def _calculate_average_confidence(self, transcription_response):
        """Calculate average confidence from word-level data if available."""
        if transcription_response is None:
            return 0.95  # Default confidence for mock

        try:
            # Try different ways to access word data from OpenAI response
            words_data = None

            if (
                hasattr(transcription_response, "words")
                and transcription_response.words
            ):
                words_data = transcription_response.words
            elif (
                hasattr(transcription_response, "json")
                and "words" in transcription_response.json()
            ):
                words_data = transcription_response.json()["words"]
            elif (
                isinstance(transcription_response, dict)
                and "words" in transcription_response
            ):
                words_data = transcription_response["words"]

            if words_data:
                confidences = []
                for word in words_data:
                    if hasattr(word, "confidence"):
                        confidences.append(float(word.confidence))
                    elif isinstance(word, dict) and "confidence" in word:
                        confidences.append(float(word["confidence"]))
                    else:
                        confidences.append(1.0)  # Default if no confidence

                if confidences:
                    return sum(confidences) / len(confidences)

        except (AttributeError, KeyError, TypeError, ValueError) as e:
            logger.warning(f"Error calculating confidence: {str(e)}")

        return 0.95  # Default confidence if not available

    def _create_segments_from_words(self, transcription, transcription_response):
        """Create segments from word-level timestamps."""
        try:
            # Try different ways to access word data from OpenAI response
            words_data = None

            if (
                hasattr(transcription_response, "words")
                and transcription_response.words
            ):
                words_data = transcription_response.words
            elif (
                hasattr(transcription_response, "json")
                and "words" in transcription_response.json()
            ):
                words_data = transcription_response.json()["words"]
            elif (
                isinstance(transcription_response, dict)
                and "words" in transcription_response
            ):
                words_data = transcription_response["words"]

            if not words_data:
                # Fallback to sentence-based segments if words not available
                self._create_sentence_segments(transcription)
                return

            segment_duration = 30.0  # Group words into 30-second segments
            current_segment_words = []
            segment_start = None

            for word in words_data:
                # Handle both dict and object attribute access
                if hasattr(word, "start"):
                    word_start = float(word.start)
                    word_end = float(word.end)
                    word_text = word.word.strip()
                else:
                    word_start = float(word.get("start", 0.0))
                    word_end = float(word.get("end", 0.0))
                    word_text = word.get("word", "").strip()

                if segment_start is None:
                    segment_start = word_start

                current_segment_words.append(word_text)

                # Create segment if duration exceeded or it's the last word
                if (word_end - segment_start >= segment_duration) or (
                    word == words_data[-1]
                ):
                    segment_text = " ".join(current_segment_words).strip()
                    if segment_text:
                        TranscriptionSegment.objects.create(
                            transcription=transcription,
                            start_time=segment_start,
                            end_time=word_end,
                            text=segment_text,
                            confidence_score=self._calculate_segment_confidence(
                                current_segment_words, words_data
                            ),
                        )

                    # Reset for next segment
                    current_segment_words = []
                    segment_start = None

        except Exception as e:
            logger.warning(
                f"Error creating word-based segments: {str(e)}, falling back to sentence segments"
            )
            logger.exception("Full traceback for segment creation error:")
            self._create_sentence_segments(transcription)

    def _create_sentence_segments(self, transcription):
        """Fallback method to create sentence-based segments."""
        text = transcription.text
        sentences = text.split(". ")
        duration_per_char = 0.1  # Rough estimate
        current_time = 0.0

        for sentence in sentences:
            if sentence.strip():
                sentence = sentence.strip() + (
                    "." if not sentence.endswith(".") else ""
                )
                segment_duration = len(sentence) * duration_per_char

                TranscriptionSegment.objects.create(
                    transcription=transcription,
                    start_time=current_time,
                    end_time=current_time + segment_duration,
                    text=sentence,
                    confidence_score=transcription.confidence_score or 0.95,
                )

                current_time += segment_duration

    def _create_word_timestamps(self, transcription, transcription_response):
        """Create word-level timestamps from OpenAI response."""
        try:
            # Check if word-level timestamps are available in the response
            words_data = None

            # Try different ways to access word data from OpenAI response
            if (
                hasattr(transcription_response, "words")
                and transcription_response.words
            ):
                words_data = transcription_response.words
            elif (
                hasattr(transcription_response, "json")
                and "words" in transcription_response.json()
            ):
                words_data = transcription_response.json()["words"]
            elif (
                isinstance(transcription_response, dict)
                and "words" in transcription_response
            ):
                words_data = transcription_response["words"]

            if not words_data:
                logger.warning(
                    "No word-level timestamps available in OpenAI response, creating mock words"
                )
                self._create_mock_word_timestamps(transcription)
                return

            logger.info(
                f"Creating {len(words_data)} real word timestamps from OpenAI API"
            )

            for index, word_data in enumerate(words_data):
                # Handle both dict and object attribute access
                if hasattr(word_data, "word"):
                    word_text = word_data.word.strip()
                    start_time = getattr(word_data, "start", 0.0)
                    end_time = getattr(word_data, "end", 0.0)
                    confidence = getattr(word_data, "confidence", 1.0)
                else:
                    word_text = word_data.get("word", "").strip()
                    start_time = word_data.get("start", 0.0)
                    end_time = word_data.get("end", 0.0)
                    confidence = word_data.get("confidence", 1.0)

                TranscriptionWord.objects.create(
                    transcription=transcription,
                    word=word_text,
                    start_time=float(start_time),
                    end_time=float(end_time),
                    confidence_score=float(confidence),
                    word_index=index,
                )

        except Exception as e:
            logger.warning(
                f"Error creating word timestamps: {str(e)}, falling back to mock"
            )
            logger.exception("Full traceback for word timestamp creation error:")
            self._create_mock_word_timestamps(transcription)

    def _create_mock_word_timestamps(self, transcription):
        """Create realistic mock word timestamps for testing."""
        words = transcription.text.split()

        # More realistic timing based on word characteristics
        current_time = 0.0
        average_words_per_minute = 150  # Typical speaking pace
        base_duration = 60.0 / average_words_per_minute  # ~0.4 seconds per word

        for index, word in enumerate(words):
            # Adjust duration based on word length and characteristics
            word_length_factor = max(
                0.3, min(2.0, len(word) / 5.0)
            )  # Longer words take more time

            # Add some natural variation
            import random

            variation = random.uniform(0.8, 1.2)  # ±20% variation

            # Punctuation causes slight pauses
            pause_factor = 1.3 if word.endswith((",", ".", "!", "?", ";", ":")) else 1.0

            duration = base_duration * word_length_factor * variation * pause_factor

            # Ensure minimum and maximum durations
            duration = max(0.2, min(1.5, duration))

            start_time = current_time
            end_time = start_time + duration

            TranscriptionWord.objects.create(
                transcription=transcription,
                word=word,
                start_time=start_time,
                end_time=end_time,
                confidence_score=0.95,
                word_index=index,
            )

            current_time = end_time + random.uniform(
                0.05, 0.15
            )  # Small gaps between words

    def _calculate_segment_confidence(self, segment_words, all_words):
        """Calculate confidence for a segment based on its words."""
        try:
            word_confidences = []
            for word_text in segment_words:
                for word_data in all_words:
                    # Handle both dict and object attribute access
                    if hasattr(word_data, "word"):
                        word_str = word_data.word.strip()
                        confidence = getattr(word_data, "confidence", 1.0)
                    else:
                        word_str = word_data.get("word", "").strip()
                        confidence = word_data.get("confidence", 1.0)

                    if word_str == word_text.strip():
                        word_confidences.append(float(confidence))
                        break

            if word_confidences:
                return sum(word_confidences) / len(word_confidences)
        except Exception as e:
            logger.warning(f"Error calculating segment confidence: {str(e)}")
        return 0.95
    
    def _get_audio_duration(self, audio_file):
        """Get audio file duration using pydub."""
        try:
            with audio_file.file.open('rb') as file:
                audio = AudioSegment.from_file(file)
                return len(audio) / 1000.0  # Convert milliseconds to seconds
        except Exception as e:
            logger.warning(f"Could not determine audio duration: {str(e)}")
            return None
    
    def _segment_audio(self, audio_file):
        """Segment audio file into chunks based on duration and file size constraints."""
        converted_temp_file = None
        try:
            # Check if conversion is needed
            if self._needs_conversion(audio_file):
                logger.info(f"Non-native format detected, converting to MP3 first")
                audio, converted_temp_file = self._convert_to_mp3(audio_file)
            else:
                # Load audio file directly for native formats
                with audio_file.file.open('rb') as file:
                    audio = AudioSegment.from_file(file)
            
            duration_ms = len(audio)
            duration_seconds = duration_ms / 1000.0
            
            logger.info(f"Audio duration: {duration_seconds:.2f}s, File size: {audio_file.file_size} bytes")
            
            # Check if file meets both duration and size constraints
            needs_duration_split = duration_seconds > self.max_segment_duration
            needs_size_split = audio_file.file_size > self.max_segment_size
            
            if not needs_duration_split and not needs_size_split:
                # File is small enough in both duration and size
                logger.info("File within limits, processing as single segment")
                return [(audio, 0.0)]
            
            # Determine optimal segment duration based on constraints
            optimal_duration = self._calculate_optimal_segment_duration(
                duration_seconds, audio_file.file_size
            )
            
            logger.info(f"Using optimal segment duration: {optimal_duration:.2f}s")
            
            segments = []
            segment_duration_ms = optimal_duration * 1000  # Convert to milliseconds
            start_ms = 0
            
            while start_ms < duration_ms:
                # Calculate target end point
                target_end_ms = start_ms + segment_duration_ms
                
                # If this is the last segment or close to the end, just use remaining audio
                if target_end_ms >= duration_ms - (segment_duration_ms * 0.1):  # Within 10% of end
                    actual_end_ms = duration_ms
                    logger.info(f"Last segment, using remaining audio until {actual_end_ms/1000.0:.2f}s")
                else:
                    # Find optimal split point using silence detection
                    actual_end_ms = self._find_optimal_split_point(audio, target_end_ms)
                
                # Create segment
                segment = audio[start_ms:actual_end_ms]
                start_time_seconds = start_ms / 1000.0
                
                segments.append((segment, start_time_seconds))
                logger.info(f"Created segment {len(segments)}: {start_time_seconds:.2f}s - {actual_end_ms/1000.0:.2f}s "
                           f"(duration: {(actual_end_ms - start_ms)/1000.0:.2f}s)")
                
                start_ms = actual_end_ms
            
            logger.info(f"Audio segmented into {len(segments)} parts")
            return segments
            
        except Exception as e:
            logger.error(f"Error segmenting audio: {str(e)}")
            raise TranscriptionError(f"Audio segmentation failed: {str(e)}")
        finally:
            # Clean up temporary converted file if it exists
            if converted_temp_file:
                self._cleanup_temp_file(converted_temp_file)
    
    def _calculate_optimal_segment_duration(self, total_duration, file_size):
        """Calculate optimal segment duration based on both time and size constraints."""
        # Calculate duration needed to stay within size limit
        bytes_per_second = file_size / total_duration
        max_duration_for_size = self.max_segment_size / bytes_per_second
        
        # Use the smaller of the two constraints
        optimal_duration = min(self.max_segment_duration, max_duration_for_size)
        
        # Ensure we don't go below 30 seconds (minimum practical segment)
        optimal_duration = max(30, optimal_duration)
        
        logger.info(f"Size constraint allows {max_duration_for_size:.1f}s, "
                   f"time constraint allows {self.max_segment_duration}s, "
                   f"using {optimal_duration:.1f}s")
        
        return optimal_duration
    
    def _needs_conversion(self, audio_file):
        """Check if audio file needs conversion to MP3."""
        file_extension = audio_file.original_filename.split('.')[-1].lower()
        return file_extension not in self.openai_native_formats
    
    def _convert_to_mp3(self, audio_file):
        """
        Convert audio file to MP3 format.
        
        Returns:
            Tuple of (converted_audio_segment, temp_file_path)
        """
        try:
            logger.info(f"Converting {audio_file.original_filename} to MP3 format")
            
            # Load audio file with pydub
            with audio_file.file.open('rb') as file:
                # Detect format from file extension
                file_extension = audio_file.original_filename.split('.')[-1].lower()
                
                # Load audio with appropriate format
                if file_extension in ['ogg', 'oga']:
                    audio = AudioSegment.from_ogg(file)
                elif file_extension == 'flac':
                    audio = AudioSegment.from_file(file, format='flac')
                elif file_extension in ['aac']:
                    audio = AudioSegment.from_file(file, format='aac')
                elif file_extension == 'opus':
                    # Opus files are typically in WebM or OGG containers
                    audio = AudioSegment.from_file(file, format='opus')
                elif file_extension == 'wav':
                    audio = AudioSegment.from_wav(file)
                else:
                    # Generic approach for other formats
                    audio = AudioSegment.from_file(file)
            
            # Convert to MP3 format with good quality settings
            # Set parameters for optimal compatibility with OpenAI
            converted_audio = audio.set_frame_rate(16000)  # 16kHz sample rate (good for speech)
            converted_audio = converted_audio.set_channels(1)  # Mono (reduces file size, good for speech)
            
            # Create temporary file for converted audio
            temp_file = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
            temp_file.close()
            
            # Export as MP3
            converted_audio.export(
                temp_file.name,
                format='mp3',
                bitrate='128k',  # Good quality for speech
                parameters=['-q:a', '2']  # High quality encoding
            )
            
            logger.info(f"Successfully converted to MP3: {temp_file.name}")
            return converted_audio, temp_file.name
            
        except Exception as e:
            logger.error(f"Error converting audio file to MP3: {str(e)}")
            raise TranscriptionError(f"Audio conversion failed: {str(e)}")
    
    def _cleanup_temp_file(self, temp_file_path):
        """Clean up temporary file."""
        try:
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                logger.debug(f"Cleaned up temporary file: {temp_file_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp file {temp_file_path}: {str(e)}")
    
    def _find_optimal_split_point(self, audio, target_split_ms, search_window_ms=10000):
        """
        Find the optimal split point near the target by detecting silence.
        
        Args:
            audio: AudioSegment object
            target_split_ms: Target split point in milliseconds
            search_window_ms: Search window around target (default: 10 seconds)
        
        Returns:
            Optimal split point in milliseconds
        """
        try:
            # Define search range around target
            start_search = max(0, target_split_ms - search_window_ms // 2)
            end_search = min(len(audio), target_split_ms + search_window_ms // 2)
            
            # Extract audio segment for analysis
            search_segment = audio[start_search:end_search]
            
            # Convert to numpy array for librosa analysis
            audio_data = np.array(search_segment.get_array_of_samples())
            
            # Handle stereo audio
            if search_segment.channels == 2:
                audio_data = audio_data.reshape((-1, 2))
                audio_data = audio_data.mean(axis=1)  # Convert to mono
            
            # Normalize audio data
            audio_data = audio_data.astype(np.float32)
            if len(audio_data) > 0:
                audio_data = audio_data / np.max(np.abs(audio_data))
            
            # Use librosa to detect onset frames (speech boundaries)
            sr = search_segment.frame_rate
            hop_length = 512
            
            # Detect onsets (speech starts)
            onset_frames = librosa.onset.onset_detect(
                y=audio_data,
                sr=sr,
                hop_length=hop_length,
                backtrack=True
            )
            
            # Convert onset frames to time positions
            onset_times = librosa.frames_to_time(onset_frames, sr=sr, hop_length=hop_length)
            
            # Also use RMS energy to find quiet segments
            rms = librosa.feature.rms(y=audio_data, hop_length=hop_length)[0]
            rms_times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=hop_length)
            
            # Find low-energy (quiet) regions
            rms_threshold = np.percentile(rms, 25)  # Bottom 25% of energy levels
            quiet_indices = np.where(rms < rms_threshold)[0]
            quiet_times = rms_times[quiet_indices]
            
            # Target time within the search segment (relative to search start)
            target_time_relative = (target_split_ms - start_search) / 1000.0
            
            # Find the best split point by combining onset and quiet regions
            candidates = []
            
            # Add onset points (end of speech segments)
            for onset_time in onset_times:
                if 1.0 < onset_time < (end_search - start_search) / 1000.0 - 1.0:  # Avoid edges
                    distance = abs(onset_time - target_time_relative)
                    candidates.append((distance, onset_time, 'onset'))
            
            # Add quiet regions
            for quiet_time in quiet_times:
                if 1.0 < quiet_time < (end_search - start_search) / 1000.0 - 1.0:  # Avoid edges
                    distance = abs(quiet_time - target_time_relative)
                    candidates.append((distance, quiet_time, 'quiet'))
            
            if candidates:
                # Sort by distance to target and pick the closest
                candidates.sort(key=lambda x: x[0])
                best_candidate = candidates[0]
                optimal_time_relative = best_candidate[1]
                candidate_type = best_candidate[2]
                
                # Convert back to absolute position in full audio
                optimal_split_ms = start_search + (optimal_time_relative * 1000)
                
                logger.info(f"Found optimal split at {optimal_split_ms:.0f}ms "
                           f"(target: {target_split_ms:.0f}ms, "
                           f"offset: {optimal_split_ms - target_split_ms:.0f}ms, "
                           f"type: {candidate_type})")
                
                return int(optimal_split_ms)
            else:
                logger.warning(f"No optimal split point found, using target: {target_split_ms}ms")
                return target_split_ms
                
        except Exception as e:
            logger.warning(f"Error with librosa analysis: {str(e)}, trying pydub silence detection")
            return self._find_split_with_pydub(audio, target_split_ms, search_window_ms)
    
    def _find_split_with_pydub(self, audio, target_split_ms, search_window_ms):
        """Fallback method using pydub's silence detection."""
        try:
            from pydub.silence import detect_nonsilent
            
            # Define search range
            start_search = max(0, target_split_ms - search_window_ms // 2)
            end_search = min(len(audio), target_split_ms + search_window_ms // 2)
            
            # Extract search segment
            search_segment = audio[start_search:end_search]
            
            # Detect non-silent ranges (speech segments)
            nonsilent_ranges = detect_nonsilent(
                search_segment,
                min_silence_len=100,  # Minimum 100ms of silence
                silence_thresh=search_segment.dBFS - 20  # 20dB below average
            )
            
            if nonsilent_ranges:
                # Find speech boundaries (ends of speech segments)
                speech_ends = [end for start, end in nonsilent_ranges]
                
                # Target position within search segment
                target_relative = target_split_ms - start_search
                
                # Find closest speech end to our target
                best_split = target_relative
                min_distance = float('inf')
                
                for speech_end in speech_ends:
                    distance = abs(speech_end - target_relative)
                    if distance < min_distance:
                        min_distance = distance
                        best_split = speech_end
                
                # Convert back to absolute position
                optimal_split_ms = start_search + best_split
                
                logger.info(f"Pydub found split at {optimal_split_ms:.0f}ms "
                           f"(target: {target_split_ms:.0f}ms, "
                           f"offset: {optimal_split_ms - target_split_ms:.0f}ms)")
                
                return int(optimal_split_ms)
            else:
                logger.warning("No speech segments detected with pydub, using target")
                return target_split_ms
                
        except Exception as e:
            logger.warning(f"Pydub fallback also failed: {str(e)}, using target")
            return target_split_ms
