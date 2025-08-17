"""
Background tasks for asynchronous processing.
Note: This uses threading for background processing. For production, consider Celery.
"""

import logging
import threading
from .models import Transcription

logger = logging.getLogger(__name__)


def process_transcription(audio_file_id, language="auto"):
    """
    Process transcription asynchronously.
    This would be a Celery task in a production environment.
    """
    try:
        from .services import TranscriptionService
        service = TranscriptionService()
        transcription = service.transcribe_audio(audio_file_id, language)
        logger.info(f"Transcription completed for audio file {audio_file_id}")
        return transcription.id
    except Exception as err:
        logger.error(
            f"Transcription task failed for audio file {audio_file_id}: {str(err)}"
        )
        raise


def process_speaker_detection_async(transcription_id):
    """
    Process speaker detection asynchronously in background thread.
    
    Args:
        transcription_id: ID of the transcription to process
    """
    def background_task():
        try:
            from .speaker_detection import speaker_detection_service
            
            # Get transcription object
            transcription = Transcription.objects.get(id=transcription_id)
            
            # Update status to processing
            transcription.speaker_detection_status = "processing"
            transcription.save()
            
            if not speaker_detection_service.is_enabled():
                logger.debug("Speaker detection service not enabled")
                transcription.speaker_detection_status = "unavailable"
                transcription.save()
                return
            
            logger.info(f"Starting background speaker detection for transcription {transcription_id}")
            
            # Prepare transcription data for speaker detection
            words_data = []
            for word in transcription.words.all():
                words_data.append({
                    'word': word.word,
                    'start': word.start_time,
                    'end': word.end_time,
                    'confidence': word.confidence_score or 1.0,
                    'word_index': word.word_index
                })
            
            segments_data = []
            for segment in transcription.segments.all():
                segments_data.append({
                    'start_time': segment.start_time,
                    'end_time': segment.end_time,
                    'text': segment.text,
                    'confidence': segment.confidence_score or 0.95
                })
            
            transcription_data = {
                'text': transcription.text,
                'language': transcription.language,
                'confidence_score': transcription.confidence_score or 0.95,
                'processing_time': transcription.processing_time or 0.0,
                'words': words_data,
                'segments': segments_data
            }
            
            # Send to speaker detection service
            speaker_result = speaker_detection_service.detect_speakers(
                transcription.audio_file, 
                transcription_data
            )
            
            if speaker_result:
                # Update transcription with speaker information
                success = speaker_detection_service.update_transcription_with_speakers(
                    transcription, speaker_result
                )
                
                if success:
                    transcription.speaker_detection_status = "completed"
                    transcription.save()
                    logger.info(f"✅ Successfully completed background speaker detection for transcription {transcription_id}")
                else:
                    transcription.speaker_detection_status = "failed"
                    transcription.save()
                    logger.warning(f"Failed to update transcription {transcription_id} with speaker data")
            else:
                transcription.speaker_detection_status = "failed"
                transcription.save()
                logger.warning(f"Speaker detection failed for transcription {transcription_id}")
                
        except Transcription.DoesNotExist:
            logger.error(f"Transcription {transcription_id} not found for speaker detection")
        except Exception as e:
            logger.error(f"Error in background speaker detection for transcription {transcription_id}: {str(e)}")
            try:
                transcription = Transcription.objects.get(id=transcription_id)
                transcription.speaker_detection_status = "failed"
                transcription.save()
            except:
                pass  # Don't fail if we can't update status
    
    # Start background thread
    thread = threading.Thread(target=background_task, daemon=True)
    thread.start()
    logger.info(f"Started background speaker detection thread for transcription {transcription_id}")


# If you want to use Celery, uncomment and configure:
# from celery import shared_task
#
# @shared_task
# def process_transcription_async(audio_file_id, language='auto'):
#     return process_transcription(audio_file_id, language)
#
# @shared_task
# def process_speaker_detection_celery(transcription_id):
#     return process_speaker_detection_async(transcription_id)
