"""
Django Signals - 自动同步知识库

在模型保存/删除时, 异步更新 Milvus 中的向量索引
"""
import threading
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from loguru import logger


def _run_async(func):
    """装饰器: 在新线程中执行, 避免阻塞请求响应"""
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)
        t.start()
    return wrapper


# ==================== 章节 ====================

@_run_async
def _index_chapter(chapter):
    try:
        from .indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer()
        indexer.index_chapter(chapter)
    except Exception as e:
        logger.error(f"索引章节 {chapter.pk} 失败: {e}")


@_run_async
def _delete_chapter_index(chapter):
    try:
        from .indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer()
        indexer.delete_chapter(chapter)
    except Exception as e:
        logger.error(f"删除章节 {chapter.pk} 向量索引失败: {e}")


@receiver(post_save, sender='chapter.ChapterList')
def on_chapter_saved(sender, instance, created, **kwargs):
    """章节保存后重新索引"""
    _index_chapter(instance)


@receiver(post_delete, sender='chapter.ChapterList')
def on_chapter_deleted(sender, instance, **kwargs):
    """章节删除后清理向量索引"""
    _delete_chapter_index(instance)


# ==================== 角色 ====================

@_run_async
def _index_character(character):
    try:
        from .indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer()
        indexer.index_character(character)
    except Exception as e:
        logger.error(f"索引角色 {character.pk} 失败: {e}")


@_run_async
def _delete_character_index(character):
    try:
        from .indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer()
        indexer.delete_character(character)
    except Exception as e:
        logger.error(f"删除角色 {character.pk} 向量索引失败: {e}")


@receiver(post_save, sender='characters.Character')
def on_character_saved(sender, instance, created, **kwargs):
    _index_character(instance)


@receiver(post_delete, sender='characters.Character')
def on_character_deleted(sender, instance, **kwargs):
    _delete_character_index(instance)


# ==================== 大纲 ====================

@_run_async
def _index_outline(outline_version):
    try:
        from .indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer()
        if outline_version.is_finalized and not outline_version.is_deleted:
            indexer.index_outline(outline_version)
        else:
            indexer.delete_outline(outline_version)
    except Exception as e:
        logger.error(f"索引大纲版本 {outline_version.pk} 失败: {e}")


@receiver(post_save, sender='outline.OutlineVersion')
def on_outline_saved(sender, instance, created, **kwargs):
    _index_outline(instance)


# ==================== 世界观 ====================

@_run_async
def _index_worldview(worldview):
    try:
        from .indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer()
        indexer.index_worldview(worldview)
    except Exception as e:
        logger.error(f"索引世界观 {worldview.pk} 失败: {e}")


@_run_async
def _delete_worldview_index(worldview):
    try:
        from .indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer()
        indexer.delete_worldview(worldview)
    except Exception as e:
        logger.error(f"删除世界观 {worldview.pk} 向量索引失败: {e}")


@receiver(post_save, sender='worldview.WorldView')
def on_worldview_saved(sender, instance, created, **kwargs):
    _index_worldview(instance)


@receiver(post_delete, sender='worldview.WorldView')
def on_worldview_deleted(sender, instance, **kwargs):
    _delete_worldview_index(instance)


# ==================== 卷大纲 ====================

@_run_async
def _index_volume(volume):
    try:
        from .indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer()
        indexer.index_volume(volume)
    except Exception as e:
        logger.error(f"索引卷 {volume.pk} 失败: {e}")


@_run_async
def _delete_volume_index(volume):
    try:
        from .indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer()
        indexer.delete_volume(volume)
    except Exception as e:
        logger.error(f"删除卷 {volume.pk} 向量索引失败: {e}")


@receiver(post_save, sender='volume.VolumeList')
def on_volume_saved(sender, instance, created, **kwargs):
    _index_volume(instance)


@receiver(post_delete, sender='volume.VolumeList')
def on_volume_deleted(sender, instance, **kwargs):
    _delete_volume_index(instance)
