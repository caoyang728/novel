from django.db import models
from apps.volume.models import VolumeList


class ChapterVersion(models.Model):
    """章节版本"""
    volume = models.ForeignKey(VolumeList, on_delete=models.CASCADE, related_name='chapter_versions', verbose_name='卷')
    version_number = models.IntegerField(default=1, verbose_name='版本号')
    is_finalized = models.BooleanField(default=False, verbose_name='是否定稿')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    is_current = models.BooleanField(default=False, verbose_name='是否为当前版本')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'chapter_version'
        verbose_name = '章节版本'
        verbose_name_plural = '章节版本'
        ordering = ['-version_number']

    def __str__(self):
        return f'{self.volume.title} - 章节版本{self.version_number}'


class ChapterList(models.Model):
    """章节"""
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_ARCHIVED = 'archived'

    STATUS_CHOICES = [
        (STATUS_DRAFT, '草稿'),
        (STATUS_PUBLISHED, '已发布'),
        (STATUS_ARCHIVED, '已归档'),
    ]

    chapter_version = models.ForeignKey(ChapterVersion, on_delete=models.CASCADE, related_name='chapters', verbose_name='章节版本')
    chapter_number = models.IntegerField(verbose_name='章节号')
    title = models.CharField(max_length=255, verbose_name='章节标题')
    summary = models.TextField(blank=True, verbose_name='章节摘要')
    content = models.TextField(blank=True, verbose_name='章节内容')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name='状态')
    word_count = models.IntegerField(default=0, verbose_name='字数')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'chapter_list'
        verbose_name = '章节'
        verbose_name_plural = '章节'
        ordering = ['chapter_number']
        unique_together = [('chapter_version', 'chapter_number')]

    def __str__(self):
        return f'{self.chapter_version.volume.title} - {self.title}'
