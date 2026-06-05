"""将 relationships 字段中的英文关系类型迁移为中文"""

from django.db import migrations
from apps.characters.constants import RELATIONSHIP_EN_TO_CN


def migrate_relationships_to_chinese(apps, schema_editor):
    Character = apps.get_model('characters', 'Character')
    for char in Character.objects.all():
        if not char.relationships or not isinstance(char.relationships, list):
            continue
        changed = False
        for rel in char.relationships:
            if not isinstance(rel, dict):
                continue
            rel_type = rel.get('relationshipType', '')
            if rel_type in RELATIONSHIP_EN_TO_CN:
                rel['relationshipType'] = RELATIONSHIP_EN_TO_CN[rel_type]
                changed = True
        if changed:
            char.save(update_fields=['relationships'])


class Migration(migrations.Migration):

    dependencies = [
        ('characters', '0007_migrate_role_gender_to_chinese'),
    ]

    operations = [
        migrations.RunPython(
            migrate_relationships_to_chinese,
            migrations.RunPython.noop,
        ),
    ]
