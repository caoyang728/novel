from django.urls import path
from .views import ApiNotesView, ApiNoteDetailView, ApiNotePolishView

urlpatterns = [
    path('api/projects/<int:project_id>/notes/', ApiNotesView.as_view(), name='notes_list'),
    path('api/projects/<int:project_id>/notes/<int:note_id>/', ApiNoteDetailView.as_view(), name='note_detail'),
    path('api/projects/<int:project_id>/notes/polish/', ApiNotePolishView.as_view(), name='note_polish'),
]