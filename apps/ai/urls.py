from django.urls import path
from .views import (
    GenerateProjectInfoView,
    SuggestTitleView,
    RewriteTitleView,
    OptimizeDescriptionView,
)

urlpatterns = [
    path('project/info/generate/', GenerateProjectInfoView.as_view(), name='ai_generate_project_info'),
    path('title/suggest/', SuggestTitleView.as_view(), name='ai_suggest_title'),
    path('title/rewrite/', RewriteTitleView.as_view(), name='ai_rewrite_title'),
    path('description/optimize/', OptimizeDescriptionView.as_view(), name='ai_optimize_description'),
]