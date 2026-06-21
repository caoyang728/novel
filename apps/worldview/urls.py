from django.urls import path
from .views import (
    ApiWorldviewDataView,
    ApiWorldviewDeepeningQuestionsView,
    ApiWorldviewDeepeningSubmitView,
    ApiWorldviewDeepeningApplyView,
    ApiWorldviewConsistencyView,
    ApiWorldviewConsistencyFixView,
    ApiWorldviewOptimizeView,
    ApiWorldviewLayerView,
    ApiWorldviewExportMarkdownView,
    ApiWorldviewChatStreamView,
    ApiWorldviewChatOpenView
)

urlpatterns = [
    path('api/projects/<int:project_id>/worldviews/', ApiWorldviewDataView.as_view(), name='api_worldview_data'),
    # 无需 pk 的路由（一个项目只有一个世界观，用 project_id 查询即可）—— 必须在 <int:pk>/ 之前
    path('api/projects/<int:project_id>/worldviews/chat/open/', ApiWorldviewChatOpenView.as_view(), name='api_worldview_chat_open'),
    path('api/projects/<int:project_id>/worldviews/export/markdown/', ApiWorldviewExportMarkdownView.as_view(), name='api_worldview_export_markdown'),
    # 需要 pk 的路由
    path('api/projects/<int:project_id>/worldviews/<int:pk>/', ApiWorldviewDataView.as_view(), name='api_worldview_data_by_id'),
    path('api/projects/<int:project_id>/worldviews/<int:pk>/deepening/questions/', ApiWorldviewDeepeningQuestionsView.as_view(), name='api_worldview_deepening_questions'),
    path('api/projects/<int:project_id>/worldviews/<int:pk>/deepening/submit/', ApiWorldviewDeepeningSubmitView.as_view(), name='api_worldview_deepening_submit'),
    path('api/projects/<int:project_id>/worldviews/<int:pk>/deepening/apply/', ApiWorldviewDeepeningApplyView.as_view(), name='api_worldview_deepening_apply'),
    path('api/projects/<int:project_id>/worldviews/<int:pk>/consistency/check/', ApiWorldviewConsistencyView.as_view(), name='api_worldview_consistency'),
    path('api/projects/<int:project_id>/worldviews/<int:pk>/consistency/fix/', ApiWorldviewConsistencyFixView.as_view(), name='api_worldview_consistency_fix'),
    path('api/projects/<int:project_id>/worldviews/<int:pk>/optimize/<str:layer>/', ApiWorldviewOptimizeView.as_view(), name='api_worldview_optimize'),
    path('api/projects/<int:project_id>/worldviews/<int:pk>/layer/<str:layer>/', ApiWorldviewLayerView.as_view(), name='api_worldview_layer'),
    path('api/projects/<int:project_id>/worldviews/chat/stream/', ApiWorldviewChatStreamView.as_view(), name='api_worldview_chat_stream'),
]
