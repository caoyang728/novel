"""
Django Signals - 角色变更时自动同步图谱

监听 Character 模型的 post_save / post_delete 事件。
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from loguru import logger

from . import tasks as _tasks


@receiver(post_save, sender='characters.Character')
def on_character_saved(sender, instance, created, **kwargs):
    """角色保存时：软删除 → 删节点；正常 → 同步节点"""
    if instance.is_deleted:
        _tasks._enqueue(_tasks.delete_character_task, instance.pk)
    else:
        _tasks._enqueue(_tasks.sync_character_task, instance.pk)


@receiver(post_delete, sender='characters.Character')
def on_character_deleted(sender, instance, **kwargs):
    """角色硬删除时：删除图谱节点"""
    _tasks._enqueue(_tasks.delete_character_task, instance.pk)
