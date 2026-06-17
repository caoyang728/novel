from django.urls import path
from .views import (
    ApiVolumeVersionListView,
    ApiVolumeVersionDetailView,
    ApiVolumeVersionSaveView,
    ApiVolumeVersionFinalizeView,
    ApiVolumeVersionOptimizeView,
    ApiVolumeVersionChatView,
    ApiVolumeLockView,
    ApiVolumeOptimizeView,
    ApiVolumeGenerateView,
)

urlpatterns = [
    # 卷版本集合
    path('api/projects/<int:project_id>/volume-versions/', ApiVolumeVersionListView.as_view(), name='api_volume_version_list'),

    # 单个卷版本
    path('api/projects/<int:project_id>/volume-versions/<int:version_id>/', ApiVolumeVersionDetailView.as_view(), name='api_volume_version_detail'),
    path('api/projects/<int:project_id>/volume-versions/<int:version_id>/save/', ApiVolumeVersionSaveView.as_view(), name='api_volume_version_save'),
    path('api/projects/<int:project_id>/volume-versions/<int:version_id>/finalize/', ApiVolumeVersionFinalizeView.as_view(), name='api_volume_version_finalize'),
    path('api/projects/<int:project_id>/volume-versions/<int:version_id>/optimize/', ApiVolumeVersionOptimizeView.as_view(), name='api_volume_version_optimize'),
    path('api/projects/<int:project_id>/volume-versions/<int:version_id>/chat/', ApiVolumeVersionChatView.as_view(), name='api_volume_version_chat'),

    # 单卷操作
    path('api/projects/<int:project_id>/volumes/<int:volume_id>/lock/', ApiVolumeLockView.as_view(), name='api_volume_lock'),
    path('api/projects/<int:project_id>/volumes/<int:volume_id>/generate/', ApiVolumeGenerateView.as_view(), name='api_volume_generate'),
    path('api/projects/<int:project_id>/volumes/optimize/', ApiVolumeOptimizeView.as_view(), name='api_volume_optimize'),
]
