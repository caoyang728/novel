from django.urls import path
from .views import (
    # Chat Views
    ApiChatOutlineView,
    ApiSaveOutlineVersionView,
    ApiLoadOutlineVersionView,
    ApiFinalizeOutlineVersionView,
    # API Views
    ApiOutlineVersionsView,
    ApiOutlineVersionDetailView,
    ApiLatestOutlineView,
    ApiOutlineFinalizeView,
    ApiOutlineDeleteView,
    ApiOutlineLockView,
    ApiChatHistoryDeleteView,
)

urlpatterns = [
    # Chat Views
    path('api/projects/<int:project_id>/outline/chat/', ApiChatOutlineView.as_view(), name='api_chat_outline'),
    path('api/projects/<int:project_id>/outline/versions/save/', ApiSaveOutlineVersionView.as_view(), name='api_save_outline_version'),
    path('api/projects/<int:project_id>/outline/versions/<int:version_id>/load/', ApiLoadOutlineVersionView.as_view(), name='api_load_outline_version'),
    path('api/projects/<int:project_id>/outline/versions/finalize/', ApiFinalizeOutlineVersionView.as_view(), name='api_finalize_outline_version'),

    # API Views
    path('api/projects/<int:project_id>/outline/versions/<int:version_id>/', ApiOutlineVersionDetailView.as_view(), name='api_outline_version_content'),
    path('api/projects/<int:project_id>/outline/versions/', ApiOutlineVersionsView.as_view(), name='api_outline_versions'),
    path('api/projects/<int:project_id>/outline/latest/', ApiLatestOutlineView.as_view(), name='api_latest_outline'),
    path('api/projects/<int:project_id>/outline/finalize/', ApiOutlineFinalizeView.as_view(), name='api_outline_finalize'),
    path('api/projects/<int:project_id>/outline/delete/', ApiOutlineDeleteView.as_view(), name='api_outline_delete'),
    path('api/projects/<int:project_id>/outline/lock/', ApiOutlineLockView.as_view(), name='api_outline_lock'),
    path('api/projects/<int:project_id>/outline/chat-history/delete/', ApiChatHistoryDeleteView.as_view(), name='api_chat_history_delete'),

]
