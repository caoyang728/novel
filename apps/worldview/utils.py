import json
from django.http import StreamingHttpResponse


def create_stream_response(generator_func):
    response = StreamingHttpResponse(generator_func(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


def make_stream_chunk(content):
    """创建流式响应的单个数据块"""
    return f'data: {json.dumps(content, ensure_ascii=False)}\n\n'


def make_start_message(content='开始生成内容...'):
    """创建开始消息"""
    return make_stream_chunk({'type': 'start', 'content': content})


def make_chunk_message(content):
    """创建数据块消息"""
    return make_stream_chunk({'type': 'chunk', 'content': content})


def make_complete_message(**kwargs):
    """创建完成消息"""
    return make_stream_chunk({'type': 'complete', **kwargs})


def make_error_message(message):
    """创建错误消息"""
    return make_stream_chunk({'type': 'error', 'message': message})


def get_worldview_context(project):
    """
    获取项目的世界观文档上下文，用于 AI 对话时提供背景信息。
    返回最新的世界观文档 Markdown 内容，无则返回 None。
    """
    from .models import WorldView
    doc = WorldView.objects.filter(project=project, is_deleted=False).order_by('-version').first()
    if not doc or not doc.content:
        return None
    return doc.content
