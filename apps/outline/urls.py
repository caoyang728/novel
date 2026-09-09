from django.urls import path
from .views import (
    # Chat Views
    ApiChatOutlineView,
    ApiSaveOutlineView,
    ApiLoadOutlineView,
    ApiFinalizeOutlineView,
    # API Views
    ApiOutlinesView,
    ApiOutlineDetailView,
    ApiLatestOutlineView,
    ApiOutlineFinalizeView,
    ApiOutlineDeleteView,
    ApiOutlineLockView,
    ApiOutlineUnlockView,
    ApiChatHistoryDeleteView,
)

urlpatterns = [
    # Chat Views
    path('api/projects/<int:project_id>/outline/chat/', ApiChatOutlineView.as_view(), name='api_chat_outline'),
    path('api/projects/<int:project_id>/outline/versions/save/', ApiSaveOutlineView.as_view(), name='api_save_outline_version'),
    path('api/projects/<int:project_id>/outline/versions/<int:version_id>/load/', ApiLoadOutlineView.as_view(), name='api_load_outline_version'),
    path('api/projects/<int:project_id>/outline/versions/finalize/', ApiFinalizeOutlineView.as_view(), name='api_finalize_outline_version'),

    # API Views
    path('api/projects/<int:project_id>/outline/versions/<int:version_id>/', ApiOutlineDetailView.as_view(), name='api_outline_version_content'),
    path('api/projects/<int:project_id>/outline/versions/', ApiOutlinesView.as_view(), name='api_outline_versions'),
    path('api/projects/<int:project_id>/outline/latest/', ApiLatestOutlineView.as_view(), name='api_latest_outline'),
    path('api/projects/<int:project_id>/outline/finalize/', ApiOutlineFinalizeView.as_view(), name='api_outline_finalize'),
    path('api/projects/<int:project_id>/outline/delete/', ApiOutlineDeleteView.as_view(), name='api_outline_delete'),
    path('api/projects/<int:project_id>/outline/lock/', ApiOutlineLockView.as_view(), name='api_outline_lock'),
    path('api/projects/<int:project_id>/outline/unlock/', ApiOutlineUnlockView.as_view(), name='api_outline_unlock'),
    path('api/projects/<int:project_id>/outline/chat-history/delete/', ApiChatHistoryDeleteView.as_view(), name='api_chat_history_delete'),

]
