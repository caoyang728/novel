from django.urls import path
from .views import (
    ChatOutlineView,
    ChatOutlineStreamView,
    SaveOutlineVersionView,
    LoadOutlineVersionView,
    FinalizeOutlineVersionView,
    DeleteOutlineVersionView,
    RestoreOutlineVersionView,
)

urlpatterns = [
    path('chat/outline/', ChatOutlineView.as_view(), name='chat_outline'),
    path('chat/outline/stream/', ChatOutlineStreamView.as_view(), name='chat_outline_stream'),
    path('outline/version/save/', SaveOutlineVersionView.as_view(), name='save_outline_version'),
    path('outline/version/<int:version_id>/load/', LoadOutlineVersionView.as_view(), name='load_outline_version'),
    path('outline/version/finalize/', FinalizeOutlineVersionView.as_view(), name='finalize_outline_version'),
    path('outline/version/delete/', DeleteOutlineVersionView.as_view(), name='delete_outline_version'),
    path('outline/version/restore/', RestoreOutlineVersionView.as_view(), name='restore_outline_version'),
]