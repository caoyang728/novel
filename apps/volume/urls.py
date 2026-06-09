from django.urls import path
from .views import (
    VolumeVersionListView,
    VolumeVersionDetailView,
    VolumeVersionSaveView,
    VolumeVersionFinalizeView,
    VolumeVersionOptimizeView,
    VolumeVersionChatView,
    VolumeLockView,
    VolumeOptimizeView,
    VolumeGenerateView,
)

urlpatterns = [
    # 卷版本集合
    path('api/volume-versions/', VolumeVersionListView.as_view(), name='api_volume_version_list'),

    # 单个卷版本
    path('api/volume-versions/<int:version_id>/', VolumeVersionDetailView.as_view(), name='api_volume_version_detail'),
    path('api/volume-versions/<int:version_id>/save/', VolumeVersionSaveView.as_view(), name='api_volume_version_save'),
    path('api/volume-versions/<int:version_id>/finalize/', VolumeVersionFinalizeView.as_view(), name='api_volume_version_finalize'),
    path('api/volume-versions/<int:version_id>/optimize/', VolumeVersionOptimizeView.as_view(), name='api_volume_version_optimize'),
    path('api/volume-versions/<int:version_id>/chat/', VolumeVersionChatView.as_view(), name='api_volume_version_chat'),

    # 单卷操作
    path('api/volume/<int:volume_id>/lock/', VolumeLockView.as_view(), name='api_volume_lock'),
    path('api/volume/<int:volume_id>/generate/', VolumeGenerateView.as_view(), name='api_volume_generate'),
    path('api/volume/optimize/', VolumeOptimizeView.as_view(), name='api_volume_optimize'),
]
