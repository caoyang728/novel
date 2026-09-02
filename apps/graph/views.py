from rest_framework.response import Response
from rest_framework import status

from apps.project.base import BaseAPIView
from .services import GraphService


class ApiGraphDataView(BaseAPIView):
    """获取项目完整图谱数据（节点+边+统计），一次请求返回全部"""

    def get(self, request, pk):
        project = self.get_project_or_404(request, pk)
        node_types = request.query_params.get('node_types')
        edge_types = request.query_params.get('edge_types')
        data = GraphService.get_graph_data(project.pk, node_types, edge_types)
        return Response({'success': True, 'data': data})


class ApiGraphSubgraphView(BaseAPIView):
    """获取指定角色的 N 跳子图"""

    def get(self, request, pk):
        project = self.get_project_or_404(request, pk)
        name = request.query_params.get('name', '').strip()
        if not name:
            return Response(
                {'success': False, 'error': '缺少 name 参数'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        hops = int(request.query_params.get('hops', 1))
        hops = max(1, min(hops, 3))  # 限制 1-3 跳
        data = GraphService.get_character_subgraph(project.pk, name, hops)
        return Response({'success': True, 'data': data})


class ApiGraphRebuildView(BaseAPIView):
    """重建项目图谱"""

    def post(self, request, pk):
        project = self.get_project_or_404(request, pk)
        from .tasks import _enqueue, rebuild_project_task
        _enqueue(rebuild_project_task, project.pk)
        return Response({'success': True, 'message': '图谱重建任务已提交'})


class ApiGraphStatsView(BaseAPIView):
    """获取图谱统计信息"""

    def get(self, request, pk):
        project = self.get_project_or_404(request, pk)
        data = GraphService.get_stats(project.pk)
        return Response({'success': True, 'data': data})
