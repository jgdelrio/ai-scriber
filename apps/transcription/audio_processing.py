"""
Audio processing utilities for format conversion and optimization.
"""

import logging
import tempfile
import os
from django.conf import settings
from django.core.files.base import ContentFile
from pydub import AudioSegment
from apps.core.exceptions import AudioFileError

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Service for audio file processing and conversion."""

    def __init__(self):
        self.force_mp3_conversion = getattr(settings, 'FORCE_MP3_CONVERSION', True)
        
    def should_convert_to_mp3(self, filename):
        """
        Determine if audio file should be converted to MP3.
        
        Args:
            filename: Original filename
            
        Returns:
            bool: True if conversion is needed
        """
        if not self.force_mp3_conversion:
            return False
            
        file_extension = filename.split('.')[-1].lower()
        return file_extension != 'mp3'
    
    def convert_uploaded_file_to_mp3(self, uploaded_file, original_filename):
        """
        Convert uploaded audio file to MP3 format.
        
        Args:
            uploaded_file: Django UploadedFile object
            original_filename: Original filename
            
        Returns:
            Tuple of (converted_file, new_filename)
        """
        if not self.should_convert_to_mp3(original_filename):
            return uploaded_file, original_filename
            
        try:
            logger.info(f"Converting uploaded file {original_filename} to MP3 format")
            
            # Load audio file with pydub
            file_extension = original_filename.split('.')[-1].lower()
            
            # Read the uploaded file content
            uploaded_file.seek(0)  # Ensure we're at the beginning
            file_content = uploaded_file.read()
            uploaded_file.seek(0)  # Reset for potential future use
            
            # Create temporary file for input
            with tempfile.NamedTemporaryFile(suffix=f'.{file_extension}', delete=False) as temp_input:
                temp_input.write(file_content)
                temp_input.flush()
                
                try:
                    # Load audio with appropriate format and error handling
                    audio = self._load_audio_file(temp_input.name, file_extension, original_filename)
                    
                    # Convert to MP3 format with good quality settings
                    # Set parameters for optimal compatibility
                    converted_audio = audio.set_frame_rate(44100)  # Standard sample rate
                    converted_audio = converted_audio.set_channels(2)  # Stereo (preserve original if mono)
                    
                    # Create temporary file for MP3 output
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_output:
                        # Export as MP3 with high quality
                        converted_audio.export(
                            temp_output.name,
                            format='mp3',
                            bitrate='320k',  # High quality
                            parameters=['-q:a', '0']  # Highest quality encoding
                        )
                        
                        # Read the converted MP3 content
                        with open(temp_output.name, 'rb') as mp3_file:
                            mp3_content = mp3_file.read()
                        
                        # Create new filename with .mp3 extension
                        base_name = os.path.splitext(original_filename)[0]
                        new_filename = f"{base_name}.mp3"
                        
                        # Create ContentFile for Django
                        converted_file = ContentFile(mp3_content, name=new_filename)
                        
                        logger.info(f"Successfully converted {original_filename} to MP3 format ({len(mp3_content)} bytes)")
                        
                        return converted_file, new_filename
                        
                finally:
                    # Clean up temporary files
                    if os.path.exists(temp_input.name):
                        os.unlink(temp_input.name)
                    if 'temp_output' in locals() and os.path.exists(temp_output.name):
                        os.unlink(temp_output.name)
                
        except Exception as e:
            logger.error(f"Error converting audio file {original_filename} to MP3: {str(e)}")
            raise AudioFileError(f"Audio conversion to MP3 failed: {str(e)}")
    
    def _load_audio_file(self, file_path, file_extension, original_filename):
        """
        Load audio file using pydub with format-specific handling.
        
        Args:
            file_path: Path to temporary audio file
            file_extension: File extension (lowercase)
            original_filename: Original filename for logging
            
        Returns:
            AudioSegment object
        """
        try:
            # Load audio with appropriate format and error handling
            if file_extension in ['ogg', 'oga']:
                try:
                    return AudioSegment.from_ogg(file_path)
                except Exception:
                    # Fallback for OGG files that might contain Opus
                    return AudioSegment.from_file(file_path)
            elif file_extension == 'flac':
                return AudioSegment.from_file(file_path, format='flac')
            elif file_extension in ['aac']:
                return AudioSegment.from_file(file_path, format='aac')
            elif file_extension == 'opus':
                return self._load_opus_file(file_path, original_filename)
            elif file_extension == 'wav':
                return AudioSegment.from_wav(file_path)
            elif file_extension in ['mp3', 'mpeg', 'mpga']:
                return AudioSegment.from_mp3(file_path)
            elif file_extension in ['mp4', 'm4a']:
                return AudioSegment.from_file(file_path, format='mp4')
            elif file_extension == 'webm':
                return AudioSegment.from_file(file_path, format='webm')
            else:
                # Generic approach for other formats
                return AudioSegment.from_file(file_path)
                
        except Exception as e:
            logger.error(f"Error loading audio file {original_filename}: {str(e)}")
            raise AudioFileError(f"Unable to load audio file: {str(e)}")
    
    def _load_opus_file(self, file_path, original_filename):
        """
        Load Opus file with multiple fallback approaches.
        
        Args:
            file_path: Path to Opus file
            original_filename: Original filename for logging
            
        Returns:
            AudioSegment object
        """
        logger.info(f"Processing Opus file: {original_filename}")
        opus_errors = []
        
        # Try different approaches in order of likelihood
        approaches = [
            ("generic format", lambda: AudioSegment.from_file(file_path)),
            ("explicit opus codec", lambda: AudioSegment.from_file(file_path, format='opus')),
            ("ogg container", lambda: AudioSegment.from_file(file_path, format='ogg')),
            ("webm container", lambda: AudioSegment.from_file(file_path, format='webm')),
            ("raw opus with codec params", lambda: AudioSegment.from_file(file_path, codec='libopus')),
        ]
        
        for approach_name, approach_func in approaches:
            try:
                logger.debug(f"Trying Opus file loading with {approach_name}")
                audio = approach_func()
                logger.info(f"Successfully loaded Opus file using {approach_name}")
                return audio
            except Exception as e:
                error_msg = str(e)
                opus_errors.append(f"{approach_name}: {error_msg}")
                logger.debug(f"Failed with {approach_name}: {error_msg}")
                continue
        
        # Last resort: try ffmpeg direct conversion
        try:
            logger.info("Attempting ffmpeg direct conversion as last resort")
            import subprocess
            
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                # Use ffmpeg to convert directly
                cmd = [
                    'ffmpeg', '-i', file_path, 
                    '-acodec', 'pcm_s16le',  # Standard WAV codec
                    '-ar', '44100',  # 44.1kHz sample rate
                    '-ac', '2',  # Stereo
                    '-y',  # Overwrite output
                    temp_wav.name
                ]
            
                result = subprocess.run(
                    cmd, 
                    capture_output=True, 
                    text=True, 
                    timeout=60
                )
                
                if result.returncode == 0:
                    # Load the converted WAV file
                    audio = AudioSegment.from_wav(temp_wav.name)
                    logger.info("Successfully converted Opus to WAV using direct ffmpeg")
                    return audio
                else:
                    logger.error(f"FFmpeg conversion failed: {result.stderr}")
                    raise Exception(f"FFmpeg error: {result.stderr}")
                    
        except Exception as ffmpeg_error:
            opus_errors.append(f"ffmpeg direct conversion: {str(ffmpeg_error)}")
            logger.error(f"FFmpeg fallback also failed: {str(ffmpeg_error)}")
        finally:
            if 'temp_wav' in locals() and os.path.exists(temp_wav.name):
                try:
                    os.unlink(temp_wav.name)
                except:
                    pass
        
        # All approaches failed
        logger.error(f"All Opus decoding approaches failed for {original_filename}")
        detailed_errors = "\n".join([f"  • {err}" for err in opus_errors])
        raise AudioFileError(
            f"Unable to decode Opus file '{original_filename}'. "
            f"This may be due to an unsupported Opus container format or corrupted file. "
            f"Try converting the file to MP3 format first.\n\nDetailed errors:\n{detailed_errors}"
        )


# Global instance
audio_processor = AudioProcessor()