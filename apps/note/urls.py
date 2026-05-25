from django.urls import path
from .views import NotesAPIView, NoteDetailAPIView, NoteAIPolishAPIView

urlpatterns = [
    path('api/projects/<int:project_id>/notes/', NotesAPIView.as_view(), name='notes_list'),
    path('api/projects/<int:project_id>/notes/<int:note_id>/', NoteDetailAPIView.as_view(), name='note_detail'),
    path('api/projects/<int:project_id>/notes/<int:note_id>/polish/', NoteAIPolishAPIView.as_view(), name='note_polish'),
]