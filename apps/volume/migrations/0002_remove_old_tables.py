from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('volume', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS volume_volumelist CASCADE;",
            reverse_sql="-- reverse not supported",
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS volume_volumeversion CASCADE;",
            reverse_sql="-- reverse not supported",
        ),
    ]
