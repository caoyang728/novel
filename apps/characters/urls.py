from django.urls import path
from .views import (
    ApiCharacterListView,
    ApiCharacterDetailView,
    ApiCharacterGenerateView,
    ApiCharacterPolishView,
    ApiCharacterCheckView,
    ApiCharacterOptimizeView,
    ApiCharacterOptimizeSaveView,
    ApiCharacterRelationshipTypesView,
)

urlpatterns = [
    path('projects/<int:pk>/characters/', ApiCharacterListView.as_view(), name='api_character_list'),
    path('projects/<int:pk>/characters/<int:character_id>/', ApiCharacterDetailView.as_view(), name='api_character_detail'),
    path('projects/<int:pk>/characters/generate/', ApiCharacterGenerateView.as_view(), name='api_character_generate'),
    path('projects/<int:pk>/characters/polish/', ApiCharacterPolishView.as_view(), name='api_character_polish'),
    path('projects/<int:pk>/characters/check/', ApiCharacterCheckView.as_view(), name='api_character_check'),
    path('projects/<int:pk>/characters/optimize/', ApiCharacterOptimizeView.as_view(), name='api_character_optimize'),
    path('projects/<int:pk>/characters/optimize/save/', ApiCharacterOptimizeSaveView.as_view(), name='api_character_optimize_save'),
    path('projects/<int:pk>/characters/relationship-types/', ApiCharacterRelationshipTypesView.as_view(), name='api_character_relationship_types'),
]
