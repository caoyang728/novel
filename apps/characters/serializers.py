from rest_framework import serializers
from apps.characters.models import Character
from apps.characters.constants import normalize_relationship_type


class CharacterListSerializer(serializers.ModelSerializer):
    """角色列表序列化器 - 精简字段"""
    
    class Meta:
        model = Character
        fields = ['id', 'name', 'role_type', 'faction', 'tagline', 'is_deleted']


class CharacterDetailSerializer(serializers.ModelSerializer):
    """角色详情序列化器 - 完整字段"""
    
    class Meta:
        model = Character
        fields = [
            'id', 'name', 'role_type', 
            'gender', 'appearance', 
            'personality', 'backstory', 'motivation', 
            'tagline', 'faction',
            'age', 'identity', 'relationships', 'experiences',
            'development', 'strengths', 'flaws', 'obsession',
            'taboos', 'abilities', 'secrets', 'dark_history',
            'weaknesses'
        ]


COMMON_CHARACTER_FIELDS = [
    'name', 'role_type', 'gender', 'appearance',
    'personality', 'backstory', 'motivation',
    'tagline', 'faction',
    'age', 'identity', 'relationships', 'experiences',
    'development', 'strengths', 'flaws', 'obsession',
    'taboos', 'abilities', 'secrets', 'dark_history',
    'weaknesses'
]


class _BaseCharacterSerializer(serializers.ModelSerializer):
    """角色CUD序列化器基类 - 提取公共字段和验证逻辑"""
    relationships = serializers.JSONField(required=False, default=list)
    experiences = serializers.JSONField(required=False, default=list)

    class Meta:
        model = Character
        fields = COMMON_CHARACTER_FIELDS

    def to_internal_value(self, data):
        """预处理：age 空字符串或非数字值转为 None，避免 IntegerField 校验失败"""
        if isinstance(data, dict) and 'age' in data:
            age_val = data['age']
            if age_val == '' or age_val is None:
                data = data.copy()
                data['age'] = None
            elif not isinstance(age_val, (int, float)):
                # 非数字值（如"青年"）直接转为 None，不报错
                try:
                    int(age_val)
                except (ValueError, TypeError):
                    data = data.copy()
                    data['age'] = None
        return super().to_internal_value(data)

    def validate_relationships(self, value):
        """归一化 relationships 中的 relationshipType，并验证结构"""
        if not isinstance(value, list):
            return value
        for r in value:
            if isinstance(r, dict):
                if not r.get('targetName') or not r.get('targetName', '').strip():
                    raise serializers.ValidationError('关系的对方角色名不能为空')
                r['relationshipType'] = normalize_relationship_type(r.get('relationshipType'))
        return value


class CharacterCreateSerializer(_BaseCharacterSerializer):
    """角色创建序列化器"""
    class Meta(_BaseCharacterSerializer.Meta):
        extra_kwargs = {
            'role_type': {'default': '配角'},
            'gender': {'default': '未知'},
            'age': {'required': False, 'allow_null': True},
            'identity': {'default': ''},
            'development': {'default': ''},
            'strengths': {'default': ''},
            'flaws': {'default': ''},
            'obsession': {'default': ''},
            'taboos': {'default': ''},
            'abilities': {'default': ''},
            'secrets': {'default': ''},
            'dark_history': {'default': ''},
            'weaknesses': {'default': ''},
        }

    def validate_name(self, value):
        """验证角色名称（创建时全项目唯一）"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError('角色名称不能为空')

        project = self.context.get('project')
        if project:
            if Character.objects.filter(project=project, name=value, is_deleted=False).exists():
                raise serializers.ValidationError('DUPLICATE_NAME')

        return value


class CharacterUpdateSerializer(_BaseCharacterSerializer):
    """角色更新序列化器"""
    class Meta(_BaseCharacterSerializer.Meta):
        extra_kwargs = {
            'name': {'required': True}
        }

    def validate_name(self, value):
        """验证角色名称（更新时排除自身）"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError('角色名称不能为空')

        project = self.context.get('project')
        instance = self.instance

        if project and instance:
            if Character.objects.filter(
                project=project,
                name=value,
                is_deleted=False
            ).exclude(pk=instance.pk).exists():
                raise serializers.ValidationError('该角色名称已存在', code='DUPLICATE_NAME')

        return value


class CharacterPolishSerializer(serializers.Serializer):
    """角色润色序列化器 - 校验AI润色请求数据"""
    name = serializers.CharField(required=True, max_length=100)
    gender = serializers.CharField(required=False, allow_blank=True, default='')
    role = serializers.CharField(required=False, allow_blank=True, default='')
    age = serializers.CharField(required=False, allow_blank=True, default='')
    identity = serializers.CharField(required=False, allow_blank=True, default='')
    personality = serializers.CharField(required=False, allow_blank=True, default='')
    strengths = serializers.CharField(required=False, allow_blank=True, default='')
    flaws = serializers.CharField(required=False, allow_blank=True, default='')
    obsession = serializers.CharField(required=False, allow_blank=True, default='')
    motivation = serializers.CharField(required=False, allow_blank=True, default='')
    appearance = serializers.CharField(required=False, allow_blank=True, default='')
    faction = serializers.CharField(required=False, allow_blank=True, default='')
    relationships = serializers.JSONField(required=False, default=list)
    abilities = serializers.CharField(required=False, allow_blank=True, default='')
    taboos = serializers.CharField(required=False, allow_blank=True, default='')
    dark_history = serializers.CharField(required=False, allow_blank=True, default='')
    secrets = serializers.CharField(required=False, allow_blank=True, default='')
    backstory = serializers.CharField(required=False, allow_blank=True, default='')
    development = serializers.CharField(required=False, allow_blank=True, default='')
    weaknesses = serializers.CharField(required=False, allow_blank=True, default='')
    tagline = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('角色名称不能为空')
        return value

    def validate_relationships(self, value):
        """归一化 relationships 中的 relationshipType，并验证结构"""
        if not isinstance(value, list):
            return value
        for r in value:
            if isinstance(r, dict):
                if not r.get('targetName') or not r.get('targetName', '').strip():
                    raise serializers.ValidationError('关系的对方角色名不能为空')
                r['relationshipType'] = normalize_relationship_type(r.get('relationshipType'))
        return value
