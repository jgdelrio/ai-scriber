from django.urls import path
from . import views

# Web interface URLs
urlpatterns = [
    path("", views.web_login, name="web_login"),
    path("register/", views.web_register, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("audio-player/<int:file_id>/", views.audio_player, name="audio_player"),
    path("logout/", views.web_logout, name="web_logout"),
]
