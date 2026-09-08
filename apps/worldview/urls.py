from django.urls import path
from .views import (
    # 文档 CRUD
    ApiWorldviewView,
    # 会话
    ApiWorldviewOpenView,
    ApiWorldviewStreamView,
    ApiWorldviewChatHistoryView,
    # 阵营提取
    ApiWorldviewFactionExtractView,
    # 版本管理
    ApiWorldviewVersionsView,
    ApiWorldviewVersionSaveView,
    ApiWorldviewVersionUpdateView,
    ApiWorldviewVersionLoadView,
    ApiWorldviewVersionLockView,
    ApiWorldviewVersionUnlockView,
    ApiWorldviewVersionDeleteView,
)

urlpatterns = [
    # 文档 CRUD
    path('api/projects/<int:project_id>/worldviews/', ApiWorldviewView.as_view(), name='api_worldview'),
    # 会话
    path('api/projects/<int:project_id>/worldviews/open/', ApiWorldviewOpenView.as_view(), name='api_worldview_open'),
    path('api/projects/<int:project_id>/worldviews/stream/', ApiWorldviewStreamView.as_view(), name='api_worldview_stream'),
    path('api/projects/<int:project_id>/worldviews/chat/history/', ApiWorldviewChatHistoryView.as_view(), name='api_worldview_chat_history'),
    # 阵营提取
    path('api/projects/<int:project_id>/worldviews/factions/extract/', ApiWorldviewFactionExtractView.as_view(), name='api_worldview_faction_extract'),
    # 版本管理（save/update 无 id，需排在 <int:version_id>/ 之前）
    path('api/projects/<int:project_id>/worldviews/versions/', ApiWorldviewVersionsView.as_view(), name='api_worldview_versions'),
    path('api/projects/<int:project_id>/worldviews/versions/save/', ApiWorldviewVersionSaveView.as_view(), name='api_worldview_version_save'),
    path('api/projects/<int:project_id>/worldviews/versions/update/', ApiWorldviewVersionUpdateView.as_view(), name='api_worldview_version_update'),
    # 单个版本操作
    path('api/projects/<int:project_id>/worldviews/versions/<int:version_id>/load/', ApiWorldviewVersionLoadView.as_view(), name='api_worldview_version_load'),
    path('api/projects/<int:project_id>/worldviews/versions/<int:version_id>/lock/', ApiWorldviewVersionLockView.as_view(), name='api_worldview_version_lock'),
    path('api/projects/<int:project_id>/worldviews/versions/<int:version_id>/unlock/', ApiWorldviewVersionUnlockView.as_view(), name='api_worldview_version_unlock'),
    path('api/projects/<int:project_id>/worldviews/versions/<int:version_id>/delete/', ApiWorldviewVersionDeleteView.as_view(), name='api_worldview_version_delete'),
]
