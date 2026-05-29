from rest_framework import serializers
from apps.characters.models import Character


class CharacterListSerializer(serializers.ModelSerializer):
    """角色列表序列化器 - 精简字段"""
    role_type_display = serializers.CharField(source='get_role_type_display', read_only=True)
    
    class Meta:
        model = Character
        fields = ['id', 'name', 'role_type', 'role_type_display', 'faction', 'tagline']


class CharacterDetailSerializer(serializers.ModelSerializer):
    """角色详情序列化器 - 完整字段"""
    role_type_display = serializers.CharField(source='get_role_type_display', read_only=True)
    gender_display = serializers.CharField(source='get_gender_display', read_only=True)
    
    class Meta:
        model = Character
        fields = [
            'id', 'name', 'role_type', 'role_type_display', 
            'gender', 'gender_display', 'appearance', 
            'personality', 'backstory', 'motivation', 
            'tagline', 'faction', 'extra'
        ]


class CharacterCreateSerializer(serializers.ModelSerializer):
    """角色创建序列化器"""
    class Meta:
        model = Character
        fields = [
            'name', 'role_type', 'gender', 'appearance', 
            'personality', 'backstory', 'motivation', 
            'tagline', 'faction', 'extra', 'relationships'
        ]
        extra_kwargs = {
            'role_type': {'default': 'supporting'},
            'gender': {'default': 'unknown'}
        }
    
    relationships = serializers.CharField(required=False, allow_blank=True)
    
    def validate_name(self, value):
        """验证角色名称"""
        value = value.strip()
        if not value:
            raise serializers.ValidationError('角色名称不能为空')
        
        project = self.context.get('project')
        if project:
            if Character.objects.filter(project=project, name=value, is_deleted=False).exists():
                raise serializers.ValidationError('该角色名称已存在')
        
        return value


class CharacterUpdateSerializer(serializers.ModelSerializer):
    """角色更新序列化器"""
    class Meta:
        model = Character
        fields = [
            'name', 'role_type', 'gender', 'appearance', 
            'personality', 'backstory', 'motivation', 
            'tagline', 'faction', 'extra'
        ]
        extra_kwargs = {
            'name': {'required': True}
        }
    
    def validate_name(self, value):
        """验证角色名称"""
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
                raise serializers.ValidationError('该角色名称已存在')
        
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
    relationships = serializers.CharField(required=False, allow_blank=True, default='')
    abilities = serializers.CharField(required=False, allow_blank=True, default='')
    taboos = serializers.CharField(required=False, allow_blank=True, default='')
    dark_history = serializers.CharField(required=False, allow_blank=True, default='')
    secrets = serializers.CharField(required=False, allow_blank=True, default='')
    backstory = serializers.CharField(required=False, allow_blank=True, default='')
    development = serializers.CharField(required=False, allow_blank=True, default='')
    weaknesses = serializers.CharField(required=False, allow_blank=True, default='')
    tags = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('角色名称不能为空')
        return value
