# Generated for WorldviewDocVersion model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('worldview', '0003_worldviewdoc_worldviewdocchathistory'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorldviewDocVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_number', models.PositiveIntegerField(default=1, verbose_name='版本号')),
                ('content', models.TextField(blank=True, default='', verbose_name='Markdown 内容')),
                ('snapshot', models.TextField(blank=True, default='', verbose_name='内容快照（前 500 字）')),
                ('is_current', models.BooleanField(default=False, verbose_name='是否为当前版本')),
                ('is_finalized', models.BooleanField(default=False, verbose_name='是否定稿（锁定）')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('doc', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='versions', to='worldview.worldviewdoc', verbose_name='所属世界观文档')),
            ],
            options={
                'verbose_name': '世界观文档版本',
                'verbose_name_plural': '世界观文档版本',
                'db_table': 'worldview_doc_version',
                'ordering': ['-version_number'],
            },
        ),
    ]
