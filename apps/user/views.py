
from loguru import logger
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

from .models import LLMConfig, UserLLMConfig, TokenUsageLog, UserEmbeddingConfig
from .rsa_utils import get_public_key_pem, decrypt_password


def _test_llm_connection(api_key, base_url, model_name):
    """测试LLM连接是否可用，返回 (success, message)"""
    import requests
    
    # 构建请求URL
    url = f"{base_url.rstrip('/')}/chat/completions" if base_url else "https://api.openai.com/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model_name,
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 10
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        data = response.json()
        
        # 调试日志
        print(f"[LLM测试] URL: {url}")
        print(f"[LLM测试] Model: {model_name}")
        print(f"[LLM测试] Status: {response.status_code}")
        print(f"[LLM测试] Response: {data}")
        
        if response.status_code == 200:
            # 检查是否有有效的响应内容
            choices = data.get('choices', [])
            if choices:
                message = choices[0].get('message', {})
                content = message.get('content', '')
                # MiMo 等推理模型可能返回 reasoning_content
                reasoning = message.get('reasoning_content', '')
                if content or reasoning:
                    return True, '连接成功'
                # 有 choices 但内容为空，也算连接成功
                return True, '连接成功（响应内容为空）'
            return False, '响应格式异常'
        else:
            error_msg = data.get('error', {}).get('message', '')
            if not error_msg:
                error_msg = str(data)[:100]
            
            if response.status_code == 401:
                return False, 'API密钥无效'
            elif response.status_code == 404:
                return False, '模型不存在'
            elif response.status_code == 429:
                return True, '连接成功（限流中）'
            return False, f'请求失败: {error_msg}'
    except requests.exceptions.Timeout:
        return False, '连接超时'
    except requests.exceptions.ConnectionError:
        return False, '无法连接到API地址'
    except Exception as e:
        return False, str(e)[:100]


def sync_default_task_config(user, llm_config):
    """将默认模型配置同步到'默认'任务场景"""
    UserLLMConfig.objects.update_or_create(
        user=user,
        task_type='default',
        defaults={
            'llm_config': llm_config,
            'temperature': None,
            'max_tokens': None,
        }
    )


def clear_default_task_config(user):
    """清除'默认'任务场景配置"""
    UserLLMConfig.objects.filter(user=user, task_type='default').delete()


# ============ Auth Views ============

class RSAPublicKeyView(APIView):
    '''获取 RSA 公钥'''

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            public_key = get_public_key_pem()
            return Response({'success': True, 'public_key': public_key})
        except Exception as e:
            logger.error(f'获取RSA公钥失败: {e}')
            return Response({'success': False, 'message': '获取公钥失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def _extract_password(request, field='password'):
    """从请求中提取密码，支持 RSA 加密和明文两种格式"""
    encrypted = request.data.get(f'{field}_encrypted')
    if encrypted:
        try:
            return decrypt_password(encrypted)
        except Exception as e:
            logger.error(f'RSA解密失败: {e}')
            raise ValueError('密码解密失败')
    return request.data.get(field)


class LoginView(APIView):
    '''登录视图'''

    authentication_classes = []     # 关闭所有认证
    permission_classes = [AllowAny]     # 允许所有人访问
    
    def get(self, request):
        return render(request, 'login.html')

    def post(self, request):
        try:
            username = request.data.get('username')
            try:
                password = _extract_password(request)
            except ValueError as e:
                return Response({'success': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
            username = request.data.get('username', '').strip()
            email = request.data.get('email', '').strip()
            try:
                password = _extract_password(request)
                password_confirm = _extract_password(request, field='password_confirm')
            except ValueError as e:
                return Response({'success': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
            username = request.data.get('username', '').strip()
            email = request.data.get('email', '').strip()
            try:
                password = _extract_password(request)
                password_confirm = _extract_password(request, field='password_confirm')
            except ValueError as e:
                return Response({'success': False, 'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

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
        user = request.user
        return JsonResponse({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'has_llm_config': LLMConfig.objects.filter(user=user, is_active=True, test_passed=True).exists()
            }
        })

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

            today = timezone.localtime().date()
            start_of_week = today - timedelta(days=7)
            start_of_month = today.replace(day=1)

            # 按日期分桶：用一个查询获取所有日志，Python 端分桶
            # 比 4 个独立的 DB 聚合查询高效得多
            all_logs = TokenUsageLog.objects.filter(user=user)
            logs_data = list(all_logs.values(
                'created_at', 'project_id',
                'input_tokens', 'output_tokens', 'total_tokens',
                'input_cache_hit_tokens', 'input_cache_miss_tokens', 'cost'
            ))

            def _make_empty():
                return {
                    'input_tokens': 0, 'input_cache_hit_tokens': 0,
                    'input_cache_miss_tokens': 0, 'output_tokens': 0,
                    'total_tokens': 0, 'cost': 0.0, 'count': 0
                }

            today_usage = _make_empty()
            week_usage = _make_empty()
            month_usage = _make_empty()
            all_usage = _make_empty()
            recent_logs = []

            for log in logs_data:
                log_date = timezone.localtime(log['created_at']).date()
                # 累加 all
                all_usage['input_tokens'] += log['input_tokens']
                all_usage['input_cache_hit_tokens'] += log['input_cache_hit_tokens']
                all_usage['input_cache_miss_tokens'] += log['input_cache_miss_tokens']
                all_usage['output_tokens'] += log['output_tokens']
                all_usage['total_tokens'] += log['total_tokens']
                all_usage['cost'] += float(log['cost'])
                all_usage['count'] += 1
                # 累加 today
                if log_date == today:
                    today_usage['input_tokens'] += log['input_tokens']
                    today_usage['input_cache_hit_tokens'] += log['input_cache_hit_tokens']
                    today_usage['input_cache_miss_tokens'] += log['input_cache_miss_tokens']
                    today_usage['output_tokens'] += log['output_tokens']
                    today_usage['total_tokens'] += log['total_tokens']
                    today_usage['cost'] += float(log['cost'])
                    today_usage['count'] += 1
                # 累加 week
                if log_date >= start_of_week:
                    week_usage['input_tokens'] += log['input_tokens']
                    week_usage['input_cache_hit_tokens'] += log['input_cache_hit_tokens']
                    week_usage['input_cache_miss_tokens'] += log['input_cache_miss_tokens']
                    week_usage['output_tokens'] += log['output_tokens']
                    week_usage['total_tokens'] += log['total_tokens']
                    week_usage['cost'] += float(log['cost'])
                    week_usage['count'] += 1
                # 累加 month
                if log_date >= start_of_month:
                    month_usage['input_tokens'] += log['input_tokens']
                    month_usage['input_cache_hit_tokens'] += log['input_cache_hit_tokens']
                    month_usage['input_cache_miss_tokens'] += log['input_cache_miss_tokens']
                    month_usage['output_tokens'] += log['output_tokens']
                    month_usage['total_tokens'] += log['total_tokens']
                    month_usage['cost'] += float(log['cost'])
                    month_usage['count'] += 1

            # 最近日志：取 100 条最新记录
            recent_qs = list(all_logs.order_by('-created_at')[:100].values(
                'created_at', 'task_type', 'project__title',
                'input_tokens', 'output_tokens', 'total_tokens',
                'input_cache_hit_tokens', 'input_cache_miss_tokens', 'cost'
            ))
            for log in recent_qs:
                log['created_at'] = timezone.localtime(log['created_at']).strftime('%Y-%m-%d %H:%M')
                log['task_type'] = log['task_type'] or 'other'
                log['project'] = log['project__title'] or '-'

            # 项目统计：数据库端 GROUP BY 聚合，避免 Python 遍历全表
            project_agg = list(all_logs.filter(
                project__isnull=False
            ).values(
                'project_id', 'project__title'
            ).annotate(
                input_tokens=models.Sum('input_tokens'),
                input_cache_hit_tokens=models.Sum('input_cache_hit_tokens'),
                input_cache_miss_tokens=models.Sum('input_cache_miss_tokens'),
                output_tokens=models.Sum('output_tokens'),
                total_tokens=models.Sum('total_tokens'),
                cost=models.Sum('cost'),
                count=models.Count('id'),
            ).order_by('-total_tokens'))

            for p in project_agg:
                p['project_title'] = p.pop('project__title') or '-'
                p['cost'] = float(p['cost'] or 0)

            return JsonResponse({
                'success': True,
                'usage': {
                    'today': today_usage,
                    'week': week_usage,
                    'month': month_usage,
                    'all': all_usage,
                    'logs': recent_qs,
                    'project_stats': project_agg
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

            # 首次添加自动设为默认
            if not LLMConfig.objects.filter(user=request.user).exists():
                is_default = True

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

            if is_default:
                sync_default_task_config(request.user, config)

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

            if task_type == 'default' and config_id:
                LLMConfig.objects.filter(user=request.user, is_default=True).exclude(pk=config_id).update(is_default=False)
                LLMConfig.objects.filter(pk=config_id, user=request.user).update(is_default=True)

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
                'base_url': config.base_url,
                'input_price': config.input_price,
                'output_price': config.output_price,
                'cache_hit_price': config.cache_hit_price
            })

        task_configs_data = []
        for tc in task_configs:
            task_configs_data.append({
                'task_type': tc.task_type,
                'llm_config_id': tc.llm_config_id,
                'temperature': tc.temperature,
                'max_tokens': tc.max_tokens
            })

        # 返回分组场景配置，供前端展示所有场景（含未配置的）
        from agent.llm_scenes import get_grouped_scenes
        grouped_scenes = get_grouped_scenes()

        return JsonResponse({
            'success': True,
            'configs': configs_data,
            'task_configs': task_configs_data,
            'grouped_scenes': grouped_scenes,
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
                input_price = float(request.data.get('input_price', 0))
                output_price = float(request.data.get('output_price', 0))
                cache_hit_price = float(request.data.get('cache_hit_price', 0))
                is_default = request.data.get('is_default') == True or request.data.get('is_default') == 'true'

                # 首次添加自动设为默认
                if not LLMConfig.objects.filter(user=request.user).exists():
                    is_default = True

                if is_default:
                    LLMConfig.objects.filter(user=request.user, is_default=True).update(is_default=False)

                config = LLMConfig.objects.create(
                    user=request.user,
                    name=name,
                    provider=provider,
                    model_name=model_name,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    input_price=input_price,
                    output_price=output_price,
                    cache_hit_price=cache_hit_price,
                    is_default=is_default
                )
                if base_url:
                    config.base_url = base_url
                config.set_api_key(api_key)
                config.save()

                # 同步到 default 任务场景
                if is_default:
                    sync_default_task_config(request.user, config)

                return JsonResponse({'success': True, 'config_id': config.id})

            elif action == 'set_task':
                task_type = request.data.get('task_type')
                config_id = request.data.get('config_id')

                temperature = request.data.get('temperature')
                max_tokens = request.data.get('max_tokens')

                defaults = {'llm_config_id': config_id}
                # null/空字符串 → 存 None，表示继承场景默认
                if temperature is not None and temperature != '':
                    defaults['temperature'] = float(temperature)
                else:
                    defaults['temperature'] = None
                if max_tokens is not None and max_tokens != '':
                    defaults['max_tokens'] = int(max_tokens)
                else:
                    defaults['max_tokens'] = None

                task_config, created = UserLLMConfig.objects.update_or_create(
                    user=request.user,
                    task_type=task_type,
                    defaults=defaults
                )

                # default 任务场景与默认模型配置双向同步
                if task_type == 'default' and config_id:
                    LLMConfig.objects.filter(user=request.user, is_default=True).exclude(pk=config_id).update(is_default=False)
                    LLMConfig.objects.filter(pk=config_id, user=request.user).update(is_default=True)

                return JsonResponse({'success': True})

            elif action == 'delete':
                config_id = request.data.get('config_id')
                config = LLMConfig.objects.get(pk=config_id, user=request.user)
                was_default = config.is_default
                config.delete()
                if was_default:
                    clear_default_task_config(request.user)
                return JsonResponse({'success': True})

            elif action == 'toggle_active':
                config_id = request.data.get('config_id')
                is_active = request.data.get('is_active')
                config = LLMConfig.objects.get(pk=config_id, user=request.user)
                config.is_active = is_active
                config.save()
                # 如果停用的是默认配置，清除 default 任务场景绑定
                if config.is_default and not is_active:
                    clear_default_task_config(request.user)
                return JsonResponse({'success': True})

            elif action == 'test_connection':
                config_id = request.data.get('config_id')
                try:
                    config = LLMConfig.objects.get(pk=config_id, user=request.user)
                    api_key = config.get_api_key()
                    if not api_key:
                        return JsonResponse({'success': False, 'message': '未配置API密钥'})
                    success, message = _test_llm_connection(api_key, config.base_url, config.model_name)
                    if success:
                        config.test_passed = True
                        config.save(update_fields=['test_passed'])
                    return JsonResponse({'success': success, 'message': message})
                except LLMConfig.DoesNotExist:
                    return JsonResponse({'success': False, 'message': '配置不存在'})

            elif action == 'test_connection_params':
                # 弹窗中测试：使用表单参数而非已保存配置
                api_key = request.data.get('api_key', '')
                base_url = request.data.get('base_url', '')
                model_name = request.data.get('model_name', '')
                if not api_key:
                    return JsonResponse({'success': False, 'message': '请先填写API密钥'})
                if not model_name:
                    return JsonResponse({'success': False, 'message': '请先填写模型名称'})
                success, message = _test_llm_connection(api_key, base_url, model_name)
                return JsonResponse({'success': success, 'message': message})

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
                input_price = float(request.data.get('input_price', 0))
                output_price = float(request.data.get('output_price', 0))
                cache_hit_price = float(request.data.get('cache_hit_price', 0))
                is_default = request.data.get('is_default') == True or request.data.get('is_default') == 'true'

                if is_default:
                    LLMConfig.objects.filter(user=request.user, is_default=True).update(is_default=False)

                config.name = name
                config.provider = provider
                config.model_name = model_name
                config.temperature = temperature
                config.max_tokens = max_tokens
                config.input_price = input_price
                config.output_price = output_price
                config.cache_hit_price = cache_hit_price
                config.is_default = is_default
                config.base_url = base_url

                if api_key:
                    config.set_api_key(api_key)
                    # API 密钥变更后需要重新测试
                    config.test_passed = False

                config.save()

                # 同步到 default 任务场景
                if is_default:
                    sync_default_task_config(request.user, config)
                elif not LLMConfig.objects.filter(user=request.user, is_default=True).exists():
                    clear_default_task_config(request.user)

                return JsonResponse({'success': True})

            return JsonResponse({'success': False, 'message': '无效的操作'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})


def _test_embedding_api(api_key, base_url, model):
    """测试 Embedding API 连通性，返回 (success, message)"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.embeddings.create(input="测试文本", model=model)
        dim = len(response.data[0].embedding)
        return True, f'连接成功 (维度: {dim})'
    except Exception as e:
        return False, str(e)[:200]


def _test_embedding_docker(docker_url, timeout):
    """测试 Embedding Docker 服务连通性，返回 (success, message)"""
    import requests
    try:
        health_url = docker_url.rsplit("/", 1)[0] + "/health"
        resp = requests.get(health_url, timeout=min(timeout, 5))
        resp.raise_for_status()
        info = resp.json()
        model = info.get('model', 'unknown')
        # 实际测试 embed
        resp2 = requests.post(docker_url, json={"texts": ["测试文本"]}, timeout=timeout)
        resp2.raise_for_status()
        embeddings = resp2.json().get("embeddings", [])
        dim = len(embeddings[0]) if embeddings else 0
        return True, f'连接成功 (模型: {model}, 维度: {dim})'
    except requests.exceptions.Timeout:
        return False, '连接超时'
    except requests.exceptions.ConnectionError:
        return False, '无法连接到Docker服务'
    except Exception as e:
        return False, str(e)[:200]


def _test_rerank_api(api_key, base_url, model):
    """测试 Rerank API 连通性，返回 (success, message)"""
    import requests
    try:
        url = f"{base_url.rstrip('/')}/rerank"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "query": "测试查询",
            "documents": ["测试文档1", "测试文档2"],
            "top_n": 2,
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get('results', [])
            return True, f'连接成功 (返回 {len(results)} 条结果)'
        else:
            error_msg = resp.json().get('error', {}).get('message', str(resp.text)[:100])
            return False, f'请求失败: {error_msg}'
    except requests.exceptions.Timeout:
        return False, '连接超时'
    except requests.exceptions.ConnectionError:
        return False, '无法连接到API地址'
    except Exception as e:
        return False, str(e)[:200]


def _test_rerank_docker(docker_url, timeout):
    """测试 Rerank Docker 服务连通性，返回 (success, message)"""
    import requests
    try:
        health_url = docker_url.rsplit("/", 1)[0] + "/health"
        resp = requests.get(health_url, timeout=min(timeout, 5))
        resp.raise_for_status()
        info = resp.json()
        model = info.get('model', 'unknown')
        # 实际测试 rerank
        resp2 = requests.post(docker_url, json={
            "query": "测试查询",
            "documents": ["测试文档1", "测试文档2"],
            "top_n": 2,
        }, timeout=timeout)
        resp2.raise_for_status()
        return True, f'连接成功 (模型: {model})'
    except requests.exceptions.Timeout:
        return False, '连接超时'
    except requests.exceptions.ConnectionError:
        return False, '无法连接到Docker服务'
    except Exception as e:
        return False, str(e)[:200]


class ApiEmbeddingConfigView(APIView):
    """Embedding / Rerank 配置 API"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """获取当前用户的 Embedding/Rerank 配置"""
        config = UserEmbeddingConfig.get_or_default(request.user)
        data = {
            'embedding_mode': config.embedding_mode,
            'embedding_api_base_url': config.embedding_api_base_url,
            'embedding_api_model': config.embedding_api_model,
            'embedding_docker_url': config.embedding_docker_url,
            'embedding_docker_timeout': config.embedding_docker_timeout,
            'rerank_mode': config.rerank_mode,
            'rerank_api_base_url': config.rerank_api_base_url,
            'rerank_api_model': config.rerank_api_model,
            'rerank_docker_url': config.rerank_docker_url,
            'rerank_docker_timeout': config.rerank_docker_timeout,
        }
        # API key 只返回是否已设置（不返回明文）
        data['has_embedding_api_key'] = bool(config.embedding_api_key)
        data['has_rerank_api_key'] = bool(config.rerank_api_key)
        return JsonResponse({'success': True, 'config': data})

    def post(self, request):
        try:
            action = request.data.get('action')

            if action == 'save':
                return self._save_config(request)
            elif action == 'test':
                return self._test_connection(request)
            else:
                return JsonResponse({'success': False, 'message': '无效的操作'})
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})

    def _save_config(self, request):
        user = request.user
        config, _ = UserEmbeddingConfig.objects.get_or_create(user=user)

        # Embedding 配置
        embedding_mode = request.data.get('embedding_mode', config.embedding_mode)
        config.embedding_mode = embedding_mode
        config.embedding_api_base_url = request.data.get('embedding_api_base_url', '')
        config.embedding_api_model = request.data.get('embedding_api_model', '')
        config.embedding_docker_url = request.data.get('embedding_docker_url', '')
        config.embedding_docker_timeout = int(request.data.get('embedding_docker_timeout', 30))

        # 支持 RSA 加密的 API key
        embedding_api_key_encrypted = request.data.get('embedding_api_key_encrypted', '')
        if embedding_api_key_encrypted:
            try:
                embedding_api_key = decrypt_password(embedding_api_key_encrypted)
                config.set_embedding_api_key(embedding_api_key)
            except Exception as e:
                logger.error(f'解密 Embedding API key 失败: {e}')
                return JsonResponse({'success': False, 'message': 'API密钥解密失败'})
        else:
            embedding_api_key = request.data.get('embedding_api_key', '')
            if embedding_api_key:
                config.set_embedding_api_key(embedding_api_key)

        # Rerank 配置
        rerank_mode = request.data.get('rerank_mode', config.rerank_mode)
        config.rerank_mode = rerank_mode
        config.rerank_api_base_url = request.data.get('rerank_api_base_url', '')
        config.rerank_api_model = request.data.get('rerank_api_model', '')
        config.rerank_docker_url = request.data.get('rerank_docker_url', '')
        config.rerank_docker_timeout = int(request.data.get('rerank_docker_timeout', 30))

        # 支持 RSA 加密的 API key
        rerank_api_key_encrypted = request.data.get('rerank_api_key_encrypted', '')
        if rerank_api_key_encrypted:
            try:
                rerank_api_key = decrypt_password(rerank_api_key_encrypted)
                config.set_rerank_api_key(rerank_api_key)
            except Exception as e:
                logger.error(f'解密 Rerank API key 失败: {e}')
                return JsonResponse({'success': False, 'message': 'API密钥解密失败'})
        else:
            rerank_api_key = request.data.get('rerank_api_key', '')
            if rerank_api_key:
                config.set_rerank_api_key(rerank_api_key)

        config.save()

        # 配置变更后清除缓存的 Embedder/Reranker 单例，下次调用会重新创建
        from apps.knowledge.embedder import EmbedderFactory
        from apps.knowledge.reranker import RerankerFactory
        EmbedderFactory.reset()
        RerankerFactory.reset()

        return JsonResponse({'success': True, 'message': '保存成功'})

    def _test_connection(self, request):
        """测试 embedding/rerank 连接"""
        test_type = request.data.get('test_type', 'embedding')

        if test_type == 'embedding':
            mode = request.data.get('embedding_mode', 'api_only')
            if mode == 'disabled':
                return JsonResponse({'success': True, 'message': 'Embedding 已关闭'})
            # 先保存的配置中读取，或用请求中的临时参数
            # 支持 RSA 加密的 API key
            api_key_encrypted = request.data.get('embedding_api_key_encrypted', '')
            if api_key_encrypted:
                try:
                    api_key = decrypt_password(api_key_encrypted)
                except Exception as e:
                    logger.error(f'解密 Embedding API key 失败: {e}')
                    return JsonResponse({'success': False, 'message': 'API密钥解密失败'})
            else:
                api_key = request.data.get('embedding_api_key', '')
            base_url = request.data.get('embedding_api_base_url', '')
            model = request.data.get('embedding_api_model', '')
            docker_url = request.data.get('embedding_docker_url', '')
            docker_timeout = int(request.data.get('embedding_docker_timeout', 30))

            # 如果临时参数为空，尝试从已保存配置读取
            if not api_key or not base_url or not model or not docker_url:
                config = UserEmbeddingConfig.get_or_default(request.user)
                if not api_key and config.embedding_api_key:
                    api_key = config.get_embedding_api_key()
                if not base_url and config.embedding_api_base_url:
                    base_url = config.embedding_api_base_url
                if not model and config.embedding_api_model:
                    model = config.embedding_api_model
                if not docker_url and config.embedding_docker_url:
                    docker_url = config.embedding_docker_url
                if docker_timeout == 30 and config.embedding_docker_timeout:
                    docker_timeout = config.embedding_docker_timeout

            results = {}
            if mode in ('api_only', 'api_first', 'docker_first'):
                if api_key and base_url and model:
                    success, msg = _test_embedding_api(api_key, base_url, model)
                    results['api'] = {'success': success, 'message': msg}
                else:
                    results['api'] = {'success': False, 'message': '缺少 API 配置参数'}

            if mode in ('docker_only', 'docker_first', 'api_first'):
                if docker_url:
                    success, msg = _test_embedding_docker(docker_url, docker_timeout)
                    results['docker'] = {'success': success, 'message': msg}
                else:
                    results['docker'] = {'success': False, 'message': '缺少 Docker 地址'}

            # 单一模式返回简洁结果
            if mode == 'api_only':
                return JsonResponse(results.get('api', {'success': False, 'message': '未配置'}))
            elif mode == 'docker_only':
                return JsonResponse(results.get('docker', {'success': False, 'message': '未配置'}))
            return JsonResponse({'success': True, 'results': results})

        elif test_type == 'rerank':
            mode = request.data.get('rerank_mode', 'disabled')
            if mode == 'disabled':
                return JsonResponse({'success': True, 'message': 'Rerank 已关闭'})

            # 支持 RSA 加密的 API key
            api_key_encrypted = request.data.get('rerank_api_key_encrypted', '')
            if api_key_encrypted:
                try:
                    api_key = decrypt_password(api_key_encrypted)
                except Exception as e:
                    logger.error(f'解密 Rerank API key 失败: {e}')
                    return JsonResponse({'success': False, 'message': 'API密钥解密失败'})
            else:
                api_key = request.data.get('rerank_api_key', '')
            base_url = request.data.get('rerank_api_base_url', '')
            model = request.data.get('rerank_api_model', '')
            docker_url = request.data.get('rerank_docker_url', '')
            docker_timeout = int(request.data.get('rerank_docker_timeout', 30))

            if not api_key or not base_url or not model or not docker_url:
                config = UserEmbeddingConfig.get_or_default(request.user)
                if not api_key and config.rerank_api_key:
                    api_key = config.get_rerank_api_key()
                if not base_url and config.rerank_api_base_url:
                    base_url = config.rerank_api_base_url
                if not model and config.rerank_api_model:
                    model = config.rerank_api_model
                if not docker_url and config.rerank_docker_url:
                    docker_url = config.rerank_docker_url
                if docker_timeout == 30 and config.rerank_docker_timeout:
                    docker_timeout = config.rerank_docker_timeout

            results = {}
            if mode in ('api_only', 'api_first', 'docker_first'):
                if api_key and base_url and model:
                    success, msg = _test_rerank_api(api_key, base_url, model)
                    results['api'] = {'success': success, 'message': msg}
                else:
                    results['api'] = {'success': False, 'message': '缺少 API 配置参数'}

            if mode in ('docker_only', 'docker_first', 'api_first'):
                if docker_url:
                    success, msg = _test_rerank_docker(docker_url, docker_timeout)
                    results['docker'] = {'success': success, 'message': msg}
                else:
                    results['docker'] = {'success': False, 'message': '缺少 Docker 地址'}

            if mode == 'api_only':
                return JsonResponse(results.get('api', {'success': False, 'message': '未配置'}))
            elif mode == 'docker_only':
                return JsonResponse(results.get('docker', {'success': False, 'message': '未配置'}))
            return JsonResponse({'success': True, 'results': results})

        return JsonResponse({'success': False, 'message': '无效的测试类型'})
