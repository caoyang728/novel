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
