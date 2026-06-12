import json
from django.http import StreamingHttpResponse
from .models import WorldView

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
    """获取项目的世界观数据作为上下文，返回 (worldview, setting_text, history_text, foundation_text, worldview_summary)"""
    worldview = WorldView.objects.filter(project=project).first()
    if not worldview:
        return {}, '', '', '', ''

    setting_text = json.dumps(worldview.setting, ensure_ascii=False, indent=2) if worldview.setting else ''
    history_text = json.dumps(worldview.history, ensure_ascii=False, indent=2) if worldview.history else ''
    foundation_text = json.dumps(worldview.foundation, ensure_ascii=False, indent=2) if worldview.foundation else ''
    society_text = json.dumps(worldview.society, ensure_ascii=False, indent=2) if worldview.society else ''
    culture_text = json.dumps(worldview.culture, ensure_ascii=False, indent=2) if worldview.culture else ''
    power_text = json.dumps(worldview.power, ensure_ascii=False, indent=2) if worldview.power else ''
    races_text = json.dumps(worldview.races, ensure_ascii=False, indent=2) if worldview.races else ''
    special_text = json.dumps(worldview.special, ensure_ascii=False, indent=2) if worldview.special else ''

    worldview_summary = f"""
基础设定：{setting_text}
世界历史：{history_text}
世界基础：{foundation_text}
社会结构：{society_text}
文化人文：{culture_text}
力量体系：{power_text}
种族族群：{races_text}
特殊规则：{special_text}
"""
    return worldview, setting_text, history_text, foundation_text, worldview_summary


def get_core_conflict(worldview):
    """获取世界观的核心冲突"""
    if hasattr(worldview, 'structure') and worldview.structure:
        return worldview.structure.get('profile', {}).get('core_conflict', '未设定')
    return '未设定'