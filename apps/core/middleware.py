import logging

logger = logging.getLogger(__name__)


class DebugRedirectMiddleware:
    """Debug middleware to log redirect issues in Lambda"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log request details
        logger.info(f"Request: {request.method} {request.get_full_path()}")
        logger.info(f"Headers: {dict(request.headers)}")
        logger.info(f"Is secure: {request.is_secure()}")
        logger.info(f"Host: {request.get_host()}")
        
        response = self.get_response(request)
        
        # Log response details if it's a redirect
        if 300 <= response.status_code < 400:
            logger.warning(f"Redirect {response.status_code}: {response.get('Location', 'No Location header')}")
            
        return response