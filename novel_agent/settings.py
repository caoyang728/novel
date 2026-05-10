import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-@k13^z+7z7z7z7z7z7z7z7z7z7z7z7z7z7z7z7z7z7'

DEBUG = True

ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'apps.core.apps.CoreConfig',
    'apps.ai.apps.AiConfig',
    'apps.project.apps.ProjectConfig',
    'apps.outline.apps.OutlineConfig',
    'apps.volume.apps.VolumeConfig',
    'apps.chapter.apps.ChapterConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.LoginRequiredMiddleware',
]

LOGIN_URL = '/login/'

ROOT_URLCONF = 'novel_agent.urls'

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

WSGI_APPLICATION = 'novel_agent.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('MYSQL_DB_DATABASE', 'novel_agent'),
        'USER': os.getenv('MYSQL_DB_USER', 'root'),
        'PASSWORD': os.getenv('MYSQL_DB_PASSWORD', ''),
        'HOST': os.getenv('MYSQL_DB_HOST', 'localhost'),
        'PORT': os.getenv('MYSQL_DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://:{os.getenv('REDIS_DB_PASSWORD', '')}@{os.getenv('REDIS_DB_HOST', 'localhost')}:{os.getenv('REDIS_DB_PORT', '6379')}/{os.getenv('REDIS_DB_DB', '0')}",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = True

LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'deepseek-v4-flash')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.deepseek.com')
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.7'))
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '4096'))
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '120'))
LLM_RETRY = int(os.getenv('LLM_RETRY', '3'))
LLM_RETRY_INTERVAL = int(os.getenv('LLM_RETRY_INTERVAL', '5'))
