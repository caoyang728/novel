from django.urls import path, include
from .views import (
    # Project
    ProjectListView,
    ProjectCreateView,
    ProjectDetailView,
    ProjectUpdateTitleView,
    ProjectUpdateInfoView,
    # 新页面视图
    OutlineBuilderView,
    TimelineView,
    VolumeView,
    ChapterGeneratorView,
    ContentManagerView,
    NoteView,
    CharacterView,
    # API
    ApiProjectListView,
    ApiProjectCreateView,
    ApiProjectDetailView,
    ApiProjectStatsView,
    ApiTitleSuggestView,
    ApiDescriptionSuggestView,
    ApiEnhanceDescriptionView,
)

urlpatterns = [
    # Project pages
    path('', ProjectListView.as_view(), name='project_list'),
    path('create/', ProjectCreateView.as_view(), name='project_create'),
    path('<int:project_id>/', ProjectDetailView.as_view(), name='project_detail'),
    path('<int:project_id>/update-title/', ProjectUpdateTitleView.as_view(), name='project_update_title'),
    path('<int:project_id>/update-info/', ProjectUpdateInfoView.as_view(), name='project_update_info'),
    
    # 新的页面路由 - 统一使用 /project_id/route/ 格式
    path('<int:project_id>/outline/', OutlineBuilderView.as_view(), name='outline_builder'),
    path('<int:project_id>/timeline/', TimelineView.as_view(), name='timeline'),
    path('<int:project_id>/volume/', VolumeView.as_view(), name='volume'),
    path('<int:project_id>/chapter/', ChapterGeneratorView.as_view(), name='chapter_generator'),
    path('<int:project_id>/content/', ContentManagerView.as_view(), name='content_manager'),
    path('<int:project_id>/note/', NoteView.as_view(), name='note'),
    path('<int:project_id>/character/', CharacterView.as_view(), name='character'),

    # API Project
    path('api/projects/', ApiProjectListView.as_view(), name='api_project_list'),
    path('api/projects/create/', ApiProjectCreateView.as_view(), name='api_project_create'),
    path('api/projects/description-optimization/', ApiEnhanceDescriptionView.as_view(), name='api_project_description_enhance_no_id'),
    path('api/projects/<int:pk>/', ApiProjectDetailView.as_view(), name='api_project_detail'),
    path('api/projects/<int:pk>/title/suggest/', ApiTitleSuggestView.as_view(), name='api_title_suggest'),
    path('api/projects/<int:pk>/description/suggest/', ApiDescriptionSuggestView.as_view(), name='api_description_suggest'),
    path('api/projects/<int:pk>/stats/', ApiProjectStatsView.as_view(), name='api_project_stats'),
    path('api/projects/<int:pk>/description-optimization/', ApiEnhanceDescriptionView.as_view(), name='api_project_description_enhance'),

    # 角色路由 - 移至 characters app
    path('api/', include('apps.characters.urls')),
]
