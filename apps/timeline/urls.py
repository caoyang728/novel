from django.urls import path
from . import views

app_name = 'timeline'

urlpatterns = [
    path('api/projects/<int:project_id>/timeline/events/', views.TimelineEventList.as_view(), name='timeline_event_list'),
    path('api/projects/<int:project_id>/timeline/events/<int:pk>/', views.TimelineEventDetail.as_view(), name='timeline_event_detail'),
    path('api/projects/<int:project_id>/timeline/chat-generate/', views.TimelineChatGenerateView.as_view(), name='timeline_chat_generate'),
    path('api/projects/<int:project_id>/timeline/generate/', views.TimelineGenerateView.as_view(), name='timeline_generate'),
    path('api/projects/<int:project_id>/timeline/merge/', views.TimelineMergeView.as_view(), name='timeline_merge'),
    path('api/projects/<int:project_id>/timeline/split/', views.TimelineSplitView.as_view(), name='timeline_split'),
    path('api/projects/<int:project_id>/timeline/optimize-single/', views.TimelineSingleOptimizeView.as_view(), name='timeline_single_optimize'),
    path('api/projects/<int:project_id>/timeline/generate-fields/', views.TimelineGenerateFieldsView.as_view(), name='timeline_generate_fields'),
    path('api/projects/<int:project_id>/timeline/check/', views.TimelineCheckView.as_view(), name='timeline_check'),
    path('api/projects/<int:project_id>/timeline/check/optimize/', views.TimelineCheckOptimizeView.as_view(), name='timeline_check_optimize'),
]
