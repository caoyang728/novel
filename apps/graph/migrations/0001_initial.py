from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('project', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='GraphNode',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('node_type', models.CharField(choices=[('character', '角色'), ('faction', '势力/阵营')], max_length=20, verbose_name='节点类型')),
                ('name', models.CharField(max_length=200, verbose_name='节点名称')),
                ('description', models.TextField(blank=True, default='', verbose_name='描述')),
                ('properties', models.JSONField(blank=True, default=dict, verbose_name='扩展属性')),
                ('source_id', models.PositiveIntegerField(blank=True, null=True, verbose_name='源记录ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='graph_nodes', to='project.projectlist', verbose_name='所属项目')),
            ],
            options={
                'verbose_name': '图谱节点',
                'verbose_name_plural': '图谱节点',
                'db_table': 'graph_node',
            },
        ),
        migrations.CreateModel(
            name='GraphEdge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('edge_type', models.CharField(choices=[('朋友', '朋友'), ('恋人', '恋人'), ('配偶', '配偶'), ('父母', '父母'), ('子女', '子女'), ('兄弟姐妹', '兄弟姐妹'), ('师父', '师父'), ('徒弟', '徒弟'), ('敌人', '敌人'), ('对手', '对手'), ('导师', '导师'), ('门生', '门生'), ('盟友', '盟友'), ('亲属', '亲属'), ('君主', '君主'), ('臣子', '臣子'), ('其他', '其他'), ('belongs_to', '隶属于')], max_length=30, verbose_name='关系类型')),
                ('description', models.TextField(blank=True, default='', verbose_name='关系描述')),
                ('properties', models.JSONField(blank=True, default=dict, verbose_name='扩展属性')),
                ('is_bidirectional', models.BooleanField(default=False, verbose_name='是否双向关系')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='graph_edges', to='project.projectlist', verbose_name='所属项目')),
                ('source', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='outgoing_edges', to='graph.graphnode', verbose_name='起点节点')),
                ('target', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='incoming_edges', to='graph.graphnode', verbose_name='终点节点')),
            ],
            options={
                'verbose_name': '图谱边',
                'verbose_name_plural': '图谱边',
                'db_table': 'graph_edge',
            },
        ),
        migrations.AddConstraint(
            model_name='graphnode',
            constraint=models.UniqueConstraint(fields=('project', 'node_type', 'name'), name='unique_graph_node_per_project'),
        ),
        migrations.AddConstraint(
            model_name='graphedge',
            constraint=models.UniqueConstraint(fields=('source', 'target', 'edge_type'), name='unique_graph_edge'),
        ),
    ]
