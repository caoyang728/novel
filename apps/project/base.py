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
        """统一从 request.data 或 request.POST 获取参数"""
        if hasattr(request, 'data') and isinstance(request.data, dict):
            return request.data.get(key)
        return request.POST.get(key) if hasattr(request, 'POST') else None

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
