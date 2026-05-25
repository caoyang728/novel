from django.urls import path
from . import views

app_name = 'timeline'

urlpatterns = [
    path('api/projects/<int:project_id>/timeline/events/', views.TimelineEventList.as_view(), name='timeline_event_list'),
    path('api/projects/<int:project_id>/timeline/events/<int:pk>/', views.TimelineEventDetail.as_view(), name='timeline_event_detail'),
    path('api/projects/<int:project_id>/timeline/chat/', views.TimelineChatView.as_view(), name='timeline_chat'),
    path('api/projects/<int:project_id>/timeline/generate/', views.GenerateTimelineView.as_view(), name='generate_timeline'),
    path('api/projects/<int:project_id>/timeline/merge/', views.MergeTimelineView.as_view(), name='merge_timeline'),
    path('api/projects/<int:project_id>/timeline/split/', views.SplitTimelineView.as_view(), name='split_timeline'),
    path('api/projects/<int:project_id>/timeline/ai-merge/', views.AiMergeTimelineView.as_view(), name='ai_merge_timeline'),
    path('api/projects/<int:project_id>/timeline/ai-split/', views.AiSplitTimelineView.as_view(), name='ai_split_timeline'),
    path('api/projects/<int:project_id>/timeline/optimize-description/', views.OptimizeDescriptionView.as_view(), name='optimize_description'),
]
