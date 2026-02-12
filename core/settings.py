from pathlib import Path
from decouple import config
from datetime import timedelta
from celery.schedules import crontab
import os

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
    'rest_framework_simplejwt.token_blacklist',

    # Local apps
    'account',
    'content',
    'quizzes',
    'assignments',
    'groups',
    'progress',
    'graduates',
    'notifications',
    'backoffice',
    'dossier',
    'payments',
    'exports',
    'certificates',

]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),

    'REFRESH_TOKEN_LIFETIME': timedelta(days=90),

    'ROTATE_REFRESH_TOKENS': True,

    'BLACKLIST_AFTER_ROTATION': True,

    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# Kaspi настройки (заглушка)
KASPI_MODE = 'stub'  # 'stub' для разработки, 'production' для боевого
# KASPI_API_URL = ''
# KASPI_MERCHANT_ID = ''
# KASPI_API_KEY = ''

# DRF Spectacular Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'LMS API',
    'DESCRIPTION': 'API для системы обучения пилотов дронов',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,

    'COMPONENT_SPLIT_REQUEST': True,
        'SECURITY': [
            {
                'bearerAuth': []
            }
        ],
}

ROOT_URLCONF = 'core.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT'),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Asia/Almaty'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'account.User'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = True

# CSRF Settings
CSRF_TRUSTED_ORIGINS = [
    'https://dpa.aerialsolutions.kz',
    'http://localhost:3000',
    'http://localhost:8007',
]

# Frontend URL
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:3000')

# Sigex eGov Authentication
SIGEX_API_URL = 'https://sigex.kz'
# Для аутентификации данные для подписания (простая строка)
SIGEX_AUTH_DATA = 'LMS Authentication Request'

# =============================================================================
# PASSWORD HASHING
# =============================================================================
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# SendPulse Configuration
SENDPULSE_API_ID = config('SENDPULSE_API_ID', default='')
SENDPULSE_API_SECRET = config('SENDPULSE_API_SECRET', default='')
SENDPULSE_FROM_EMAIL = config('SENDPULSE_FROM_EMAIL', default='')
SENDPULSE_FROM_NAME = config('SENDPULSE_FROM_NAME', default='')
SENDPULSE_API_URL = 'https://api.sendpulse.com'

# CELERY
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://redis:6379/0')

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# Опции для надёжности
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

CELERY_BEAT_SCHEDULE = {
    # Создание досье инструкторов — каждый день в 3:00
    'create-instructor-dossiers': {
        'task': 'dossier.tasks.create_instructor_dossiers_task',
        'schedule': crontab(hour=3, minute=0),
    },

    # Очистка истекших JWT токенов — каждый день в 4:00
    'flush-expired-tokens': {
        'task': 'account.tasks.flush_expired_tokens_task',
        'schedule': crontab(hour=4, minute=0),
    },

    # Деактивация членств с истекшим дедлайном — каждый час
    'deactivate-expired-memberships': {
        'task': 'groups.tasks.deactivate_expired_memberships_task',
        'schedule': crontab(minute=0),
    },
}

# Django Silk - профилирование запросов
SILK_ENABLED = config('SILK_ENABLED', default=False, cast=bool)

if SILK_ENABLED:
    INSTALLED_APPS += ['silk']
    MIDDLEWARE.insert(0, 'silk.middleware.SilkyMiddleware')

    SILKY_PYTHON_PROFILER = True
    SILKY_META = True
    SILKY_MAX_RECORDED_REQUESTS = 500
    SILKY_MAX_RECORDED_REQUESTS_CHECK_PERCENT = 10
    # Аутентификация для доступа к Silk
    SILKY_AUTHENTICATION = True
    SILKY_AUTHORISATION = True  # Только superuser

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'notifications': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}