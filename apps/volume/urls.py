from django.urls import path
from .views import (
    GenerateVolumesView,
    ApiVolumeChatView,
    ApiVolumeVersionsView,
    ApiVolumeVersionView,
    ApiSaveVolumeVersionView,
    ApiVolumeFinalizeView,
    ApiVolumeDeleteView,
)

urlpatterns = [
    path('api/volume/generate/', GenerateVolumesView.as_view(), name='api_volume_generate'),
    path('api/volume/chat/', ApiVolumeChatView.as_view(), name='api_volume_chat'),
    path('api/projects/<int:project_id>/volume-versions/', ApiVolumeVersionsView.as_view(), name='api_volume_versions'),
    path('api/volume/version/<int:version_id>/', ApiVolumeVersionView.as_view(), name='api_volume_version'),
    path('api/volume/save/', ApiSaveVolumeVersionView.as_view(), name='api_volume_save'),
    path('api/volume/finalize/', ApiVolumeFinalizeView.as_view(), name='api_volume_finalize'),
    path('api/volume/delete/', ApiVolumeDeleteView.as_view(), name='api_volume_delete'),
]
