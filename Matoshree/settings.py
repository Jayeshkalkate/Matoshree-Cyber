import os
from pathlib import Path
from decouple import config
import dj_database_url
import cloudinary
from cloudinary import config as cloudinary_config

BASE_DIR = Path(__file__).resolve().parent.parent

# Logs
LOG_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# ------------------------------------------------------------------
# SECURITY & DEBUG
# ------------------------------------------------------------------
SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='localhost,127.0.0.1',
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# ------------------------------------------------------------------
# DATABASE
# ------------------------------------------------------------------
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL', default='sqlite:///db.sqlite3'),
        conn_max_age=600,
        ssl_require=True
    )
}

# ------------------------------------------------------------------
# APPLICATION DEFINITION
# ------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corematoshree',
    'cloudinary',
    'cloudinary_storage',
    # 'django.contrib.sitemaps',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Note: csrf_exempt is a decorator, not middleware – removed.
]

ROOT_URLCONF = 'Matoshree.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'corematoshree.context_processors.business_info',
                'corematoshree.context_processors.payment_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'Matoshree.wsgi.application'

SESSION_ENGINE = 'django.contrib.sessions.backends.db'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'corematoshree.User'
LOGIN_REDIRECT_URL = '/'
LOGIN_URL = 'login'

# ---------- LANGUAGE & TIME (i18n disabled) ----------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = False          # Disable internationalization
USE_TZ = True

EXTERNAL_JOBS_RSS_URL = 'https://majhinaukri.in/feed/'

# ------------------------------------------------------------------
# STATIC & MEDIA
# ------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

STORAGES = {
    'default': {
        'BACKEND': 'cloudinary_storage.storage.MediaCloudinaryStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

GST_RATE = config('GST_RATE', default=0.18, cast=float)

# ------------------------------------------------------------------
# CLOUDINARY
# ------------------------------------------------------------------
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': config('CLOUDINARY_API_KEY'),
    'API_SECRET': config('CLOUDINARY_API_SECRET'),
}

cloudinary.config(
    cloud_name=config('CLOUDINARY_CLOUD_NAME'),
    api_key=config('CLOUDINARY_API_KEY'),
    api_secret=config('CLOUDINARY_API_SECRET'),
)

if DEBUG:
    print("✅ Cloudinary storage is ACTIVE with cloud_name:", config('CLOUDINARY_CLOUD_NAME'))

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ------------------------------------------------------------------
# EMAIL
# ------------------------------------------------------------------
EMAIL_BACKEND = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@example.com')
CONTACT_EMAIL = config('CONTACT_EMAIL', default=DEFAULT_FROM_EMAIL)

ADMINS = []
admin_list = config('ADMINS', default='')
if admin_list:
    for part in admin_list.split(','):
        part = part.strip()
        if part and '<' in part and '>' in part:
            name = part[:part.index('<')].strip()
            email = part[part.index('<')+1:part.index('>')].strip()
            ADMINS.append((name, email))

# ------------------------------------------------------------------
# SECURITY (production)
# ------------------------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    X_FRAME_OPTIONS = 'DENY'
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

_csrf_origins = config('CSRF_TRUSTED_ORIGINS', default='')
if _csrf_origins:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in _csrf_origins.split(',') if origin.strip()]
else:
    CSRF_TRUSTED_ORIGINS = []
if DEBUG:
    CSRF_TRUSTED_ORIGINS += ['http://localhost:8000', 'http://127.0.0.1:8000']

# ------------------------------------------------------------------
# LOGGING
# ------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'django.log'),
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'WARNING',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'payment_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'payments.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'corematoshree': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': True,
        },
        'corematoshree.payment': {
            'handlers': ['payment_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# ------------------------------------------------------------------
# PAYMENT – Razorpay (replaces old UPI/Cash flow)
# ------------------------------------------------------------------
RAZORPAY_KEY_ID = config('RAZORPAY_KEY_ID', default='')
RAZORPAY_KEY_SECRET = config('RAZORPAY_KEY_SECRET', default='')
RAZORPAY_WEBHOOK_SECRET = config('RAZORPAY_WEBHOOK_SECRET', default='')  # optional

PAYMENT_TIMEOUT_MINUTES = config('PAYMENT_TIMEOUT_MINUTES', default=15, cast=int)

RAZORPAY_FEE_PERCENT = config('RAZORPAY_FEE_PERCENT', default=2.0, cast=float)
RAZORPAY_FEE_FIXED = config('RAZORPAY_FEE_FIXED', default=0, cast=float)

# (Optional) legacy settings – kept for reference, not used in Razorpay flow
# PAYMENT_MAX_RETRY = config('PAYMENT_MAX_RETRY', default=3, cast=int)
# PAYMENT_AMOUNT_MIN = config('PAYMENT_AMOUNT_MIN', default=1, cast=int)
# PAYMENT_AMOUNT_MAX = config('PAYMENT_AMOUNT_MAX', default=100000, cast=int)
