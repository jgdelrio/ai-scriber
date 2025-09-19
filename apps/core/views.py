from django.http import JsonResponse
from django.conf import settings
from django.db import connection
from django.utils import timezone
import os


def health_check(request):
    """
    Health check endpoint for the service.
    Returns service status, version, and database connectivity.
    """
    try:
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    # Check if running in Lambda
    is_lambda = os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None
    
    health_data = {
        "status": "healthy" if db_status == "healthy" else "unhealthy",
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "timestamp": timezone.now().isoformat(),
        "database": db_status,
        "environment": "lambda" if is_lambda else "local",
    }
    
    # Return 200 if healthy, 503 if unhealthy
    status_code = 200 if db_status == "healthy" else 503
    
    response = JsonResponse(health_data, status=status_code)
    
    # Add CORS headers
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    
    return response