from django.db import models
from apps.project.models import ProjectList


class TimelineEvent(models.Model):
    """时间线事件"""
    project = models.ForeignKey(ProjectList, on_delete=models.CASCADE, related_name='timeline_events', verbose_name='所属项目')
    title = models.CharField(max_length=255, verbose_name='事件标题')
    description = models.TextField(blank=True, verbose_name='事件描述')
    start_chapter = models.IntegerField(default=1, verbose_name='起始章节')
    end_chapter = models.IntegerField(default=1, verbose_name='结束章节')
    event_order = models.IntegerField(default=0, verbose_name='排序顺序')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'timeline_event'
        verbose_name = '时间线事件'
        verbose_name_plural = '时间线事件'
        ordering = ['event_order']

    def __str__(self):
        return f'{self.title} (章节 {self.start_chapter}-{self.end_chapter})'


class TimelineChatHistory(models.Model):
    """时间线聊天历史"""
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]
    project = models.ForeignKey(ProjectList, on_delete=models.CASCADE, related_name='timeline_chat_histories', verbose_name='项目')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='角色')
    content = models.TextField(verbose_name='内容')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'timeline_chat_history'
        verbose_name = '时间线聊天历史'
        verbose_name_plural = '时间线聊天历史'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.project.title} - {self.role}'
