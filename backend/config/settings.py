import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-secret-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "routing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# The built React app (frontend/dist) is copied here so one service can serve everything.
FRONTEND_DIR = BASE_DIR / "frontend_build"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [FRONTEND_DIR],
        "APP_DIRS": False,
        "OPTIONS": {},
    }
]

DATABASES = {}

# File cache so forecasts survive server restarts and are shared by all workers.
# This keeps us well inside the free Open-Meteo limits.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.environ.get("CACHE_DIR", BASE_DIR / ".cache"),
        "TIMEOUT": 60 * 60,
        "OPTIONS": {"MAX_ENTRIES": 20000},
    }
}

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
WHITENOISE_ROOT = FRONTEND_DIR

CORS_ALLOWED_ORIGINS = [
    o for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o
]

USE_TZ = True
TIME_ZONE = "UTC"

# Used in the User-Agent for the free OSM-based services (they ask for a contact).
APP_CONTACT = os.environ.get("APP_CONTACT", "truck-weather-routing demo")

OSRM_URL = os.environ.get("OSRM_URL", "https://router.project-osrm.org")
