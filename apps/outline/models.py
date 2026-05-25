from django.db import models
from apps.project.models import ProjectList


class OutlineVersion(models.Model):
    """大纲版本"""
    project = models.ForeignKey(ProjectList, on_delete=models.CASCADE, related_name='outline_versions', verbose_name='项目')
    version_number = models.IntegerField(default=1, verbose_name='版本号')
    content = models.TextField(verbose_name='大纲内容')
    is_finalized = models.BooleanField(default=False, verbose_name='是否定稿')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    is_current = models.BooleanField(default=False, verbose_name='是否为当前版本')
    snapshot = models.TextField(blank=True, verbose_name='内容快照')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'outline_version'
        verbose_name = '大纲版本'
        verbose_name_plural = '大纲版本'
        ordering = ['-version_number']

    def __str__(self):
        return f'{self.project.title} - 版本{self.version_number}'

    @classmethod
    def get_or_create_building_version(cls, project):
        """获取或创建构建中的版本（version_number=0）"""
        obj, created = cls.objects.get_or_create(
            project=project,
            version_number=0,
            defaults={
                'content': '',
                'is_finalized': False,
                'is_current': True,
            }
        )
        if not created and not obj.is_current:
            obj.is_current = True
            obj.save()
        return obj


class OutlineChatHistory(models.Model):
    """大纲聊天历史"""
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]
    outline_version = models.ForeignKey(OutlineVersion, on_delete=models.CASCADE, related_name='outline_chat_histories', verbose_name='大纲版本')
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
        return f'{self.outline_version.project.title} - {self.role}'


class OutlineExpansion(models.Model):
    """大纲扩展内容"""
    CATEGORY_CHOICES = [
        ('world', '世界观'),
        ('magic', '设定体系'),
        ('history', '历史背景'),
        ('culture', '文化风俗'),
        ('location', '地点场景'),
        ('rule', '规则设定'),
        ('plot', '情节伏笔'),
        ('other', '其他'),
    ]

    outline_version = models.ForeignKey(OutlineVersion, on_delete=models.CASCADE, related_name='expansions', verbose_name='大纲版本')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other', verbose_name='分类')
    key_name = models.CharField(max_length=200, verbose_name='关键词')
    content = models.TextField(verbose_name='扩展内容')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'outline_expansion'
        verbose_name = '大纲扩展'
        verbose_name_plural = '大纲扩展'
        ordering = ['category', 'key_name']

    def __str__(self):
        return f'{self.key_name} ({self.get_category_display()})'
