from django.db import models


GENRE_CHOICES = [
    ('xuanhuan', '玄幻/仙侠'),
    ('wuxia', '武侠'),
    ('fantasy', '西方奇幻'),
    ('scifi', '科幻'),
    ('history', '历史/架空'),
    ('urban', '都市'),
    ('apocalypse', '末世/灾变'),
    ('general', '通用'),
]


class WorldView(models.Model):
    """世界观文档（Markdown 整体存储，对话式 AI 构建）

    每个版本是主表的一行，通过 (project, version) UNIQUE 约束管理。
    取当前版本：WorldView.objects.filter(project=project, is_deleted=False).first()
    （依赖 Meta.ordering = ['-version']）
    """

    project = models.ForeignKey(
        'project.ProjectList',
        on_delete=models.CASCADE,
        related_name='worldviews',
        verbose_name='所属项目'
    )
    version = models.PositiveIntegerField(default=1, verbose_name='版本号')
    genre = models.CharField(
        max_length=20,
        choices=GENRE_CHOICES,
        default='general',
        verbose_name='题材类型'
    )
    title = models.CharField(max_length=200, blank=True, default='', verbose_name='文档标题')
    content = models.TextField(blank=True, default='', verbose_name='世界观内容（Markdown）')
    faction_index = models.JSONField(default=list, blank=True, verbose_name='阵营索引缓存')
    is_finalized = models.BooleanField(default=False, verbose_name='是否定稿（锁定）')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    last_question = models.TextField(blank=True, default='', verbose_name='最后一条 AI 问题')
    last_options = models.JSONField(default=list, blank=True, verbose_name='最后一条 AI 选项')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'worldview'
        verbose_name = '世界观文档'
        verbose_name_plural = verbose_name
        ordering = ['-version']
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'version'],
                name='uq_worldview_project_version'
            ),
        ]

    def __str__(self):
        return f'{self.project.title} - 世界观 v{self.version}'


class WorldViewChatHistory(models.Model):
    """世界观聊天历史"""
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]

    worldview = models.ForeignKey(
        WorldView,
        on_delete=models.CASCADE,
        related_name='chat_histories',
        verbose_name='所属世界观'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='角色')
    content = models.TextField(verbose_name='内容')
    options = models.JSONField(default=list, blank=True, verbose_name='快捷选项')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'worldview_chat_history'
        verbose_name = '世界观聊天历史'
        verbose_name_plural = verbose_name
        ordering = ['created_at']

    def __str__(self):
        return f'{self.worldview_id} - {self.role}'
