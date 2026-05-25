from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0010_alter_character_name_and_more'),
        ('characters', '0003_character'),
    ]

    state_operations = [
        migrations.DeleteModel(name='Character'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]
