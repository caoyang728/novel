"""
知识库索引器（PostgreSQL + pgvector 重写版，替代原 Milvus 实现）

- 对外接口与原 Milvus 版完全兼容（index_xxx / delete_xxx / rebuild_project）
- 使用 Django ORM + pg_catalog 的 pgvector：
    单条 upsert: create_or_update
    批量 upsert: bulk_create(..., update_conflicts=True, update_fields=['content','embedding','metadata','project_id','doc_type'])
    前缀删除: filter(id__startswith=prefix).delete()
- 长耗时的 embedding 不变（仍用 EmbedderFactory）
"""
import json
import re
from loguru import logger
from django.db import close_old_connections
from .client import ensure_backend_ready
from .models import KnowledgeVector
from .embedder import EmbedderFactory

# Chunk 配置
CHUNK_MAX_TOKENS = 512
CHUNK_OVERLAP_RATIO = 0.1  # 10% overlap
EMBEDDING_API_MAX_TOKENS = 3072


class KnowledgeIndexer:
    """知识库索引器（PG+pgvector 后端）"""

    def __init__(self):
        ensure_backend_ready()
        self.embedder = EmbedderFactory.create()

    # ================================================================
    # 大纲
    # ================================================================
    def index_outline(self, outline_version):
        """索引大纲 — 按段落分块，每块 ≤ 512 token"""
        if not outline_version.content:
            return 0
        chunks = self._chunk_text(outline_version.content)
        if not chunks:
            return 0
        prefix = f"{outline_version.project_id}_outline_{outline_version.pk}"
        count = 0
        for i, chunk_text in enumerate(chunks):
            pk = f"{prefix}_{i}"
            if self._upsert_doc(
                pk=pk,
                project_id=outline_version.project_id,
                doc_type="outline",
                content=chunk_text,
                metadata={
                    "version_number": outline_version.version_number,
                    "outline_version_id": outline_version.pk,
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                },
            ):
                count += 1
        return count

    def delete_outline(self, outline_version):
        return self._delete_by_prefix(f"{outline_version.project_id}_outline_{outline_version.pk}")

    # ================================================================
    # 世界观（按 8 类分条写入）
    # ================================================================
    def index_worldview(self, worldview):
        """索引世界观 — 按 8 类分条，超长字段内部再分块"""
        categories = {
            "setting": self._format_worldview_setting(worldview),
            "foundation": self._format_worldview_section(worldview.foundation),
            "power": self._format_worldview_section(worldview.power),
            "races": self._format_worldview_section(worldview.races),
            "society": self._format_worldview_section(worldview.society),
            "culture": self._format_worldview_section(worldview.culture),
            "history": self._format_worldview_section(worldview.history),
            "special": self._format_worldview_section(worldview.special),
        }
        entries, texts = [], []
        for category, content in categories.items():
            if not content or not content.strip():
                continue
            chunks = self._chunk_text(content) if self._token_count(content) > EMBEDDING_API_MAX_TOKENS else [content]
            for ci, chunk_text in enumerate(chunks):
                pk = f"{worldview.project_id}_worldview_{worldview.pk}_{category}"
                if len(chunks) > 1:
                    pk += f"_{ci}"
                entries.append({
                    "id": pk,
                    "project_id": worldview.project_id,
                    "doc_type": "worldview",
                    "content": chunk_text[:65535],
                    "metadata": {
                        "worldview_id": worldview.pk,
                        "category": category,
                        "chunk_index": ci,
                        "total_chunks": len(chunks),
                    },
                })
                texts.append(chunk_text)
        if not entries:
            return 0
        embeddings = self._embed_batch_safe(texts)
        data = []
        for entry, emb in zip(entries, embeddings):
            if emb is None:
                continue
            entry["embedding"] = emb
            data.append(entry)
        return self._bulk_upsert(data)

    def delete_worldview(self, worldview):
        return self._delete_by_prefix(f"{worldview.project_id}_worldview_{worldview.pk}")

    def _format_worldview_setting(self, worldview):
        setting = worldview.setting or {}
        if not setting:
            return ""
        parts = []
        for key in ("identity", "position", "overview", "conflict"):
            val = setting.get(key, "")
            if isinstance(val, dict):
                val = json.dumps(val, ensure_ascii=False)
            if val:
                parts.append(f"{key}: {val}")
        return "\n".join(parts)

    @staticmethod
    def _format_worldview_section(data):
        if not data:
            return ""
        if isinstance(data, str):
            return data
        if isinstance(data, dict):
            parts = []
            for k, v in data.items():
                if isinstance(v, dict):
                    v = json.dumps(v, ensure_ascii=False)
                if v:
                    parts.append(f"{k}: {v}")
            return "\n".join(parts)
        return str(data)

    # ================================================================
    # 角色
    # ================================================================
    def index_character(self, character):
        if character.is_deleted:
            return self.delete_character(character)
        content = self._format_character(character)
        if not content:
            return 0
        pk = f"{character.project_id}_character_{character.pk}"
        return self._upsert_doc(
            pk=pk,
            project_id=character.project_id,
            doc_type="character",
            content=content,
            metadata={
                "character_id": character.pk,
                "name": character.name,
                "role_type": character.role_type or "",
            },
        )

    def delete_character(self, character):
        return self._delete_by_prefix(f"{character.project_id}_character_{character.pk}")

    def _format_character(self, char):
        """格式化角色为文本"""
        parts = [f"姓名: {char.name}"]
        if char.role_type:
            parts.append(f"角色类型: {char.role_type}")
        if char.gender and char.gender != "未知":
            parts.append(f"性别: {char.gender}")
        if char.age:
            parts.append(f"年龄: {char.age}")
        if char.identity:
            parts.append(f"身份: {char.identity}")
        if char.faction:
            parts.append(f"阵营: {char.faction}")
        for field in ('appearance', 'personality', 'backstory', 'motivation',
                      'tagline', 'abilities', 'development', 'strengths',
                      'flaws', 'obsession', 'taboos', 'secrets', 'dark_history', 'weaknesses'):
            val = getattr(char, field, None)
            if val:
                label = {'appearance': '外貌', 'personality': '性格',
                         'backstory': '背景', 'motivation': '动机',
                         'tagline': '标签', 'abilities': '能力',
                         'development': '成长', 'strengths': '优点',
                         'flaws': '缺点', 'obsession': '执念',
                         'taboos': '禁忌', 'secrets': '秘密',
                         'dark_history': '过往黑历史', 'weaknesses': '弱点'}.get(field, field)
                parts.append(f"{label}: {val}")
        if char.relationships:
            rels = []
            for rel in char.relationships:
                if isinstance(rel, dict):
                    target = rel.get("targetName", "")
                    rel_type = rel.get("relationshipType", "")
                    if target and rel_type:
                        rels.append(f"{target}({rel_type})")
            if rels:
                parts.append(f"关系: {', '.join(rels)}")
        return "\n".join(parts)

    # ==================== 卷大纲 ====================

    def index_volume(self, volume):
        """索引卷大纲"""
        content = volume.content or volume.summary
        if not content:
            return 0
        pk = f"{volume.volume_version.project_id}_volume_{volume.pk}"
        return self._upsert_doc(
            pk=pk,
            project_id=volume.volume_version.project_id,
            doc_type="volume",
            content=content,
            metadata={
                "volume_id": volume.pk,
                "volume_number": volume.volume_number,
                "volume_title": volume.title,
                "chapter_count": volume.chapter_count or 0,
            },
        )

    def delete_volume(self, volume):
        return self._delete_by_prefix(f"{volume.volume_version.project_id}_volume_{volume.pk}")

    # ================================================================
    # 章节（按段落 chunk 拆分）
    # ================================================================
    def index_chapter(self, chapter):
        """按段落拆分章节并索引"""
        # 先删除旧数据
        project_id = chapter.volume.volume_version.project_id
        # 先删旧的段落
        self._delete_by_prefix(f"{project_id}_chapter_{chapter.pk}")

        # 确定要索引的文本: content 优先, 没有则用 summary
        text = chapter.content or chapter.summary
        if not text:
            return 0
        paragraphs = self._chunk_text(text)
        if not paragraphs:
            return 0
        entries = []
        for i, para in enumerate(paragraphs):
            pk = f"{project_id}_chapter_{chapter.pk}_{i}"
            entries.append({
                "id": pk,
                "project_id": project_id,
                "doc_type": "chapter",
                "content": para[:65535],
                "metadata": {
                    "chapter_id": chapter.pk,
                    "chapter_number": chapter.chapter_number,
                    "chapter_title": chapter.title or "",
                    "volume_id": chapter.volume_id,
                    "volume_number": chapter.volume.volume_number,
                    "paragraph_index": i,
                    "total_paragraphs": len(paragraphs),
                },
            })
        embeddings = self._embed_batch_safe(paragraphs)
        data = []
        for entry, emb in zip(entries, embeddings):
            if emb is None:
                continue
            entry["embedding"] = emb
            data.append(entry)
        n = self._bulk_upsert(data)
        logger.debug(f"章节 {chapter.pk} 索引完成: {n} 个段落")
        return n

    def delete_chapter(self, chapter):
        project_id = chapter.volume.volume_version.project_id
        return self._delete_by_prefix(f"{project_id}_chapter_{chapter.pk}")

    # ================================================================
    # Chunk 策略（保持原 Milvus 版完全一致的 token/overlap 算法）
    # ================================================================
    def _chunk_text(self, text):
        if not text or not text.strip():
            return []

        # Step 1: 按空行拆分为段落
        raw_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not raw_paragraphs:
            raw_paragraphs = [text.strip()]

        # Step 2: 进一步拆分超长段落
        segments = []
        for para in raw_paragraphs:
            if self._token_count(para) <= CHUNK_MAX_TOKENS:
                segments.append(para)
            else:
                segments.extend(self._split_long_paragraph(para))
        if not segments:
            return []
        return self._merge_segments(segments)

    @staticmethod
    def _token_count(text):
        """估算文本的 token 数量（中英文混合）"""
        if not text:
            return 0
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("gpt-4o")
            return len(enc.encode(text))
        except Exception:  # noqa: BLE001
            return max(1, len(text) // 2)

    @staticmethod
    def _split_long_paragraph(para):
        """拆分超长段落：先按换行，再按句子边界"""
        # 按换行拆分
        lines = [l.strip() for l in para.split('\n') if l.strip()]
        result = []
        for line in lines:
            if KnowledgeIndexer._token_count(line) <= CHUNK_MAX_TOKENS:
                result.append(line)
            else:
                # 按句子边界拆分（中文。！？英文.!?）
                sentences = re.split(r'(?<=[。！？.!?])\s*', line)
                sentences = [s.strip() for s in sentences if s.strip()]
                result.extend(sentences)
        return result

    @staticmethod
    def _merge_segments(segments):
        overlap_tokens = int(CHUNK_MAX_TOKENS * CHUNK_OVERLAP_RATIO)
        chunks, current_chunk, current_tokens = [], "", 0
        for seg in segments:
            seg_tokens = KnowledgeIndexer._token_count(seg)
            if current_tokens + seg_tokens <= CHUNK_MAX_TOKENS:
                # 可以追加到当前 chunk
                current_chunk = (current_chunk + "\n\n" + seg) if current_chunk else seg
                current_tokens = KnowledgeIndexer._token_count(current_chunk)
            else:
                # 当前 chunk 已满，保存并开始新 chunk
                if current_chunk:
                    chunks.append(current_chunk)

                # 新 chunk 从当前段落开始，加上 overlap
                if chunks and overlap_tokens > 0:
                    # 从上一个 chunk 末尾取 overlap 部分
                    prev_chunk = chunks[-1]
                    overlap_text = KnowledgeIndexer._extract_tail(prev_chunk, overlap_tokens)
                    current_chunk = overlap_text + "\n\n" + seg if overlap_text else seg
                else:
                    current_chunk = seg
                current_tokens = KnowledgeIndexer._token_count(current_chunk)
        if current_chunk:
            chunks.append(current_chunk)
        return chunks

    @staticmethod
    def _extract_tail(text, max_tokens):
        """从文本末尾截取不超过 max_tokens 的部分"""
        if not text:
            return ""
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("gpt-4o")
            tokens = enc.encode(text)
            if len(tokens) <= max_tokens:
                return text
            return enc.decode(tokens[-max_tokens:])
        except Exception:  # noqa: BLE001
            return text[-max_tokens * 2:]

    # ================================================================
    # Embedding 封装
    # ================================================================
    def _embed_safe(self, text):
        """安全获取 embedding, 失败返回 None。超长文本自动截断到 API 限制"""
        try:
            truncated = self._truncate_to_tokens(text, EMBEDDING_API_MAX_TOKENS)
            return self.embedder.embed(truncated)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"获取 embedding 失败: {e}")
            return None

    def _embed_batch_safe(self, texts):
        """安全批量获取 embedding, 失败返回与输入等长的 None 列表。超长文本自动截断"""
        try:
            truncated = [self._truncate_to_tokens(t, EMBEDDING_API_MAX_TOKENS) for t in texts]
            return self.embedder.embed_batch(truncated)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"批量获取 embedding 失败: {e}")
            return [None] * len(texts)

    @staticmethod
    def _truncate_to_tokens(text, max_tokens):
        """将文本截断到指定 token 数以内"""
        if not text:
            return text
        try:
            import tiktoken
            enc = tiktoken.encoding_for_model("gpt-4o")
            tokens = enc.encode(text)
            if len(tokens) <= max_tokens:
                return text
            return enc.decode(tokens[:max_tokens])
        except Exception:  # noqa: BLE001
            max_chars = max_tokens * 2
            return text[:max_chars] if len(text) > max_chars else text

    # ================================================================
    # 写库底层方法
    # ================================================================
    def _upsert_doc(self, pk, project_id, doc_type, content, metadata):
        """单条 upsert"""
        embedding = self._embed_safe(content)
        if embedding is None:
            return 0
        try:
            KnowledgeVector.objects.update_or_create(
                id=pk,
                defaults=dict(
                    project_id=project_id,
                    doc_type=doc_type,
                    content=content[:65535],
                    embedding=embedding,
                    metadata=metadata or {},
                ),
            )
            return 1
        except Exception as e:  # noqa: BLE001
            logger.error(f"KnowledgeVector upsert 失败 id={pk}: {e}")
            return 0

    def _bulk_upsert(self, data):
        """批量 upsert（Django 5.1+ bulk_create(update_conflicts=True) 原生支持）"""
        if not data:
            return 0
        try:
            rows = [KnowledgeVector(**d) for d in data]
            KnowledgeVector.objects.bulk_create(
                rows,
                batch_size=200,
                update_conflicts=True,
                unique_fields=['id'],
                update_fields=['project_id', 'doc_type', 'content', 'embedding', 'metadata', 'updated_at'],
            )
            return len(rows)
        except Exception as e:  # noqa: BLE001
            logger.error(f"KnowledgeVector 批量 upsert 失败: {e}")
            # 降级：逐条 update_or_create 保证成功
            ok = 0
            for d in data:
                try:
                    KnowledgeVector.objects.update_or_create(
                        id=d['id'],
                        defaults={k: v for k, v in d.items() if k != 'id'},
                    )
                    ok += 1
                except Exception as ee:  # noqa: BLE001
                    logger.error(f"降级 upsert 失败 id={d.get('id')}: {ee}")
            return ok

    def _delete_by_prefix(self, prefix):
        """按 id 前缀删（替代 Milvus 的 id like "xxx%"）"""
        if not prefix:
            return 0
        try:
            deleted, _ = KnowledgeVector.objects.filter(id__startswith=prefix).delete()
            return deleted
        except Exception as e:  # noqa: BLE001
            logger.warning(f"按前缀删除向量失败 (prefix={prefix}): {e}")
            return 0

    # ================================================================
    # 全量重建
    # ================================================================
    def rebuild_project(self, project_id):
        close_old_connections()
        logger.info(f"开始重建项目 {project_id} 的知识库索引")

        # 先清除该项目的所有旧向量记录（避免 PK 格式变更后残留孤儿数据）
        deleted, _ = KnowledgeVector.objects.filter(project_id=project_id).delete()
        logger.info(f"  已清除旧记录: {deleted} 条")

        from apps.outline.models import OutlineVersion
        from apps.worldview.models import WorldView
        from apps.characters.models import Character
        from apps.volume.models import VolumeList
        from apps.chapter.models import ChapterList

        count = 0
        versions = OutlineVersion.objects.filter(project_id=project_id, is_finalized=True, is_deleted=False)
        for v in versions:
            count += self.index_outline(v) or 0
        logger.info(f"  大纲已索引: {versions.count()} 条")
        try:
            worldview = WorldView.objects.get(project_id=project_id)
            count += self.index_worldview(worldview) or 0
            logger.info("  世界观已索引")
        except WorldView.DoesNotExist:
            logger.info("  世界观不存在, 跳过")
        characters = Character.objects.filter(project_id=project_id, is_deleted=False)
        for c in characters:
            count += self.index_character(c) or 0
        logger.info(f"  角色已索引: {characters.count()} 条")
        volumes = VolumeList.objects.filter(volume_version__project_id=project_id)
        for v in volumes:
            count += self.index_volume(v) or 0
        logger.info(f"  卷大纲已索引: {volumes.count()} 条")
        chapters = ChapterList.objects.filter(volume__volume_version__project_id=project_id)
        for ch in chapters:
            count += self.index_chapter(ch) or 0
        logger.info(f"  章节已索引: {chapters.count()} 条")
        logger.info(f"项目 {project_id} 知识库重建完成, 共 {count} 条记录")
        return count
