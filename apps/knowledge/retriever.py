"""
知识库检索器

从 Milvus 向量库中检索项目相关上下文:
- 大纲 (outline)
- 世界观 (worldview)
- 角色 (character)
- 卷大纲 (volume)
- 章节段落 (chapter)

支持 include / exclude 过滤, 以及 Milvus 不可用时的降级策略
"""
from loguru import logger
from .client import get_collection, get_collection_available
from .embedder import EmbedderFactory

# 每种 doc_type 的默认 top_k
DEFAULT_TOP_K = {
    "outline": 1,
    "worldview": 3,
    "character": 5,
    "volume": 2,
    "chapter": 10,
}

ALL_DOC_TYPES = list(DEFAULT_TOP_K.keys())


class KnowledgeRetriever:
    """知识库检索器"""

    def __init__(self):
        self.collection = get_collection()
        self.embedder = EmbedderFactory.create()

    def retrieve(
        self,
        project_id,
        include=None,
        exclude=None,
        query_text=None,
        top_k=None,
    ):
        """
        检索项目知识上下文

        参数:
            project_id: 项目 ID
            include:   要返回的 doc_type 列表, None 表示全部
            exclude:   要排除的 doc_type 列表
            query_text: 语义检索的查询文本（如当前章节概述）, 不传则不按语义排序
            top_k:     每种类型的 top_k, 可自定义; 为 None 时使用默认值

        返回:
            {
                "outline": [{"content": "...", "metadata": {...}}, ...],
                "worldview": [...],
                "character": [...],
                "volume": [...],
                "chapter": [...],
            }
        """
        # 确定要检索的 doc_type
        doc_types = self._resolve_doc_types(include, exclude)

        # 尝试从 Milvus 检索
        if self.collection:
            try:
                return self._vector_retrieve(project_id, doc_types, query_text, top_k)
            except Exception as e:
                logger.warning(f"Milvus 检索失败, 降级到数据库查询: {e}")

        # 降级: 全量数据库查询
        logger.info(f"使用降级模式检索项目 {project_id}")
        return self._fallback_retrieve(project_id, doc_types)

    def _resolve_doc_types(self, include, exclude):
        """解析要检索的文档类型"""
        if include:
            # 只返回指定的类型
            return [t for t in include if t in ALL_DOC_TYPES]
        elif exclude:
            return [t for t in ALL_DOC_TYPES if t not in exclude]
        return list(ALL_DOC_TYPES)

    def _get_top_k(self, doc_type, top_k):
        """获取各类型的 top_k"""
        if top_k and doc_type in top_k:
            return top_k[doc_type]
        return DEFAULT_TOP_K.get(doc_type, 5)

    # ==================== 向量检索 ====================

    def _vector_retrieve(self, project_id, doc_types, query_text, top_k):
        """从 Milvus 向量检索"""
        result = {}

        if query_text and query_text.strip():
            # 有查询文本时, 用语义检索
            query_embedding = self.embedder.embed(query_text)
            for doc_type in doc_types:
                k = self._get_top_k(doc_type, top_k)
                docs = self._search_by_type(project_id, doc_type, query_embedding, k)
                result[doc_type] = docs
        else:
            # 无查询文本时, 返回每种类型最新的记录（不按语义排序）
            for doc_type in doc_types:
                k = self._get_top_k(doc_type, top_k)
                docs = self._query_by_type(project_id, doc_type, k)
                result[doc_type] = docs

        # 对 chapter 类型按 chapter_number + paragraph_index 排序
        if "chapter" in result:
            result["chapter"] = sorted(
                result["chapter"],
                key=lambda d: (
                    d.get("metadata", {}).get("chapter_number", 0),
                    d.get("metadata", {}).get("paragraph_index", 0),
                ),
            )

        return result

    def _search_by_type(self, project_id, doc_type, query_embedding, limit):
        """按向量相似度搜索"""
        if not self.collection:
            return []
        try:
            search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
            expr = f'project_id == "{project_id}" && doc_type == "{doc_type}"'
            results = self.collection.search(
                data=[query_embedding],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                expr=expr,
                output_fields=["content", "metadata"],
            )
            docs = []
            for hits in results:
                for hit in hits:
                    docs.append({
                        "content": hit.entity.get("content", ""),
                        "metadata": hit.entity.get("metadata", {}),
                    })
            return docs
        except Exception as e:
            logger.error(f"向量检索失败 (doc_type={doc_type}): {e}")
            return []

    def _query_by_type(self, project_id, doc_type, limit):
        """按类型查询（不按语义排序）"""
        if not self.collection:
            return []
        try:
            expr = f'project_id == "{project_id}" && doc_type == "{doc_type}"'
            results = self.collection.query(
                expr=expr,
                output_fields=["content", "metadata"],
                limit=limit,
            )
            return [
                {"content": r.get("content", ""), "metadata": r.get("metadata", {})}
                for r in results
            ]
        except Exception as e:
            logger.error(f"查询失败 (doc_type={doc_type}): {e}")
            return []

    # ==================== 降级检索（数据库全量查询）====================

    def _fallback_retrieve(self, project_id, doc_types):
        """降级：直接从数据库全量查询"""
        result = {}

        if "outline" in doc_types:
            result["outline"] = self._fallback_outline(project_id)
        if "worldview" in doc_types:
            result["worldview"] = self._fallback_worldview(project_id)
        if "character" in doc_types:
            result["character"] = self._fallback_characters(project_id)
        if "volume" in doc_types:
            result["volume"] = self._fallback_volumes(project_id)
        if "chapter" in doc_types:
            result["chapter"] = self._fallback_chapters(project_id)

        return result

    def _fallback_outline(self, project_id):
        try:
            from apps.outline.models import OutlineVersion
            versions = OutlineVersion.objects.filter(
                project_id=project_id, is_finalized=True, is_deleted=False
            ).order_by('-version_number')
            if versions.exists():
                v = versions.first()
                return [{"content": v.content or "", "metadata": {"version_number": v.version_number}}]
        except Exception as e:
            logger.error(f"降级检索大纲失败: {e}")
        return []

    def _fallback_worldview(self, project_id):
        try:
            from apps.worldview.models import WorldView
            worldview = WorldView.objects.filter(project_id=project_id).first()
            if worldview:
                parts = []
                sections = [
                    ("setting", worldview.setting),
                    ("foundation", worldview.foundation),
                    ("power", worldview.power),
                    ("races", worldview.races),
                    ("society", worldview.society),
                    ("culture", worldview.culture),
                    ("history", worldview.history),
                    ("special", worldview.special),
                ]
                import json
                for category, data in sections:
                    if data:
                        if isinstance(data, dict):
                            text = json.dumps(data, ensure_ascii=False)
                        else:
                            text = str(data)
                        parts.append({"content": text, "metadata": {"category": category}})
                return parts[:3]  # 最多 3 条
        except Exception as e:
            logger.error(f"降级检索世界观失败: {e}")
        return []

    def _fallback_characters(self, project_id):
        try:
            from apps.characters.models import Character
            chars = Character.objects.filter(project_id=project_id, is_deleted=False)
            result = []
            for c in chars:
                parts = [f"姓名: {c.name}"]
                if c.role_type:
                    parts.append(f"角色类型: {c.role_type}")
                if c.personality:
                    parts.append(f"性格: {c.personality}")
                if c.backstory:
                    parts.append(f"背景: {c.backstory}")
                if c.motivation:
                    parts.append(f"动机: {c.motivation}")
                result.append({
                    "content": "\n".join(parts),
                    "metadata": {"character_id": c.pk, "name": c.name, "role_type": c.role_type or ""},
                })
            return result
        except Exception as e:
            logger.error(f"降级检索角色失败: {e}")
        return []

    def _fallback_volumes(self, project_id):
        try:
            from apps.volume.models import VolumeList
            volumes = VolumeList.objects.filter(
                volume_version__project_id=project_id
            ).order_by('volume_number')
            return [
                {
                    "content": v.content or v.summary or "",
                    "metadata": {
                        "volume_id": v.pk,
                        "volume_number": v.volume_number,
                        "volume_title": v.title,
                    },
                }
                for v in volumes
            ]
        except Exception as e:
            logger.error(f"降级检索卷大纲失败: {e}")
        return []

    def _fallback_chapters(self, project_id):
        try:
            from apps.chapter.models import ChapterList
            chapters = ChapterList.objects.filter(
                volume__volume_version__project_id=project_id
            ).order_by('volume__volume_number', 'chapter_number')
            return [
                {
                    "content": ch.content or ch.summary or "",
                    "metadata": {
                        "chapter_id": ch.pk,
                        "chapter_number": ch.chapter_number,
                        "chapter_title": ch.title or "",
                        "volume_id": ch.volume_id,
                        "volume_number": ch.volume.volume_number,
                    },
                }
                for ch in chapters
            ]
        except Exception as e:
            logger.error(f"降级检索章节失败: {e}")
        return []
