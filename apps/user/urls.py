from django.urls import path
from .views import (
    # Auth
    LoginView,
    LogoutView,
    RegisterView,
    ResetPasswordView,
    ApiUserView,
    ApiRefreshTokenView,
    # Token Usage
    TokenUsageView,
    ApiTokenUsageToday,
    ApiTokenUsageStats,
    # LLM Config
    LLMConfigView,
    ApiLLMConfigView,
)

urlpatterns = [
    # Auth pages
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register.html', RegisterView.as_view(), name='register'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),

    # Token usage
    path('token-usage/', TokenUsageView.as_view(), name='token_usage'),
    path('llm-config/', LLMConfigView.as_view(), name='llm_config'),

    # API Auth
    path('api/auth/user/', ApiUserView.as_view(), name='api_user'),
    # path('api/auth/login/', ApiLoginView.as_view(), name='api_login'),
    # path('api/auth/logout/', ApiLogoutView.as_view(), name='api_logout'),
    # path('api/auth/register/', ApiRegisterView.as_view(), name='api_register'),
    path('api/auth/refresh/', ApiRefreshTokenView.as_view(), name='api_refresh'),

    # API Token
    path('api/token-usage/today/', ApiTokenUsageToday.as_view(), name='api_token_usage_today'),
    path('api/token-usage/stats/', ApiTokenUsageStats.as_view(), name='api_token_usage_stats'),

    # API LLM
    path('api/llm-config/', ApiLLMConfigView.as_view(), name='api_llm_config'),
]
