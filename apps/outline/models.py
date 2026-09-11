from django.db import models
from apps.project.models import ProjectList


class Outline(models.Model):
    """大纲"""
    project = models.ForeignKey(ProjectList, on_delete=models.CASCADE, related_name='outlines', verbose_name='项目')
    version = models.IntegerField(default=1, verbose_name='版本号')
    content = models.TextField(verbose_name='大纲内容')
    is_finalized = models.BooleanField(default=False, verbose_name='是否定稿')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    last_question = models.TextField(blank=True, default='', verbose_name='最后一条 AI 问题')
    last_options = models.JSONField(default=list, blank=True, verbose_name='最后一条 AI 选项')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'outline'
        verbose_name = '大纲'
        verbose_name_plural = '大纲'
        ordering = ['-version']

    def __str__(self):
        return f'{self.project.title} - 大纲 v{self.version}'

    @classmethod
    def get_or_create_building(cls, project):
        """获取或创建构建中的版本（version=0）"""
        obj, created = cls.objects.get_or_create(
            project=project,
            version=0,
            defaults={
                'content': '',
                'is_finalized': False,
            }
        )
        return obj


class OutlineChatHistory(models.Model):
    """大纲聊天历史"""
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]
    outline = models.ForeignKey(Outline, on_delete=models.CASCADE, related_name='chat_histories', verbose_name='所属大纲')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='角色')
    content = models.TextField(verbose_name='内容')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'outline_chat_history'
        verbose_name = '大纲聊天历史'
        verbose_name_plural = '大纲聊天历史'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.outline.project.title} - {self.role}'

