from rest_framework import serializers
from .models import GraphNode, GraphEdge


class GraphNodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GraphNode
        fields = ['id', 'node_type', 'name', 'description', 'properties']


class GraphEdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = GraphEdge
        fields = ['id', 'source_id', 'target_id', 'edge_type', 'description', 'is_bidirectional']


class GraphDataSerializer(serializers.Serializer):
    """完整图谱数据（节点 + 边）"""
    nodes = GraphNodeSerializer(many=True)
    edges = GraphEdgeSerializer(many=True)
