# -*- coding: utf-8 -*-
"""
世界观模块清理迁移

合并 WorldviewDocVersion 到 WorldView，删除旧版 WorldView（JSON 分层），
重命名表：worldview_doc -> worldview，worldview_doc_chat_history -> worldview_chat_history。
"""
from django.db import migrations, models
from django.db.migrations.operations import SeparateDatabaseAndState
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('worldview', '0006_worldviewdocchathistory_version_and_more'),
    ]

    operations = [
        # ================================================================
        # 1. Django 状态操作（不执行 SQL，仅更新 Django 内部模型注册）
        # ================================================================

        # 1.1 删除 WorldviewDocVersion 模型注册
        SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='WorldviewDocVersion'),
            ],
            database_operations=[],
        ),

        # 1.2 删除旧版 WorldViewChatHistory（来自0001_initial的旧聊天模型）
        SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='WorldViewChatHistory'),
            ],
            database_operations=[],
        ),

        # 1.3 重命名 WorldviewDoc -> WorldView，更新字段定义
        SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameModel(
                    old_name='WorldviewDoc',
                    new_name='WorldView',
                ),
                migrations.AlterModelOptions(
                    name='worldview',
                    options={
                        'db_table': 'worldview',
                        'verbose_name': '世界观文档',
                        'verbose_name_plural': '世界观文档',
                        'ordering': ['-version'],
                    },
                ),
                migrations.AlterField(
                    model_name='worldview',
                    name='project',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='worldviews',
                        to='project.projectlist',
                        verbose_name='所属项目',
                    ),
                ),
                migrations.AddField(
                    model_name='worldview',
                    name='is_finalized',
                    field=models.BooleanField(default=False, verbose_name='是否定稿（锁定）'),
                ),
                migrations.AddField(
                    model_name='worldview',
                    name='last_question',
                    field=models.TextField(blank=True, default='', verbose_name='最后一条 AI 问题'),
                ),
                migrations.AddField(
                    model_name='worldview',
                    name='last_options',
                    field=models.JSONField(blank=True, default=list, verbose_name='最后一条 AI 选项'),
                ),
                migrations.AddConstraint(
                    model_name='worldview',
                    constraint=models.UniqueConstraint(
                        fields=('project', 'version'),
                        name='uq_worldview_project_version',
                    ),
                ),
            ],
            database_operations=[],
        ),

        # 1.4 重命名 WorldviewDocChatHistory -> WorldViewChatHistory
        SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameModel(
                    old_name='WorldviewDocChatHistory',
                    new_name='WorldViewChatHistory',
                ),
                migrations.AlterModelOptions(
                    name='worldviewchathistory',
                    options={
                        'db_table': 'worldview_chat_history',
                        'verbose_name': '世界观聊天历史',
                        'verbose_name_plural': '世界观聊天历史',
                        'ordering': ['created_at'],
                    },
                ),
                migrations.AlterField(
                    model_name='worldviewchathistory',
                    name='worldview',
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='chat_histories',
                        to='worldview.worldview',
                        verbose_name='所属世界观',
                    ),
                ),
                migrations.RemoveField(
                    model_name='worldviewchathistory',
                    name='doc',
                ),
                migrations.RemoveField(
                    model_name='worldviewchathistory',
                    name='version',
                ),
            ],
            database_operations=[],
        ),

        # ================================================================
        # 2. 数据库操作（实际执行 SQL）
        # ================================================================

        # 2.1 删除旧表（worldview 旧 JSON 表 + worldview_chat_history 旧表）
        migrations.RunSQL(
            sql=[
                'DROP TABLE IF EXISTS worldview_chat_history CASCADE;',
                'DROP TABLE IF EXISTS worldview CASCADE;',
            ],
            reverse_sql=[],
        ),

        # 2.2 重命名新表到最终名称
        migrations.RunSQL(
            sql=[
                'ALTER TABLE IF EXISTS worldview_doc RENAME TO worldview;',
                'ALTER TABLE IF EXISTS worldview_doc_chat_history RENAME TO worldview_chat_history;',
            ],
            reverse_sql=[
                'ALTER TABLE IF EXISTS worldview RENAME TO worldview_doc;',
                'ALTER TABLE IF EXISTS worldview_chat_history RENAME TO worldview_doc_chat_history;',
            ],
        ),

        # 2.3 添加新字段和约束
        migrations.RunSQL(
            sql=[
                'ALTER TABLE worldview ADD COLUMN IF NOT EXISTS is_finalized BOOLEAN DEFAULT FALSE;',
                "ALTER TABLE worldview ADD COLUMN IF NOT EXISTS last_question TEXT DEFAULT '';",
                "ALTER TABLE worldview ADD COLUMN IF NOT EXISTS last_options JSONB DEFAULT '[]';",
                'ALTER TABLE worldview DROP CONSTRAINT IF EXISTS worldview_project_id_key;',
                'ALTER TABLE worldview DROP CONSTRAINT IF EXISTS worldview_project_id_08d182e9_uniq;',
                'ALTER TABLE worldview ADD CONSTRAINT fk_worldview_project '
                'FOREIGN KEY (project_id) REFERENCES project_list(id) ON DELETE CASCADE;',
                'ALTER TABLE worldview ADD CONSTRAINT uq_worldview_project_version '
                'UNIQUE (project_id, version);',
            ],
            reverse_sql=[
                'ALTER TABLE worldview DROP CONSTRAINT IF EXISTS uq_worldview_project_version;',
                'ALTER TABLE worldview DROP CONSTRAINT IF EXISTS fk_worldview_project;',
                'ALTER TABLE worldview ADD CONSTRAINT worldview_project_id_key UNIQUE (project_id);',
                'ALTER TABLE worldview DROP COLUMN IF EXISTS is_finalized;',
                'ALTER TABLE worldview DROP COLUMN IF EXISTS last_question;',
                'ALTER TABLE worldview DROP COLUMN IF EXISTS last_options;',
            ],
        ),

        # 2.4 重建聊天历史表的外键
        migrations.RunSQL(
            sql=[
                "ALTER TABLE worldview_chat_history DROP CONSTRAINT IF EXISTS "
                "worldview_chat_history_doc_id_26eb9b17_fk_worldview_doc_id;",
                "ALTER TABLE worldview_chat_history DROP CONSTRAINT IF EXISTS "
                "worldview_chat_history_version_id_08fb1c42_fk_worldview_do_id;",
                "ALTER TABLE worldview_chat_history DROP COLUMN IF EXISTS version_id;",
                # 重命名 doc_id -> worldview_id（与 Django 状态一致）
                "ALTER TABLE worldview_chat_history RENAME COLUMN doc_id TO worldview_id;",
                # 添加指向新 worldview 表的外键
                'ALTER TABLE worldview_chat_history '
                'ADD CONSTRAINT fk_chathistory_worldview '
                'FOREIGN KEY (worldview_id) REFERENCES worldview(id) ON DELETE CASCADE;',
            ],
            reverse_sql=[
                'ALTER TABLE worldview_chat_history DROP CONSTRAINT IF EXISTS fk_chathistory_worldview;',
                'ALTER TABLE worldview_chat_history RENAME COLUMN worldview_id TO doc_id;',
            ],
        ),

        # 2.5 删除版本表
        migrations.RunSQL(
            sql=[
                'DROP TABLE IF EXISTS worldview_doc_version CASCADE;',
            ],
            reverse_sql=[],
        ),
    ]
