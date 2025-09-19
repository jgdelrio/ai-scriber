from datetime import datetime
from storages.backends.s3boto3 import S3Boto3Storage
from django.conf import settings
import os


class DatePartitionedS3Storage(S3Boto3Storage):
    """
    Custom S3 storage that organizes files by date partitions.
    Structure: user-data/YYYY/MM/DD/audios/ or user-data/YYYY/MM/DD/transcriptions/
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bucket_name = getattr(settings, 'AWS_STORAGE_BUCKET_NAME', 'ai-scriber')
        self.region_name = getattr(settings, 'AWS_S3_REGION_NAME', 'eu-west-1')
    
    def _get_date_partition_path(self, file_type='audios'):
        """
        Generate date-partitioned path.
        
        Args:
            file_type (str): 'audios' or 'transcriptions'
        
        Returns:
            str: Path like 'user-data/2024/01/15/audios/'
        """
        now = datetime.now()
        return f"user-data/{now.year:04d}/{now.month:02d}/{now.day:02d}/{file_type}/"
    
    def get_available_name(self, name, max_length=None):
        """
        Generate available filename with date partitioning.
        """
        # Extract file extension and base name
        base_name, ext = os.path.splitext(name)
        
        # Determine file type based on extension or context
        audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
        text_extensions = {'.txt', '.json', '.csv', '.xml'}
        
        if ext.lower() in audio_extensions:
            file_type = 'audios'
        elif ext.lower() in text_extensions:
            file_type = 'transcriptions'
        else:
            # Default to audios for unknown types
            file_type = 'audios'
        
        # Generate partitioned path
        date_path = self._get_date_partition_path(file_type)
        partitioned_name = f"{date_path}{name}"
        
        return super().get_available_name(partitioned_name, max_length)
    
    def url(self, name):
        """
        Generate URL for the file.
        """
        # Ensure the name includes the full partitioned path
        if not name.startswith('user-data/'):
            # If name doesn't have partition path, add it
            base_name, ext = os.path.splitext(name)
            audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
            file_type = 'audios' if ext.lower() in audio_extensions else 'transcriptions'
            date_path = self._get_date_partition_path(file_type)
            name = f"{date_path}{name}"
        
        return super().url(name)
    
    def delete(self, name):
        """
        Delete file from S3.
        """
        # Ensure the name includes the full partitioned path
        if not name.startswith('user-data/'):
            base_name, ext = os.path.splitext(name)
            audio_extensions = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.aac', '.wma'}
            file_type = 'audios' if ext.lower() in audio_extensions else 'transcriptions'
            date_path = self._get_date_partition_path(file_type)
            name = f"{date_path}{name}"
        
        return super().delete(name)


class TranscriptionS3Storage(DatePartitionedS3Storage):
    """
    Specialized storage for transcription text files.
    """
    
    def get_available_name(self, name, max_length=None):
        """
        Force transcription files to go to transcriptions folder.
        """
        date_path = self._get_date_partition_path('transcriptions')
        partitioned_name = f"{date_path}{name}"
        return S3Boto3Storage.get_available_name(self, partitioned_name, max_length)