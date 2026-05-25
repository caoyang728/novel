from django.db import models
from apps.project.models import ProjectList
from apps.outline.models import OutlineVersion


class VolumeVersion(models.Model):
    """卷版本"""
    project = models.ForeignKey(ProjectList, on_delete=models.CASCADE, related_name='volume_versions', verbose_name='项目')
    outline_version = models.ForeignKey(OutlineVersion, on_delete=models.CASCADE, related_name='volume_versions', verbose_name='关联大纲版本')
    version_number = models.IntegerField(default=1, verbose_name='版本号')
    is_finalized = models.BooleanField(default=False, verbose_name='是否定稿')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    is_current = models.BooleanField(default=False, verbose_name='是否为当前版本')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'volume_version'
        verbose_name = '卷版本'
        verbose_name_plural = '卷版本'
        ordering = ['-version_number']

    def __str__(self):
        return f'{self.project.title} - 卷版本{self.version_number}'


class VolumeList(models.Model):
    """卷"""
    volume_version = models.ForeignKey(VolumeVersion, on_delete=models.CASCADE, related_name='volumes', verbose_name='卷版本')
    volume_number = models.IntegerField(verbose_name='卷号')
    title = models.CharField(max_length=255, verbose_name='卷标题')
    summary = models.TextField(blank=True, verbose_name='卷摘要')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'volume_list'
        verbose_name = '卷'
        verbose_name_plural = '卷'
        ordering = ['volume_number']
        unique_together = [('volume_version', 'volume_number')]

    def __str__(self):
        return f'{self.volume_version.project.title} - {self.title}'
