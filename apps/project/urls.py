from django.urls import path
from .views import (
    ProjectListView,
    ProjectCreateView,
    ProjectDetailView,
    ProjectUpdateTitleView,
    ProjectUpdateInfoView,
    TokenUsageView,
    ApiTokenUsageToday,
    ApiTokenUsageStats,
    ApiProjectListView,
    ApiProjectDetailView,
    ApiProjectCreateView,
    ApiProjectDeleteView,
)

urlpatterns = [
    path('', ProjectListView.as_view(), name='project_list'),
    path('create/', ProjectCreateView.as_view(), name='project_create'),
    path('<int:pk>/', ProjectDetailView.as_view(), name='project_detail'),
    path('<int:pk>/update-title/', ProjectUpdateTitleView.as_view(), name='project_update_title'),
    path('<int:pk>/update-info/', ProjectUpdateInfoView.as_view(), name='project_update_info'),
    path('token-usage/', TokenUsageView.as_view(), name='token_usage'),
    path('api/token-usage/today/', ApiTokenUsageToday.as_view(), name='api_token_usage_today'),
    path('api/token-usage/stats/', ApiTokenUsageStats.as_view(), name='api_token_usage_stats'),
    path('api/projects/', ApiProjectListView.as_view(), name='api_project_list'),
    path('api/projects/<int:pk>/', ApiProjectDetailView.as_view(), name='api_project_detail'),
    path('api/projects/create/', ApiProjectCreateView.as_view(), name='api_project_create'),
    path('api/projects/<int:pk>/delete/', ApiProjectDeleteView.as_view(), name='api_project_delete'),
]