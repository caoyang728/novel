# Generated for Markdown-based worldview doc (new version, parallel to legacy WorldView)

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0002_projectlist_min_words_per_chapter'),
        ('worldview', '0002_add_military_technology_structural_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorldviewDoc',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('genre', models.CharField(
                    choices=[('xuanhuan', '玄幻/仙侠'), ('wuxia', '武侠'), ('fantasy', '西方奇幻'),
                             ('scifi', '科幻'), ('history', '历史/架空'), ('urban', '都市'),
                             ('apocalypse', '末世/灾变'), ('general', '通用')],
                    default='general', max_length=20, verbose_name='题材类型')),
                ('title', models.CharField(blank=True, default='', max_length=200, verbose_name='文档标题')),
                ('content', models.TextField(blank=True, default='', verbose_name='世界观内容（Markdown）')),
                ('faction_index', models.JSONField(blank=True, default=list, verbose_name='阵营索引缓存')),
                ('version', models.PositiveIntegerField(default=1, verbose_name='版本号')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('project', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='worldview_doc',
                    to='project.projectlist',
                    verbose_name='所属项目')),
            ],
            options={
                'verbose_name': '世界观文档（Markdown）',
                'verbose_name_plural': '世界观文档（Markdown）',
                'db_table': 'worldview_doc',
            },
        ),
        migrations.CreateModel(
            name='WorldviewDocChatHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    choices=[('user', '用户'), ('assistant', '助手')],
                    max_length=20, verbose_name='角色')),
                ('content', models.TextField(verbose_name='内容')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('doc', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='chat_histories',
                    to='worldview.worldviewdoc',
                    verbose_name='所属世界观文档')),
            ],
            options={
                'verbose_name': '世界观文档聊天历史',
                'verbose_name_plural': '世界观文档聊天历史',
                'db_table': 'worldview_doc_chat_history',
                'ordering': ['created_at'],
            },
        ),
    ]
