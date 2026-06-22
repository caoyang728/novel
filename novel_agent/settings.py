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
    'apps.project.apps.ProjectConfig',
    'apps.outline.apps.OutlineConfig',
    'apps.volume.apps.VolumeConfig',
    'apps.chapter.apps.ChapterConfig',
    'apps.characters.apps.CharactersConfig',
    'apps.user.apps.UserConfig',
    'apps.worldview.apps.WorldviewConfig',
    'apps.note.apps.NoteConfig',
    'apps.timeline.apps.TimelineConfig',
    'apps.knowledge.apps.KnowledgeConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'novel_agent.middleware.JWTAuthenticationMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'novel_agent.middleware.LoginRequiredMiddleware',
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
            'SOCKET_CONNECT_TIMEOUT': 5,  # 连接超时（秒），避免 Redis 不可达时长时间阻塞
            'SOCKET_TIMEOUT': 5,          # 读写超时（秒）
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
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = True

LLM_API_KEY = os.getenv('LLM_API_KEY', '')
LLM_MODEL = os.getenv('LLM_MODEL', 'deepseek-v4-flash')
LLM_BASE_URL = os.getenv('LLM_BASE_URL', 'https://api.deepseek.com')
LLM_TEMPERATURE = float(os.getenv('LLM_TEMPERATURE', '0.7'))
LLM_MAX_TOKENS = int(os.getenv('LLM_MAX_TOKENS', '4096'))
LLM_TIMEOUT = int(os.getenv('LLM_TIMEOUT', '600'))
LLM_OUTLINE_TIMEOUT = int(os.getenv('LLM_OUTLINE_TIMEOUT', '300'))  # 大纲构建专用超时（秒）
LLM_RETRY = int(os.getenv('LLM_RETRY', '3'))
LLM_RETRY_INTERVAL = int(os.getenv('LLM_RETRY_INTERVAL', '5'))

# JWT Settings
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ========== Milvus 向量库配置 ==========
MILVUS_MODE = os.getenv('MILVUS_MODE', 'docker')  # docker | local
MILVUS_HOST = os.getenv('MILVUS_HOST', 'localhost')
MILVUS_PORT = os.getenv('MILVUS_PORT', '19530')
MILVUS_COLLECTION_NAME = os.getenv('MILVUS_COLLECTION_NAME', 'novel_knowledge')
MILVUS_LOCAL_DB = os.getenv('MILVUS_LOCAL_DB', str(BASE_DIR / 'milvus_demo.db'))

# ========== Embedding 配置 ==========
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'deepseek-v4-flash')
EMBEDDING_DIM = int(os.getenv('EMBEDDING_DIM', '1024'))
EMBEDDING_DOCKER_URL = os.getenv('EMBEDDING_DOCKER_URL', 'http://localhost:8080/embed')
EMBEDDING_DOCKER_TIMEOUT = int(os.getenv('EMBEDDING_DOCKER_TIMEOUT', '30'))

import rest_framework_simplejwt

REST_FRAMEWORK = {
    # DRF 全局 JWT 认证（用于 API 请求）
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    # API 请求需要认证（可选，用中间件也行）
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # 接口统一返回401，不跳转
    "EXCEPTION_HANDLER": "utils.exceptions.custom_exception_handler",
    # 限流配置
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "user": "60/minute",        # 默认：每用户每分钟60次
        "ai_gen": "10/minute",      # AI 生成/润色/检测/优化：每分钟10次
    },
}
