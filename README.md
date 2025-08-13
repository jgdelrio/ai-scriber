# AI Scriber

A Django-based REST API service for transcribing audio files to text using OpenAI Whisper. 
This service provides secure user authentication, file upload capabilities, and advanced audio transcription functionality with support for multiple audio formats, intelligent file segmentation, and optional speaker detection.


## Features

- **User Authentication**: Token-based authentication with user registration and login  
- **Multi-Format Support**: MP3, MP4, MPEG, MPGA, M4A, WAV, WebM, OGG, Opus, AAC, FLAC  
- **OpenAI Whisper Integration**: Real-time transcription with word-level timestamps  
- **Intelligent File Processing**: Automatic segmentation for large files (`>20MB` or `>8min`)  
- **Smart Audio Conversion**: Automatic MP3 conversion for non-native formats using FFmpeg  
- **Speaker Detection**: Optional integration with external speaker separation service  
- **Dark Mode UI**: Modern web interface with responsive design  
- **Batch Operations**: Upload, transcribe, and manage multiple files  
- **Export Functionality**: Download transcriptions as text files  
- **Docker Support**: Containerized deployment ready  

---

## Tech Stack

- **Backend**: Django 4.2+ with Django REST Framework  
- **AI/ML**: OpenAI Whisper API for transcription  
- **Audio Processing**: pydub, librosa, FFmpeg for format conversion and segmentation  
- **Database**: PostgreSQL (production), SQLite (development)  
- **Package Manager**: uv (modern Python package manager)  
- **Authentication**: Token-based authentication  
- **File Storage**: Local file system with configurable upload paths  
- **Containerization**: Docker with docker-compose  
- **Frontend**: Responsive HTML/CSS/JavaScript with dark mode support  

---

## API Endpoints

### Authentication
- `POST /api/v1/auth/register/` - User registration  
- `POST /api/v1/auth/login/` - User login  
- `POST /api/v1/auth/logout/` - User logout  
- `GET /api/v1/auth/profile/` - Get user profile  

### Transcription
- `POST /api/v1/transcription/upload/` - Upload audio file for transcription  
- `GET /api/v1/transcription/files/` - List user's audio files  
- `GET /api/v1/transcription/files/{id}/` - Get specific audio file details  
- `DELETE /api/v1/transcription/files/{id}/` - Delete audio file  
- `GET /api/v1/transcription/files/{id}/transcription/` - Get transcription with timestamps  
- `POST /api/v1/transcription/files/{id}/retranscribe/` - Retry transcription  
- `GET /api/v1/transcription/supported-formats/` - Get supported audio formats and limits  

### Web Interface
- `/` - Dashboard for file upload and management  
- `/audio-player/{id}/` - Audio player with real-time word highlighting  

---

## Quick Start

### Prerequisites
- Python 3.12+  
- uv package manager  
- PostgreSQL (for production) or SQLite (for development)  
- FFmpeg (for audio format conversion)  
- OpenAI API key (for transcription)  

### Installation
1. **Clone the repository**  
   ```bash
   git clone <repository-url>
   cd ai-scriber
   ```

2. **Install dependencies with uv**
   ```bash
   # Install all dependencies including development tools
   uv sync --extra dev
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   # Required: Add your OpenAI API key
   # Optional: Configure speaker detection service
   ```

4. **Run database migrations**
   ```bash
   uv run python manage.py makemigrations
   uv run python manage.py migrate
   ```

5. **Create a superuser**
   ```bash
   uv run python manage.py createsuperuser
   ```

6. **Start the development server**
   ```bash
   uv run python manage.py runserver 8080
   ```

The API will be available at `http://localhost:8080/`

### Using Docker

1. **Start all services**
   ```bash
   docker-compose up -d
   ```

2. **Run migrations in the container**
   ```bash
   docker-compose exec web uv run python manage.py migrate
   ```

3. **Create superuser in the container**
   ```bash
   docker-compose exec web uv run python manage.py createsuperuser
   ```

## Testing

### Run Tests
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=apps

# Run specific test file
uv run pytest apps/transcription/tests/test_models.py

# Run tests with verbose output
uv run pytest -v
```

### Test Structure
- `apps/*/tests/` - Test files for each Django app
- `tests/` - Project-wide integration tests
- `pytest.ini` - Pytest configuration (if needed)


## Development

### Code Quality Tools
```bash
# Format code with Black
uv run black .

# Sort imports with isort
uv run isort .

# Lint code with flake8
uv run flake8
```

### Development Dependencies

The project includes several development tools:
- **django-debug-toolbar**: Debug information in browser
- **django-extensions**: Additional Django management commands
- **ipython**: Enhanced Python shell
- **pytest**: Testing framework
- **black**: Code formatter
- **isort**: Import sorter
- **flake8**: Code linter

---

## Configuration

### Environment Variables

Key environment variables (see `.env.example`):

**Required:**
- `SECRET_KEY`: Django secret key for security
- `OPENAI_API_KEY`: OpenAI API key for transcription service

**Database:**
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: Database configuration

**Audio Processing:**
- `MAX_AUDIO_FILE_SIZE`: Maximum file size for uploads (default: 20MB)
- `OPENAI_CALL_TIMEOUT`: Timeout for OpenAI API calls (default: 600s)

**Optional Speaker Detection:**
- `SPEAKER_DETECTION_HOST`: Host for speaker detection service
- `SPEAKER_DETECTION_PORT`: Port for speaker detection service

**General:**
- `DEBUG`: Enable/disable debug mode
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts

---

### Audio File Settings

- **Supported formats**: MP3, MP4, MPEG, MPGA, M4A, WAV, WebM, OGG, Opus, AAC, FLAC
- **Max file size**: 20MB (files larger than this are automatically segmented)
- **Max duration**: 8 minutes (longer files are automatically segmented)
- **Auto-conversion**: Non-native formats automatically converted to MP3
- **Storage**: Local filesystem under `media/audio/`
- **Intelligence**: Optimal split points detected using silence analysis

---

## Project Structure

```
ai-scriber/
├── config/ # Django project configuration
│ ├── settings/ # Environment-specific settings
│ ├── urls.py # Main URL configuration
│ ├── wsgi.py # WSGI configuration
│ └── asgi.py # ASGI configuration
├── apps/ # Django applications
│ ├── core/ # Shared utilities and base classes
│ ├── accounts/ # User authentication
│ └── transcription/ # Audio transcription functionality
├── media/ # User uploaded files
├── static/ # Static files (CSS, JS, images)
├── templates/ # HTML templates
├── requirements/ # Legacy requirements files
├── tests/ # Project-wide tests
├── docker-compose.yml # Docker services configuration
├── Dockerfile # Docker container definition
├── pyproject.toml # Project dependencies and metadata
└── manage.py # Django management script
```


---

## Advanced Features

### Speaker Detection Integration

AI Scriber supports optional integration with external speaker detection services:

1. **Configuration**: Set `SPEAKER_DETECTION_HOST` and `SPEAKER_DETECTION_PORT` environment variables
2. **Health Check**: Service availability is checked on startup
3. **Automatic Processing**: After transcription, audio and timestamps are sent for speaker separation
4. **Enhanced Output**: Transcriptions are updated with speaker labels and segments

**API Integration:**
- `GET /healthcheck` - Service health check
- `POST /speaker-detection` - Process audio file with timestamps

---

### Audio Processing Intelligence

- **Format Detection**: Automatically detects and converts non-native formats using FFmpeg
- **Smart Segmentation**: Files >20MB or >8min are intelligently split at optimal points
- **Silence Detection**: Uses librosa and pydub to find natural speech boundaries
- **Quality Optimization**: Converts to 16kHz mono MP3 for optimal OpenAI processing

---

## Deployment

### Production Deployment

1. Set environment variables for production
2. Use PostgreSQL database
3. Configure static file serving
4. Set up reverse proxy (nginx)
5. Use gunicorn as WSGI server

### Docker Production

```bash
# Build production image
docker build -t ai-scriber:latest .

# Run with production settings
docker run -p 8080:8080 --env-file .env ai-scriber:latest
```


## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `uv run pytest`
5. Format code: `uv run black . && uv run isort .`
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.
