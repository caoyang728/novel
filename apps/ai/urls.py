from django.urls import path


urlpatterns = [
    # path('project/info/generate/', GenerateProjectInfoView.as_view(), name='ai_generate_project_info'),  # 未被前端使用
    # path('title/suggest/', SuggestTitleView.as_view(), name='ai_suggest_title'),  # 未被前端使用（project应用已有相同功能：/api/title/suggest/）
    # path('title/rewrite/', RewriteTitleView.as_view(), name='ai_rewrite_title'),  # 未被前端使用
    # path('description/optimize/', OptimizeDescriptionView.as_view(), name='ai_optimize_description'),  # 未被前端使用
]
