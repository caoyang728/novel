from django.db import models
from apps.volume.models import VolumeList


class ChapterList(models.Model):
    """章节"""
    STATUS_SUMMARY = 'summary'
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_ARCHIVED = 'archived'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_SUMMARY, '已生成概述'),
        (STATUS_DRAFT, '草稿'),
        (STATUS_PUBLISHED, '已发布'),
        (STATUS_ARCHIVED, '已归档'),
        (STATUS_FAILED, '生成失败'),
    ]

    STATE_NORMAL = 'normal'
    STATE_LOCKED = 'locked'
    STATE_DELETED = 'deleted'

    STATE_CHOICES = [
        (STATE_NORMAL, '正常'),
        (STATE_LOCKED, '已锁定'),
        (STATE_DELETED, '已删除'),
    ]

    volume = models.ForeignKey(VolumeList, on_delete=models.CASCADE, related_name='chapter_list', verbose_name='卷')
    chapter_number = models.IntegerField(verbose_name='章节号')
    title = models.CharField(max_length=255, verbose_name='章节标题', default='')
    summary = models.TextField(blank=True, default='', verbose_name='章节摘要')
    content = models.TextField(blank=True, default='', verbose_name='章节内容')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name='状态')
    state = models.CharField(max_length=20, choices=STATE_CHOICES, default=STATE_NORMAL, verbose_name='保护状态')
    word_count = models.IntegerField(default=0, verbose_name='字数')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'chapter_list'
        verbose_name = '章节'
        verbose_name_plural = '章节'
        ordering = ['chapter_number']
        unique_together = [('volume', 'chapter_number')]

    def __str__(self):
        return f'{self.volume.title} - 第{self.chapter_number}章 {self.title}'
