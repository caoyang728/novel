from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('volume', '0001_initial'),
        ('outline', '0003_rename_outlineversion_outline_and_more'),
    ]

    operations = [
        # 重命名 VolumeVersion.outline_version → outline
        migrations.RenameField(
            model_name='volumeversion',
            old_name='outline_version',
            new_name='outline',
        ),
        # 更新 FK to 指向新的 outline 表
        migrations.AlterField(
            model_name='volumeversion',
            name='outline',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='volume_versions',
                to='outline.outline',
                verbose_name='关联大纲',
            ),
        ),
    ]
