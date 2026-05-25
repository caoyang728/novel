from django.db import models
from django.contrib.auth import get_user_model
from apps.project.models import ProjectList

User = get_user_model()


class Note(models.Model):
    STATUS_CHOICES = [
        ('unused', '未使用'),
        ('used', '已使用'),
        ('published', '已发布'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notes', verbose_name='用户')
    project = models.ForeignKey(ProjectList, on_delete=models.CASCADE, related_name='notes', verbose_name='项目')
    content = models.TextField(verbose_name='随手记内容')
    title = models.CharField(max_length=200, blank=True, verbose_name='标题')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unused', verbose_name='状态')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'project_note'
        verbose_name = '随手记'
        verbose_name_plural = '随手记'
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f'随手记 {self.id}'
