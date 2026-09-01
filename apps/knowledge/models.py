"""
知识库向量表（替代原 Milvus collection: novel_knowledge）

- 与业务库同库，project_id 做真实外键（级联清理、性能更好）
- embedding 向量列走 django-pgvector 的 VectorField，底层 PG type = vector(EMBEDDING_DIM)
- metadata 用 JSONB（比 JSON 快 + 支持 GIN 索引）
"""
from django.db import models
from django.conf import settings
from pgvector.django import VectorField, HnswIndex


class KnowledgeVector(models.Model):
    """单条知识向量记录（与原 Milvus 文档一一对应，主键 id 格式保持兼容）"""

    DOC_TYPE_CHOICES = [
        ('outline', '大纲版本'),
        ('worldview', '世界观分区'),
        ('character', '角色'),
        ('volume', '卷大纲'),
        ('chapter', '章节段落'),
    ]

    # 与旧 Milvus id 格式保持一致："{project_id}_{doc_type}_{pk_or_category}[_suffix]"
    # 例如："42_outline_7" / "42_worldview_99_setting" / "42_chapter_5012_3"
    id = models.CharField(max_length=256, primary_key=True, verbose_name='向量记录ID')

    # 真实外键：删项目时 ON DELETE CASCADE 自动清理该项目所有向量
    project = models.ForeignKey(
        'project.ProjectList',
        on_delete=models.CASCADE,
        related_name='knowledge_vectors',
        db_index=True,
        verbose_name='所属项目',
    )

    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES, db_index=True, verbose_name='文档类型')
    content = models.TextField(verbose_name='原始文本内容')
    metadata = models.JSONField(default=dict, blank=True, verbose_name='扩展元数据(JSONB)')

    # 向量列。维度是 DB schema 常量（pgvector HNSW ≤2000），与 settings 默认的 EMBEDDING_DIM=1024 一致。
    # 如果你想改 embedding 维度：先改下面字面量，再运行 makemigrations 生成 ALTER 迁移，再重新全量 encode knowledge_vector。
    embedding = VectorField(
        dimensions=1024,
        verbose_name='embedding向量',
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    class Meta:
        db_table = 'knowledge_vector'
        verbose_name = '知识库向量记录'
        verbose_name_plural = verbose_name
        indexes = [
            # 等价原 Milvus filter="project_id == X && doc_type == Y" 的下推优化
            models.Index(fields=['project_id', 'doc_type'], name='idx_kv_project_doc'),
            # HNSW 近似最近邻（COSINE 距离），对应原 Milvus metric_type=COSINE
            HnswIndex(
                name='idx_kv_embedding_hnsw',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            ),
        ]

    def __str__(self):
        return f"{self.project_id} / {self.doc_type} / {self.id[-32:]}"
