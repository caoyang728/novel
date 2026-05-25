from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('characters', '0002_delete_character'),
    ]

    state_operations = [
        migrations.CreateModel(
            name='Character',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='姓名/名称')),
                ('role_type', models.CharField(choices=[('protagonist', '主角'), ('supporting', '配角'), ('antagonist', '反派'), ('minor', '路人'), ('narrator', '旁白/叙述者')], default='supporting', max_length=20, verbose_name='角色类型')),
                ('gender', models.CharField(choices=[('male', '男'), ('female', '女'), ('unknown', '未知')], default='unknown', max_length=10, verbose_name='性别')),
                ('appearance', models.TextField(blank=True, verbose_name='外貌特征')),
                ('personality', models.TextField(blank=True, verbose_name='性格特点')),
                ('backstory', models.TextField(blank=True, verbose_name='背景故事')),
                ('motivation', models.TextField(blank=True, verbose_name='核心动机')),
                ('tagline', models.CharField(blank=True, max_length=255, verbose_name='人物标签/签名')),
                ('faction', models.CharField(blank=True, max_length=255, verbose_name='势力/阵营')),
                ('extra', models.JSONField(blank=True, default=dict, verbose_name='扩展信息')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='characters', to='project.projectlist', verbose_name='所属项目')),
            ],
            options={
                'verbose_name': '人物',
                'verbose_name_plural': '人物',
                'db_table': 'character',
                'ordering': ['role_type', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='character',
            constraint=models.UniqueConstraint(fields=('project', 'name'), name='unique_character_name_per_project'),
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(state_operations=state_operations)
    ]
