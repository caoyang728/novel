from django.contrib import admin
from .models import GraphNode, GraphEdge


@admin.register(GraphNode)
class GraphNodeAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'node_type', 'name', 'source_id', 'created_at']
    list_filter = ['node_type', 'project']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(GraphEdge)
class GraphEdgeAdmin(admin.ModelAdmin):
    list_display = ['id', 'project', 'source', 'edge_type', 'target', 'is_bidirectional']
    list_filter = ['edge_type', 'project']
    search_fields = ['description']
    readonly_fields = ['created_at', 'updated_at']
