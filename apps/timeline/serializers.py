from rest_framework import serializers
from .models import TimelineEvent


class TimelineEventSerializer(serializers.ModelSerializer):
    """时间线事件序列化器"""
    time_range = serializers.CharField(read_only=True)

    class Meta:
        model = TimelineEvent
        fields = [
            'id', 'title', 'description', 'era_unit',
            'start_year', 'start_month', 'end_year', 'end_month',
            'is_active', 'time_range'
        ]
        read_only_fields = ['id', 'time_range']

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('标题不能为空')
        if len(value) > 255:
            raise serializers.ValidationError('标题长度不能超过255个字符')
        return value

    def validate_era_unit(self, value):
        if value and len(value) > 50:
            raise serializers.ValidationError('纪元单位长度不能超过50个字符')
        # 清理"元年"/"年"后缀
        if value:
            value = value.replace('元年', '').replace('年', '')
        return value.strip()

    def validate_start_month(self, value):
        if value < 0:
            raise serializers.ValidationError('开始月份不能小于0')
        return value

    def validate_end_month(self, value):
        if value < 0:
            raise serializers.ValidationError('结束月份不能小于0')
        return value

    def validate(self, data):
        # 结束时间不应早于开始时间（同纪元下）
        start_year = data.get('start_year', 0)
        start_month = data.get('start_month', 0)
        end_year = data.get('end_year', 0)
        end_month = data.get('end_month', 0)

        if end_year < start_year:
            raise serializers.ValidationError('结束年份不能早于开始年份')
        if end_year == start_year and end_month < start_month:
            raise serializers.ValidationError('结束月份不能早于开始月份')

        return data


class TimelineEventCreateUpdateSerializer(serializers.Serializer):
    """时间线事件创建/更新序列化器（用于 POST 接口）"""
    id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, max_length=10000)
    era_unit = serializers.CharField(max_length=50, allow_blank=True)
    start_year = serializers.IntegerField()
    start_month = serializers.IntegerField(min_value=0)
    end_year = serializers.IntegerField()
    end_month = serializers.IntegerField(min_value=0)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('标题不能为空')
        return value

    def validate_era_unit(self, value):
        if value:
            value = value.replace('元年', '').replace('年', '')
        return value.strip()

    def validate_start_month(self, value):
        if value < 0:
            raise serializers.ValidationError('开始月份不能小于0')
        return value

    def validate_end_month(self, value):
        if value < 0:
            raise serializers.ValidationError('结束月份不能小于0')
        return value

    def validate(self, data):
        # 结束时间不应早于开始时间（同纪元下）
        start_year = data.get('start_year', 0)
        start_month = data.get('start_month', 0)
        end_year = data.get('end_year', 0)
        end_month = data.get('end_month', 0)

        if end_year < start_year:
            raise serializers.ValidationError('结束年份不能早于开始年份')
        if end_year == start_year and end_month < start_month:
            raise serializers.ValidationError('结束月份不能早于开始月份')

        return data


class TimelineSplitSerializer(serializers.Serializer):
    """时间线拆分序列化器"""
    event_id = serializers.IntegerField()
    era_unit = serializers.CharField(max_length=50, required=False, default='', allow_blank=True)
    split_points = serializers.ListField(child=serializers.DictField())

    def validate_event_id(self, value):
        if value <= 0:
            raise serializers.ValidationError('无效的事件ID')
        return value

    def validate_split_points(self, value):
        if not value:
            raise serializers.ValidationError('拆分点不能为空')
        for point in value:
            year = point.get('year', 0)
            month = point.get('month', 0)
            if not isinstance(year, int) or not isinstance(month, int):
                raise serializers.ValidationError('拆分点的年份和月份必须是整数')
            if month < 0:
                raise serializers.ValidationError('拆分点月份不能小于0')
        return value


class TimelineMergeSerializer(serializers.Serializer):
    """时间线合并序列化器"""
    event_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=2,
        max_length=50
    )


class TimelineCheckOptimizeSerializer(serializers.Serializer):
    """时间线检查优化序列化器"""
    events = serializers.ListField(
        child=serializers.DictField(),
        max_length=50
    )
    user_solution = serializers.CharField(required=False, default='', allow_blank=True, max_length=2000)


class TimelineSingleOptimizeSerializer(serializers.Serializer):
    """单事件优化序列化器"""
    title = serializers.CharField(required=False, default='', allow_blank=True)
    era_unit = serializers.CharField(max_length=50, required=False, default='', allow_blank=True)
    start_year = serializers.IntegerField(required=False, default=0)
    start_month = serializers.IntegerField(required=False, default=0, min_value=0)
    end_year = serializers.IntegerField(required=False, default=0)
    end_month = serializers.IntegerField(required=False, default=0, min_value=0)
    content = serializers.CharField(required=False, default='', allow_blank=True, max_length=10000)
    prev_item = serializers.DictField(required=False, allow_null=True, default=None)
    next_item = serializers.DictField(required=False, allow_null=True, default=None)

    def validate(self, data):
        if not data.get('title') and not data.get('content'):
            raise serializers.ValidationError('标题和内容不能同时为空')
        return data


class TimelineGenerateFieldsSerializer(serializers.Serializer):
    """根据描述生成事件字段序列化器"""
    description = serializers.CharField(max_length=10000)
    prev_item = serializers.DictField(required=False, allow_null=True, default=None)
    next_item = serializers.DictField(required=False, allow_null=True, default=None)
