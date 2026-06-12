"""
LLM 场景配置
定义不同任务场景的默认配置
"""

LLM_SCENES = {
    "worldview_build": {
        "name": "构建世界观",
        "default_temperature": 0.8,
        "default_max_tokens": 4000,
    },
    "worldview_deepen": {
        "name": "世界观深化",
        "default_temperature": 0.75,
        "default_max_tokens": 2500,
    },
    "worldview_consistency": {
        "name": "一致性检查",
        "default_temperature": 0.3,
        "default_max_tokens": 1500,
    },
    "character_design": {
        "name": "角色设计",
        "default_temperature": 0.75,
        "default_max_tokens": 2000,
    },
    "location_design": {
        "name": "地点设计",
        "default_temperature": 0.7,
        "default_max_tokens": 1500,
    },
    "faction_design": {
        "name": "阵营设计",
        "default_temperature": 0.7,
        "default_max_tokens": 1500,
    },
    "outline_optimize": {
        "name": "大纲优化",
        "default_temperature": 0.3,
        "default_max_tokens": 50000,
    },
    "volume_generate": {
        "name": "卷生成",
        "default_temperature": 0.7,
        "default_max_tokens": 100000,
    },
    "volume_optimize": {
        "name": "卷优化",
        "default_temperature": 0.7,
        "default_max_tokens": 30000,
    },
    "volume_chat": {
        "name": "卷对话",
        "default_temperature": 0.7,
        "default_max_tokens": 10000,
    },
    "chapter_generate": {
        "name": "章节生成",
        "default_temperature": 0.7,
        "default_max_tokens": 100000,
    },
    "content_generate": {
        "name": "内容生成",
        "default_temperature": 0.7,
        "default_max_tokens": 2000,
    },
    "timeline_generate": {
        "name": "时间线生成",
        "default_temperature": 0.5,
        "default_max_tokens": 8000,
    },
    "dialogue_generate": {
        "name": "对话生成",
        "default_temperature": 0.6,
        "default_max_tokens": 1500,
    },
    "default": {
        "name": "默认",
        "default_temperature": 0.7,
        "default_max_tokens": 2000,
    },
}


def get_scene_config(scene: str) -> dict:
    """
    获取场景配置
    
    Args:
        scene: 场景标识
    
    Returns:
        dict: 场景配置字典
    """
    return LLM_SCENES.get(scene, LLM_SCENES["default"])
