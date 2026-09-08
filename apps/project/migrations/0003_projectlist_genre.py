# Generated for adding genre field to ProjectList

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0002_projectlist_min_words_per_chapter'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectlist',
            name='genre',
            field=models.CharField(
                choices=[('xuanhuan', '玄幻/仙侠'), ('wuxia', '武侠'), ('fantasy', '西方奇幻'),
                         ('scifi', '科幻'), ('history', '历史/架空'), ('urban', '都市'),
                         ('apocalypse', '末世/灾变'), ('general', '通用')],
                default='general', max_length=20, verbose_name='题材类型'),
        ),
    ]
