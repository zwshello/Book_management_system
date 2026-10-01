"""Book service configuration; identity is verified without a user DB."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SERVICE_NAME = "book-service"
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
    "catalog",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "catalog.middleware.RequestIdMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "book_db"),
        "USER": os.getenv("MYSQL_USER", ""),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
        "TEST": {"NAME": os.getenv("MYSQL_TEST_DATABASE", "book_db_test")},
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["catalog.authentication.UserJWTAuthentication"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "catalog.errors.exception_handler",
}

JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n")
if not JWT_PUBLIC_KEY.startswith("-----BEGIN PUBLIC KEY-----"):
    raise ImproperlyConfigured("Configure user-service JWT_PUBLIC_KEY")
SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "SIGNING_KEY": "",  # This service cannot issue user tokens.
    "VERIFYING_KEY": JWT_PUBLIC_KEY,
    "ISSUER": os.getenv("JWT_ISSUER", "library-user-service"),
    "AUDIENCE": os.getenv("JWT_AUDIENCE", "library-services"),
    "USER_ID_CLAIM": "sub",
}
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "")
parsed_user_service_url = urlsplit(USER_SERVICE_URL)
if (
    parsed_user_service_url.scheme not in {"http", "https"}
    or not parsed_user_service_url.hostname
    or parsed_user_service_url.username
    or parsed_user_service_url.password
    or parsed_user_service_url.query
    or parsed_user_service_url.fragment
):
    raise ImproperlyConfigured("Configure a valid USER_SERVICE_URL")
BOOK_SERVICE_TOKEN = os.getenv("BOOK_SERVICE_TOKEN", "")
BORROW_SERVICE_TOKEN = os.getenv("BORROW_SERVICE_TOKEN", "")
STATISTICS_SERVICE_TOKEN = os.getenv("STATISTICS_SERVICE_TOKEN", "")
USER_SERVICE_TIMEOUT = float(os.getenv("USER_SERVICE_TIMEOUT", "3"))
if not 0 < USER_SERVICE_TIMEOUT <= 30:
    raise ImproperlyConfigured("USER_SERVICE_TIMEOUT must be >0 and <=30")

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
