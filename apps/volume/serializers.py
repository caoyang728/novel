"""
Volume serializers - 卷相关序列化器
"""
from rest_framework import serializers


class VolumeSerializer(serializers.Serializer):
    """卷数据序列化器 - 用于校验和创建 Volume"""
    volume_number = serializers.IntegerField(min_value=1)
    title = serializers.CharField(max_length=255)
    summary = serializers.CharField(required=False, default='', allow_blank=True)
    chapter_count = serializers.IntegerField(required=False, default=0, min_value=0)
    content = serializers.CharField(required=False, default='', allow_blank=True)
    is_locked = serializers.BooleanField(required=False, default=False)

    def create(self, validated_data):
        from apps.volume.models import Volume
        project = self.context.get('project')
        outline = self.context.get('outline')
        version = self.context.get('version', 1)
        return Volume.objects.create(project=project, outline=outline, version=version, **validated_data)
