from django.urls import path
from . import views

app_name = 'timeline'

urlpatterns = [
    path('api/projects/<int:project_id>/timeline/events/', views.ApiTimelineEventListView.as_view(), name='timeline_event_list'),
    path('api/projects/<int:project_id>/timeline/events/<int:pk>/', views.ApiTimelineEventDetailView.as_view(), name='timeline_event_detail'),
    path('api/projects/<int:project_id>/timeline/chat-generate/', views.ApiTimelineChatGenerateView.as_view(), name='timeline_chat_generate'),
    path('api/projects/<int:project_id>/timeline/generate/', views.ApiTimelineGenerateView.as_view(), name='timeline_generate'),
    path('api/projects/<int:project_id>/timeline/merge/', views.ApiTimelineMergeView.as_view(), name='timeline_merge'),
    path('api/projects/<int:project_id>/timeline/split/', views.ApiTimelineSplitView.as_view(), name='timeline_split'),
    path('api/projects/<int:project_id>/timeline/optimize-single/', views.ApiTimelineSingleOptimizeView.as_view(), name='timeline_single_optimize'),
    path('api/projects/<int:project_id>/timeline/generate-fields/', views.ApiTimelineGenerateFieldsView.as_view(), name='timeline_generate_fields'),
    path('api/projects/<int:project_id>/timeline/check/', views.ApiTimelineCheckView.as_view(), name='timeline_check'),
    path('api/projects/<int:project_id>/timeline/check/optimize/', views.ApiTimelineCheckOptimizeView.as_view(), name='timeline_check_optimize'),
]
