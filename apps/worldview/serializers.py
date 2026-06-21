"""
世界观数据序列化器 — 按 WORLDVIEW_STRUCTURE 逐字段校验，只保留/展示结构内定义的字段。
"""
from rest_framework import serializers


# ==================== setting 层 ====================

class IdentitySerializer(serializers.Serializer):
    world_name = serializers.CharField(allow_blank=True, required=False, default='')
    genre = serializers.CharField(allow_blank=True, required=False, default='')


class PositionSerializer(serializers.Serializer):
    identity = serializers.CharField(allow_blank=True, required=False, default='')
    tone = serializers.CharField(allow_blank=True, required=False, default='')


class SettingSerializer(serializers.Serializer):
    identity = IdentitySerializer(required=False, default=dict)
    position = PositionSerializer(required=False, default=dict)
    overview = serializers.CharField(allow_blank=True, required=False, default='')
    conflict = serializers.CharField(allow_blank=True, required=False, default='')


# ==================== foundation 层 ====================

class GeographySerializer(serializers.Serializer):
    continent_distribution = serializers.CharField(allow_blank=True, required=False, default='')
    special_terrain = serializers.CharField(allow_blank=True, required=False, default='')


class CalendarSerializer(serializers.Serializer):
    era = serializers.CharField(allow_blank=True, required=False, default='')
    days_per_year = serializers.CharField(allow_blank=True, required=False, default='')
    seasons = serializers.CharField(allow_blank=True, required=False, default='')
    festivals = serializers.CharField(allow_blank=True, required=False, default='')


class RulesSerializer(serializers.Serializer):
    natural_laws = serializers.CharField(allow_blank=True, required=False, default='')
    boundaries = serializers.CharField(allow_blank=True, required=False, default='')
    axioms = serializers.ListField(child=serializers.CharField(allow_blank=True), required=False, default=list)


class FoundationSerializer(serializers.Serializer):
    geography = GeographySerializer(required=False, default=dict)
    calendar = CalendarSerializer(required=False, default=dict)
    rules = RulesSerializer(required=False, default=dict)
    balance = serializers.CharField(allow_blank=True, required=False, default='')


# ==================== power 层 ====================

class EnergySerializer(serializers.Serializer):
    types = serializers.CharField(allow_blank=True, required=False, default='')
    distribution = serializers.CharField(allow_blank=True, required=False, default='')
    properties = serializers.CharField(allow_blank=True, required=False, default='')


class MartialSerializer(serializers.Serializer):
    categories = serializers.CharField(allow_blank=True, required=False, default='')
    inheritance = serializers.CharField(allow_blank=True, required=False, default='')


class TreasureSerializer(serializers.Serializer):
    categories = serializers.CharField(allow_blank=True, required=False, default='')
    pills = serializers.CharField(allow_blank=True, required=False, default='')


class BeastSerializer(serializers.Serializer):
    levels = serializers.CharField(allow_blank=True, required=False, default='')
    mythical = serializers.CharField(allow_blank=True, required=False, default='')


class PowerSerializer(serializers.Serializer):
    energy = EnergySerializer(required=False, default=dict)
    level = serializers.CharField(allow_blank=True, required=False, default='')
    martial = MartialSerializer(required=False, default=dict)
    treasure = TreasureSerializer(required=False, default=dict)
    beast = BeastSerializer(required=False, default=dict)


# ==================== races 层 ====================

class TraitSerializer(serializers.Serializer):
    lifespan = serializers.CharField(allow_blank=True, required=False, default='')
    reproduction = serializers.CharField(allow_blank=True, required=False, default='')
    physique = serializers.CharField(allow_blank=True, required=False, default='')


class RacesSerializer(serializers.Serializer):
    category = serializers.CharField(allow_blank=True, required=False, default='')
    value = serializers.CharField(allow_blank=True, required=False, default='')
    trait = TraitSerializer(required=False, default=dict)
    relation = serializers.CharField(allow_blank=True, required=False, default='')


# ==================== society 层 ====================

class CourtSerializer(serializers.Serializer):
    political_system = serializers.CharField(allow_blank=True, required=False, default='')
    bureaucracy = serializers.CharField(allow_blank=True, required=False, default='')


class SectSerializer(serializers.Serializer):
    levels = serializers.CharField(allow_blank=True, required=False, default='')
    relationships = serializers.CharField(allow_blank=True, required=False, default='')


class SocietyMartialSerializer(serializers.Serializer):
    factions = serializers.CharField(allow_blank=True, required=False, default='')
    alliances = serializers.CharField(allow_blank=True, required=False, default='')


class StrataSerializer(serializers.Serializer):
    social_classes = serializers.CharField(allow_blank=True, required=False, default='')
    mobility = serializers.CharField(allow_blank=True, required=False, default='')


class CurrencySerializer(serializers.Serializer):
    types = serializers.CharField(allow_blank=True, required=False, default='')
    rules = serializers.CharField(allow_blank=True, required=False, default='')


class SocietySerializer(serializers.Serializer):
    court = CourtSerializer(required=False, default=dict)
    sect = SectSerializer(required=False, default=dict)
    martial = SocietyMartialSerializer(required=False, default=dict)
    external = serializers.CharField(allow_blank=True, required=False, default='')
    strata = StrataSerializer(required=False, default=dict)
    currency = CurrencySerializer(required=False, default=dict)
    resource = serializers.CharField(allow_blank=True, required=False, default='')


# ==================== culture 层 ====================

class CustomSerializer(serializers.Serializer):
    festivals = serializers.CharField(allow_blank=True, required=False, default='')
    rituals = serializers.CharField(allow_blank=True, required=False, default='')


class LanguageSerializer(serializers.Serializer):
    languages = serializers.CharField(allow_blank=True, required=False, default='')
    writing_system = serializers.CharField(allow_blank=True, required=False, default='')


class DailySerializer(serializers.Serializer):
    clothing = serializers.CharField(allow_blank=True, required=False, default='')
    cuisine = serializers.CharField(allow_blank=True, required=False, default='')
    architecture = serializers.CharField(allow_blank=True, required=False, default='')
    transportation = serializers.CharField(allow_blank=True, required=False, default='')


class ReligionSerializer(serializers.Serializer):
    deities = serializers.CharField(allow_blank=True, required=False, default='')
    organization = serializers.CharField(allow_blank=True, required=False, default='')
    faith_differences = serializers.CharField(allow_blank=True, required=False, default='')


class CultureSerializer(serializers.Serializer):
    custom = CustomSerializer(required=False, default=dict)
    language = LanguageSerializer(required=False, default=dict)
    daily = DailySerializer(required=False, default=dict)
    religion = ReligionSerializer(required=False, default=dict)


# ==================== history 层 ====================

class HistorySerializer(serializers.Serializer):
    ancient = serializers.CharField(allow_blank=True, required=False, default='')
    modern = serializers.CharField(allow_blank=True, required=False, default='')
    crisis = serializers.CharField(allow_blank=True, required=False, default='')
    destiny = serializers.CharField(allow_blank=True, required=False, default='')
    future = serializers.CharField(allow_blank=True, required=False, default='')


# ==================== special 层 ====================

class FateSerializer(serializers.Serializer):
    fortune_rules = serializers.CharField(allow_blank=True, required=False, default='')
    destiny_types = serializers.CharField(allow_blank=True, required=False, default='')


class ReincarnationSerializer(serializers.Serializer):
    soul_rules = serializers.CharField(allow_blank=True, required=False, default='')
    mechanics = serializers.CharField(allow_blank=True, required=False, default='')


class SpecialSerializer(serializers.Serializer):
    taboo = serializers.CharField(allow_blank=True, required=False, default='')
    secret = serializers.CharField(allow_blank=True, required=False, default='')
    fate = FateSerializer(required=False, default=dict)
    reincarnation = ReincarnationSerializer(required=False, default=dict)
    transmigration = serializers.CharField(allow_blank=True, required=False, default='')
    system = serializers.CharField(allow_blank=True, required=False, default='')
    rules = serializers.CharField(allow_blank=True, required=False, default='')


# ==================== 顶层 & 辅助函数 ====================

_LAYER_SERIALIZERS = {
    'setting': SettingSerializer,
    'foundation': FoundationSerializer,
    'power': PowerSerializer,
    'races': RacesSerializer,
    'society': SocietySerializer,
    'culture': CultureSerializer,
    'history': HistorySerializer,
    'special': SpecialSerializer,
}


def clean_worldview_layer(layer_name, data):
    """清洗单个世界观层的数据 — 只保留结构内定义的字段，忽略未知字段"""
    if not data:
        return {}
    serializer_class = _LAYER_SERIALIZERS.get(layer_name)
    if not serializer_class:
        return data
    serializer = serializer_class(data=data or {})
    if serializer.is_valid():
        return dict(serializer.data)  # 用 .data 走 to_representation，确保输出键名正确
    return {}


def clean_worldview_data(worldview_dict):
    """清洗完整的世界观数据（8 层）"""
    cleaned = {}
    for layer_name in _LAYER_SERIALIZERS:
        layer_data = worldview_dict.get(layer_name, {})
        cleaned[layer_name] = clean_worldview_layer(layer_name, layer_data)
    return cleaned


def prepare_worldview_for_llm(worldview):
    """从 worldview 模型实例构建清洗后的 JSON 字符串，供 LLM 使用"""
    import json
    data = {}
    for layer_name in _LAYER_SERIALIZERS:
        raw = getattr(worldview, layer_name, None) or {}
        data[layer_name] = clean_worldview_layer(layer_name, raw)
    return json.dumps(data, ensure_ascii=False)
