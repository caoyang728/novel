"""角色关系类型常量和工具函数"""

from loguru import logger

# 关系反向映射（只列出反向不同的条目，查找失败时使用原值）
RELATIONSHIP_REVERSE = {
    '父母': '子女',
    '子女': '父母',
    '师父': '徒弟',
    '徒弟': '师父',
    '导师': '门生',
    '门生': '导师',
    '君主': '臣子',
    '臣子': '君主',
}

# 所有允许的关系类型白名单
VALID_RELATIONSHIP_TYPES = {
    '朋友', '恋人', '配偶', '父母', '子女', '兄弟姐妹',
    '师父', '徒弟', '敌人', '对手', '导师', '门生',
    '盟友', '亲属', '君主', '臣子', '其他'
}

# 英文→中文映射（兼容 LLM 返回英文或数据库旧数据）
RELATIONSHIP_EN_TO_CN = {
    'friend': '朋友', 'lover': '恋人', 'spouse': '配偶',
    'parent': '父母', 'child': '子女', 'sibling': '兄弟姐妹',
    'master': '师父', 'apprentice': '徒弟', 'disciple': '徒弟',
    'enemy': '敌人', 'rival': '对手', 'mentor': '导师',
    'protégé': '门生', 'protege': '门生', 'partner': '盟友',
    'ally': '盟友', 'family': '亲属', 'other': '其他',
}


def get_reverse_type(rel_type):
    """获取反向关系类型，自反关系直接返回原值"""
    return RELATIONSHIP_REVERSE.get(rel_type, rel_type)


def normalize_relationship_type(rel_type):
    """归一化关系类型：英文→中文，不在白名单中的→'其他'"""
    if not rel_type:
        return '其他'
    if rel_type in VALID_RELATIONSHIP_TYPES:
        return rel_type
    cn = RELATIONSHIP_EN_TO_CN.get(rel_type.lower())
    if cn:
        return cn
    logger.warning(f"未知关系类型 '{rel_type}'，归一化为 '其他'")
    return '其他'
