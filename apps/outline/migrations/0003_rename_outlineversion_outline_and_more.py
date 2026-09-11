from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('outline', '0002_outlineversion_last_options_and_more'),
        ('project', '0001_initial'),
    ]

    operations = [
        # 重命名模型 OutlineVersion → Outline
        migrations.RenameModel(
            old_name='OutlineVersion',
            new_name='Outline',
        ),
        # 重命名字段 version_number → version
        migrations.RenameField(
            model_name='outline',
            old_name='version_number',
            new_name='version',
        ),
        # 更新 related_name: outline_versions → outlines
        migrations.AlterField(
            model_name='outline',
            name='project',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='outlines',
                to='project.projectlist',
                verbose_name='项目',
            ),
        ),
        # 重命名 OutlineChatHistory.outline_version → outline
        migrations.RenameField(
            model_name='outlinechathistory',
            old_name='outline_version',
            new_name='outline',
        ),
        # 更新 related_name: outline_chat_histories → chat_histories
        migrations.AlterField(
            model_name='outlinechathistory',
            name='outline',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='chat_histories',
                to='outline.outline',
                verbose_name='所属大纲',
            ),
        ),
        # 重命名 OutlineExpansion.outline_version → outline
        migrations.RenameField(
            model_name='outlineexpansion',
            old_name='outline_version',
            new_name='outline',
        ),
    ]
