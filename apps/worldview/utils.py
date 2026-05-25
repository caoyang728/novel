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


def get_core_conflict(worldview):
    """获取世界观的核心冲突"""
    if hasattr(worldview, 'structure') and worldview.structure:
        return worldview.structure.get('profile', {}).get('core_conflict', '未设定')
    return '未设定'