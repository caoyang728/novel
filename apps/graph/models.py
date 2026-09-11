from django.db import models


class GraphNode(models.Model):
    """图谱节点"""

    NODE_TYPE_CHOICES = [
        ('character', '角色'),
        ('faction', '势力/阵营'),
        ('location', '地点'),
        ('event', '事件'),
    ]

    project = models.ForeignKey(
        'project.ProjectList',
        on_delete=models.CASCADE,
        related_name='graph_nodes',
        verbose_name='所属项目',
    )
    node_type = models.CharField(max_length=20, choices=NODE_TYPE_CHOICES, verbose_name='节点类型')
    name = models.CharField(max_length=200, verbose_name='节点名称')
    description = models.TextField(blank=True, default='', verbose_name='描述')
    properties = models.JSONField(default=dict, blank=True, verbose_name='扩展属性')

    # 关联源数据（方便回溯到 Character 模型）
    source_id = models.PositiveIntegerField(null=True, blank=True, verbose_name='源记录ID')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'graph_node'
        verbose_name = '图谱节点'
        verbose_name_plural = '图谱节点'
        constraints = [
            models.UniqueConstraint(
                fields=['project', 'node_type', 'name'],
                name='unique_graph_node_per_project',
            )
        ]

    def __str__(self):
        return f"[{self.get_node_type_display()}] {self.name}"


class GraphEdge(models.Model):
    """图谱边（关系）"""

    EDGE_TYPE_CHOICES = [
        ('朋友', '朋友'), ('恋人', '恋人'), ('配偶', '配偶'),
        ('父母', '父母'), ('子女', '子女'), ('兄弟姐妹', '兄弟姐妹'),
        ('师父', '师父'), ('徒弟', '徒弟'), ('敌人', '敌人'),
        ('对手', '对手'), ('导师', '导师'), ('门生', '门生'),
        ('盟友', '盟友'), ('亲属', '亲属'), ('君主', '君主'),
        ('臣子', '臣子'), ('其他', '其他'),
        ('belongs_to', '隶属于'),
        ('occurs_at', '发生于'),
        ('involves', '涉及'),
        ('located_in', '位于'),
        ('present_at', '在场'),
        ('trajectory', '轨迹'),
    ]

    project = models.ForeignKey(
        'project.ProjectList',
        on_delete=models.CASCADE,
        related_name='graph_edges',
        verbose_name='所属项目',
    )
    source = models.ForeignKey(
        GraphNode,
        on_delete=models.CASCADE,
        related_name='outgoing_edges',
        verbose_name='起点节点',
    )
    target = models.ForeignKey(
        GraphNode,
        on_delete=models.CASCADE,
        related_name='incoming_edges',
        verbose_name='终点节点',
    )
    edge_type = models.CharField(max_length=30, choices=EDGE_TYPE_CHOICES, verbose_name='关系类型')
    description = models.TextField(blank=True, default='', verbose_name='关系描述')
    properties = models.JSONField(default=dict, blank=True, verbose_name='扩展属性')
    is_bidirectional = models.BooleanField(default=False, verbose_name='是否双向关系')

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'graph_edge'
        verbose_name = '图谱边'
        verbose_name_plural = '图谱边'
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'target', 'edge_type'],
                name='unique_graph_edge',
            )
        ]

    def __str__(self):
        return f"{self.source.name} --[{self.edge_type}]--> {self.target.name}"
