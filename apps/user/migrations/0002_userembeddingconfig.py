from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('user', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserEmbeddingConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('embedding_mode', models.CharField(choices=[('api_only', '仅云API'), ('docker_only', '仅Docker'), ('api_first', 'API优先，Docker兜底'), ('docker_first', 'Docker优先，API兜底'), ('disabled', '关闭')], default='api_only', max_length=20, verbose_name='Embedding模式')),
                ('embedding_api_key', models.CharField(blank=True, default='', max_length=500, verbose_name='Embedding API密钥')),
                ('embedding_api_base_url', models.CharField(blank=True, default='', max_length=500, verbose_name='Embedding API地址')),
                ('embedding_api_model', models.CharField(blank=True, default='', max_length=200, verbose_name='Embedding API模型')),
                ('embedding_docker_url', models.CharField(blank=True, default='', max_length=500, verbose_name='Embedding Docker地址')),
                ('embedding_docker_timeout', models.IntegerField(default=30, verbose_name='Embedding Docker超时(秒)')),
                ('rerank_mode', models.CharField(choices=[('api_only', '仅云API'), ('docker_only', '仅Docker'), ('api_first', 'API优先，Docker兜底'), ('docker_first', 'Docker优先，API兜底'), ('disabled', '关闭')], default='disabled', max_length=20, verbose_name='Rerank模式')),
                ('rerank_api_key', models.CharField(blank=True, default='', max_length=500, verbose_name='Rerank API密钥')),
                ('rerank_api_base_url', models.CharField(blank=True, default='', max_length=500, verbose_name='Rerank API地址')),
                ('rerank_api_model', models.CharField(blank=True, default='', max_length=200, verbose_name='Rerank API模型')),
                ('rerank_docker_url', models.CharField(blank=True, default='', max_length=500, verbose_name='Rerank Docker地址')),
                ('rerank_docker_timeout', models.IntegerField(default=30, verbose_name='Rerank Docker超时(秒)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='embedding_config', to=settings.AUTH_USER_MODEL, verbose_name='用户')),
            ],
            options={
                'verbose_name': '用户Embedding配置',
                'verbose_name_plural': '用户Embedding配置',
                'db_table': 'user_embedding_config',
            },
        ),
    ]
