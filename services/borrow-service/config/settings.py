"""Independent borrow database; cross-service communication uses REST only."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SERVICE_NAME = "borrow-service"
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
    "borrowing",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "borrowing.middleware.RequestIdMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "borrow_db"),
        "USER": os.getenv("MYSQL_USER", ""),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
        "TEST": {"NAME": os.getenv("MYSQL_TEST_DATABASE", "borrow_db_test")},
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "borrowing.authentication.UserJWTAuthentication"
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "EXCEPTION_HANDLER": "borrowing.errors.exception_handler",
}

JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n")
if not JWT_PUBLIC_KEY.startswith("-----BEGIN PUBLIC KEY-----"):
    raise ImproperlyConfigured("Configure user-service JWT_PUBLIC_KEY")
SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "SIGNING_KEY": "",
    "VERIFYING_KEY": JWT_PUBLIC_KEY,
    "ISSUER": os.getenv("JWT_ISSUER", "library-user-service"),
    "AUDIENCE": os.getenv("JWT_AUDIENCE", "library-services"),
    "USER_ID_CLAIM": "sub",
}
# No hard-coded service addresses: deployment supplies local or service DNS URLs.
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "")
BOOK_SERVICE_URL = os.getenv("BOOK_SERVICE_URL", "")
for variable, service_url in (
    ("USER_SERVICE_URL", USER_SERVICE_URL),
    ("BOOK_SERVICE_URL", BOOK_SERVICE_URL),
):
    value = urlsplit(service_url)
    if (
        value.scheme not in {"http", "https"}
        or not value.hostname
        or value.username
        or value.password
        or value.query
        or value.fragment
    ):
        raise ImproperlyConfigured(f"Configure a valid {variable}")
BORROW_SERVICE_TOKEN = os.getenv("BORROW_SERVICE_TOKEN", "")
STATISTICS_SERVICE_TOKEN = os.getenv("STATISTICS_SERVICE_TOKEN", "")
SERVICE_TIMEOUT = float(os.getenv("SERVICE_TIMEOUT", "3"))
BORROW_DAYS = int(os.getenv("BORROW_DAYS", "30"))
MAX_ACTIVE_BORROWS = int(os.getenv("MAX_ACTIVE_BORROWS", "5"))
if (
    not 0 < SERVICE_TIMEOUT <= 30
    or not 1 <= BORROW_DAYS <= 365
    or not 1 <= MAX_ACTIVE_BORROWS <= 100
):
    raise ImproperlyConfigured("Invalid timeout/borrow policy configuration")

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
