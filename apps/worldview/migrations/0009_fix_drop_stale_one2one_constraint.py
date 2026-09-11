# 修复 0007 迁移遗留的 OneToOneField 唯一约束
# 0007 尝试删除 worldview_project_id_key，但实际约束名是 worldview_doc_project_id_key

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('worldview', '0008_remove_worldview_genre'),
    ]

    operations = [
        migrations.RunSQL(
            sql=[
                "ALTER TABLE worldview DROP CONSTRAINT IF EXISTS worldview_doc_project_id_key;",
                "ALTER TABLE worldview DROP CONSTRAINT IF EXISTS worldview_doc_project_id_08d182e9_uniq;",
            ],
            reverse_sql=[],
        ),
    ]
