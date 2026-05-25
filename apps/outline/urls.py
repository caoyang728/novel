from django.urls import path
from .views import (
    # Page Views
    # OutlineBuilderView,
    # OutlineVersionDetailView,
    # VolumeBuilderView,
    # VolumeVersionDetailView,
    # ChapterSummaryView,
    # ChapterVersionDetailView,
    # ChapterContentDetailView,
    # ChapterContentApiView,
    # OutlineVersionContentApiView,
    # Chat Views
    APIChatOutlineView,
    SaveOutlineVersionView,
    LoadOutlineVersionView,
    FinalizeOutlineVersionView,
    # DeleteOutlineVersionView,  # 未被前端使用
    # RestoreOutlineVersionView,  # 未被前端使用
    # API Views
    ApiOutlineVersionsView,
    ApiOutlineVersionDetailView,
    ApiLatestOutlineView,
    ApiOutlineFinalizeView,
    ApiOutlineDeleteView,
    # ApiOutlineSaveVersionView,
    ApiChatHistoryDeleteView,
    # ApiChatHistoryRestoreView,
)

urlpatterns = [
    # Page Views
    # path('<int:pk>/outline/', OutlineBuilderView.as_view(), name='outline_builder'),
    # path('<int:pk>/outline/version/<int:version_pk>/', OutlineVersionDetailView.as_view(), name='outline_version_detail'),
    # path('<int:pk>/volume/', VolumeBuilderView.as_view(), name='volume_builder'),
    # path('<int:pk>/volume/version/<int:version_pk>/', VolumeVersionDetailView.as_view(), name='volume_version_detail'),
    # path('<int:pk>/volume/<int:volume_pk>/chapters/', ChapterSummaryView.as_view(), name='chapter_summary'),
    # path('<int:pk>/volume/<int:volume_pk>/chapters/version/<int:version_pk>/', ChapterVersionDetailView.as_view(), name='chapter_version_detail'),
    # path('<int:pk>/volume/<int:volume_pk>/chapter/<int:chapter_pk>/', ChapterContentDetailView.as_view(), name='chapter_content_detail'),

    # Chat Views
    path('chat/new-outline/', APIChatOutlineView.as_view(), name='chat_new_outline_stream'),
    path('api/outline/version/save/', SaveOutlineVersionView.as_view(), name='save_outline_version'),
    path('outline/version/<int:version_id>/load/', LoadOutlineVersionView.as_view(), name='load_outline_version'),
    path('outline/version/finalize/', FinalizeOutlineVersionView.as_view(), name='finalize_outline_version'),
    # path('outline/version/delete/', DeleteOutlineVersionView.as_view(), name='delete_outline_version'),  # 未被前端使用
    # path('outline/version/restore/', RestoreOutlineVersionView.as_view(), name='restore_outline_version'),  # 未被前端使用

    # API Views
    path('api/chat/new-outline/', APIChatOutlineView.as_view(), name='api_chat_new_outline'),
    path('api/chat/outline/', APIChatOutlineView.as_view(), name='api_chat_outline'),
    path('api/chat/outline/stream/', APIChatOutlineView.as_view(), name='api_chat_outline_stream'),
    # path('api/chapter/<int:chapter_id>/content/', ChapterContentApiView.as_view(), name='chapter_content_api'),
    path('api/outline/version/<int:version_id>/', ApiOutlineVersionDetailView.as_view(), name='api_outline_version_content'),
    path('api/projects/<int:pk>/outline/versions/', ApiOutlineVersionsView.as_view(), name='api_outline_versions'),
    path('api/projects/<int:pk>/outline/latest/', ApiLatestOutlineView.as_view(), name='api_latest_outline'),
    path('api/outline/finalize/', ApiOutlineFinalizeView.as_view(), name='api_outline_finalize'),
    path('api/outline/delete/', ApiOutlineDeleteView.as_view(), name='api_outline_delete'),
    # path('api/outline/save-version/', ApiOutlineSaveVersionView.as_view(), name='api_outline_save_version'),
    path('api/chat-history/delete/', ApiChatHistoryDeleteView.as_view(), name='api_chat_history_delete'),
    # path('api/chat-history/restore/', ApiChatHistoryRestoreView.as_view(), name='api_chat_history_restore'),

]
