"""
ChapterList 初始迁移 - FK 指向 Volume 单表模型
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('volume', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChapterList',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chapter_number', models.IntegerField(verbose_name='章节号')),
                ('title', models.CharField(default='', max_length=255, verbose_name='章节标题')),
                ('summary', models.TextField(blank=True, default='', verbose_name='章节摘要')),
                ('content', models.TextField(blank=True, default='', verbose_name='章节内容')),
                ('status', models.CharField(choices=[('summary', '已生成概述'), ('draft', '草稿'), ('published', '已发布'), ('archived', '已归档'), ('failed', '生成失败')], default='draft', max_length=20, verbose_name='状态')),
                ('state', models.CharField(choices=[('normal', '正常'), ('locked', '已锁定'), ('deleted', '已删除')], default='normal', max_length=20, verbose_name='保护状态')),
                ('word_count', models.IntegerField(default=0, verbose_name='字数')),
                ('published_at', models.DateTimeField(blank=True, null=True, verbose_name='发布时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('volume', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chapter_list', to='volume.volume', verbose_name='卷')),
            ],
            options={
                'verbose_name': '章节',
                'verbose_name_plural': '章节',
                'db_table': 'chapter_list',
                'ordering': ['chapter_number'],
                'unique_together': {('volume', 'chapter_number')},
            },
        ),
    ]
