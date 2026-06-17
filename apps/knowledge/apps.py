from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.knowledge'
    verbose_name = '知识库'

    def ready(self):
        # 注册 signals，不在此处连接 Milvus（懒加载）
        from . import signals  # noqa: F401
