from django.db import models


class Character(models.Model):
    """人物角色"""

    project = models.ForeignKey('project.ProjectList', on_delete=models.CASCADE, related_name='characters', verbose_name='所属项目')
    name = models.CharField(max_length=100, verbose_name='姓名/名称')
    role_type = models.CharField(max_length=20, default='配角', verbose_name='角色类型')
    gender = models.CharField(max_length=10, default='未知', verbose_name='性别')

    # 核心设定
    appearance = models.TextField(blank=True, verbose_name='外貌特征')
    personality = models.TextField(blank=True, verbose_name='性格特点')
    backstory = models.TextField(blank=True, verbose_name='背景故事')
    motivation = models.TextField(blank=True, verbose_name='核心动机')
    tagline = models.CharField(max_length=255, blank=True, verbose_name='人物标签/签名')
    faction = models.CharField(max_length=255, blank=True, verbose_name='势力/阵营')

    # 从 extra 拆出的独立字段
    age = models.PositiveIntegerField(blank=True, null=True, verbose_name='年龄')
    identity = models.CharField(max_length=255, blank=True, default='', verbose_name='身份/称号')
    relationships = models.JSONField(default=list, blank=True, verbose_name='人际关系')
    experiences = models.JSONField(default=list, blank=True, verbose_name='经历')
    development = models.TextField(blank=True, default='', verbose_name='成长轨迹')
    strengths = models.TextField(blank=True, default='', verbose_name='优点/特长')
    flaws = models.TextField(blank=True, default='', verbose_name='缺点')
    obsession = models.TextField(blank=True, default='', verbose_name='执念/软肋')
    taboos = models.TextField(blank=True, default='', verbose_name='禁忌')
    abilities = models.TextField(blank=True, default='', verbose_name='能力')
    secrets = models.TextField(blank=True, default='', verbose_name='秘密')
    dark_history = models.TextField(blank=True, default='', verbose_name='过往黑历史')
    weaknesses = models.TextField(blank=True, default='', verbose_name='弱点/代价')

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
