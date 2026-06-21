"""Rename society.class → society.strata in existing WorldView records."""

from django.db import migrations


def rename_class_to_strata(apps, schema_editor):
    WorldView = apps.get_model('worldview', 'WorldView')
    for wv in WorldView.objects.iterator():
        if wv.society and 'class' in wv.society:
            wv.society['strata'] = wv.society.pop('class')
            wv.save(update_fields=['society'])


def reverse_rename(apps, schema_editor):
    WorldView = apps.get_model('worldview', 'WorldView')
    for wv in WorldView.objects.iterator():
        if wv.society and 'strata' in wv.society:
            wv.society['class'] = wv.society.pop('strata')
            wv.save(update_fields=['society'])


class Migration(migrations.Migration):

    dependencies = [
        ('worldview', '0005_alter_worldview_project'),
    ]

    operations = [
        migrations.RunPython(rename_class_to_strata, reverse_rename),
    ]
