from django.apps import AppConfig


class GraphConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.graph'
    verbose_name = '知识图谱'

    def ready(self):
        import apps.graph.signals  # noqa: F401
