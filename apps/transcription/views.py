from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.conf import settings
from .models import AudioFile, Transcription
from .serializers import (
    AudioFileSerializer,
    AudioFileUploadSerializer,
    TranscriptionSerializer,
)
from .tasks import process_transcription
from .audio_processing import audio_processor
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
            uploaded_file = serializer.validated_data["file"]
            original_filename = uploaded_file.name
            
            # Process audio file (convert to MP3 if configured)
            processed_file, processed_filename = audio_processor.convert_uploaded_file_to_mp3(
                uploaded_file, original_filename
            )
            
            # Create audio file record with processed file
            audio_file = AudioFile.objects.create(
                owner=request.user,
                file=processed_file,
                original_filename=original_filename,  # Keep original filename for user reference
                file_size=processed_file.size,
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


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def update_speaker_names(request, audio_file_id):
    """Update speaker names in the transcription."""
    audio_file = get_object_or_404(AudioFile, id=audio_file_id, owner=request.user)

    try:
        transcription = audio_file.transcription
    except Transcription.DoesNotExist:
        return Response(
            {"error": "No transcription found for this file"},
            status=status.HTTP_404_NOT_FOUND,
        )

    speaker_names = request.data.get("speaker_names", {})
    update_all = request.data.get("update_all", True)

    if not speaker_names:
        return Response(
            {"error": "No speaker names provided"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        from .models import Speaker
        
        if update_all:
            # Update all speakers - speaker_names is a dict like {"speaker_1": "Paul", "speaker_2": "John"}
            for speaker_id, new_name in speaker_names.items():
                if new_name.strip():
                    # Update or create speaker record
                    speaker, created = Speaker.objects.get_or_create(
                        transcription=transcription,
                        speaker_id=speaker_id,
                        defaults={'speaker_name': new_name.strip()}
                    )
                    if not created:
                        speaker.speaker_name = new_name.strip()
                        speaker.save()
        else:
            # Update individual occurrences - speaker_names contains unique keys
            # This is a more complex case that would require storing position-specific speaker names
            # For now, we'll treat it the same as update_all but could be extended later
            for key, change_info in speaker_names.items():
                if isinstance(change_info, dict):
                    speaker_id = change_info.get('speakerId')
                    new_name = change_info.get('newName', '').strip()
                    if speaker_id and new_name:
                        speaker, created = Speaker.objects.get_or_create(
                            transcription=transcription,
                            speaker_id=speaker_id,
                            defaults={'speaker_name': new_name}
                        )
                        if not created:
                            speaker.speaker_name = new_name
                            speaker.save()

        # Regenerate speaker-separated text
        transcription.speaker_separated_text = transcription.generate_speaker_separated_text()
        transcription.save()

        return Response(
            {
                "message": "Speaker names updated successfully",
                "updated_speakers": len(speaker_names),
            }
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to update speaker names: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_speaker(request, audio_file_id):
    """Add a new speaker to the transcription at a specific position."""
    audio_file = get_object_or_404(AudioFile, id=audio_file_id, owner=request.user)

    try:
        transcription = audio_file.transcription
    except Transcription.DoesNotExist:
        return Response(
            {"error": "No transcription found for this file"},
            status=status.HTTP_404_NOT_FOUND,
        )

    speaker_id = request.data.get("speaker_id", "").strip()
    speaker_name = request.data.get("speaker_name", "").strip()
    word_timestamps = request.data.get("word_timestamps", [])
    split_position = request.data.get("split_position", 0)

    if not speaker_id or not speaker_name:
        return Response(
            {"error": "Speaker ID and name are required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        from .models import Speaker, TranscriptionWord
        
        # Create the new speaker
        speaker, created = Speaker.objects.get_or_create(
            transcription=transcription,
            speaker_id=speaker_id,
            defaults={'speaker_name': speaker_name, 'speaker_label': speaker_name}
        )
        
        if not created:
            speaker.speaker_name = speaker_name
            speaker.save()

        # Update word timestamps with new speaker assignments
        if word_timestamps:
            # Delete existing word timestamps
            TranscriptionWord.objects.filter(transcription=transcription).delete()

            # Create new word timestamps with updated speaker IDs
            for word_data in word_timestamps:
                TranscriptionWord.objects.create(
                    transcription=transcription,
                    word=word_data.get("word", ""),
                    start_time=word_data.get("start", 0.0),
                    end_time=word_data.get("end", 0.0),
                    confidence_score=0.95,
                    word_index=word_data.get("index", 0),
                    speaker_id=word_data.get("speaker_id"),
                )

        # Regenerate speaker-separated text
        transcription.speaker_separated_text = transcription.generate_speaker_separated_text()
        transcription.save()

        return Response(
            {
                "message": "Speaker added successfully",
                "speaker_id": speaker_id,
                "speaker_name": speaker_name,
                "split_position": split_position,
            }
        )

    except Exception as e:
        return Response(
            {"error": f"Failed to add speaker: {str(e)}"},
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


@api_view(["GET"])
def supported_formats(request):
    """Get supported audio formats and file size limit."""
    return Response({
        "formats": settings.SUPPORTED_AUDIO_FORMATS,
        "max_file_size": settings.MAX_AUDIO_FILE_SIZE,
        "max_file_size_mb": settings.MAX_AUDIO_FILE_SIZE // (1024 * 1024),
    })
