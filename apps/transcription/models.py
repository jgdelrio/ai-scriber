from django.db import models
from django.contrib.auth import get_user_model
from apps.core.utils import generate_unique_filename

User = get_user_model()


def audio_upload_path(instance, filename):
    """Generate upload path for audio files."""
    return f'audio/{instance.owner.id}/{generate_unique_filename(filename)}'


class AudioFile(models.Model):
    """Model for uploaded audio files."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='audio_files')
    file = models.FileField(upload_to=audio_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    duration = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.original_filename} - {self.owner.email}"


class Transcription(models.Model):
    """Model for transcription results."""
    
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('de', 'German'),
        ('it', 'Italian'),
        ('pt', 'Portuguese'),
        ('ru', 'Russian'),
        ('ja', 'Japanese'),
        ('ko', 'Korean'),
        ('zh', 'Chinese'),
        ('auto', 'Auto-detect'),
    ]
    
    audio_file = models.OneToOneField(AudioFile, on_delete=models.CASCADE, related_name='transcription')
    text = models.TextField(blank=True)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='auto')
    confidence_score = models.FloatField(null=True, blank=True)
    processing_time = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Transcription for {self.audio_file.original_filename}"


class TranscriptionSegment(models.Model):
    """Model for transcription segments with timestamps."""
    
    transcription = models.ForeignKey(Transcription, on_delete=models.CASCADE, related_name='segments')
    start_time = models.FloatField()
    end_time = models.FloatField()
    text = models.TextField()
    confidence_score = models.FloatField(null=True, blank=True)
    
    class Meta:
        ordering = ['start_time']
    
    def __str__(self):
        return f"Segment {self.start_time}-{self.end_time}s"


class TranscriptionWord(models.Model):
    """Model for individual word timestamps."""
    
    transcription = models.ForeignKey(Transcription, on_delete=models.CASCADE, related_name='words')
    word = models.CharField(max_length=100)
    start_time = models.FloatField()
    end_time = models.FloatField()
    confidence_score = models.FloatField(null=True, blank=True)
    word_index = models.PositiveIntegerField()  # Position in the full text
    
    class Meta:
        ordering = ['word_index']
    
    def __str__(self):
        return f"Word '{self.word}' at {self.start_time}s"