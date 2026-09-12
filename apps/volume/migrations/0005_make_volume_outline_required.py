import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('outline', '0006_remove_outline_is_current_remove_outline_snapshot'),
        ('volume', '0004_fill_null_outlines'),
    ]

    operations = [
        migrations.AlterField(
            model_name='volume',
            name='outline',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='volumes', to='outline.outline', verbose_name='关联大纲'),
        ),
    ]
