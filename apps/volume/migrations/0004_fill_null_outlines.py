from django.db import migrations


def fix_null_outlines(apps, schema_editor):
    """将 outline 为空的 Volume 关联到同项目下最新的大纲版本"""
    Volume = apps.get_model('volume', 'Volume')
    Outline = apps.get_model('outline', 'Outline')

    null_volumes = Volume.objects.filter(outline__isnull=True)
    for vol in null_volumes:
        latest_outline = (
            Outline.objects
            .filter(project=vol.project, is_deleted=False, version__gt=0)
            .order_by('-version')
            .first()
        )
        if latest_outline:
            vol.outline = latest_outline
            vol.save(update_fields=['outline'])


def reverse_fix(apps, schema_editor):
    """回滚：不做任何操作，保留关联关系"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('volume', '0003_alter_volume_outline'),
        ('outline', '0006_remove_outline_is_current_remove_outline_snapshot'),
    ]

    operations = [
        migrations.RunPython(fix_null_outlines, reverse_fix),
    ]
