from django.urls import path
from .views import (
    ApiCharacterListView,
    ApiCharacterDetailView,
    ApiCharacterGenerateView,
    ApiCharacterPolishView
)

urlpatterns = [
    path('projects/<int:pk>/characters/', ApiCharacterListView.as_view(), name='api_character_list'),
    path('projects/<int:pk>/characters/<int:character_id>/', ApiCharacterDetailView.as_view(), name='api_character_detail'),
    path('projects/<int:pk>/characters/generate/', ApiCharacterGenerateView.as_view(), name='api_character_generate'),
    path('projects/<int:pk>/characters/polish/', ApiCharacterPolishView.as_view(), name='api_character_polish'),
]
