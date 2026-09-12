"""
Django Signals - 自动同步知识库索引

在模型保存/删除时提交 Celery 异步任务更新 pgvector（若 broker 不可用则降级同步）。
不再使用后台线程：因为 gunicorn 下线程共享连接池可能泄漏，Celery 自带 retry/监控更稳。
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from loguru import logger

from . import tasks as _tasks


# ====================================================================
# 章节
# ====================================================================
@receiver(post_save, sender='chapter.ChapterList')
def on_chapter_saved(sender, instance, created, **kwargs):  # noqa: ARG001
    _tasks._enqueue(_tasks.index_chapter_task, instance.pk)


@receiver(post_delete, sender='chapter.ChapterList')
def on_chapter_deleted(sender, instance, **kwargs):  # noqa: ARG001
    _tasks._enqueue(_tasks.delete_chapter_task, instance.pk)


# ====================================================================
# 角色
# ====================================================================
@receiver(post_save, sender='characters.Character')
def on_character_saved(sender, instance, created, **kwargs):  # noqa: ARG001
    _tasks._enqueue(_tasks.index_character_task, instance.pk)


@receiver(post_delete, sender='characters.Character')
def on_character_deleted(sender, instance, **kwargs):  # noqa: ARG001
    _tasks._enqueue(_tasks.delete_character_task, instance.pk)


# ====================================================================
# 大纲（只有 finalized=True 且未删才索引，否则删索引）
# ====================================================================
@receiver(post_save, sender='outline.Outline')
def on_outline_saved(sender, instance, created, **kwargs):  # noqa: ARG001
    if instance.is_finalized and not instance.is_deleted:
        _tasks._enqueue(_tasks.index_outline_task, instance.pk)
    else:
        _tasks._enqueue(_tasks.delete_outline_task, instance.pk)


# ====================================================================
# 世界观
# ====================================================================
@receiver(post_save, sender='worldview.WorldView')
def on_worldview_saved(sender, instance, created, **kwargs):  # noqa: ARG001
    _tasks._enqueue(_tasks.index_worldview_task, instance.pk)


@receiver(post_delete, sender='worldview.WorldView')
def on_worldview_deleted(sender, instance, **kwargs):  # noqa: ARG001
    _tasks._enqueue(_tasks.delete_worldview_task, instance.pk)


# ====================================================================
# 卷大纲
# ====================================================================
@receiver(post_save, sender='volume.Volume')
def on_volume_saved(sender, instance, created, **kwargs):  # noqa: ARG001
    _tasks._enqueue(_tasks.index_volume_task, instance.pk)


@receiver(post_delete, sender='volume.Volume')
def on_volume_deleted(sender, instance, **kwargs):  # noqa: ARG001
    _tasks._enqueue(_tasks.delete_volume_task, instance.pk)
