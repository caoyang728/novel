from django.db import models


class Character(models.Model):
    """人物角色"""
    ROLE_TYPE_CHOICES = [
        ('protagonist', '主角'),
        ('supporting', '配角'),
        ('antagonist', '反派'),
        ('minor', '路人'),
        ('narrator', '旁白/叙述者'),
    ]

    GENDER_CHOICES = [
        ('male', '男'),
        ('female', '女'),
        ('unknown', '未知'),
    ]

    project = models.ForeignKey('project.ProjectList', on_delete=models.CASCADE, related_name='characters', verbose_name='所属项目')
    name = models.CharField(max_length=100, verbose_name='姓名/名称')
    role_type = models.CharField(max_length=20, choices=ROLE_TYPE_CHOICES, default='supporting', verbose_name='角色类型')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='unknown', verbose_name='性别')

    # 核心设定
    appearance = models.TextField(blank=True, verbose_name='外貌特征')
    personality = models.TextField(blank=True, verbose_name='性格特点')
    backstory = models.TextField(blank=True, verbose_name='背景故事')
    motivation = models.TextField(blank=True, verbose_name='核心动机')
    tagline = models.CharField(max_length=255, blank=True, verbose_name='人物标签/签名')
    faction = models.CharField(max_length=255, blank=True, verbose_name='势力/阵营')

    # 扩展信息（JSON格式存储，方便扩展）
    extra = models.JSONField(default=dict, blank=True, verbose_name='扩展信息')

    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'character'
        verbose_name = '人物'
        verbose_name_plural = '人物'
        ordering = ['role_type', 'name']
        constraints = [
            models.UniqueConstraint(fields=['project', 'name'], name='unique_character_name_per_project')
        ]

    def __str__(self):
        return self.name
