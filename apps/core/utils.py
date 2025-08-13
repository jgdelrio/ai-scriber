"""
Utility functions for the application.
"""

import os
import uuid
from django.utils.text import slugify


def get_file_extension(filename):
    """Get file extension from filename."""
    return os.path.splitext(filename)[1].lower()


def generate_unique_filename(filename):
    """Generate unique filename with UUID prefix."""
    name, ext = os.path.splitext(filename)
    return f"{uuid.uuid4().hex}_{slugify(name)}{ext}"


def validate_audio_file(file):
    """Validate audio file format and size."""
    from django.conf import settings
    from .exceptions import UnsupportedAudioFormat, AudioFileTooLarge

    # Check file size
    if file.size > settings.MAX_AUDIO_FILE_SIZE:
        raise AudioFileTooLarge(
            f"File size exceeds {settings.MAX_AUDIO_FILE_SIZE} bytes"
        )

    # Check file format
    ext = get_file_extension(file.name)[1:]  # Remove the dot
    if ext not in settings.SUPPORTED_AUDIO_FORMATS:
        raise UnsupportedAudioFormat(f"Unsupported format: {ext}")

    return True
