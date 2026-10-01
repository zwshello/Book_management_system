"""User service settings. Secrets are loaded from the local environment."""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SERVICE_NAME = "user-service"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY.startswith("CHANGE_ME"):
    raise ImproperlyConfigured(
        "Set a unique DJANGO_SECRET_KEY in this service's .env"
    )

DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() in {"1", "true", "yes"}
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(
        ","
    )
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "accounts",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "accounts.middleware.RequestIdMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = []
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "user_db"),
        "USER": os.getenv("MYSQL_USER", ""),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", ""),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
        "TEST": {"NAME": os.getenv("MYSQL_TEST_DATABASE", "user_db_test")},
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated"
    ],
    "EXCEPTION_HANDLER": "accounts.errors.exception_handler",
}

AUTH_USER_MODEL = "accounts.User"
BOOK_SERVICE_TOKEN = os.getenv("BOOK_SERVICE_TOKEN", "")
BORROW_SERVICE_TOKEN = os.getenv("BORROW_SERVICE_TOKEN", "")
STATISTICS_SERVICE_TOKEN = os.getenv("STATISTICS_SERVICE_TOKEN", "")
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"
    },
]

JWT_PRIVATE_KEY = os.getenv("JWT_PRIVATE_KEY", "").replace("\\n", "\n")
JWT_PUBLIC_KEY = os.getenv("JWT_PUBLIC_KEY", "").replace("\\n", "\n")
if not JWT_PRIVATE_KEY.startswith("-----BEGIN PRIVATE KEY-----"):
    raise ImproperlyConfigured(
        "Set JWT_PRIVATE_KEY in user-service environment"
    )
if not JWT_PUBLIC_KEY.startswith("-----BEGIN PUBLIC KEY-----"):
    raise ImproperlyConfigured(
        "Set JWT_PUBLIC_KEY in user-service environment"
    )
SIMPLE_JWT = {
    "ALGORITHM": "RS256",
    "SIGNING_KEY": JWT_PRIVATE_KEY,
    "VERIFYING_KEY": JWT_PUBLIC_KEY,
    "ISSUER": os.getenv("JWT_ISSUER", "library-user-service"),
    "AUDIENCE": os.getenv("JWT_AUDIENCE", "library-services"),
    "USER_ID_CLAIM": "sub",
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "CHECK_REVOKE_TOKEN": True,
}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
