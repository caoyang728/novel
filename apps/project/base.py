"""
项目级基础视图类 - 所有 API 视图的公共基类
提供：鉴权、参数获取、项目查询、SSE工具、LLM chunk 解析、项目上下文
"""
import json
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.project.models import ProjectList
from novel_agent.authentication import JWTAuthentication


class BaseAPIView(APIView):
    """项目级API基础类 - 封装鉴权、项目查询和通用工具方法"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # ---------- 参数获取 ----------

    def _get_param(self, request, key):
        """统一从 request.data 获取参数"""
        if hasattr(request, 'data') and isinstance(request.data, dict):
            return request.data.get(key)
        return None

    # ---------- 项目查询 ----------

    def get_project(self, request, pk=None):
        """获取项目，支持 pk 或 project_id 参数，不存在则返回404或错误响应"""
        project_id = pk or self._get_param(request, 'project_id')
        if not project_id:
            return None, JsonResponse({'success': False, 'message': '缺少project_id'}, status=400)
        try:
            project = ProjectList.objects.get(pk=project_id, user=request.user)
            return project, None
        except ProjectList.DoesNotExist:
            return None, JsonResponse({'success': False, 'message': '项目不存在'}, status=404)

    def get_project_or_404(self, request, pk):
        """获取项目，不存在直接抛404（用于URL路径参数场景）"""
        return get_object_or_404(ProjectList, pk=pk, user=request.user)

    # ---------- 项目上下文 ----------

    def get_worldview_context(self, project):
        """获取项目世界观上下文"""
        from utils.helpers import format_worldview_context
        return format_worldview_context(project)

    def get_characters_context(self, project):
        """获取项目人物上下文"""
        from utils.helpers import format_characters_context
        return format_characters_context(project)

    def get_timeline_context(self, project):
        """获取项目时间线上下文"""
        from utils.helpers import format_timeline_context
        return format_timeline_context(project)

    def get_project_context(self, project):
        """获取项目的世界观、人物、时间线上下文（组合方法，按需使用）"""
        return (
            self.get_worldview_context(project),
            self.get_characters_context(project),
            self.get_timeline_context(project),
        )

    def get_knowledge_context(self, project, include=None, exclude=None, query_text=None):
        """
        从知识库（Milvus/降级DB）检索项目上下文
        返回合并为文本的上下文，适用于注入 LLM prompt
        """
        try:
            from apps.knowledge.retriever import KnowledgeRetriever
            retriever = KnowledgeRetriever()
            raw = retriever.retrieve(
                project_id=str(project.pk),
                include=include,
                exclude=exclude,
                query_text=query_text,
            )
            return self._format_knowledge_result(raw)
        except Exception as e:
            from loguru import logger
            logger.warning(f"知识库检索失败, 降级到传统格式化: {e}")
            return (
                self.get_worldview_context(project),
                self.get_characters_context(project),
            )

    @staticmethod
    def _format_knowledge_result(raw):
        """将知识库检索结果格式化为 (worldview_text, characters_text) 元组"""
        parts = []

        # 世界观
        worldview_parts = []
        for item in raw.get("worldview", []):
            worldview_parts.append(item.get("content", ""))
        worldview_text = "\n".join(worldview_parts) if worldview_parts else "（暂无世界观设定）"

        # 角色
        character_parts = []
        for item in raw.get("character", []):
            character_parts.append(item.get("content", ""))
        characters_text = "\n".join(character_parts) if character_parts else "（暂无人物设定）"

        # 大纲
        for item in raw.get("outline", []):
            parts.append(f"【大纲】\n{item.get('content', '')}")

        # 卷大纲
        for item in raw.get("volume", []):
            meta = item.get("metadata", {})
            vol_num = meta.get("volume_number", "")
            vol_title = meta.get("volume_title", "")
            header = f"【卷{vol_num}：{vol_title}】"
            parts.append(f"{header}\n{item.get('content', '')}")

        # 章节
        for item in raw.get("chapter", []):
            meta = item.get("metadata", {})
            ch_num = meta.get("chapter_number", "")
            ch_title = meta.get("chapter_title", "")
            header = f"【第{ch_num}章 {ch_title}】"
            parts.append(f"{header}\n{item.get('content', '')}")

        extra_context = "\n\n".join(parts) if parts else ""

        return worldview_text, characters_text, extra_context

    def get_knowledge_context_for_chapter(self, project, chapter, include=None, exclude=None):
        """
        章节生成专用：从知识库检索上下文
        返回 (worldview_text, characters_text, extra_context) 三元组
        extra_context 包含大纲、卷大纲、相关章节段落
        """
        query_text = chapter.summary or chapter.title or ""
        return self.get_knowledge_context(
            project=project,
            include=include,
            exclude=exclude,
            query_text=query_text,
        )

    # ---------- SSE 工具 ----------

    @staticmethod
    def sse_event(event_type, data=None, **kwargs):
        """格式化 SSE 事件"""
        payload = {'type': event_type}
        if data:
            payload.update(data)
        payload.update(kwargs)
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @staticmethod
    def sse_response(generator_func):
        """创建 SSE StreamingHttpResponse"""
        response = StreamingHttpResponse(generator_func(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    # ---------- Token 统计 ----------

    @staticmethod
    def log_token_usage(task_type, result=None, input_tokens=0, output_tokens=0, user=None, project=None, usage_result=None, llm_config=None):
        """记录Token使用量

        3种调用模式：
        1. 流式模式：传入 result（last_chunk）和 usage_result（含 usage_metadata 的 chunk）
           self.log_token_usage('worldview_foundation', result=last_chunk, usage_result=usage_chunk, user=request.user, project=project)
        2. 非流式模式：传入 result（含 usage_metadata 的 AIMessage）
           self.log_token_usage('worldview_deepen', result=result, user=request.user, project=project)
        3. 手动模式：仅传入 input_tokens/output_tokens（cache 字段为 null，前端标记为"预估"）
           self.log_token_usage('worldview_generate', input_tokens=100, output_tokens=200, user=request.user, project=project)
        """
        from agent.llm import log_token_usage as _log_token_usage
        _log_token_usage(task_type, result=result, input_tokens=input_tokens,
                         output_tokens=output_tokens, user=user, project=project, usage_result=usage_result, llm_config=llm_config)

    # ---------- LLM 工具 ----------

    @staticmethod
    def get_chunk_text(chunk):
        """从 LangChain 的 stream chunk 中提取纯文本内容"""
        if hasattr(chunk, 'content'):
            content = chunk.content
            if isinstance(content, list):
                return ''.join(block.get('text', str(block)) if isinstance(block, dict) else str(block) for block in content)
            elif isinstance(content, str):
                return content
            else:
                return str(content)
        return str(chunk)
