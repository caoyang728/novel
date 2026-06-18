from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class LLMConfig(models.Model):
    """LLM配置"""
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('azure', 'Azure OpenAI'),
        ('claude', 'Claude'),
        ('deepseek', 'DeepSeek'),
        ('qwen', '通义千问'),
        ('ollama', 'Ollama'),
        ('custom', '自定义'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='llm_configs', verbose_name='用户')
    name = models.CharField(max_length=100, verbose_name='配置名称')
    provider = models.CharField(max_length=100, choices=PROVIDER_CHOICES, default='openai', verbose_name='提供商')
    model_name = models.CharField(max_length=200, verbose_name='模型名称')
    api_key = models.CharField(max_length=500, blank=True, verbose_name='API密钥')
    base_url = models.URLField(blank=True, verbose_name='API地址')
    max_tokens = models.IntegerField(default=2000, verbose_name='最大Token数')
    temperature = models.FloatField(default=0.7, verbose_name='温度参数')
    is_default = models.BooleanField(default=False, verbose_name='是否默认')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    test_passed = models.BooleanField(default=False, verbose_name='测试是否通过')
    input_price = models.FloatField(default=0, verbose_name='输入单价(元/百万Token)')
    output_price = models.FloatField(default=0, verbose_name='输出单价(元/百万Token)')
    cache_hit_price = models.FloatField(default=0, verbose_name='缓存命中单价(元/百万Token)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'llm_config'
        verbose_name = 'LLM配置'
        verbose_name_plural = 'LLM配置'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} - {self.model_name}'

    def set_api_key(self, api_key):
        """安全存储API密钥"""
        from django.conf import settings
        import base64
        encoded = base64.b64encode(api_key.encode()).decode()
        self.api_key = encoded

    def get_api_key(self):
        """获取解密后的API密钥"""
        try:
            from django.conf import settings
            import base64
            return base64.b64decode(self.api_key.encode()).decode()
        except Exception:
            return None


class UserLLMConfig(models.Model):
    """用户LLM配置 - 不同任务使用不同配置"""
    TASK_CHOICES = [
        ('default', '默认'),

        ('worldview_build', '世界观构建'),
        ('worldview_deepen', '世界观深化'),
        ('worldview_consistency', '世界观一致性检查'),
        
        ('character_design', '角色设计'),
        ('character_polish', '角色润色'),
        ('character_check', '角色校验'),
        ('timeline_generate', '时间线生成'),
        ('timeline_merge', '时间线合并'),
        ('timeline_check', '时间线检查'),
        ('outline_optimize', '大纲优化'),

        ('volume_batch_generate', '卷批量生成'),
        ('volume_single_generate', '单卷生成'),
        ('volume_single_optimize', '单卷优化'),
        ('volume_chat', '卷对话写作'),
        
        ('chapter_batch_generate', '章节批量生成'),
        ('chapter_split', '章节拆分'),
        ('chapter_optimize', '章节优化'),
        ('chapter_verify', '章节校验'),
        ('note_polish', '随手记润色'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_llm_configs', verbose_name='用户')
    llm_config = models.ForeignKey(LLMConfig, on_delete=models.CASCADE, related_name='user_configs', verbose_name='LLM配置')
    task_type = models.CharField(max_length=50, choices=TASK_CHOICES, default='default', verbose_name='任务类型')
    max_tokens = models.IntegerField(null=True, blank=True, verbose_name='最大Token数(空=继承场景默认)')
    temperature = models.FloatField(null=True, blank=True, verbose_name='温度参数(空=继承场景默认)')

    class Meta:
        db_table = 'user_llm_config'
        verbose_name = '用户LLM配置'
        verbose_name_plural = '用户LLM配置'
        unique_together = ['user', 'task_type']

    def __str__(self):
        return f'{self.user.username} - {self.task_type}'


class TokenUsageLog(models.Model):
    """Token使用日志"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='token_usage_logs', verbose_name='用户')
    project = models.ForeignKey('project.ProjectList', on_delete=models.CASCADE, related_name='token_usage_logs', verbose_name='项目', null=True, blank=True)
    llm_config = models.ForeignKey(LLMConfig, on_delete=models.SET_NULL, null=True, blank=True, related_name='token_usage_logs', verbose_name='LLM配置')
    model_name = models.CharField(max_length=200, verbose_name='模型名称')
    input_tokens = models.IntegerField(default=0, verbose_name='输入Token数')
    output_tokens = models.IntegerField(default=0, verbose_name='输出Token数')
    total_tokens = models.IntegerField(default=0, verbose_name='总Token数')
    input_cache_hit_tokens = models.IntegerField(default=0, verbose_name='输入缓存命中Token数')
    input_cache_miss_tokens = models.IntegerField(default=0, verbose_name='输入缓存未命中Token数')
    cost = models.DecimalField(max_digits=10, decimal_places=4, default=0, verbose_name='费用')
    task_type = models.CharField(max_length=50, blank=True, verbose_name='任务类型')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')

    class Meta:
        verbose_name = 'Token使用日志'
        verbose_name_plural = 'Token使用日志'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.total_tokens} tokens'

    @classmethod
    def get_daily_usage(cls, user):
        """获取用户今日使用量"""
        from django.utils import timezone
        from datetime import timedelta
        today = timezone.now().date()
        logs = cls.objects.filter(user=user, created_at__date=today)
        return logs.aggregate(
            total_tokens=models.Sum('total_tokens'),
            input_tokens=models.Sum('input_tokens'),
            output_tokens=models.Sum('output_tokens'),
            input_cache_hit_tokens=models.Sum('input_cache_hit_tokens'),
            input_cache_miss_tokens=models.Sum('input_cache_miss_tokens'),
            count=models.Count('id')
        )
