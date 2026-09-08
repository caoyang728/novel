from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


def generate_project_title():
    """生成项目标题"""
    count = ProjectList.objects.count() + 1
    return f"小说{count}"


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


class ProjectList(models.Model):
    """项目列表"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='project_lists', verbose_name='用户')
    title = models.CharField(max_length=255, default=generate_project_title, verbose_name='项目名称')
    description = models.TextField(blank=True, verbose_name='项目描述')
    genre = models.CharField(max_length=20, choices=GENRE_CHOICES, default='general', verbose_name='题材类型')
    status = models.CharField(max_length=50, default='draft', verbose_name='状态')
    finalized = models.BooleanField(default=False, verbose_name='是否定稿')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    min_words_per_chapter = models.PositiveIntegerField(default=3000, verbose_name='单章最少字数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'project_list'
        verbose_name = '项目'
        verbose_name_plural = '项目'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['user', 'title'], name='unique_project_title_per_user')
        ]

    def __str__(self):
        return self.title
