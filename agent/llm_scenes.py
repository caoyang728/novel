"""
LLM 场景配置
定义不同任务场景的默认配置
"""

LLM_SCENES = {
    # ==================== 世界观 ====================
    "worldview_build": {
        "name": "世界观构建",
        "group": "worldview",
        "group_name": "世界观",
        "default_temperature": 0.8,
        "default_max_tokens": 50000,
    },
    "worldview_deepen": {
        "name": "世界观深化",
        "group": "worldview",
        "group_name": "世界观",
        "default_temperature": 0.5,
        "default_max_tokens": 12000,
    },
    "worldview_consistency": {
        "name": "世界观一致性检查",
        "group": "worldview",
        "group_name": "世界观",
        "default_temperature": 0.3,
        "default_max_tokens": 12000,
    },
    # ==================== 人物清单 ====================
    "character_design": {
        "name": "角色设计",
        "group": "character",
        "group_name": "人物清单",
        "default_temperature": 0.75,
        "default_max_tokens": 32000,
    },
    "character_polish": {
        "name": "角色润色",
        "group": "character",
        "group_name": "人物清单",
        "default_temperature": 0.5,
        "default_max_tokens": 4000,
    },
    "character_check": {
        "name": "角色校验",
        "group": "character",
        "group_name": "人物清单",
        "default_temperature": 0.3,
        "default_max_tokens": 16000,
    },
    # ==================== 时间线 ====================
    "timeline_generate": {
        "name": "时间线生成",
        "group": "timeline",
        "group_name": "时间线",
        "default_temperature": 0.7,
        "default_max_tokens": 32000,
    },
    "timeline_merge": {
        "name": "时间线合并",
        "group": "timeline",
        "group_name": "时间线",
        "default_temperature": 0.3,
        "default_max_tokens": 2000,
    },
    "timeline_check": {
        "name": "时间线检查",
        "group": "timeline",
        "group_name": "时间线",
        "default_temperature": 0.3,
        "default_max_tokens": 8000,
    },
    # ==================== 大纲 ====================
    "outline_optimize": {
        "name": "大纲优化",
        "group": "outline",
        "group_name": "大纲",
        "default_temperature": 0.5,
        "default_max_tokens": 50000,
    },
    # ==================== 卷 ====================
    "volume_batch_generate": {
        "name": "卷批量生成",
        "group": "volume",
        "group_name": "卷",
        "default_temperature": 0.7,
        "default_max_tokens": 64000,
    },
    "volume_single_generate": {
        "name": "单卷生成",
        "group": "volume",
        "group_name": "卷",
        "default_temperature": 0.7,
        "default_max_tokens": 32000,
    },
    "volume_single_optimize": {
        "name": "单卷优化",
        "group": "volume",
        "group_name": "卷",
        "default_temperature": 0.7,
        "default_max_tokens": 16000,
    },
    "volume_chat": {
        "name": "卷对话写作",
        "group": "volume",
        "group_name": "卷",
        "default_temperature": 0.7,
        "default_max_tokens": 10000,
    },
    # ==================== 章节 ====================
    "chapter_batch_generate": {
        "name": "章节批量生成",
        "group": "chapter",
        "group_name": "章节",
        "default_temperature": 0.7,
        "default_max_tokens": 100000,
    },
    "chapter_split": {
        "name": "章节拆分",
        "group": "chapter",
        "group_name": "章节",
        "default_temperature": 0.3,
        "default_max_tokens": 8000,
    },
    "chapter_optimize": {
        "name": "章节优化",
        "group": "chapter",
        "group_name": "章节",
        "default_temperature": 0.5,
        "default_max_tokens": 16000,
    },
    "chapter_verify": {
        "name": "章节校验",
        "group": "chapter",
        "group_name": "章节",
        "default_temperature": 0.3,
        "default_max_tokens": 8000,
    },
    # ==================== 随手记 ====================
    "note_polish": {
        "name": "随手记润色",
        "group": "note",
        "group_name": "随手记",
        "default_temperature": 0.5,
        "default_max_tokens": 4000,
    },
    # ==================== 默认 ====================
    "default": {
        "name": "默认",
        "group": "default",
        "group_name": "默认",
        "default_temperature": 0.7,
        "default_max_tokens": 4000,
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


def get_scene_choices():
    """获取场景选项列表，用于模型 choices"""
    return [(key, val["name"]) for key, val in LLM_SCENES.items()]


def get_grouped_scenes():
    """获取按分组的场景列表，用于前端展示"""
    groups = {}
    for scene_key, scene_val in LLM_SCENES.items():
        group_key = scene_val.get("group", "default")
        group_name = scene_val.get("group_name", "默认")
        if group_key not in groups:
            groups[group_key] = {
                "name": group_name,
                "scenes": []
            }
        groups[group_key]["scenes"].append({
            "key": scene_key,
            "name": scene_val["name"],
            "default_temperature": scene_val["default_temperature"],
            "default_max_tokens": scene_val["default_max_tokens"],
        })
    return groups
