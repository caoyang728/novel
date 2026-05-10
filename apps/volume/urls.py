from django.urls import path
from .views import (
    GenerateVolumesView,
    SaveVolumeVersionView,
    LoadVolumeVersionView,
    OptimizeVolumesView,
    FinalizeVolumeVersionView,
)

urlpatterns = [
    path('volume/generate/', GenerateVolumesView.as_view(), name='generate_volumes'),
    path('volume/version/save/', SaveVolumeVersionView.as_view(), name='save_volume_version'),
    path('volume/version/<int:version_id>/load/', LoadVolumeVersionView.as_view(), name='load_volume_version'),
    path('volume/optimize/', OptimizeVolumesView.as_view(), name='optimize_volumes'),
    path('volume/version/finalize/', FinalizeVolumeVersionView.as_view(), name='finalize_volume_version'),
]