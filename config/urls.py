"""
URL configuration for ai-scriber project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import health_check
from django.http import JsonResponse

def test_view(request):
    return JsonResponse({"status": "test_view_works", "path": request.path})

def static_admin(request):
    from django.http import HttpResponse
    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Static Admin Test</title></head>
    <body>
        <h1>Static Admin Test</h1>
        <p>Path: {}</p>
        <p>Method: {}</p>
        <p>Headers: {}</p>
        <p>This should work without any redirects.</p>
    </body>
    </html>
    """.format(request.path, request.method, dict(request.headers))
    return HttpResponse(html)

urlpatterns = [
    # Health check endpoints
    path('healthcheck/', health_check, name='healthcheck'),
    path('api/health/', health_check, name='api_health'),
    path('test/', test_view, name='test'),
    path('static-admin/', static_admin, name='static_admin'),
    
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