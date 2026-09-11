from django.db import models


class Character(models.Model):
    """人物角色 —— 混合存储：结构化字段 + Markdown 内容"""

    project = models.ForeignKey('project.ProjectList', on_delete=models.CASCADE, related_name='characters', verbose_name='所属项目')

    # ---- 结构化字段（查询/筛选/图谱必需）----
    name = models.CharField(max_length=100, verbose_name='姓名/名称')
    role_type = models.CharField(max_length=20, default='配角', verbose_name='角色类型')
    gender = models.CharField(max_length=10, default='未知', verbose_name='性别')
    age = models.PositiveIntegerField(blank=True, null=True, verbose_name='年龄')
    faction = models.CharField(max_length=255, blank=True, verbose_name='势力/阵营')
    identity = models.CharField(max_length=255, blank=True, default='', verbose_name='身份/称号')
    tagline = models.CharField(max_length=255, blank=True, verbose_name='人物标签/签名')
    relationships = models.JSONField(default=list, blank=True, verbose_name='人际关系')

    # ---- Markdown 内容（叙事性字段，题材无关自由扩展）----
    # 包含：性格特点、外貌特征、背景故事、核心动机、优点、缺点、
    #       执念/软肋、禁忌、能力、弱点、秘密、黑历史、成长轨迹、经历等
    content = models.TextField(blank=True, default='', verbose_name='角色内容（Markdown）')

    # ---- 系统字段 ----
    dynamic_states = models.JSONField(default=dict, blank=True, verbose_name='动态状态')
    source = models.CharField(
        max_length=20, blank=True, default='manual',
        choices=[
            ('manual', '手动创建'),
            ('ai_generate', 'AI生成'),
            ('outline_extract', '大纲提取'),
            ('volume_extract', '卷提取'),
            ('chapter_discover', '章节发现'),
        ],
        verbose_name='创建来源'
    )
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


class CharacterTrajectory(models.Model):
    """角色轨迹 —— 记录角色的成长历程（以时间为主，关联章节）"""

    SOURCE_CHOICES = [
        ('chapter', '章节生成'),
        ('manual', '手动记录'),
        ('outline_extract', '大纲提取'),
        ('volume_extract', '卷提取'),
    ]

    character = models.ForeignKey(
        Character, on_delete=models.CASCADE,
        related_name='trajectories', verbose_name='角色'
    )
    project = models.ForeignKey(
        'project.ProjectList', on_delete=models.CASCADE,
        related_name='character_trajectories', verbose_name='项目'
    )
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES,
        default='manual', verbose_name='记录来源'
    )

    # ---- 核心字段（可查询/筛选）----
    title = models.CharField(max_length=200, default='', verbose_name='轨迹标题')
    start_time = models.CharField(max_length=50, blank=True, default='', verbose_name='起始时间（故事内）')
    end_time = models.CharField(max_length=50, blank=True, default='', verbose_name='结束时间（故事内）')
    chapter_ids = models.JSONField(default=list, blank=True, verbose_name='涉及章节ID列表')
    order = models.IntegerField(default=0, verbose_name='排序序号')

    # ---- 详情字段（JSONB，灵活存储可选内容）----
    details = models.JSONField(default=dict, blank=True, verbose_name='轨迹详情')
    # details 结构示例：
    # {
    #   "description": "详细描述...",
    #   "location": "北京",
    #   "emotional_state": "焦虑",
    #   "power_level": "初级",
    #   "key_events": ["事件1", "事件2"],
    #   "tags": ["成长", "转折"]
    # }

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'character_trajectory'
        verbose_name = '角色轨迹'
        verbose_name_plural = '角色轨迹'
        ordering = ['character', 'order', 'created_at']
        indexes = [
            models.Index(fields=['character', 'order']),
            models.Index(fields=['project', 'created_at']),
        ]

    def __str__(self):
        return f'{self.character.name} - {self.title}'
