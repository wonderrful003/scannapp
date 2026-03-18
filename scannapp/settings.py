"""
ScannApp Django Settings
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'change-this-in-production-use-env-file')

DEBUG = os.getenv('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.staticfiles',
    'corsheaders',
    'scanner',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # add this line
]

ROOT_URLCONF = 'scannapp.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
    ]},
}]

WSGI_APPLICATION = 'scannapp.wsgi.application'

# No database needed — Google Sheets is our storage
DATABASES = {}

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ── CORS — allow your GitHub Pages frontend ──────────────────────────────────
# Add your GitHub Pages URL here, e.g. https://yourname.github.io
CORS_ALLOWED_ORIGINS = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:8000,http://127.0.0.1:8000'
).split(',')

# During development allow all origins (set to False in production)
CORS_ALLOW_ALL_ORIGINS = os.getenv('CORS_ALLOW_ALL', 'True') == 'True'

# ── Google Sheets config ──────────────────────────────────────────────────────
GOOGLE_SHEET_ID           = os.getenv('GOOGLE_SHEET_ID', '')
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv(
    'GOOGLE_SERVICE_ACCOUNT_FILE',
    str(BASE_DIR / 'service_account.json')
)

# ── OCR config ────────────────────────────────────────────────────────────────
# On Linux/Ubuntu: sudo apt install tesseract-ocr
# On Windows: set this to your tesseract.exe path
import shutil
TESSERACT_CMD = os.getenv('TESSERACT_CMD') or shutil.which('tesseract') or '/usr/bin/tesseract'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
