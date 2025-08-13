from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from .models import AudioFile, Transcription
from .serializers import (
    AudioFileSerializer,
    AudioFileUploadSerializer,
    TranscriptionSerializer,
)
from .tasks import process_transcription
from apps.core.permissions import IsOwner
from apps.core.exceptions import AudioFileError, TranscriptionError


class AudioFileListView(generics.ListAPIView):
    """List all audio files for the authenticated user."""

    serializer_class = AudioFileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AudioFile.objects.filter(owner=self.request.user)


class AudioFileDetailView(generics.RetrieveDestroyAPIView):
    """Retrieve or delete a specific audio file."""

    serializer_class = AudioFileSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return AudioFile.objects.filter(owner=self.request.user)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def upload_audio(request):
    """Upload and process an audio file."""
    serializer = AudioFileUploadSerializer(data=request.data)

    if serializer.is_valid():
        try:
            # Create audio file record
            audio_file = AudioFile.objects.create(
                owner=request.user,
                file=serializer.validated_data["file"],
                original_filename=serializer.validated_data["file"].name,
                file_size=serializer.validated_data["file"].size,
                status="ready",  # Ready for transcription
            )

            # Return the created audio file
            response_serializer = AudioFileSerializer(audio_file)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except AudioFileError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "Upload failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def retranscribe(request, audio_file_id):
    """Retry transcription for a failed audio file."""
    audio_file = get_object_or_404(AudioFile, id=audio_file_id, owner=request.user)

    if audio_file.status not in ["failed", "ready", "completed"]:
        return Response(
            {"error": "Cannot retranscribe file that is currently processing"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        language = request.data.get("language", "auto")
        # For now, process synchronously. In production, use Celery:
        # process_transcription_async.delay(audio_file.id, language)
        process_transcription(audio_file.id, language)

        audio_file.refresh_from_db()
        serializer = AudioFileSerializer(audio_file)
        return Response(serializer.data)

    except TranscriptionError as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_transcription(request, audio_file_id):
    """Update transcription text and word timestamps."""
    audio_file = get_object_or_404(AudioFile, id=audio_file_id, owner=request.user)

    try:
        transcription = audio_file.transcription
    except Transcription.DoesNotExist:
        return Response(
            {"error": "No transcription found for this file"},
            status=status.HTTP_404_NOT_FOUND,
        )

    new_text = request.data.get("text", "").strip()
    word_timestamps = request.data.get("word_timestamps", [])

    if not new_text:
        return Response(
            {"error": "Text cannot be empty"}, status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Update transcription text
        transcription.text = new_text
        transcription.save()

        # Update word timestamps
        from .models import TranscriptionWord

        # Delete existing word timestamps
        TranscriptionWord.objects.filter(transcription=transcription).delete()

        # Create new word timestamps
        for word_data in word_timestamps:
            TranscriptionWord.objects.create(
                transcription=transcription,
                word=word_data.get("word", ""),
                start_time=word_data.get("start", 0.0),
                end_time=word_data.get("end", 0.0),
                confidence_score=0.95,  # Default confidence for edited words
                word_index=word_data.get("index", 0),
            )

        return Response(
            {
                "message": "Transcription updated successfully",
                "text": transcription.text,
                "word_count": len(word_timestamps),
            }
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to update transcription: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class TranscriptionDetailView(generics.RetrieveAPIView):
    """Retrieve transcription details."""

    serializer_class = TranscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transcription.objects.filter(audio_file__owner=self.request.user)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transcription_by_audio_file(request, audio_file_id):
    """Get transcription for a specific audio file."""
    audio_file = get_object_or_404(AudioFile, id=audio_file_id, owner=request.user)

    try:
        transcription = audio_file.transcription
        serializer = TranscriptionSerializer(transcription)
        return Response(serializer.data)
    except Transcription.DoesNotExist:
        return Response(
            {"error": "Transcription not available"}, status=status.HTTP_404_NOT_FOUND
        )
