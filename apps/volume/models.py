from django.db import models
from apps.project.models import ProjectList
from apps.outline.models import Outline


class Volume(models.Model):
    """卷 - 单表设计，version 控制版本"""
    project = models.ForeignKey(ProjectList, on_delete=models.CASCADE, related_name='volumes', verbose_name='项目')
    outline = models.ForeignKey(Outline, on_delete=models.PROTECT, related_name='volumes', verbose_name='关联大纲')
    version = models.PositiveIntegerField(default=1, verbose_name='版本号')
    volume_number = models.IntegerField(verbose_name='卷号')
    title = models.CharField(max_length=255, verbose_name='卷标题')
    summary = models.TextField(blank=True, verbose_name='卷摘要')
    content = models.TextField(blank=True, default='', verbose_name='卷大纲')
    chapter_count = models.IntegerField(default=0, verbose_name='预估章节数')
    is_locked = models.BooleanField(default=False, verbose_name='是否锁定（定稿）')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'volume'
        verbose_name = '卷'
        verbose_name_plural = '卷'
        unique_together = [('project', 'version', 'volume_number')]
        ordering = ['version', 'volume_number']

    def __str__(self):
        return f'{self.project.title} - V{self.version} 第{self.volume_number}卷 {self.title}'
