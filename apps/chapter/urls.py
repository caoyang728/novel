from django.urls import path
from .views import (
    ApiChapterGenerateView,
    ApiChapterContentView,
    ApiChapterVerifyView,
    ApiChapterVerifyFixView,
    ApiChapterSplitView,
    ApiChapterSaveView,
    ApiChapterStatusView,
    ApiChapterLoadView,
    ApiChapterDetailView,
    ApiChapterChatView,
    ApiChapterHardDeleteView,
    ApiChapterReorderView,
)

urlpatterns = [
    path('api/projects/<int:project_id>/chapters/generate/', ApiChapterGenerateView.as_view(), name='api_chapter_generate'),
    path('api/projects/<int:project_id>/chapters/content/', ApiChapterContentView.as_view(), name='api_chapter_content'),
    path('api/projects/<int:project_id>/chapters/verify/', ApiChapterVerifyView.as_view(), name='api_chapter_verify'),
    path('api/projects/<int:project_id>/chapters/verify-fix/', ApiChapterVerifyFixView.as_view(), name='api_chapter_verify_fix'),
    path('api/projects/<int:project_id>/chapters/split/', ApiChapterSplitView.as_view(), name='api_chapter_split'),
    path('api/projects/<int:project_id>/chapters/save/', ApiChapterSaveView.as_view(), name='api_chapter_save'),
    path('api/projects/<int:project_id>/chapters/status/', ApiChapterStatusView.as_view(), name='api_chapter_status'),
    path('api/projects/<int:project_id>/chapters/hard-delete/', ApiChapterHardDeleteView.as_view(), name='api_chapter_hard_delete'),
    path('api/projects/<int:project_id>/chapters/reorder/', ApiChapterReorderView.as_view(), name='api_chapter_reorder'),
    path('api/projects/<int:project_id>/chapters/volume/<int:volume_id>/load/', ApiChapterLoadView.as_view(), name='api_chapter_load'),
    path('api/projects/<int:project_id>/chapters/<int:chapter_id>/', ApiChapterDetailView.as_view(), name='api_chapter_detail'),
    path('api/projects/<int:project_id>/chapters/chat/', ApiChapterChatView.as_view(), name='api_chapter_chat'),
]
