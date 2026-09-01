"""
Celery 应用入口（celery -A novel_agent worker/beat）
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'novel_agent.settings')

app = Celery('novel_agent')
# 从 Django settings 读取 CELERY_* 配置
app.config_from_object('django.conf:settings', namespace='CELERY')
# 自动发现所有 app 下的 tasks.py
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
