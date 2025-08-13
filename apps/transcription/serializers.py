from rest_framework import serializers
from .models import AudioFile, Transcription, TranscriptionSegment
from apps.core.utils import validate_audio_file


class TranscriptionSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TranscriptionSegment
        fields = ("id", "start_time", "end_time", "text", "confidence_score")


class TranscriptionSerializer(serializers.ModelSerializer):
    segments = TranscriptionSegmentSerializer(many=True, read_only=True)

    class Meta:
        model = Transcription
        fields = (
            "id",
            "text",
            "language",
            "confidence_score",
            "processing_time",
            "created_at",
            "updated_at",
            "segments",
        )


class AudioFileSerializer(serializers.ModelSerializer):
    transcription = TranscriptionSerializer(read_only=True)

    class Meta:
        model = AudioFile
        fields = (
            "id",
            "file",
            "original_filename",
            "file_size",
            "duration",
            "status",
            "created_at",
            "updated_at",
            "transcription",
        )
        read_only_fields = (
            "id",
            "file_size",
            "duration",
            "status",
            "created_at",
            "updated_at",
        )

    def validate_file(self, value):
        validate_audio_file(value)
        return value

    def create(self, validated_data):
        validated_data["owner"] = self.context["request"].user
        validated_data["original_filename"] = validated_data["file"].name
        validated_data["file_size"] = validated_data["file"].size
        return super().create(validated_data)


class AudioFileUploadSerializer(serializers.ModelSerializer):
    language = serializers.ChoiceField(
        choices=Transcription.LANGUAGE_CHOICES, default="auto", required=False
    )

    class Meta:
        model = AudioFile
        fields = ("file", "language")

    def validate_file(self, value):
        validate_audio_file(value)
        return value
