from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('outline', '0003_rename_outlineversion_outline_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='OutlineExpansion',
        ),
    ]
