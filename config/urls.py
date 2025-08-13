"""
URL configuration for ai-scriber project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Web interface (homepage)
    path('', include('apps.accounts.web_urls')),
    
    # Admin
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/transcription/', include('apps.transcription.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)