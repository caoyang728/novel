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
from .views_doc import (
    ApiWorldviewDocView,
    ApiWorldviewDocChatOpenView,
    ApiWorldviewDocChatStreamView,
    ApiWorldviewDocChatHistoryView,
    ApiWorldviewDocFactionExtractView,
    ApiWorldviewDocVersionsView,
    ApiWorldviewDocVersionLoadView,
    ApiWorldviewDocVersionSaveView,
    ApiWorldviewDocVersionUpdateView,
    ApiWorldviewDocVersionLockView,
    ApiWorldviewDocVersionUnlockView,
    ApiWorldviewDocVersionDeleteView,
)

urlpatterns = [
    path('api/projects/<int:project_id>/worldviews/', ApiWorldviewDataView.as_view(), name='api_worldview_data'),
    # 无需 pk 的路由（一个项目只有一个世界观，用 project_id 查询即可）—— 必须在 <int:pk>/ 之前
    path('api/projects/<int:project_id>/worldviews/chat/open/', ApiWorldviewChatOpenView.as_view(), name='api_worldview_chat_open'),
    path('api/projects/<int:project_id>/worldviews/export/markdown/', ApiWorldviewExportMarkdownView.as_view(), name='api_worldview_export_markdown'),
    # ========== 世界观文档（Markdown 新版，与旧版并行） ==========
    path('api/projects/<int:project_id>/worldview-doc/', ApiWorldviewDocView.as_view(), name='api_worldview_doc'),
    path('api/projects/<int:project_id>/worldview-doc/chat/open/', ApiWorldviewDocChatOpenView.as_view(), name='api_worldview_doc_chat_open'),
    path('api/projects/<int:project_id>/worldview-doc/chat/history/', ApiWorldviewDocChatHistoryView.as_view(), name='api_worldview_doc_chat_history'),
    path('api/projects/<int:project_id>/worldview-doc/chat/stream/', ApiWorldviewDocChatStreamView.as_view(), name='api_worldview_doc_chat_stream'),
    path('api/projects/<int:project_id>/worldview-doc/factions/extract/', ApiWorldviewDocFactionExtractView.as_view(), name='api_worldview_doc_faction_extract'),
    # 版本管理
    path('api/projects/<int:project_id>/worldview-doc/versions/', ApiWorldviewDocVersionsView.as_view(), name='api_worldview_doc_versions'),
    path('api/projects/<int:project_id>/worldview-doc/versions/save/', ApiWorldviewDocVersionSaveView.as_view(), name='api_worldview_doc_version_save'),
    path('api/projects/<int:project_id>/worldview-doc/versions/update/', ApiWorldviewDocVersionUpdateView.as_view(), name='api_worldview_doc_version_update'),
    path('api/projects/<int:project_id>/worldview-doc/versions/<int:version_id>/load/', ApiWorldviewDocVersionLoadView.as_view(), name='api_worldview_doc_version_load'),
    path('api/projects/<int:project_id>/worldview-doc/versions/<int:version_id>/lock/', ApiWorldviewDocVersionLockView.as_view(), name='api_worldview_doc_version_lock'),
    path('api/projects/<int:project_id>/worldview-doc/versions/<int:version_id>/unlock/', ApiWorldviewDocVersionUnlockView.as_view(), name='api_worldview_doc_version_unlock'),
    path('api/projects/<int:project_id>/worldview-doc/versions/<int:version_id>/delete/', ApiWorldviewDocVersionDeleteView.as_view(), name='api_worldview_doc_version_delete'),
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
