"""
知识库索引器

负责将项目相关数据（大纲、世界观、角色、卷大纲、章节段落）写入 Milvus

支持:
- 单条 upsert (signal 触发)
- 按前缀删除 (删除旧数据后重建)
- 全量重建 (management command 调用)
"""
import json
import re
from django.db import close_old_connections
from loguru import logger
from .client import get_client, get_collection_name
from .embedder import EmbedderFactory

# Chunk 配置
CHUNK_MAX_TOKENS = 512
CHUNK_OVERLAP_RATIO = 0.1  # 10% overlap

# Embedding API 输入限制 (智谱 embedding-3: 3072, embedding-2: 512)
EMBEDDING_API_MAX_TOKENS = 3072


class KnowledgeIndexer:
    """知识库索引器"""

    def __init__(self):
        self.client = get_client()
        self.coll_name = get_collection_name()
        self.embedder = EmbedderFactory.create()

    # ==================== 大纲 ====================

    def index_outline(self, outline_version):
        """索引大纲（仅 finalized 的大纲版本）"""
        if not outline_version.content:
            return

        pk = f"{outline_version.project_id}_outline_{outline_version.pk}"
        self._upsert_doc(
            pk=pk,
            project_id=str(outline_version.project_id),
            doc_type="outline",
            content=outline_version.content,
            metadata={
                "version_number": outline_version.version_number,
                "outline_version_id": outline_version.pk,
            },
        )

    def delete_outline(self, outline_version):
        self._delete_by_prefix(f"{outline_version.project_id}_outline_{outline_version.pk}")

    # ==================== 世界观 ====================

    def index_worldview(self, worldview):
        """索引世界观，按 8 大类别分别存储"""
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

        # 收集所有待 embedding 的文本
        entries = []
        texts_to_embed = []
        for category, content in categories.items():
            if not content or not content.strip():
                continue
            pk = f"{worldview.project_id}_worldview_{worldview.pk}_{category}"
            entries.append({
                "id": pk,
                "project_id": str(worldview.project_id),
                "doc_type": "worldview",
                "content": content[:65535],
                "metadata": {"worldview_id": worldview.pk, "category": category},
            })
            texts_to_embed.append(content)

        if entries and self.client:
            embeddings = self._embed_batch_safe(texts_to_embed)
            data = []
            for entry, emb in zip(entries, embeddings):
                if emb is not None:
                    entry["embedding"] = emb
                    data.append(entry)
            if data:
                self.client.upsert(collection_name=self.coll_name, data=data)

    def delete_worldview(self, worldview):
        self._delete_by_prefix(f"{worldview.project_id}_worldview_{worldview.pk}")

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

    def _format_worldview_section(self, data):
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

    # ==================== 角色 ====================

    def index_character(self, character):
        """索引单个角色"""
        if character.is_deleted:
            self.delete_character(character)
            return

        content = self._format_character(character)
        if not content:
            return

        pk = f"{character.project_id}_character_{character.pk}"
        self._upsert_doc(
            pk=pk,
            project_id=str(character.project_id),
            doc_type="character",
            content=content,
            metadata={
                "character_id": character.pk,
                "name": character.name,
                "role_type": character.role_type or "",
            },
        )

    def delete_character(self, character):
        self._delete_by_prefix(f"{character.project_id}_character_{character.pk}")

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
        if char.appearance:
            parts.append(f"外貌: {char.appearance}")
        if char.personality:
            parts.append(f"性格: {char.personality}")
        if char.backstory:
            parts.append(f"背景: {char.backstory}")
        if char.motivation:
            parts.append(f"动机: {char.motivation}")
        if char.tagline:
            parts.append(f"标签: {char.tagline}")
        if char.abilities:
            parts.append(f"能力: {char.abilities}")
        if char.development:
            parts.append(f"成长: {char.development}")
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
            return

        pk = f"{volume.volume_version.project_id}_volume_{volume.pk}"
        self._upsert_doc(
            pk=pk,
            project_id=str(volume.volume_version.project_id),
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
        self._delete_by_prefix(f"{volume.volume_version.project_id}_volume_{volume.pk}")

    # ==================== 章节段落 ====================

    def index_chapter(self, chapter):
        """按段落拆分章节并索引"""
        # 先删除旧数据
        project_id = chapter.volume.volume_version.project_id
        self._delete_by_prefix(f"{project_id}_chapter_{chapter.pk}")

        # 确定要索引的文本: content 优先, 没有则用 summary
        text = chapter.content or chapter.summary
        if not text:
            return

        paragraphs = self._chunk_text(text)
        if not paragraphs:
            return

        entries = []
        for i, para in enumerate(paragraphs):
            pk = f"{project_id}_chapter_{chapter.pk}_{i}"
            entries.append({
                "id": pk,
                "project_id": str(project_id),
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

        if entries and self.client:
            embeddings = self._embed_batch_safe(paragraphs)
            data = []
            for entry, emb in zip(entries, embeddings):
                if emb is not None:
                    entry["embedding"] = emb
                    data.append(entry)
            if data:
                self.client.upsert(collection_name=self.coll_name, data=data)
                logger.debug(f"章节 {chapter.pk} 索引完成: {len(data)} 个段落")

    def delete_chapter(self, chapter):
        project_id = chapter.volume.volume_version.project_id
        self._delete_by_prefix(f"{project_id}_chapter_{chapter.pk}")

    def _chunk_text(self, text):
        """
        语义拆分 + Token 限制 + Overlap 的混合 chunk 策略

        1. 先按空行(段落)拆分 → 语义边界
        2. 长段落按换行/句子边界继续拆分
        3. 合并短片段到 512 token chunk，相邻 chunk 保留 10% overlap
        """
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

        # Step 3: 合并短片段到 chunk，带 overlap
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
        except Exception:
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
        """合并短片段为 chunk，相邻 chunk 保留 10% overlap"""
        if not segments:
            return []

        overlap_tokens = int(CHUNK_MAX_TOKENS * CHUNK_OVERLAP_RATIO)
        chunks = []
        current_chunk = ""
        current_tokens = 0

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
            tail_tokens = tokens[-max_tokens:]
            return enc.decode(tail_tokens)
        except Exception:
            # fallback: 取末尾约 max_tokens * 2 字符
            return text[-max_tokens * 2:]

    # ==================== 通用方法 ====================

    def _embed_safe(self, text):
        """安全获取 embedding, 失败返回 None。超长文本自动截断到 API 限制"""
        try:
            truncated = self._truncate_to_tokens(text, EMBEDDING_API_MAX_TOKENS)
            return self.embedder.embed(truncated)
        except Exception as e:
            logger.warning(f"获取 embedding 失败: {e}")
            return None

    def _embed_batch_safe(self, texts):
        """安全批量获取 embedding, 失败返回与输入等长的 None 列表。超长文本自动截断"""
        try:
            truncated = [self._truncate_to_tokens(t, EMBEDDING_API_MAX_TOKENS) for t in texts]
            return self.embedder.embed_batch(truncated)
        except Exception as e:
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
        except Exception:
            # fallback: 中文约 0.5 token/字，取安全系数
            max_chars = max_tokens * 2
            return text[:max_chars] if len(text) > max_chars else text

    def _upsert_doc(self, pk, project_id, doc_type, content, metadata):
        """上传单条记录到 Milvus"""
        if not self.client:
            return
        embedding = self._embed_safe(content)
        if embedding is None:
            return
        self.client.upsert(collection_name=self.coll_name, data=[{
            "id": pk,
            "project_id": project_id,
            "doc_type": doc_type,
            "content": content[:65535],
            "embedding": embedding,
            "metadata": metadata,
        }])

    def _delete_by_prefix(self, prefix):
        """按 id 前缀删除记录"""
        if not self.client:
            return
        try:
            expr = f'id like "{prefix}%"'
            self.client.delete(collection_name=self.coll_name, filter=expr)
        except Exception as e:
            logger.warning(f"删除向量记录失败 (prefix={prefix}): {e}")

    # ==================== 全量重建 ====================

    def rebuild_project(self, project_id):
        """全量重建某个项目的所有知识索引"""
        from apps.outline.models import OutlineVersion
        from apps.worldview.models import WorldView
        from apps.characters.models import Character
        from apps.volume.models import VolumeList
        from apps.chapter.models import ChapterList

        # 每个项目开始前关闭旧连接，避免 embedding 耗时导致 MySQL 超时断开
        close_old_connections()

        logger.info(f"开始重建项目 {project_id} 的知识库索引")

        count = 0

        # 大纲
        versions = OutlineVersion.objects.filter(project_id=project_id, is_finalized=True, is_deleted=False)
        for v in versions:
            self.index_outline(v)
            count += 1
        logger.info(f"  大纲已索引: {versions.count()} 条")

        # 世界观
        try:
            worldview = WorldView.objects.get(project_id=project_id)
            self.index_worldview(worldview)
            count += 1
            logger.info(f"  世界观已索引")
        except WorldView.DoesNotExist:
            logger.info(f"  世界观不存在, 跳过")

        # 角色
        characters = Character.objects.filter(project_id=project_id, is_deleted=False)
        for c in characters:
            self.index_character(c)
        count += characters.count()
        logger.info(f"  角色已索引: {characters.count()} 条")

        # 卷大纲
        volumes = VolumeList.objects.filter(volume_version__project_id=project_id)
        for v in volumes:
            self.index_volume(v)
        count += volumes.count()
        logger.info(f"  卷大纲已索引: {volumes.count()} 条")

        # 章节
        chapters = ChapterList.objects.filter(volume__volume_version__project_id=project_id)
        for ch in chapters:
            self.index_chapter(ch)
        count += chapters.count()
        logger.info(f"  章节已索引: {chapters.count()} 条")

        logger.info(f"项目 {project_id} 知识库重建完成, 共 {count} 条记录")
        return count
