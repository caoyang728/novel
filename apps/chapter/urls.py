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
    path('api/chapter/generate/', ApiChapterGenerateView.as_view(), name='api_chapter_generate'),
    path('api/chapter/content/', ApiChapterContentView.as_view(), name='api_chapter_content'),
    path('api/chapter/verify/', ApiChapterVerifyView.as_view(), name='api_chapter_verify'),
    path('api/chapter/verify-fix/', ApiChapterVerifyFixView.as_view(), name='api_chapter_verify_fix'),
    path('api/chapter/split/', ApiChapterSplitView.as_view(), name='api_chapter_split'),
    path('api/chapter/save/', ApiChapterSaveView.as_view(), name='api_chapter_save'),
    path('api/chapter/status/', ApiChapterStatusView.as_view(), name='api_chapter_status'),
    path('api/chapter/hard-delete/', ApiChapterHardDeleteView.as_view(), name='api_chapter_hard_delete'),
    path('api/chapter/reorder/', ApiChapterReorderView.as_view(), name='api_chapter_reorder'),
    path('api/chapter/volume/<int:volume_id>/load/', ApiChapterLoadView.as_view(), name='api_chapter_load'),
    path('api/chapter/<int:chapter_id>/detail/', ApiChapterDetailView.as_view(), name='api_chapter_detail'),
    path('api/chapter/chat/', ApiChapterChatView.as_view(), name='api_chapter_chat'),
]
