"""
Custom exceptions for the application.
"""


class TranscriptionError(Exception):
    """Exception raised during transcription process."""

    pass


class AudioFileError(Exception):
    """Exception raised for audio file processing errors."""

    pass


class UnsupportedAudioFormat(AudioFileError):
    """Exception raised when audio format is not supported."""

    pass


class AudioFileTooLarge(AudioFileError):
    """Exception raised when audio file is too large."""

    pass
