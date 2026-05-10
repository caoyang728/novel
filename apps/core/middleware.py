from django.shortcuts import redirect
from django.conf import settings


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 不需要登录的路径
        allowed_paths = [
            settings.LOGIN_URL,
            '/register/',
            '/reset-password/',
            '/admin/',
            '/api/auth/login/',
            '/api/auth/register/',
        ]
        
        # 检查是否是允许的路径
        path = request.path
        allowed = False
        for allowed_path in allowed_paths:
            if path.startswith(allowed_path):
                allowed = True
                break
        
        # 如果未登录且不允许访问，则重定向到登录页
        if not request.user.is_authenticated and not allowed:
            return redirect(f'{settings.LOGIN_URL}?next={request.path}')
        
        # 继续处理请求
        response = self.get_response(request)
        return response
