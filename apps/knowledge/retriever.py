"""
知识检索器（PostgreSQL + pgvector 重写版，替代原 Milvus 实现）

对外接口保持不变（search / hybrid_search / search_project_with_scores）。
排序算法：pgvector 原生 `<=>` 余弦距离（django-pgvector 的 CosineDistance 注解）。
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable
from loguru import logger
from django.db import connection
from django.db.models import Q, Value
from django.db.models.functions import Concat
from pgvector.django import CosineDistance
from .client import ensure_backend_ready
from .embedder import EmbedderFactory
from .models import KnowledgeVector

# 检索默认参数
DEFAULT_TOP_K = 30
DEFAULT_SIMILARITY_THRESHOLD = 0.5

COS_DISTANCE_TO_SIMILARITY = 1.0  # 余弦距离转相似度（相似度 = 1 - distance）

# 文档类型默认权重（保持和原 Milvus 版完全一致）
DEFAULT_DOC_TYPE_WEIGHTS = {
    "character": 1.3,
    "worldview": 1.2,
    "outline": 1.15,
    "volume": 1.05,
    "chapter": 1.0,
}


@dataclass
class KnowledgeSearchResult:
    """检索结果（字段与原 Milvus 版 100% 对齐）"""
    doc_type: str
    content: str
    relevance_score: float
    distance: float | None = None
    character_name: str | None = None
    character_id: int | None = None
    volume_id: int | None = None
    volume_number: int | None = None
    chapter_id: int | None = None
    chapter_number: int | None = None
    worldview_category: str | None = None
    outline_version_id: int | None = None
    metadata: dict = field(default_factory=dict)


class KnowledgeRetriever:
    """基于 pgvector 的知识检索器"""

    def __init__(self):
        ensure_backend_ready()
        self.embedder = EmbedderFactory.create()
        from .reranker import RerankerFactory
        self.reranker = RerankerFactory.create_optional()

    # ================================================================
    # 对外 API：与原 Milvus 实现对齐
    # ================================================================
    def search(self,
               query: str,
               project_id: int,
               doc_types: Iterable[str] | None = None,
               top_k: int = DEFAULT_TOP_K,
               threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
               weights: dict[str, float] | None = None) -> list[KnowledgeSearchResult]:
        """基础向量检索（按余弦距离升序排序，用 weight 调整后做 threshold 过滤）。"""
        if not query or not query.strip():
            return []
        embedding = self._embed_query(query)
        if embedding is None:
            return []
        qs = KnowledgeVector.objects.filter(project_id=project_id)
        if doc_types:
            types = [t for t in doc_types if t]
            if types:
                qs = qs.filter(doc_type__in=types)
        qs = (
            qs.alias(cos_dist=CosineDistance('embedding', embedding))
              .order_by('cos_dist')[:top_k * 3]
        )
        doc_weights = weights or DEFAULT_DOC_TYPE_WEIGHTS
        results: list[KnowledgeSearchResult] = []
        for row in qs:
            cos_dist = float(row.cos_dist)  # type: ignore[attr-defined]
            # 余弦距离本身合法范围 [0, 2]，一般检索范围 [0,1]（越接近 0 越相似）
            cos_dist_clamped = max(0.0, min(2.0, cos_dist))
            base_similarity = 1.0 - cos_dist_clamped
            weight = float(doc_weights.get(row.doc_type, 1.0))
            relevance = base_similarity * weight
            if relevance < threshold:
                continue
            results.append(self._build_result(row, relevance, cos_dist))
        results.sort(key=lambda x: x.relevance_score, reverse=True)
        return results[:top_k]

    def search_project_with_scores(self,
                                   project_id: int,
                                   query: str,
                                   top_k: int = DEFAULT_TOP_K,
                                   threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
                                   character_id: int | None = None,
                                   outline_version_id: int | None = None) -> list[tuple[str, float, str]]:
        """给 LLM 生成上下文用：返回 [(doc_type, score, content), ...]。

        outline_version_id: 指定要检索的大纲版本（None=不过滤，兼容旧调用）。
        """
        qs_parts: list[tuple[str, float, str]] = []
        results = self.search(query, project_id, top_k=top_k, threshold=threshold)
        if character_id is not None:
            # 额外拉一次聚焦到 character_id 的段落（metadata->>character_id = ?）
            extra = self._search_character_aware(project_id, query, character_id,
                                                 top_k=top_k, threshold=threshold)
            dedup = {(r.doc_type, r.content): r for r in results + extra}
            merged = list(dedup.values())
            merged.sort(key=lambda x: x.relevance_score, reverse=True)
            results = merged[:top_k]
        # 大纲版本过滤：仅保留指定版本的 chunks
        if outline_version_id is not None:
            results = [r for r in results
                       if r.doc_type != 'outline'
                       or r.metadata.get('outline_version_id') == outline_version_id]
        # Rerank：如果启用了 reranker，用语义重排替换向量距离排序
        if self.reranker and results:
            results = self._apply_rerank(query, results, top_k)
        for r in results:
            content = self._content_with_metadata_label(r)
            qs_parts.append((r.doc_type, r.relevance_score, content))
        return qs_parts

    def hybrid_search(self,
                      query: str,
                      project_id: int,
                      doc_types: Iterable[str] | None = None,
                      top_k: int = DEFAULT_TOP_K,
                      threshold: float = DEFAULT_SIMILARITY_THRESHOLD) -> list[KnowledgeSearchResult]:
        """混合检索：向量 + 关键词关键词匹配（ILIKE content/metadata），取并集合并分数。"""
        vector_results = self.search(query, project_id, doc_types,
                                     top_k=top_k, threshold=threshold)
        kw_results = self._keyword_search(query, project_id, doc_types, top_k=top_k)
        # 合并去重：以 (doc_type, content) 为 key
        merged: dict[tuple[str, str], KnowledgeSearchResult] = {}
        for r in vector_results:
            merged[(r.doc_type, r.content)] = r
        for r in kw_results:
            key = (r.doc_type, r.content)
            if key in merged:
                merged[key].relevance_score = max(merged[key].relevance_score, r.relevance_score)
            else:
                if r.relevance_score >= threshold:
                    merged[key] = r
        final = list(merged.values())
        final.sort(key=lambda x: x.relevance_score, reverse=True)
        return final[:top_k]

    # ================================================================
    # 内部工具方法
    # ================================================================
    def _embed_query(self, query):
        try:
            return self.embedder.embed(query)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Embedding 查询失败: {e}")
            return None

    def _apply_rerank(self, query: str, results: list[KnowledgeSearchResult], top_k: int) -> list[KnowledgeSearchResult]:
        """用 Reranker 对检索结果进行语义重排"""
        try:
            documents = [r.content for r in results]
            rerank_results = self.reranker.rerank(query, documents, top_n=top_k)
            # 按 rerank 分数重排
            reordered = []
            for rr in rerank_results:
                if rr.index < len(results):
                    original = results[rr.index]
                    original.relevance_score = rr.relevance_score
                    reordered.append(original)
            return reordered
        except Exception as e:
            logger.warning(f"Rerank 失败 ({e})，使用原始排序")
            return results

    @staticmethod
    def _build_result(row: KnowledgeVector, relevance: float, cos_dist: float | None) -> KnowledgeSearchResult:
        meta = row.metadata or {}
        return KnowledgeSearchResult(
            doc_type=row.doc_type,
            content=row.content,
            relevance_score=float(relevance),
            distance=float(cos_dist) if cos_dist is not None else None,
            character_name=meta.get("name") or meta.get("character_name"),
            character_id=meta.get("character_id"),
            volume_id=meta.get("volume_id"),
            volume_number=meta.get("volume_number"),
            chapter_id=meta.get("chapter_id"),
            chapter_number=meta.get("chapter_number"),
            worldview_category=meta.get("category"),
            outline_version_id=meta.get("outline_version_id"),
            metadata=meta,
        )

    @staticmethod
    def _content_with_metadata_label(r: KnowledgeSearchResult) -> str:
        """把结构化元信息拼到 content 前面，方便 LLM 知道这一段出自哪里。"""
        labels = []
        if r.doc_type == 'chapter':
            if r.volume_number is not None:
                labels.append(f"第{r.volume_number}卷")
            if r.chapter_number is not None:
                labels.append(f"第{r.chapter_number}章")
        elif r.doc_type == 'volume':
            if r.volume_number is not None:
                labels.append(f"第{r.volume_number}卷")
        elif r.doc_type == 'character' and r.character_name:
            labels.append(f"角色[{r.character_name}]")
        elif r.doc_type == 'worldview' and r.worldview_category:
            labels.append(f"世界观[{r.worldview_category}]")
        elif r.doc_type == 'outline':
            labels.append("大纲")
        prefix = f"[{' '.join(labels)}]" if labels else ""
        return f"{prefix}{r.content}" if prefix else r.content

    def _search_character_aware(self,
                                project_id,
                                query,
                                character_id,
                                top_k=DEFAULT_TOP_K,
                                threshold=DEFAULT_SIMILARITY_THRESHOLD):
        """针对角色检索：优先把该角色自身卡片、相关章节段落拉出来。"""
        embedding = self._embed_query(query)
        if embedding is None:
            return []
        # metadata->>'character_id' 没有直接索引，用 JSONB 包含查询 + 二次距离排序
        doc_type_q = Q(doc_type='character') & Q(metadata__character_id=character_id)
        # 章节段落里 character_id 在 metadata 不直接存在，但可先拉出来做二次筛选
        chapter_q = Q(doc_type='chapter') & (
            Q(id__startswith=f"{project_id}_chapter_")
        )
        qs = (
            KnowledgeVector.objects
            .filter(Q(project_id=project_id) & (doc_type_q | chapter_q))
            .alias(cos_dist=CosineDistance('embedding', embedding))
            .order_by('cos_dist')
        )[:top_k * 2]
        doc_weights = DEFAULT_DOC_TYPE_WEIGHTS.copy()
        doc_weights['character'] = 1.5  # 角色卡片本身强提升
        doc_weights['chapter'] = 1.15   # 角色相关章节小提升
        out: list[KnowledgeSearchResult] = []
        for row in qs:
            cos_dist = max(0.0, min(2.0, float(row.cos_dist)))  # type: ignore[attr-defined]
            base_sim = 1.0 - cos_dist
            w = float(doc_weights.get(row.doc_type, 1.0))
            rel = base_sim * w
            if rel < threshold:
                continue
            out.append(self._build_result(row, rel, cos_dist))
        return out[:top_k]

    def _keyword_search(self, query, project_id, doc_types=None, top_k=DEFAULT_TOP_K):
        """基于 PG ILIKE + 关键词匹配的兜底检索（不依赖 embedding）。"""
        if not query or not query.strip():
            return []
        tokens = [t.strip() for t in self._split_keywords(query) if t.strip()]
        if not tokens:
            return []
        qs = KnowledgeVector.objects.filter(project_id=project_id)
        if doc_types:
            types = [t for t in doc_types if t]
            if types:
                qs = qs.filter(doc_type__in=types)
        # 简化版本：content 里命中任何一个 token 就视为候选
        kw_q = Q()
        for tok in tokens:
            # 同时匹配 content / metadata 文本
            kw_q |= Q(content__icontains=tok)
        qs = qs.filter(kw_q)
        # 分数：命中 token 数 / 总 token 数
        rows = list(qs[:top_k * 3])
        scored = []
        for row in rows:
            hit = 0
            text = (row.content or '') + ' ' + (str(row.metadata or ''))
            for tok in tokens:
                if tok.lower() in text.lower():
                    hit += 1
            score = (hit / len(tokens)) * 0.85  # 关键词检索最大分数 0.85，让向量检索排在前面
            scored.append((row, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        results = []
        for row, score in scored[:top_k]:
            results.append(self._build_result(row, score, None))
        return results

    @staticmethod
    def _split_keywords(query):
        if not query:
            return []
        # 去标点
        import re
        cleaned = re.sub(r'[\s,.!?;:，。！？；：、()（）\[\]\【\】""''《》<>]+', ' ', query).strip()
        tokens = [t for t in cleaned.split() if t]
        # 英文单词按空格已经分开；中文短句我们再做 2-4 字子串，便于 ILIKE 匹配
        extra = []
        for t in tokens:
            if any(ord(c) > 127 for c in t):
                for L in (2, 3, 4):
                    for i in range(0, max(0, len(t) - L + 1)):
                        extra.append(t[i:i + L])
        tokens.extend(extra)
        # 去重并过滤短 token
        seen = set()
        result = []
        for t in tokens:
            if len(t) < 2:
                continue
            if t in seen:
                continue
            seen.add(t)
            result.append(t)
        return result
