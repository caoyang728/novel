"""
Volume 初始迁移 - 直接创建单表 Volume 模型
（已合并旧版 VolumeVersion + VolumeList 的迁移历史）
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('project', '0001_initial'),
        ('outline', '0003_rename_outlineversion_outline_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Volume',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.PositiveIntegerField(default=1, verbose_name='版本号')),
                ('volume_number', models.IntegerField(verbose_name='卷号')),
                ('title', models.CharField(max_length=255, verbose_name='卷标题')),
                ('summary', models.TextField(blank=True, verbose_name='卷摘要')),
                ('content', models.TextField(blank=True, default='', verbose_name='卷大纲')),
                ('chapter_count', models.IntegerField(default=0, verbose_name='预估章节数')),
                ('is_locked', models.BooleanField(default=False, verbose_name='是否锁定（定稿）')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('outline', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='volumes',
                    to='outline.outline',
                    verbose_name='关联大纲',
                )),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='volumes',
                    to='project.projectlist',
                    verbose_name='项目',
                )),
            ],
            options={
                'verbose_name': '卷',
                'verbose_name_plural': '卷',
                'db_table': 'volume',
                'unique_together': {('project', 'version', 'volume_number')},
                'ordering': ['version', 'volume_number'],
            },
        ),
    ]
