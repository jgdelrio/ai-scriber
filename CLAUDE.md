# AI Scriber - Claude Development Notes

## Project Overview
Django-based service for transcribing audio files to text using REST API.

## Package Management
This project uses **uv** as the package manager instead of pip.

### Installation Commands
```bash
# Install dependencies
uv sync

# Install with development dependencies
uv sync --extra dev

# Install with production dependencies
uv sync --extra prod

# Add new dependency
uv add package-name

# Add development dependency
uv add --dev package-name
```

### Development Setup
```bash
# Create virtual environment and install dependencies
uv sync --extra dev

# Run migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Create superuser
uv run python manage.py createsuperuser

# Start development server
uv run python manage.py runserver
```

### Testing
```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=apps
```

### Code Quality
```bash
# Format code
uv run black .

# Sort imports
uv run isort .

# Lint code
uv run flake8
```

## Project Structure
- `config/` - Django project configuration and settings
- `apps/` - Django applications (core, accounts, transcription)
- `requirements/` - Legacy requirements files (use pyproject.toml instead)
- `media/audio/` - Uploaded audio files storage
- `static/` - Static files
- `templates/` - HTML templates

## Environment Variables
Copy `.env.example` to `.env` and configure:
- `SECRET_KEY` - Django secret key
- `DEBUG` - Debug mode (True/False)
- `DB_*` - Database connection settings
- `MAX_AUDIO_FILE_SIZE` - Maximum file size for uploads

## API Endpoints
- `POST /api/v1/auth/register/` - User registration
- `POST /api/v1/auth/login/` - User login
- `POST /api/v1/transcription/upload/` - Upload audio file
- `GET /api/v1/transcription/files/` - List user's audio files
- `GET /api/v1/transcription/files/{id}/transcription/` - Get transcription

## Docker Support
```bash
# Development with Docker
docker-compose up

# Production build
docker build -t ai-scriber .
```

## Notes
- The transcription service currently uses mock data
- Requires integration with actual transcription API (OpenAI Whisper, Google Speech-to-Text, etc.)
- Uses PostgreSQL for production, SQLite for development
- Token-based authentication implemented