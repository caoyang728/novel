from django.urls import path
from .views import (
    # Page Views
    # ChapterGeneratorView,
    # ContentManagerView,
    # API Views
    # GenerateChapterSummariesView,  # 未被前端使用（使用stream版本）
    GenerateChapterSummariesStreamView,
    # OptimizeChapterSummariesView,  # 未被前端使用
    # FinalizeChapterVersionView,  # 未被前端使用
    # GenerateChapterContentView,  # 未被前端使用（使用stream版本）
    GenerateChapterContentStreamView,
    # GenerateChaptersBatchView,  # 未被前端使用
    VerifyChapterView,
    SplitChapterView,
    ContinueChapterView,
    OptimizeChapterContentView,
    SaveChapterView,
    PublishChapterView,
    ArchiveChapterView,
    LoadChapterVersionsView,
    SetCurrentChapterVersionView,
    ChatChapterWriteView,
)

urlpatterns = [
    # Page Views
    # path('chapter_generator.html', ChapterGeneratorView.as_view(), name='chapter_generator'),
    # path('content_manager.html', ContentManagerView.as_view(), name='content_manager'),
    
    # API Views
    # path('chapter/summaries/generate/', GenerateChapterSummariesView.as_view(), name='generate_chapter_summaries'),  # 未被前端使用（使用stream版本）
    path('chapter/summaries/generate/stream/', GenerateChapterSummariesStreamView.as_view(), name='generate_chapter_summaries_stream'),
    # path('chapter/summaries/optimize/', OptimizeChapterSummariesView.as_view(), name='optimize_chapter_summaries'),  # 未被前端使用
    # path('chapter/version/finalize/', FinalizeChapterVersionView.as_view(), name='finalize_chapter_version'),  # 未被前端使用
    # path('chapter/content/generate/', GenerateChapterContentView.as_view(), name='generate_chapter_content'),  # 未被前端使用（使用stream版本）
    path('chapter/content/stream/', GenerateChapterContentStreamView.as_view(), name='generate_chapter_content_stream'),
    # path('chapter/batch/generate/', GenerateChaptersBatchView.as_view(), name='generate_chapters_batch'),  # 未被前端使用
    path('chapter/verify/', VerifyChapterView.as_view(), name='verify_chapter'),
    path('chapter/split/', SplitChapterView.as_view(), name='split_chapter'),
    path('chapter/continue/', ContinueChapterView.as_view(), name='continue_chapter'),
    path('chapter/content/optimize/', OptimizeChapterContentView.as_view(), name='optimize_chapter_content'),
    path('chapter/save/', SaveChapterView.as_view(), name='save_chapter'),
    path('chapter/publish/', PublishChapterView.as_view(), name='publish_chapter'),
    path('chapter/archive/', ArchiveChapterView.as_view(), name='archive_chapter'),
    path('chapter/versions/<int:volume_version_id>/load/', LoadChapterVersionsView.as_view(), name='load_chapter_versions'),
    path('chapter/version/current/', SetCurrentChapterVersionView.as_view(), name='set_current_chapter_version'),
    path('ai/chat/chapter/write/', ChatChapterWriteView.as_view(), name='chat_chapter_write'),
]
