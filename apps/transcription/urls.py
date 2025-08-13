from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_audio, name='upload_audio'),
    path('files/', views.AudioFileListView.as_view(), name='audio_file_list'),
    path('files/<int:pk>/', views.AudioFileDetailView.as_view(), name='audio_file_detail'),
    path('files/<int:audio_file_id>/retranscribe/', views.retranscribe, name='retranscribe'),
    path('files/<int:audio_file_id>/transcription/', views.transcription_by_audio_file, name='transcription_by_audio_file'),
    path('transcriptions/<int:pk>/', views.TranscriptionDetailView.as_view(), name='transcription_detail'),
]