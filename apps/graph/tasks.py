"""
Celery 任务：图谱异步同步

复用 knowledge/tasks.py 的 _enqueue + _sync_fallback 模式。
"""
from celery import shared_task
from loguru import logger


def _sync_fallback(fn, *args, **kwargs):
    """提交 Celery 失败的兜底：在当前进程里直接跑"""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.error(f"graph 同步兜底执行 {fn.__name__} 失败: {e}")
        return None


def _enqueue(task_fn, *args, **kwargs):
    try:
        return task_fn.delay(*args, **kwargs)
    except Exception as e:
        logger.warning(f"提交 Celery 任务 {task_fn.name} 失败，走同步兜底: {e}")
        return _sync_fallback(task_fn, *args, **kwargs)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    rate_limit='60/m',
    name='graph.sync_character',
)
def sync_character_task(self, character_id: int):
    from .services import GraphService
    return GraphService.sync_character(character_id)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=2,
    name='graph.delete_character',
)
def delete_character_task(self, character_id: int):
    from .services import GraphService
    return GraphService.delete_character(character_id)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=1,
    soft_time_limit=300,
    name='graph.rebuild_project',
)
def rebuild_project_task(self, project_id: int):
    from .services import GraphService
    return GraphService.rebuild_project(project_id)
