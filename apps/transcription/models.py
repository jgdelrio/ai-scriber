from django.db import models
from django.contrib.auth import get_user_model
from apps.core.utils import generate_unique_filename

User = get_user_model()


def audio_upload_path(instance, filename):
    """Generate upload path for audio files."""
    return f"audio/{instance.owner.id}/{generate_unique_filename(filename)}"


class AudioFile(models.Model):
    """Model for uploaded audio files."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="audio_files"
    )
    file = models.FileField(upload_to=audio_upload_path)
    original_filename = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    duration = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.original_filename} - {self.owner.email}"


class Transcription(models.Model):
    """Model for transcription results."""

    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("es", "Spanish"),
        ("fr", "French"),
        ("de", "German"),
        ("it", "Italian"),
        ("pt", "Portuguese"),
        ("ru", "Russian"),
        ("ja", "Japanese"),
        ("ko", "Korean"),
        ("zh", "Chinese"),
        ("auto", "Auto-detect"),
    ]

    SPEAKER_DETECTION_STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("unavailable", "Service Unavailable"),
    ]

    audio_file = models.OneToOneField(
        AudioFile, on_delete=models.CASCADE, related_name="transcription"
    )
    text = models.TextField(blank=True)  # Original transcription text
    speaker_separated_text = models.TextField(blank=True)  # Formatted with speaker labels
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default="auto")
    confidence_score = models.FloatField(null=True, blank=True)
    processing_time = models.FloatField(null=True, blank=True)
    speaker_detection_status = models.CharField(
        max_length=20, 
        choices=SPEAKER_DETECTION_STATUS_CHOICES, 
        default="not_started"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Transcription for {self.audio_file.original_filename}"
    
    def generate_speaker_separated_text(self):
        """
        Generate speaker-separated transcription text from segments.
        
        Returns:
            str: Formatted text with speaker labels and line breaks
        """
        if not self.segments.filter(speaker_id__isnull=False).exists():
            return self.text  # No speaker information, return original text
        
        formatted_lines = []
        current_speaker = None
        current_segment_texts = []
        
        for segment in self.segments.all():
            speaker_display = self._get_speaker_display_name(segment.speaker_id)
            
            # If speaker changed, finalize previous speaker's section
            if current_speaker is not None and current_speaker != speaker_display:
                if current_segment_texts:
                    formatted_lines.append(f"{current_speaker}: {' '.join(current_segment_texts)}")
                current_segment_texts = []
            
            current_speaker = speaker_display
            current_segment_texts.append(segment.text.strip())
        
        # Add the last speaker's section
        if current_speaker and current_segment_texts:
            formatted_lines.append(f"{current_speaker}: {' '.join(current_segment_texts)}")
        
        return '\n\n'.join(formatted_lines)
    
    def _get_speaker_display_name(self, speaker_id):
        """Get the best display name for a speaker."""
        if not speaker_id:
            return "Unknown Speaker"
        
        try:
            speaker = self.speakers.get(speaker_id=speaker_id)
            return speaker.speaker_name or speaker.speaker_label or speaker_id
        except Speaker.DoesNotExist:
            return speaker_id


class Speaker(models.Model):
    """Model for speakers identified in transcriptions."""
    
    transcription = models.ForeignKey(
        Transcription, on_delete=models.CASCADE, related_name="speakers"
    )
    speaker_id = models.CharField(max_length=50)  # e.g., "speaker_1", "speaker_2"
    speaker_label = models.CharField(max_length=100, null=True, blank=True)  # e.g., "John Doe", "Speaker A"
    speaker_name = models.CharField(max_length=100, null=True, blank=True)  # User-assigned name
    confidence_score = models.FloatField(null=True, blank=True)
    total_speaking_time = models.FloatField(default=0.0)  # Total seconds speaking
    word_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ["speaker_id"]
        unique_together = ["transcription", "speaker_id"]
    
    def __str__(self):
        name = self.speaker_name or self.speaker_label or self.speaker_id
        return f"{name} ({self.total_speaking_time:.1f}s)"


class TranscriptionSegment(models.Model):
    """Model for transcription segments with timestamps."""

    transcription = models.ForeignKey(
        Transcription, on_delete=models.CASCADE, related_name="segments"
    )
    start_time = models.FloatField()
    end_time = models.FloatField()
    text = models.TextField()
    confidence_score = models.FloatField(null=True, blank=True)
    speaker_id = models.CharField(max_length=50, null=True, blank=True)
    speaker_label = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        speaker_info = f" ({self.speaker_label})" if self.speaker_label else ""
        return f"Segment {self.start_time}-{self.end_time}s{speaker_info}"


class TranscriptionWord(models.Model):
    """Model for individual word timestamps."""

    transcription = models.ForeignKey(
        Transcription, on_delete=models.CASCADE, related_name="words"
    )
    word = models.CharField(max_length=100)
    start_time = models.FloatField()
    end_time = models.FloatField()
    confidence_score = models.FloatField(null=True, blank=True)
    word_index = models.PositiveIntegerField()  # Position in the full text
    speaker_id = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        ordering = ["word_index"]

    def __str__(self):
        return f"Word '{self.word}' at {self.start_time}s"
