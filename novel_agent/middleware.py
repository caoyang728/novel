from django.http import JsonResponse
from django.shortcuts import redirect
from django.conf import settings
import json


def _authenticate_jwt(request):
    """
    尝试从请求头解析 JWT token，返回用户或 None
    """
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return None

    token = auth_header[7:]
    if not token:
        return None

    from rest_framework_simplejwt.tokens import AccessToken
    from rest_framework_simplejwt.exceptions import InvalidToken
    from django.contrib.auth.models import User

    try:
        access_token = AccessToken(token)
        user_id = access_token['user_id']
        user = User.objects.get(id=user_id)
        return user
    except (InvalidToken, User.DoesNotExist, Exception):
        return None


class JWTAuthenticationMiddleware:
    """
    JWT 认证中间件
    - API 请求：强制 JWT 认证，无 token 返回 401
    - 页面请求：无 token 重定向登录页，有 token 放行
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # API 认证路径放行（登录、刷新 token 等）
        api_auth_paths = [
            '/api/auth/refresh/',
        ]
        if any(path.startswith(p) for p in api_auth_paths):
            return self.get_response(request)

        # 尝试 JWT 认证
        user = _authenticate_jwt(request)

        if user:
            request.user = user

        # API 请求必须有有效 token
        if path.startswith('/api/'):
            if not user:
                return JsonResponse({'success': False, 'error': '请先登录'}, status=401)
            return self.get_response(request)

        # 页面请求处理
        public_pages = [
            '/login/',
            '/reset-password/',
            '/admin/',
            '/static/',
            '/',  # 根路径（会重定向到 index.html）
            '/index.html',  # index.html 公开，前端检查认证
            '/project.html',
            '/outline.html',
            '/token.html',
            '/llm_config.html',
            '/volume.html',
            '/content.html',
            '/worldview_builder.html',
            '/character.html',
            '/chapter.html',
            '/register.html',
            '/reset_password.html',
            '/login.html',
        ]

        if any(path.startswith(p) for p in public_pages):
            return self.get_response(request)

        # 无 token 且非公开页面 → 重定向登录
        if not user:
            return redirect(f'{settings.LOGIN_URL}?next={request.path}')

        return self.get_response(request)


class LoginRequiredMiddleware:
    """
    已废弃，功能合并到 JWTAuthenticationMiddleware
    保留此类以避免 settings.py 报错
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)
