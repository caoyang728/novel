from django.db import models


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
            '"calendar":{"era":"","days_per_year":"","seasons":""},'
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

    # ---------- 社会结构 (court / sect / jianghu / external / class / currency / resource) ----------
    society = models.JSONField(
        default=dict, blank=True,
        verbose_name='社会结构',
        help_text=(
            '{"court":{"political_system":"","bureaucracy":""},'
            '"sect":{"levels":"","relationships":""},'
            '"jianghu":{"factions":"","alliances":""},'
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

    # ---------- 特殊规则 (taboo / secret / fate / reincarnation / transmigration / system / transmigration_rules) ----------
    special = models.JSONField(
        default=dict, blank=True,
        verbose_name='特殊规则',
        help_text=(
            '{"taboo":"","secret":"",'
            '"fate":{"fortune_rules":"","destiny_types":""},'
            '"reincarnation":{"soul_rules":"","mechanics":""},'
            '"transmigration":"","system":"","transmigration_rules":""}'
        )
    )

    # ---------- 军事体系 (forces / weapons / warfare / defense) ----------
    military = models.JSONField(
        default=dict, blank=True,
        verbose_name='军事体系',
        help_text=(
            '{"forces":{"army_structure":"","elite_units":""},'
            '"weapons":{"types":"","legendary":""},'
            '"warfare":{"rules":"","history":""},'
            '"defense":{"fortifications":"","strategic_points":""}}'
        )
    )

    # ---------- 科技体系 (level / key_tech / communication / ethics) ----------
    technology = models.JSONField(
        default=dict, blank=True,
        verbose_name='科技体系',
        help_text=(
            '{"level":"",'
            '"key_tech":"",'
            '"communication":"",'
            '"transport":"",'
            '"ethics":""}'
        )
    )

    # ---------- 扩展数据（列表式结构化数据） ----------
    factions = models.JSONField(default=list, blank=True, verbose_name='阵营列表')
    """[{"name":"","position":"","doctrine":""}, ...]"""

    locations = models.JSONField(default=list, blank=True, verbose_name='地点列表')
    """[{"name":"","terrain":"","overview":""}, ...]"""

    relations = models.JSONField(default=list, blank=True, verbose_name='关系列表')
    """[{"source":"","type":"","target":"","description":""}, ...]"""

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
        return f'{self.worldview.project.title} - {self.role}'


class WorldviewDoc(models.Model):
    """世界观文档（新版）

    与旧版 WorldView（JSON 分层结构）并行存在，采用 Markdown 整体存储，
    通过对话式 AI 构建和修改。确认稳定后再替换旧版。

    - content: Markdown 正文，Web 展示与 LLM 上下文均直接使用
    - genre: 题材分类，决定 AI 构建时使用的提示词骨架
    - faction_index: LLM 从正文中提取的阵营索引缓存（供角色表单下拉框使用），
      结构为 [{"name": "蜀国", "subs": ["投降派", "抗战派"]}, ...]
    """

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

    project = models.OneToOneField(
        'project.ProjectList',
        on_delete=models.CASCADE,
        related_name='worldview_doc',
        verbose_name='所属项目'
    )
    genre = models.CharField(
        max_length=20,
        choices=GENRE_CHOICES,
        default='general',
        verbose_name='题材类型'
    )
    title = models.CharField(max_length=200, blank=True, default='', verbose_name='文档标题')
    content = models.TextField(blank=True, default='', verbose_name='世界观内容（Markdown）')
    faction_index = models.JSONField(default=list, blank=True, verbose_name='阵营索引缓存')
    version = models.PositiveIntegerField(default=1, verbose_name='版本号')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'worldview_doc'
        verbose_name = '世界观文档（Markdown）'
        verbose_name_plural = verbose_name

    def __str__(self):
        return f'{self.project.title} - 世界观文档'


class WorldviewDocVersion(models.Model):
    """世界观文档版本"""
    doc = models.ForeignKey(
        WorldviewDoc,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name='所属世界观文档'
    )
    version_number = models.PositiveIntegerField(default=1, verbose_name='版本号')
    content = models.TextField(blank=True, default='', verbose_name='Markdown 内容')
    snapshot = models.TextField(blank=True, default='', verbose_name='内容快照（前 500 字）')
    last_question = models.TextField(blank=True, default='', verbose_name='最后一条 AI 问题')
    last_options = models.JSONField(default=list, blank=True, verbose_name='最后一条 AI 选项')
    is_current = models.BooleanField(default=False, verbose_name='是否为当前版本')
    is_finalized = models.BooleanField(default=False, verbose_name='是否定稿（锁定）')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'worldview_doc_version'
        verbose_name = '世界观文档版本'
        verbose_name_plural = verbose_name
        ordering = ['-version_number']

    def save(self, *args, **kwargs):
        self.snapshot = self.content[:500] if self.content else ''
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.doc.project.title} - 世界观v{self.version_number}'


class WorldviewDocChatHistory(models.Model):
    """世界观文档（新版）聊天历史"""
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]

    doc = models.ForeignKey(
        WorldviewDoc,
        on_delete=models.CASCADE,
        related_name='chat_histories',
        verbose_name='所属世界观文档'
    )
    version = models.ForeignKey(
        'WorldviewDocVersion',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='chat_histories',
        verbose_name='所属版本'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='角色')
    content = models.TextField(verbose_name='内容')
    options = models.JSONField(default=list, blank=True, verbose_name='快捷选项')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'worldview_doc_chat_history'
        verbose_name = '世界观文档聊天历史'
        verbose_name_plural = verbose_name
        ordering = ['created_at']

    def __str__(self):
        return f'{self.doc_id} - {self.role}'
