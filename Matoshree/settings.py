"""
Django settings for Matoshree project.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

# =============================================================================
# Base Directory & Environment
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

# =============================================================================
# Security & Core Settings
# =============================================================================

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is required.")

# DEBUG – set to False in production via environment variable
DEBUG = os.getenv("DEBUG", "True").lower() == "true"

ALLOWED_HOSTS = [
    host.strip() for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()
]

BASE_URL = os.getenv("BASE_URL", "")

CSRF_TRUSTED_ORIGINS = os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in CSRF_TRUSTED_ORIGINS if origin.strip()]

# =============================================================================
# Installed Apps
# =============================================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "cloudinary",
    "cloudinary_storage",

    # Local
    "corematoshree",
    
    # SSL Server
    # "sslserver",
]

# =============================================================================
# Middleware
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# =============================================================================
# Debug Toolbar (ONLY in development)
# =============================================================================

if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1']   # adjust for your environment

# =============================================================================
# URL & WSGI
# =============================================================================

ROOT_URLCONF = "Matoshree.urls"
WSGI_APPLICATION = "Matoshree.wsgi.application"

# =============================================================================
# Templates
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "corematoshree.context_processors.business_info",
                "corematoshree.context_processors.payment_settings",
            ],
        },
    },
]

# =============================================================================
# Database
# =============================================================================

DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=600,
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = 0

# =============================================================================
# Cloudinary / Media Storage
# =============================================================================

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME", "dqsl67215"),
    "API_KEY": os.getenv("CLOUDINARY_API_KEY", "438720846710921"),
    "API_SECRET": os.getenv("CLOUDINARY_API_SECRET", ""),
}

# Force Cloudinary storage regardless of environment variables
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

# MEDIA_URL = '/media/'
# MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Optional: also set the URL if you need to reference it directly
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "")

# =============================================================================
# Static Files
# =============================================================================

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# =============================================================================
# Password Validation
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =============================================================================
# Internationalization & Localization
# =============================================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("en", "English"),
    ("mr", "Marathi"),
    ("hi", "Hindi"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

# =============================================================================
# Email Configuration
# =============================================================================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "default@example.com")

# =============================================================================
# Authentication
# =============================================================================

AUTH_USER_MODEL = "corematoshree.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# =============================================================================
# Security (Production)
# =============================================================================

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True

# =============================================================================
# Default Auto Field
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================================================================
# Logging
# =============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING" if not DEBUG else "DEBUG",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO" if not DEBUG else "DEBUG",
            "propagate": False,
        },
    },
}

if DEBUG:
    LOGGING["loggers"]["django.db.backends"] = {
        "level": "DEBUG",
        "handlers": ["console"],
        "propagate": False,
    }

# =============================================================================
# CACHES – Performance Optimisation
# =============================================================================

REDIS_URL = os.getenv("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "PARSER_CLASS": "redis.connection.HiredisParser",
                "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
                "CONNECTION_POOL_CLASS_KWARGS": {
                    "max_connections": 50,
                    "timeout": 20,
                },
                "MAX_CONNECTIONS": 1000,
                "PICKLE_VERSION": -1,
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
            "TIMEOUT": 60 * 5,
            "OPTIONS": {
                "MAX_ENTRIES": 2000,
            }
        }
    }

# =============================================================================
# PAYMENT - RAZORPAY
# =============================================================================

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")