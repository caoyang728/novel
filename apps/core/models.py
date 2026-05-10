from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User
import shortuuid
from cryptography.fernet import Fernet
import os

def get_or_create_fernet_key():
    key = os.environ.get('FERNET_KEY')
    if not key:
        key = Fernet.generate_key().decode()
        os.environ['FERNET_KEY'] = key
    return key

fernet = Fernet(get_or_create_fernet_key().encode())

def encrypt(value):
    if not value:
        return ''
    return fernet.encrypt(value.encode()).decode()

def decrypt(value):
    if not value:
        return ''
    return fernet.decrypt(value.encode()).decode()

def generate_project_title():
    projects_count = Project.objects.count() + 1
    return f"小说{projects_count}"

def generate_session_id():
    return shortuuid.uuid()

class Project(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='projects', verbose_name='所属用户', null=True, blank=True)
    title = models.CharField(max_length=255, verbose_name='项目名称', default=generate_project_title)
    description = models.TextField(blank=True, verbose_name='项目描述')
    finalized = models.BooleanField(default=False, verbose_name='是否定稿')
    is_deleted = models.BooleanField(default=False, verbose_name='是否已删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'project'
        verbose_name = '项目'
        verbose_name_plural = '项目'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class OutlineVersion(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='outline_versions', verbose_name='项目')
    version_number = models.IntegerField(default=1, verbose_name='版本号')
    content = models.TextField(verbose_name='大纲内容')
    is_finalized = models.BooleanField(default=False, verbose_name='是否定稿')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    snapshot = models.TextField(blank=True, verbose_name='内容快照')

    class Meta:
        db_table = 'outline_version'
        verbose_name = '大纲版本'
        verbose_name_plural = '大纲版本'
        ordering = ['-version_number']

    def __str__(self):
        return f'{self.project.title} - 大纲版本{self.version_number}'

class OutlineMessage(models.Model):
    ROLE_CHOICES = [
        ('user', '用户'),
        ('assistant', '助手'),
    ]
    
    outline_version = models.ForeignKey(OutlineVersion, on_delete=models.CASCADE, related_name='messages', verbose_name='大纲版本')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, verbose_name='角色')
    content = models.TextField(verbose_name='内容')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'outline_message'
        verbose_name = '大纲消息'
        verbose_name_plural = '大纲消息'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.outline_version.project.title} - {self.role}'

class VolumeVersion(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='volume_versions', verbose_name='项目')
    outline_version = models.ForeignKey(OutlineVersion, on_delete=models.CASCADE, related_name='volume_versions', verbose_name='关联大纲版本')
    version_number = models.IntegerField(default=1, verbose_name='版本号')
    is_finalized = models.BooleanField(default=False, verbose_name='是否定稿')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'volume_version'
        verbose_name = '卷版本'
        verbose_name_plural = '卷版本'
        ordering = ['-version_number']

    def __str__(self):
        return f'{self.project.title} - 卷版本{self.version_number}'

class Volume(models.Model):
    volume_version = models.ForeignKey(VolumeVersion, on_delete=models.CASCADE, related_name='volumes', verbose_name='卷版本')
    volume_number = models.IntegerField(verbose_name='卷号')
    title = models.CharField(max_length=255, verbose_name='卷标题')
    summary = models.TextField(blank=True, verbose_name='卷摘要')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        db_table = 'volume'
        verbose_name = '卷'
        verbose_name_plural = '卷'
        ordering = ['volume_number']
        unique_together = ['volume_version', 'volume_number']

    def __str__(self):
        return f'{self.volume_version.project.title} - 第{self.volume_number}卷: {self.title}'

class ChapterVersion(models.Model):
    volume = models.ForeignKey(Volume, on_delete=models.CASCADE, related_name='chapter_versions', verbose_name='卷')
    version_number = models.IntegerField(default=1, verbose_name='版本号')
    is_finalized = models.BooleanField(default=False, verbose_name='是否定稿')
    is_deleted = models.BooleanField(default=False, verbose_name='是否删除')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'chapter_version'
        verbose_name = '章节版本'
        verbose_name_plural = '章节版本'
        ordering = ['-version_number']

    def __str__(self):
        return f'{self.volume.title} - 章节版本{self.version_number}'

class Chapter(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_ARCHIVED = 'archived'

    STATUS_CHOICES = [
        (STATUS_DRAFT, '草稿'),
        (STATUS_PUBLISHED, '已发布'),
        (STATUS_ARCHIVED, '已归档'),
    ]

    chapter_version = models.ForeignKey(ChapterVersion, on_delete=models.CASCADE, related_name='chapters', verbose_name='章节版本')
    chapter_number = models.IntegerField(verbose_name='章节号')
    title = models.CharField(max_length=255, verbose_name='章节标题')
    summary = models.TextField(blank=True, verbose_name='章节摘要')
    content = models.TextField(blank=True, verbose_name='章节内容')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT, verbose_name='状态')
    word_count = models.IntegerField(default=0, verbose_name='字数')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='发布时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'chapter'
        verbose_name = '章节'
        verbose_name_plural = '章节'
        ordering = ['chapter_number']
        unique_together = ['chapter_version', 'chapter_number']

    def __str__(self):
        return f'{self.chapter_version.volume.title} - 第{self.chapter_number}章: {self.title}'

    def save(self, *args, **kwargs):
        self.word_count = len(self.content) if self.content else 0
        super().save(*args, **kwargs)

class ChatHistory(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='chat_histories', verbose_name='项目')
    session_id = models.CharField(max_length=64, unique=True, default=generate_session_id)
    messages = models.JSONField(default=list, verbose_name='聊天消息')
    current_outline = models.TextField(blank=True, verbose_name='当前大纲')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'chat_history'
        verbose_name = '聊天历史'
        verbose_name_plural = '聊天历史'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.project.title} - {self.session_id[:8]}'

class LLMConfig(models.Model):
    PROVIDER_CHOICES = [
        ('deepseek', 'DeepSeek'),
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('qwen', 'Qwen'),
        ('gemini', 'Gemini'),
        ('custom', '自定义'),
    ]
    TASK_CHOICES = [
        ('outline', '大纲生成'),
        ('volume', '卷结构生成'),
        ('chapter', '章节概要生成'),
        ('content', '章节内容生成'),
        ('other', '其他任务'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='llm_configs', verbose_name='用户', null=True, blank=True)
    name = models.CharField(max_length=100, verbose_name='配置名称')
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES, verbose_name='LLM提供商')
    api_key = models.TextField(verbose_name='API密钥')
    base_url = models.URLField(blank=True, verbose_name='API地址')
    model_name = models.CharField(max_length=100, verbose_name='模型名称')
    temperature = models.FloatField(default=0.7, verbose_name='温度')
    max_tokens = models.IntegerField(default=4096, verbose_name='最大token数')
    is_default = models.BooleanField(default=False, verbose_name='是否为默认配置')
    task_type = models.CharField(max_length=50, choices=TASK_CHOICES, default='other', verbose_name='适用任务类型')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        db_table = 'llm_config'
        verbose_name = 'LLM配置'
        verbose_name_plural = 'LLM配置'
        ordering = ['-updated_at']
        
    def __str__(self):
        return f'{self.name} ({self.provider})'
    
    def set_api_key(self, value):
        self.api_key = encrypt(value)
    
    def get_api_key(self):
        return decrypt(self.api_key)

class UserLLMConfig(models.Model):
    TASK_CHOICES = [
        ('outline', '大纲生成'),
        ('volume', '卷结构生成'),
        ('chapter', '章节概要生成'),
        ('content', '章节内容生成'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_llm_configs', verbose_name='用户')
    task_type = models.CharField(max_length=50, choices=TASK_CHOICES, verbose_name='任务类型')
    llm_config = models.ForeignKey(LLMConfig, on_delete=models.CASCADE, related_name='task_usages', verbose_name='LLM配置')
    temperature = models.FloatField(null=True, blank=True, verbose_name='温度')
    max_tokens = models.IntegerField(null=True, blank=True, verbose_name='最大token数')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'user_llm_config'
        verbose_name = '用户任务LLM配置'
        verbose_name_plural = '用户任务LLM配置'
        unique_together = ['user', 'task_type']
        
    def __str__(self):
        return f'{self.user.username} - {self.task_type}'
    
    def get_effective_temperature(self):
        return self.temperature if self.temperature is not None else self.llm_config.temperature
    
    def get_effective_max_tokens(self):
        return self.max_tokens if self.max_tokens is not None else self.llm_config.max_tokens

class TokenUsageLog(models.Model):
    TASK_CHOICES = [
        ('outline', '大纲生成'),
        ('volume', '卷结构生成'),
        ('chapter', '章节概要生成'),
        ('content', '章节内容生成'),
        ('other', '其他任务'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='token_usage_logs', verbose_name='用户', null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='token_usage_logs', verbose_name='项目', null=True, blank=True)
    task_type = models.CharField(max_length=50, choices=TASK_CHOICES, verbose_name='任务类型')
    llm_config = models.ForeignKey(LLMConfig, on_delete=models.SET_NULL, related_name='usage_logs', verbose_name='LLM配置', null=True, blank=True)
    prompt_tokens = models.IntegerField(default=0, verbose_name='输入token数')
    completion_tokens = models.IntegerField(default=0, verbose_name='输出token数')
    total_tokens = models.IntegerField(default=0, verbose_name='总token数')
    cache_hit = models.BooleanField(default=False, verbose_name='是否命中缓存')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        db_table = 'token_usage_log'
        verbose_name = 'Token使用日志'
        verbose_name_plural = 'Token使用日志'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.user.username if self.user else "匿名"} - {self.task_type} - {self.total_tokens} tokens'
    
    @classmethod
    def get_daily_usage(cls, user, date=None):
        from django.utils import timezone
        if date is None:
            date = timezone.now().date()
        
        start_date = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.min.time()))
        end_date = timezone.make_aware(timezone.datetime.combine(date, timezone.datetime.max.time()))
        
        logs = cls.objects.filter(user=user, created_at__range=(start_date, end_date))
        
        prompt_tokens = logs.aggregate(total=models.Sum('prompt_tokens'))['total'] or 0
        completion_tokens = logs.aggregate(total=models.Sum('completion_tokens'))['total'] or 0
        total_tokens = logs.aggregate(total=models.Sum('total_tokens'))['total'] or 0
        cache_hits = logs.filter(cache_hit=True).count()
        cache_misses = logs.filter(cache_hit=False).count()
        
        return {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
            'cache_hits': cache_hits,
            'cache_misses': cache_misses,
        }
