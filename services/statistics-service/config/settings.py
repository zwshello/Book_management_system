"""Statistics service aggregates protected APIs and owns no business DB."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SERVICE_NAME = "statistics-service"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY.startswith("CHANGE_ME"):
    raise ImproperlyConfigured("Set a unique DJANGO_SECRET_KEY in this service's .env")

DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes"}
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "analytics",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "analytics.middleware.RequestIdMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.dummy"}}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["analytics.authentication.UserJWTAuthentication"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "analytics.errors.exception_handler",
}

JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n")
if not JWT_PUBLIC_KEY.startswith("-----BEGIN PUBLIC KEY-----"):
    raise ImproperlyConfigured("Configure user-service JWT_PUBLIC_KEY")
SIMPLE_JWT = {
    "ALGORITHM": "RS256", "SIGNING_KEY": "", "VERIFYING_KEY": JWT_PUBLIC_KEY,
    "ISSUER": os.getenv("JWT_ISSUER", "library-user-service"),
    "AUDIENCE": os.getenv("JWT_AUDIENCE", "library-services"),
    "USER_ID_CLAIM": "sub",
}
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "")
BOOK_SERVICE_URL = os.getenv("BOOK_SERVICE_URL", "")
BORROW_SERVICE_URL = os.getenv("BORROW_SERVICE_URL", "")
for name, url in (("USER_SERVICE_URL", USER_SERVICE_URL), ("BOOK_SERVICE_URL", BOOK_SERVICE_URL), ("BORROW_SERVICE_URL", BORROW_SERVICE_URL)):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ImproperlyConfigured(f"Configure a valid {name}")
STATISTICS_SERVICE_TOKEN = os.getenv("STATISTICS_SERVICE_TOKEN", "")
SERVICE_TIMEOUT = float(os.getenv("SERVICE_TIMEOUT", "3"))
if not 0 < SERVICE_TIMEOUT <= 30:
    raise ImproperlyConfigured("SERVICE_TIMEOUT must be >0 and <=30")

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
