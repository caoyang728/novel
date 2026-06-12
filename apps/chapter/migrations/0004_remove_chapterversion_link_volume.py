from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('chapter', '0003_alter_chapterlist_status'),
        ('volume', '0001_initial'),
    ]

    operations = [
        # 1. 添加 volume FK（先允许为空）
        migrations.AddField(
            model_name='chapterlist',
            name='volume',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chapters', to='volume.volumelist', verbose_name='卷'),
        ),

        # 2. 从 chapter_version → volume 迁移数据
        migrations.RunSQL(
            sql="UPDATE chapter_list SET volume_id = (SELECT volume_id FROM chapter_version WHERE chapter_version.id = chapter_list.chapter_version_id)",
            reverse_sql="UPDATE chapter_list SET chapter_version_id = (SELECT id FROM chapter_version WHERE chapter_version.volume_id = chapter_list.volume_id LIMIT 1)"
        ),

        # 3. 删除 chapter_version FK
        migrations.RemoveField(
            model_name='chapterlist',
            name='chapter_version',
        ),

        # 4. 使 volume 不再允许为空
        migrations.AlterField(
            model_name='chapterlist',
            name='volume',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chapters', to='volume.volumelist', verbose_name='卷'),
        ),

        # 5. 更新 unique_together
        migrations.AlterUniqueTogether(
            name='chapterlist',
            unique_together={('volume', 'chapter_number')},
        ),

        # 6. 删除 ChapterVersion 模型
        migrations.DeleteModel(
            name='ChapterVersion',
        ),
    ]
