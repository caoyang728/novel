from django.urls import path
from .views import (
    # Chat Views
    APIChatOutlineView,
    SaveOutlineVersionView,
    LoadOutlineVersionView,
    FinalizeOutlineVersionView,
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
    path('api/chat/outline/', APIChatOutlineView.as_view(), name='api_chat_outline'),
    path('api/outline/version/save/', SaveOutlineVersionView.as_view(), name='save_outline_version'),
    path('outline/version/<int:version_id>/load/', LoadOutlineVersionView.as_view(), name='load_outline_version'),
    path('outline/version/finalize/', FinalizeOutlineVersionView.as_view(), name='finalize_outline_version'),
    
    # API Views
    path('api/outline/version/<int:version_id>/', ApiOutlineVersionDetailView.as_view(), name='api_outline_version_content'),
    path('api/projects/<int:pk>/outline/versions/', ApiOutlineVersionsView.as_view(), name='api_outline_versions'),
    path('api/projects/<int:pk>/outline/latest/', ApiLatestOutlineView.as_view(), name='api_latest_outline'),
    path('api/outline/finalize/', ApiOutlineFinalizeView.as_view(), name='api_outline_finalize'),
    path('api/outline/delete/', ApiOutlineDeleteView.as_view(), name='api_outline_delete'),
    path('api/outline/lock/', ApiOutlineLockView.as_view(), name='api_outline_lock'),
    path('api/chat-history/delete/', ApiChatHistoryDeleteView.as_view(), name='api_chat_history_delete'),

]
