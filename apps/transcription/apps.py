from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class TranscriptionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.transcription"
    
    def ready(self):
        """Called when the app is ready. Check speaker detection service health."""
        # Only run health check in production/development, not during migrations
        import sys
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            self.check_speaker_detection_service()
    
    def check_speaker_detection_service(self):
        """Check if speaker detection service is available on startup."""
        try:
            from .speaker_detection import speaker_detection_service
            
            if speaker_detection_service.is_enabled():
                is_healthy = speaker_detection_service.check_health()
                if not is_healthy:
                    logger.warning(
                        "⚠️  Speaker detection service is configured but not responding. "
                        "Transcriptions will proceed without speaker separation."
                    )
            else:
                logger.debug("Speaker detection service not configured")
                
        except Exception as e:
            logger.error(f"Error checking speaker detection service: {str(e)}")
            # Don't fail startup if speaker detection check fails
