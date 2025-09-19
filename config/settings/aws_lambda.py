"""
Django settings for Lambda deployment.
"""
import os
import boto3
from botocore.credentials import InstanceMetadataProvider, InstanceMetadataFetcher

from .base import *


# Lambda-specific settings
DEBUG = True  # Enable temporarily for debugging
ALLOWED_HOSTS = ['*']

# Essential middleware for Lambda
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.core.middleware.DebugRedirectMiddleware',  # Keep debug middleware
]

# Database - RDS Configuration for Lambda
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get("DB_NAME", "djangomain"),
        'USER': os.environ.get("DB_USER", "postgres"),
        'PASSWORD': os.environ.get("DB_PASSWORD", ""),
        'HOST': os.environ.get("DB_HOST", "localhost"),
        'PORT': os.environ.get("DB_PORT", "5432"),
        'OPTIONS': {
            # Lambda-optimized connection settings
            'connect_timeout': 10,
            'application_name': 'ai-scriber-lambda',
        },
        # Lambda-specific timeouts
        'CONN_MAX_AGE': 0,  # Don't reuse connections across invocations
        'CONN_HEALTH_CHECKS': True,
        'ATOMIC_REQUESTS': True,  # Wrap each request in a transaction
    }
}


def get_rds_auth_token():
    """Generate RDS IAM auth token"""
    try:
        # Get AWS credentials from Lambda environment
        session = boto3.Session()
        credentials = session.get_credentials()

        # Generate RDS auth token
        client = boto3.client('rds', region_name=os.environ.get('AWS_REGION', 'eu-west-1'))
        token = client.generate_db_auth_token(
            DBHostname=os.environ.get('DB_HOST'),
            Port=int(os.environ.get('DB_PORT', '5432')),
            DBUsername=os.environ.get('DB_USER'),
            Region=os.environ.get('AWS_REGION', 'eu-west-1')
        )
        return token
    except Exception as e:
        print(f"Error generating RDS auth token: {e}")
        return os.environ.get('DB_PASSWORD', '')

# RDS IAM Authentication (optional but recommended)
if os.environ.get('USE_RDS_IAM_AUTH', 'false').lower() == 'true':
    # Use IAM authentication if enabled
    DATABASES['default']['PASSWORD'] = get_rds_auth_token()
    DATABASES['default']['OPTIONS']['sslmode'] = 'require'

# Static files - Use S3 for static files in Lambda
if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    # Use S3 for user data storage
    AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_S3_SCRIBER_BUCKET', 'ai-scriber')
    AWS_S3_REGION_NAME = os.environ.get('AWS_REGION', 'eu-west-1')
    AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'
    
    # Static files (keep separate from user data)
    STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
    STATICFILES_STORAGE = 'storages.backends.s3boto3.StaticS3Boto3Storage'
    
    # Media files (user data with date partitioning)
    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/user-data/'
    DEFAULT_FILE_STORAGE = 'apps.core.storage.DatePartitionedS3Storage'
else:
    # Local storage for testing
    STATIC_URL = '/static/'
    STATIC_ROOT = '/tmp/static/'
    MEDIA_URL = '/media/'
    MEDIA_ROOT = '/tmp/media/'

# File upload settings for Lambda
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB

# Cache - Use ElastiCache or DynamoDB for Lambda
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Logging for Lambda
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Security settings for Lambda URL
SECURE_SSL_REDIRECT = False  # Lambda URL handles SSL
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_TLS = False  # Disable to prevent HTTPS enforcement issues
SECURE_BROWSER_XSS_FILTER = False
SECURE_CONTENT_TYPE_NOSNIFF = False
SECURE_HSTS_SECONDS = 0  # Disable HSTS

# Fix redirect loops in Lambda environment
FORCE_SCRIPT_NAME = None
APPEND_SLASH = True  # Re-enable to handle URLs without trailing slash

# Session and CSRF settings for Lambda
SESSION_COOKIE_SECURE = False  # Lambda URL uses HTTPS but cookies need to be accessible
CSRF_COOKIE_SECURE = False     # Same for CSRF cookies
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'  # Allow cross-site requests
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_SAVE_EVERY_REQUEST = True

# Trust Lambda URL proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
ALLOWED_HOSTS = ['*']  # Lambda URL is dynamic

# Login/Logout URLs for admin
LOGIN_URL = '/admin/login/'
LOGOUT_URL = '/admin/logout/'
LOGIN_REDIRECT_URL = '/admin/'
LOGOUT_REDIRECT_URL = '/admin/'

# Lambda-specific optimizations
CONN_MAX_AGE = 0  # Don't keep database connections open
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
