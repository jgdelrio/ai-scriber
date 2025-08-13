from django.contrib import admin
from .models import AudioFile, Transcription, TranscriptionSegment


@admin.register(AudioFile)
class AudioFileAdmin(admin.ModelAdmin):
    list_display = (
        "original_filename",
        "owner",
        "status",
        "file_size",
        "duration",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("original_filename", "owner__email")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


class TranscriptionSegmentInline(admin.TabularInline):
    model = TranscriptionSegment
    extra = 0
    readonly_fields = ("start_time", "end_time", "text", "confidence_score")


@admin.register(Transcription)
class TranscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "audio_file",
        "language",
        "confidence_score",
        "processing_time",
        "created_at",
    )
    list_filter = ("language", "created_at")
    search_fields = ("audio_file__original_filename", "text")
    readonly_fields = ("created_at", "updated_at")
    inlines = [TranscriptionSegmentInline]
    ordering = ("-created_at",)


@admin.register(TranscriptionSegment)
class TranscriptionSegmentAdmin(admin.ModelAdmin):
    list_display = ("transcription", "start_time", "end_time", "confidence_score")
    list_filter = ("transcription__language",)
    search_fields = ("text",)
    ordering = ("transcription", "start_time")
