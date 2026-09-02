import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me')

DEBUG = os.getenv('DJANGO_DEBUG', 'False').lower() == 'true'

ALLOWED_HOSTS = [h.strip() for h in os.getenv('DJANGO_ALLOWED_HOSTS', '*').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'pgvector.django',      # PostgreSQL + pgvector
    'django_celery_results',
    'django_celery_beat',
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

# ============ 数据库：PostgreSQL + pgvector（一库两用：业务 + 向量） ============
def _build_pg_location():
    host = os.getenv('PG_DB_HOST', 'localhost')
    port = os.getenv('PG_DB_PORT', '5432')
    user = os.getenv('PG_DB_USER', 'novel_agent')
    password = os.getenv('PG_DB_PASSWORD', '')
    database = os.getenv('PG_DB_DATABASE', 'novel_agent')
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('PG_DB_DATABASE', 'novel_agent'),
        'USER': os.getenv('PG_DB_USER', 'novel_agent'),
        'PASSWORD': os.getenv('PG_DB_PASSWORD', ''),
        'HOST': os.getenv('PG_DB_HOST', 'localhost'),
        'PORT': os.getenv('PG_DB_PORT', '5432'),
        'OPTIONS': {
            'sslmode': os.getenv('PG_SSL_MODE', 'prefer'),
        },
        'CONN_MAX_AGE': int(os.getenv('PG_CONN_MAX_AGE', '600')),
        'CONN_HEALTH_CHECKS': True,
    }
}

# 方便其他地方（比如直连、pgloader）复用
DATABASE_URL = _build_pg_location()

CACHES = {
    'default': {
        'BACKEND': 'novel_agent.cache_backend.RedisFallbackCache',
        'LOCATION': f"redis://:{os.getenv('REDIS_DB_PASSWORD', '')}@{os.getenv('REDIS_DB_HOST', 'localhost')}:{os.getenv('REDIS_DB_PORT', '6379')}/{os.getenv('REDIS_DB_DB', '0')}",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,  # 连接超时（秒）
            'SOCKET_TIMEOUT': 5,          # 读写超时（秒）
        },
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

STATIC_URL = '/static/'
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
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ============ Embedding 配置 ============
# 向量维度固定与 knowledge_vector.embedding 列对齐；修改维度需要 ALTER TABLE 重建列
EMBEDDING_DIM = int(os.getenv('EMBEDDING_DIM', '1024'))
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'deepseek-v4-flash')
EMBEDDING_API_KEY = os.getenv('EMBEDDING_API_KEY', LLM_API_KEY)
EMBEDDING_BASE_URL = os.getenv('EMBEDDING_BASE_URL', LLM_BASE_URL)
# Docker Embedding 服务地址（docker-compose 内部: http://embedding:8000/embed）
EMBEDDING_DOCKER_URL = os.getenv('EMBEDDING_DOCKER_URL', 'http://embedding:8000/embed')
EMBEDDING_DOCKER_TIMEOUT = int(os.getenv('EMBEDDING_DOCKER_TIMEOUT', '30'))

# ============ Celery（Broker 复用 Redis；Result Backend 用 Django DB） ============
def _build_redis_url():
    password = os.getenv('REDIS_DB_PASSWORD', '')
    host = os.getenv('REDIS_DB_HOST', 'localhost')
    port = os.getenv('REDIS_DB_PORT', '6379')
    db = int(os.getenv('REDIS_DB_DB', '0')) + 1  # 用 DB 1 放 Celery，跟 Django cache 的 DB 0 隔离
    auth = f":{password}@" if password else ""
    return f"redis://{auth}{host}:{port}/{db}"


CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', _build_redis_url())
CELERY_RESULT_BACKEND = 'django-db'
CELERY_RESULT_EXTENDED = True
CELERY_CACHE_BACKEND = 'default'

CELERY_ACCEPT_CONTENT = ['json', 'pickle']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = int(os.getenv('CELERY_TASK_TIME_LIMIT', '3600'))  # 单任务最长1小时
CELERY_TASK_SOFT_TIME_LIMIT = int(os.getenv('CELERY_TASK_SOFT_TIME_LIMIT', '3500'))
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # 长任务场景：公平调度优先

CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SYNC_EVERY = int(os.getenv('CELERY_BEAT_SYNC_EVERY', '60'))

# ============ Django REST Framework ============
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
