from django.urls import path
from .views import (
    ApiGraphDataView,
    ApiGraphSubgraphView,
    ApiGraphRebuildView,
    ApiGraphStatsView,
)

urlpatterns = [
    path('api/projects/<int:pk>/graph/', ApiGraphDataView.as_view(), name='api_graph_data'),
    path('api/projects/<int:pk>/graph/subgraph/', ApiGraphSubgraphView.as_view(), name='api_graph_subgraph'),
    path('api/projects/<int:pk>/graph/rebuild/', ApiGraphRebuildView.as_view(), name='api_graph_rebuild'),
    path('api/projects/<int:pk>/graph/stats/', ApiGraphStatsView.as_view(), name='api_graph_stats'),
]
