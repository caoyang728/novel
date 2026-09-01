"""novel_agent 包入口。

Django 启动 + Celery 应用导出。保证 celery -A novel_agent 能拿到 app，
同时 Django 其他模块需要 `from novel_agent import celery_app` 时方便。
"""
from .celery import app as celery_app

__all__ = ('celery_app',)
