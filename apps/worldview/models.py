from django.db import models
from django.conf import settings


class WorldView(models.Model):
    """世界观完整设定

    每个 JSONField 对应 HTML 中的一个 Tab，其内部 key 与 HTML 的
    section-nav-btn onclick 参数（子区块名）保持一致。
    """

    project = models.OneToOneField(
        'project.ProjectList',
        on_delete=models.CASCADE,
        related_name='worldview',
        verbose_name='所属项目'
    )

    # ---------- 基础设定 (identity / position / overview / conflict) ----------
    setting = models.JSONField(
        default=dict, blank=True,
        verbose_name='基础设定',
        help_text=(
            '{"identity":{"world_name":"","genre":""},'
            '"position":{"identity":"","tone":""},'
            '"overview":"",'
            '"conflict":""}'
        )
    )

    # ---------- 世界基础 (geography / calendar / rules / balance) ----------
    foundation = models.JSONField(
        default=dict, blank=True,
        verbose_name='世界基础',
        help_text=(
            '{"geography":{"continent_distribution":"","special_terrain":""},'
            '"calendar":{"era":"","days_per_year":"","seasons":"","festivals":""},'
            '"rules":{"natural_laws":"","boundaries":"","axioms":[]},'
            '"balance":""}'
        )
    )

    # ---------- 力量体系 (energy / level / martial / treasure / beast) ----------
    power = models.JSONField(
        default=dict, blank=True,
        verbose_name='力量体系',
        help_text=(
            '{"energy":{"types":"","distribution":"","properties":""},'
            '"level":"",'
            '"martial":{"categories":"","inheritance":""},'
            '"treasure":{"categories":"","pills":""},'
            '"beast":{"levels":"","mythical":""}}'
        )
    )

    # ---------- 种族族群 (category / value / trait / relation) ----------
    races = models.JSONField(
        default=dict, blank=True,
        verbose_name='种族族群',
        help_text=(
            '{"category":"","value":"",'
            '"trait":{"lifespan":"","reproduction":"","physique":""},'
            '"relation":""}'
        )
    )

    # ---------- 社会结构 (court / sect / martial / external / class / currency / resource) ----------
    society = models.JSONField(
        default=dict, blank=True,
        verbose_name='社会结构',
        help_text=(
            '{"court":{"political_system":"","bureaucracy":""},'
            '"sect":{"levels":"","relationships":""},'
            '"martial":{"factions":"","alliances":""},'
            '"external":"",'
            '"strata":{"social_classes":"","mobility":""},'
            '"currency":{"types":"","rules":""},'
            '"resource":""}'
        )
    )

    # ---------- 文化人文 (custom / language / daily / religion) ----------
    culture = models.JSONField(
        default=dict, blank=True,
        verbose_name='文化人文',
        help_text=(
            '{"custom":{"festivals":"","rituals":""},'
            '"language":{"languages":"","writing_system":""},'
            '"daily":{"clothing":"","cuisine":"","architecture":"","transportation":""},'
            '"religion":{"deities":"","organization":"","faith_differences":""}}'
        )
    )

    # ---------- 历史进程 (ancient / modern / crisis / destiny / future) ----------
    history = models.JSONField(
        default=dict, blank=True,
        verbose_name='历史进程',
        help_text=(
            '{"ancient":"","modern":"","crisis":"","destiny":"","future":""}'
        )
    )

    # ---------- 特殊规则 (taboo / secret / fate / reincarnation / transmigration / system / rules) ----------
    special = models.JSONField(
        default=dict, blank=True,
        verbose_name='特殊规则',
        help_text=(
            '{"taboo":"","secret":"",'
            '"fate":{"fortune_rules":"","destiny_types":""},'
            '"reincarnation":{"soul_rules":"","mechanics":""},'
            '"transmigration":"","system":"","rules":""}'
        )
    )

    # # ---------- 扩展数据（弹窗 / 问答） ----------
    # factions = models.JSONField(default=list, blank=True, verbose_name='阵营列表')
    # """[{"name":"","position":"","doctrine":""}, ...]"""

    # locations = models.JSONField(default=list, blank=True, verbose_name='地点列表')
    # """[{"name":"","terrain":"","overview":""}, ...]"""

    # relations = models.JSONField(default=list, blank=True, verbose_name='关系列表')
    # """[{"source":"","type":"","target":"","description":""}, ...]"""

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'worldview'
        verbose_name = '世界观详细设定'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.project.title} - 世界观详细设定"


class WorldViewChatHistory(models.Model):
    """世界观聊天历史"""
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]
    
    worldview = models.ForeignKey(
        WorldView,
        on_delete=models.CASCADE,
        related_name='worldview_chat_histories',
        verbose_name='所属世界观'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='角色')
    content = models.TextField(verbose_name='内容')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'worldview_chat_history'
        verbose_name = '世界观聊天历史'
        verbose_name_plural = verbose_name
        ordering = ['created_at']

    def __str__(self):
        return f'{self.project.title} - {self.world.name} - {self.role}'
