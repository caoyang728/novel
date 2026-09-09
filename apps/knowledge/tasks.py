"""
Celery 任务：知识库异步索引 + 全量重建

设计原则：
- Signal 调用不再自己开线程，统一提交到 Celery 队列，有 retry/死信/监控
- 任务入参只用「主键 ID」，避免把 ORM 对象/长文本序列化到 broker
- 若 Celery worker 没启动（比如本地还没 worker），提交失败时兜底到同步执行
"""
from celery import shared_task
from loguru import logger


def _sync_fallback(fn, *args, **kwargs):
    """提交 Celery 失败的兜底：在当前进程里直接跑（至少保证数据正确）。"""
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001
        logger.error(f"同步兜底执行 {fn.__name__} 失败: {e}")
        return None


def _enqueue(task_fn, *args, **kwargs):
    try:
        return task_fn.delay(*args, **kwargs)
    except Exception as e:  # noqa: BLE001（broker 未连接 / 未装 celery 等）
        logger.warning(f"提交 Celery 任务 {task_fn.name} 失败，走同步兜底: {e}")
        return _sync_fallback(task_fn, *args, **kwargs)


# ================================================================
# 大纲
# ================================================================
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    rate_limit='30/m',
    name='knowledge.index_outline',
)
def index_outline_task(self, outline_version_id: int):  # noqa: ARG001
    from apps.outline.models import Outline
    from .indexer import KnowledgeIndexer
    try:
        obj = Outline.objects.get(pk=outline_version_id)
    except Outline.DoesNotExist:
        logger.warning(f"index_outline: 版本 {outline_version_id} 已删除，跳过")
        return 0
    return KnowledgeIndexer().index_outline(obj)


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=2, name='knowledge.delete_outline')
def delete_outline_task(self, outline_version_id: int):  # noqa: ARG001
    from apps.outline.models import Outline
    from .indexer import KnowledgeIndexer
    try:
        obj = Outline.objects.get(pk=outline_version_id)
    except Outline.DoesNotExist:
        return 0
    return KnowledgeIndexer().delete_outline(obj)


# ================================================================
# 世界观
# ================================================================
@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, rate_limit='20/m', name='knowledge.index_worldview')
def index_worldview_task(self, worldview_id: int):  # noqa: ARG001
    from apps.worldview.models import WorldView
    from .indexer import KnowledgeIndexer
    try:
        obj = WorldView.objects.get(pk=worldview_id)
    except WorldView.DoesNotExist:
        logger.warning(f"index_worldview: {worldview_id} 不存在，跳过")
        return 0
    return KnowledgeIndexer().index_worldview(obj)


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=2, name='knowledge.delete_worldview')
def delete_worldview_task(self, worldview_id: int):  # noqa: ARG001
    from apps.worldview.models import WorldView
    from .indexer import KnowledgeIndexer
    try:
        obj = WorldView.objects.get(pk=worldview_id)
    except WorldView.DoesNotExist:
        return 0
    return KnowledgeIndexer().delete_worldview(obj)


# ================================================================
# 角色
# ================================================================
@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, rate_limit='60/m', name='knowledge.index_character')
def index_character_task(self, character_id: int):  # noqa: ARG001
    from apps.characters.models import Character
    from .indexer import KnowledgeIndexer
    try:
        obj = Character.objects.get(pk=character_id)
    except Character.DoesNotExist:
        logger.warning(f"index_character: {character_id} 不存在，跳过")
        return 0
    return KnowledgeIndexer().index_character(obj)


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=2, name='knowledge.delete_character')
def delete_character_task(self, character_id: int):  # noqa: ARG001
    from apps.characters.models import Character
    from .indexer import KnowledgeIndexer
    try:
        obj = Character.objects.get(pk=character_id)
    except Character.DoesNotExist:
        return 0
    return KnowledgeIndexer().delete_character(obj)


# ================================================================
# 卷
# ================================================================
@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, rate_limit='30/m', name='knowledge.index_volume')
def index_volume_task(self, volume_id: int):  # noqa: ARG001
    from apps.volume.models import VolumeList
    from .indexer import KnowledgeIndexer
    try:
        obj = VolumeList.objects.get(pk=volume_id)
    except VolumeList.DoesNotExist:
        logger.warning(f"index_volume: {volume_id} 不存在，跳过")
        return 0
    return KnowledgeIndexer().index_volume(obj)


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=2, name='knowledge.delete_volume')
def delete_volume_task(self, volume_id: int):  # noqa: ARG001
    from apps.volume.models import VolumeList
    from .indexer import KnowledgeIndexer
    try:
        obj = VolumeList.objects.get(pk=volume_id)
    except VolumeList.DoesNotExist:
        return 0
    return KnowledgeIndexer().delete_volume(obj)


# ================================================================
# 章节段落
# ================================================================
@shared_task(bind=True, autoretry_for=(Exception,), max_retries=3, rate_limit='20/m', name='knowledge.index_chapter')
def index_chapter_task(self, chapter_id: int):  # noqa: ARG001
    from apps.chapter.models import ChapterList
    from .indexer import KnowledgeIndexer
    try:
        obj = ChapterList.objects.get(pk=chapter_id)
    except ChapterList.DoesNotExist:
        logger.warning(f"index_chapter: {chapter_id} 不存在，跳过")
        return 0
    return KnowledgeIndexer().index_chapter(obj)


@shared_task(bind=True, autoretry_for=(Exception,), max_retries=2, name='knowledge.delete_chapter')
def delete_chapter_task(self, chapter_id: int):  # noqa: ARG001
    from apps.chapter.models import ChapterList
    from .indexer import KnowledgeIndexer
    try:
        obj = ChapterList.objects.get(pk=chapter_id)
    except ChapterList.DoesNotExist:
        return 0
    return KnowledgeIndexer().delete_chapter(obj)


# ================================================================
# 全量重建（返回 task_id 方便前端轮询）
# ================================================================
@shared_task(
    bind=True,
    name='knowledge.rebuild_project',
    max_retries=1,  # 全量重建最多 retry 一次
    soft_time_limit=3600,
    time_limit=3660,
)
def rebuild_project_task(self, project_id: int):  # noqa: ARG001
    from .indexer import KnowledgeIndexer
    return KnowledgeIndexer().rebuild_project(project_id)


def rebuild_all_projects_task_ids():
    """给 management command / 运维脚本用：逐个项目提交重建任务，返回 [(pid, task_id), ...]。"""
    from apps.project.models import ProjectList
    results = []
    for p in ProjectList.objects.filter(is_deleted=False).only('pk'):
        results.append((p.pk, rebuild_project_task.delay(p.pk).id))
    return results
