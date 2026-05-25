
from venv import logger
from django.shortcuts import render, redirect
from django.views import View
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken
from datetime import timedelta
from django.db import models

from novel_agent.authentication import JWTAuthentication

from .models import LLMConfig, UserLLMConfig, TokenUsageLog


# ============ Auth Views ============

class LoginView(APIView):
    '''登录视图'''

    authentication_classes = []     # 关闭所有认证
    permission_classes = [AllowAny]     # 允许所有人访问
    
    def get(self, request):
        return render(request, 'login.html')

    def post(self, request):
        try:
            username = request.data.get('username')
            password = request.data.get('password')

            user = authenticate(request, username=username, password=password)
            if user:
                # 生成 JWT token
                refresh = RefreshToken.for_user(user)
                return Response({
                    'success': True,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email
                    },
                    'access': str(refresh.access_token),
                    'refresh': str(refresh)
                })
            return Response({'success': False, 'message': '用户名或密码错误'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'登录视图报错: {e}')
            return Response({'success': False, 'message': 'internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LogoutView(APIView):
    '''注销视图'''

    authentication_classes = []
    permission_classes = []

    def post(self, request):
        logout(request)
       
        if request.content_type == 'text/html' or 'text/html' in request.META.get('HTTP_ACCEPT', ''):
            return redirect('login')
        
        # 如果是 API 请求 → 返回 JSON
        return Response({'success': True, 'message': '注销成功'})


class RegisterView(APIView):
    '''注册视图'''
    
    authentication_classes = []     # 关闭所有认证
    permission_classes = [AllowAny]     # 允许所有人访问

    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        try:
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')
            password_confirm = request.POST.get('password_confirm', '')

            if not username or not email or not password:
                return Response({'success': False, 'message': '请填写所有必填字段'}, status=status.HTTP_400_BAD_REQUEST)

            if password != password_confirm:
                return Response({'success': False, 'message': '两次输入的密码不一致'}, status=status.HTTP_400_BAD_REQUEST)

            if User.objects.filter(username=username).exists():
                return Response({'success': False, 'message': '用户名已被使用'}, status=status.HTTP_409_CONFLICT)

            if User.objects.filter(email=email).exists():
                return Response({'success': False, 'message': '该邮箱已被注册'}, status=status.HTTP_409_CONFLICT)

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            user.save()

            login(request, user)

            return Response({
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            })
        except Exception as e:
            logger.error(f'注册视图报错: {e}')
            return Response({'success': False, 'message': 'internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResetPasswordView(APIView):
    '''重置密码视图'''

    authentication_classes = []     # 关闭所有认证
    permission_classes = [AllowAny]     # 允许所有人访问

    def get(self, request):
        return render(request, 'reset_password.html')

    def post(self, request):
        try:
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')
            password_confirm = request.POST.get('password_confirm', '')

            if not username or not email or not password:
                return Response({'success': False, 'message': '请填写所有必填字段'}, status=status.HTTP_400_BAD_REQUEST)

            if password != password_confirm:
                return Response({'success': False, 'message': '两次输入的密码不一致'}, status=status.HTTP_400_BAD_REQUEST)

        
            user = User.objects.get(username=username, email=email)
            user.set_password(password)
            user.save()

            return Response({'success': True, 'message': '密码重置成功，请使用新密码登录'})
        except User.DoesNotExist:
            return Response({'success': False, 'message': '用户名或邮箱不正确'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f'重置密码失败: {e}')
            return Response({'success': False, 'message': '用户名或邮箱不正确'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApiRefreshTokenView(APIView):
    '''刷新Token'''

    authentication_classes = []     # 关闭所有认证
    permission_classes = [AllowAny]     # 允许所有人访问

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response({'success': False, 'message': '缺少 refresh token'}, status=status.HTTP_401_UNAUTHORIZED)

        
            refresh = RefreshToken(refresh_token)
            return Response({'success':True, 'access': str(refresh.access_token)})
        except InvalidToken:
            return Response({'success': False, 'message': '无效的 refresh token'}, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            logger.error(f'刷新token失败: {e}')
            return Response({'success': False, 'message': 'internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApiUserView(APIView):
    '''获取当前用户信息API'''

    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 尝试从请求头获取 token
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            from rest_framework_simplejwt.tokens import AccessToken
            from rest_framework_simplejwt.exceptions import InvalidToken
            try:
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                from django.contrib.auth.models import User
                user = User.objects.get(id=user_id)
                return JsonResponse({
                    'success': True,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email
                    }
                })
            except (InvalidToken, User.DoesNotExist):
                pass
        return JsonResponse({'success': False, 'error': '未登录'}, status=401)

# ============ Token Usage Views ============

class TokenUsageView(View):
    '''令牌使用视图'''
    def get(self, request):
        return render(request, 'token.html')


class ApiTokenUsageToday(APIView):
    '''今日令牌使用视图'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            today_usage = TokenUsageLog.get_daily_usage(request.user)
            return JsonResponse({'success': True, 'usage': today_usage})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiTokenUsageStats(APIView):
    '''令牌使用统计视图'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            time_range = request.GET.get('range', 'all')

            today = timezone.now().date()
            start_of_week = today - timedelta(days=7)
            start_of_month = today.replace(day=1)

            def get_logs_by_range(range_type):
                if range_type == 'today':
                    return TokenUsageLog.objects.filter(user=user, created_at__date=today)
                elif range_type == 'week':
                    return TokenUsageLog.objects.filter(user=user, created_at__date__gte=start_of_week)
                elif range_type == 'month':
                    return TokenUsageLog.objects.filter(user=user, created_at__date__gte=start_of_month)
                else:
                    return TokenUsageLog.objects.filter(user=user)

            def aggregate(logs):
                data = logs.aggregate(
                    prompt=models.Sum('prompt_tokens'),
                    prompt_hit=models.Sum('prompt_tokens', filter=models.Q(cache_hit=True)),
                    prompt_miss=models.Sum('prompt_tokens', filter=models.Q(cache_hit=False)),
                    completion=models.Sum('completion_tokens'),
                    total=models.Sum('total_tokens'),
                    hits=models.Count('id', filter=models.Q(cache_hit=True)),
                    misses=models.Count('id', filter=models.Q(cache_hit=False)),
                    count=models.Count('id')
                )
                return {
                    'prompt_tokens': data['prompt'] or 0,
                    'prompt_hit': data['prompt_hit'] or 0,
                    'prompt_miss': data['prompt_miss'] or 0,
                    'completion_tokens': data['completion'] or 0,
                    'total_tokens': data['total'] or 0,
                    'cache_hits': data['hits'] or 0,
                    'cache_misses': data['misses'] or 0,
                    'count': data['count'] or 0
                }

            today_logs = get_logs_by_range('today')
            week_logs = get_logs_by_range('week')
            month_logs = get_logs_by_range('month')
            all_logs = get_logs_by_range('all')

            today_usage = aggregate(today_logs)
            week_usage = aggregate(week_logs)
            month_usage = aggregate(month_logs)
            all_usage = aggregate(all_logs)

            current_logs = get_logs_by_range(time_range)
            recent_logs = list(current_logs.order_by('-created_at')[:100].values(
                'created_at', 'task_type', 'project__title',
                'prompt_tokens', 'completion_tokens', 'total_tokens', 'cache_hit'
            ))

            for log in recent_logs:
                log['created_at'] = log['created_at'].strftime('%Y-%m-%d %H:%M')
                log['task_type'] = log['task_type'] or 'other'
                log['project'] = log['project__title'] or '-'

            project_stats = {}
            project_logs = all_logs.filter(project__isnull=False).select_related('project')
            for log in project_logs:
                project_id = log.project_id
                project_title = log.project.title
                if project_id not in project_stats:
                    project_stats[project_id] = {
                        'project_id': project_id,
                        'project_title': project_title,
                        'prompt_tokens': 0,
                        'prompt_hit': 0,
                        'prompt_miss': 0,
                        'completion_tokens': 0,
                        'total_tokens': 0,
                        'cache_hits': 0,
                        'cache_misses': 0,
                        'count': 0
                    }
                project_stats[project_id]['prompt_tokens'] += log.prompt_tokens
                if log.cache_hit:
                    project_stats[project_id]['prompt_hit'] += log.prompt_tokens
                    project_stats[project_id]['cache_hits'] += 1
                else:
                    project_stats[project_id]['prompt_miss'] += log.prompt_tokens
                    project_stats[project_id]['cache_misses'] += 1
                project_stats[project_id]['completion_tokens'] += log.completion_tokens
                project_stats[project_id]['total_tokens'] += log.total_tokens
                project_stats[project_id]['count'] += 1

            project_list = sorted(project_stats.values(), key=lambda x: x['total_tokens'], reverse=True)

            return JsonResponse({
                'success': True,
                'usage': {
                    'today': today_usage,
                    'week': week_usage,
                    'month': month_usage,
                    'all': all_usage,
                    'logs': recent_logs,
                    'project_stats': project_list
                }
            })
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'error': str(e)})


# ============ LLM Config Views ============

class LLMConfigView(View):
    '''LLM配置视图'''
    def get(self, request):
        # 页面只负责渲染 HTML，数据由前端通过 API 获取
        # 这样未登录用户也能访问页面，然后由前端处理登录
        return render(request, 'llm_config.html')

    def post(self, request):
        action = request.POST.get('action')

        if action == 'create':
            name = request.POST.get('name')
            provider = request.POST.get('provider')
            api_key = request.POST.get('api_key')
            base_url = request.POST.get('base_url', '')
            model_name = request.POST.get('model_name')
            temperature = float(request.POST.get('temperature', 0.7))
            max_tokens = int(request.POST.get('max_tokens', 4096))
            is_default = request.POST.get('is_default') == 'on'

            if is_default:
                LLMConfig.objects.filter(user=request.user, is_default=True).update(is_default=False)

            config = LLMConfig.objects.create(
                user=request.user,
                name=name,
                provider=provider,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                is_default=is_default
            )
            if base_url:
                config.base_url = base_url
            config.set_api_key(api_key)
            config.save()

        elif action == 'set_task':
            task_type = request.POST.get('task_type')
            config_id = request.POST.get('config_id')

            temperature = request.POST.get('temperature')
            max_tokens = request.POST.get('max_tokens')

            defaults = {'llm_config_id': config_id}
            if temperature:
                defaults['temperature'] = float(temperature)
            if max_tokens:
                defaults['max_tokens'] = int(max_tokens)

            task_config, created = UserLLMConfig.objects.update_or_create(
                user=request.user,
                task_type=task_type,
                defaults=defaults
            )

        elif action == 'delete':
            config_id = request.POST.get('config_id')
            config = LLMConfig.objects.get(pk=config_id, user=request.user)
            config.delete()

        return redirect('llm_config')


class ApiLLMConfigView(APIView):
    '''LLM配置API'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        configs = LLMConfig.objects.filter(user=request.user)
        task_configs = UserLLMConfig.objects.filter(user=request.user)

        configs_data = []
        for config in configs:
            configs_data.append({
                'id': config.id,
                'name': config.name,
                'provider': config.provider,
                'model_name': config.model_name,
                'temperature': config.temperature,
                'max_tokens': config.max_tokens,
                'is_default': config.is_default,
                'is_active': getattr(config, 'is_active', True),
                'base_url': config.base_url
            })

        task_configs_data = []
        for tc in task_configs:
            task_configs_data.append({
                'task_type': tc.task_type,
                'llm_config_id': tc.llm_config_id,
                'temperature': tc.temperature,
                'max_tokens': tc.max_tokens
            })

        return JsonResponse({
            'success': True,
            'configs': configs_data,
            'task_configs': task_configs_data,
            'provider_choices': LLMConfig.PROVIDER_CHOICES,
            'task_choices': UserLLMConfig.TASK_CHOICES
        })

    def post(self, request):
        try:
            action = request.data.get('action')

            if action == 'create':
                name = request.data.get('name')
                provider = request.data.get('provider')
                api_key = request.data.get('api_key')
                base_url = request.data.get('base_url', '')
                model_name = request.data.get('model_name')
                temperature = float(request.data.get('temperature', 0.7))
                max_tokens = int(request.data.get('max_tokens', 4096))
                is_default = request.data.get('is_default') == True or request.data.get('is_default') == 'true'

                if is_default:
                    LLMConfig.objects.filter(user=request.user, is_default=True).update(is_default=False)

                config = LLMConfig.objects.create(
                    user=request.user,
                    name=name,
                    provider=provider,
                    model_name=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    is_default=is_default
                )
                if base_url:
                    config.base_url = base_url
                config.set_api_key(api_key)
                config.save()

                return JsonResponse({'success': True, 'config_id': config.id})

            elif action == 'set_task':
                task_type = request.data.get('task_type')
                config_id = request.data.get('config_id')

                temperature = request.data.get('temperature')
                max_tokens = request.data.get('max_tokens')

                defaults = {'llm_config_id': config_id}
                if temperature:
                    defaults['temperature'] = float(temperature)
                if max_tokens:
                    defaults['max_tokens'] = int(max_tokens)

                task_config, created = UserLLMConfig.objects.update_or_create(
                    user=request.user,
                    task_type=task_type,
                    defaults=defaults
                )

                return JsonResponse({'success': True})

            elif action == 'delete':
                config_id = request.data.get('config_id')
                config = LLMConfig.objects.get(pk=config_id, user=request.user)
                config.delete()
                return JsonResponse({'success': True})

            elif action == 'toggle_active':
                config_id = request.data.get('config_id')
                is_active = request.data.get('is_active')
                config = LLMConfig.objects.get(pk=config_id, user=request.user)
                config.is_active = is_active
                config.save()
                return JsonResponse({'success': True})

            elif action == 'update':
                config_id = request.data.get('config_id')
                config = LLMConfig.objects.get(pk=config_id, user=request.user)

                name = request.data.get('name')
                provider = request.data.get('provider')
                api_key = request.data.get('api_key')
                base_url = request.data.get('base_url', '')
                model_name = request.data.get('model_name')
                temperature = float(request.data.get('temperature', 0.7))
                max_tokens = int(request.data.get('max_tokens', 4096))
                is_default = request.data.get('is_default') == True or request.data.get('is_default') == 'true'

                if is_default:
                    LLMConfig.objects.filter(user=request.user, is_default=True).update(is_default=False)

                config.name = name
                config.provider = provider
                config.model_name = model_name
                config.temperature = temperature
                config.max_tokens = max_tokens
                config.is_default = is_default
                config.base_url = base_url

                if api_key:
                    config.set_api_key(api_key)

                config.save()

                return JsonResponse({'success': True})

            return JsonResponse({'success': False, 'message': '无效的操作'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
