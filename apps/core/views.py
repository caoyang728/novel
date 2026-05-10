import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from datetime import timedelta
from .models import Project, OutlineVersion, VolumeVersion, Volume, ChapterVersion, Chapter, LLMConfig, UserLLMConfig, TokenUsageLog

from apps.ai.services import LLMService


class LoginView(View):
    '''登录视图'''
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return render(request, 'login.html')
    
    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get('next', '')
            if not next_url or next_url.startswith('/login') or next_url.startswith('/api/auth'):
                return redirect('/index.html')
            return redirect(next_url)
        return render(request, 'login.html', {
            'error': '用户名或密码错误'
        })


class LogoutView(View):
    '''注销视图'''
    def get(self, request):
        logout(request)
        return redirect('login')


class RegisterView(View):
    '''注册视图'''
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return render(request, 'register.html')
    
    def post(self, request):
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        
        if not username or not email or not password:
            return render(request, 'register.html', {
                'error': '请填写所有必填字段'
            })
        
        if password != password_confirm:
            return render(request, 'register.html', {
                'error': '两次输入的密码不一致'
            })
        
        if User.objects.filter(username=username).exists():
            return render(request, 'register.html', {
                'error': '用户名已被使用'
            })
        
        if User.objects.filter(email=email).exists():
            return render(request, 'register.html', {
                'error': '该邮箱已被注册'
            })
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.save()
        
        login(request, user)
        return redirect('project_list')


class ResetPasswordView(View):
    '''重置密码视图'''
    def get(self, request):
        return render(request, 'reset_password.html')
    
    def post(self, request):
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password_confirm = request.POST.get('password_confirm', '')
        
        if not username or not email or not password:
            return render(request, 'reset_password.html', {
                'error': '请填写所有必填字段'
            })
        
        if password != password_confirm:
            return render(request, 'reset_password.html', {
                'error': '两次输入的密码不一致'
            })
        
        try:
            user = User.objects.get(username=username, email=email)
            user.set_password(password)
            user.save()
            
            return render(request, 'reset_password.html', {
                'success': '密码重置成功，请使用新密码登录'
            })
        except User.DoesNotExist:
            return render(request, 'reset_password.html', {
                'error': '用户名或邮箱不正确'
            })


class TokenUsageView(View):
    '''令牌使用视图'''
    def get(self, request):
        return render(request, 'token_usage.html')


class ApiTokenUsageToday(View):
    '''今日令牌使用视图'''
    def get(self, request):
        try:
            today_usage = TokenUsageLog.get_daily_usage(request.user)
            return JsonResponse({'success': True, 'usage': today_usage})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiTokenUsageStats(View):
    '''令牌使用统计视图'''
    def get(self, request):
        try:
            user = request.user
            time_range = request.GET.get('range', 'all')  # today, week, month, all
            
            today = timezone.now().date()
            start_of_week = today - timedelta(days=7)
            start_of_month = today.replace(day=1)
            
            from django.db import models
            
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


class ProjectListView(View):
    '''项目列表视图'''
    def get(self, request):
        projects = Project.objects.filter(user=request.user)
        finalized_count = projects.filter(finalized=True).count()
        return render(request, 'index.html', {
            'projects': projects,
            'finalized_count': finalized_count
        })


class ProjectCreateView(View):
    '''项目创建视图'''
    def get(self, request):
        return render(request, 'index.html')
    
    def post(self, request):
        title = request.POST.get('title', '')
        if not title or title.strip() == '':
            from .models import generate_project_title
            title = generate_project_title()
        description = request.POST.get('description', '')
        project = Project.objects.create(title=title, description=description, user=request.user)
        return redirect('project_detail', pk=project.pk)


class ProjectDetailView(View):
    '''项目详情视图'''
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        view_type = request.GET.get('view', 'novel')
        version_id = request.GET.get('version')

        outline_versions = project.outline_versions.filter(is_deleted=False).order_by('-created_at')
        deleted_outline_versions = project.outline_versions.filter(is_deleted=True).order_by('-created_at')
        volume_versions = project.volume_versions.filter(is_deleted=False).order_by('-created_at')
        chapter_versions = []

        selected_outline = None
        selected_volume = None
        selected_chapter = None

        if view_type == 'outline' and version_id:
            try:
                selected_outline = OutlineVersion.objects.get(pk=version_id, project=project, is_deleted=False)
            except OutlineVersion.DoesNotExist:
                selected_outline = None
        elif view_type == 'volume' and version_id:
            try:
                selected_volume = VolumeVersion.objects.get(pk=version_id, project=project, is_deleted=False)
                chapter_versions = ChapterVersion.objects.filter(volume__volume_version=selected_volume, is_deleted=False).order_by('-created_at')
            except VolumeVersion.DoesNotExist:
                selected_volume = None
        elif view_type == 'chapter' and version_id:
            try:
                selected_chapter = ChapterVersion.objects.get(pk=version_id, is_deleted=False)
            except ChapterVersion.DoesNotExist:
                selected_chapter = None

        outline_count = outline_versions.count()
        volume_count = volume_versions.count()
        chapter_count = Chapter.objects.filter(
            chapter_version__volume__volume_version__project=project,
            chapter_version__is_deleted=False
        ).count()

        return render(request, 'project.html', {
            'project': project,
            'view_type': view_type,
            'outline_versions': outline_versions,
            'deleted_outline_versions': deleted_outline_versions,
            'volume_versions': volume_versions,
            'chapter_versions': chapter_versions,
            'selected_outline': selected_outline,
            'selected_volume': selected_volume,
            'selected_chapter': selected_chapter,
            'active_tab': view_type,
            'selected_version': f"{view_type}_{version_id}" if version_id else None,
            'outline_count': outline_count,
            'volume_count': volume_count,
            'chapter_count': chapter_count
        })


class ApiProjectDetailView(View):
    '''项目详情API视图'''
    def get(self, request, pk):
        try:
            project = get_object_or_404(Project, pk=pk, user=request.user)
            view_type = request.GET.get('view', 'novel')
            version_id = request.GET.get('version')

            outline_versions = project.outline_versions.filter(is_deleted=False).order_by('-created_at')
            deleted_outline_versions = project.outline_versions.filter(is_deleted=True).order_by('-created_at')
            volume_versions = project.volume_versions.filter(is_deleted=False).order_by('-created_at')

            outline_data = [{
                'pk': v.pk,
                'version_number': v.version_number,
                'is_finalized': v.is_finalized,
                'updated_at': v.updated_at.strftime('%Y-%m-%d %H:%M'),
                'content': v.content if view_type == 'outline' and str(v.pk) == str(version_id) else None
            } for v in outline_versions]

            deleted_outline_data = [{
                'pk': v.pk,
                'version_number': v.version_number,
                'updated_at': v.updated_at.strftime('%Y-%m-%d %H:%M')
            } for v in deleted_outline_versions]

            volume_data = [{
                'pk': v.pk,
                'version_number': v.version_number,
                'is_finalized': v.is_finalized,
                'updated_at': v.updated_at.strftime('%Y-%m-%d %H:%M')
            } for v in volume_versions]

            selected_outline = None
            selected_volume = None
            selected_chapter = None
            chapter_versions = []

            if view_type == 'outline' and version_id:
                try:
                    selected_outline = OutlineVersion.objects.get(pk=version_id, project=project, is_deleted=False)
                except OutlineVersion.DoesNotExist:
                    pass
            elif view_type == 'volume' and version_id:
                try:
                    selected_volume = VolumeVersion.objects.get(pk=version_id, project=project, is_deleted=False)
                    chapters = ChapterVersion.objects.filter(volume__volume_version=selected_volume, is_deleted=False).order_by('-created_at')
                    chapter_versions = [{
                        'pk': c.pk,
                        'chapter_number': c.chapter_number,
                        'title': c.title,
                        'is_finalized': c.is_finalized,
                        'updated_at': c.updated_at.strftime('%Y-%m-%d %H:%M')
                    } for c in chapters]
                except VolumeVersion.DoesNotExist:
                    pass
            elif view_type == 'chapter' and version_id:
                try:
                    selected_chapter = ChapterVersion.objects.get(pk=version_id, is_deleted=False)
                except ChapterVersion.DoesNotExist:
                    pass

            return JsonResponse({
                'success': True,
                'project': {
                    'pk': project.pk,
                    'title': project.title,
                    'description': project.description,
                    'finalized': project.finalized,
                    'created_at': project.created_at.strftime('%Y-%m-%d %H:%M'),
                    'updated_at': project.updated_at.strftime('%Y-%m-%d %H:%M')
                },
                'view_type': view_type,
                'outline_versions': outline_data,
                'deleted_outline_versions': deleted_outline_data,
                'volume_versions': volume_data,
                'selected_outline': {
                    'pk': selected_outline.pk,
                    'version_number': selected_outline.version_number,
                    'content': selected_outline.content,
                    'is_finalized': selected_outline.is_finalized,
                    'created_at': selected_outline.created_at.strftime('%Y-%m-%d %H:%M'),
                    'updated_at': selected_outline.updated_at.strftime('%Y-%m-%d %H:%M')
                } if selected_outline else None,
                'selected_volume': {
                    'pk': selected_volume.pk,
                    'version_number': selected_volume.version_number,
                    'content': selected_volume.content,
                    'is_finalized': selected_volume.is_finalized,
                    'created_at': selected_volume.created_at.strftime('%Y-%m-%d %H:%M'),
                    'updated_at': selected_volume.updated_at.strftime('%Y-%m-%d %H:%M')
                } if selected_volume else None,
                'selected_chapter': {
                    'pk': selected_chapter.pk,
                    'chapter_number': selected_chapter.chapter_number,
                    'title': selected_chapter.title,
                    'content': selected_chapter.content,
                    'is_finalized': selected_chapter.is_finalized,
                    'created_at': selected_chapter.created_at.strftime('%Y-%m-%d %H:%M'),
                    'updated_at': selected_chapter.updated_at.strftime('%Y-%m-%d %H:%M')
                } if selected_chapter else None,
                'chapter_versions': chapter_versions
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

class ApiProjectStatsView(View):
    '''项目统计API视图'''
    def get(self, request, pk):
        try:
            project = get_object_or_404(Project, pk=pk, user=request.user)
            
            volume_count = Volume.objects.filter(
                volume_version__project=project,
                volume_version__is_deleted=False
            ).count()
            
            chapters = Chapter.objects.filter(
                chapter_version__volume__volume_version__project=project,
                chapter_version__is_deleted=False
            )
            
            chapter_count = chapters.count()
            chapter_with_summary = chapters.exclude(summary__isnull=True).exclude(summary='').count()
            chapter_with_content = chapters.exclude(content__isnull=True).exclude(content='').count()
            chapter_finalized = chapters.filter(chapter_version__is_finalized=True).count()
            chapter_published = chapters.filter(status=Chapter.STATUS_PUBLISHED).count()
            
            return JsonResponse({
                'success': True,
                'volume_count': volume_count,
                'chapter_count': chapter_count,
                'chapter_with_summary': chapter_with_summary,
                'chapter_with_content': chapter_with_content,
                'chapter_finalized': chapter_finalized,
                'chapter_published': chapter_published
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class VolumeGeneratorView(View):
    '''卷生成器视图'''
    def get(self, request):
        return render(request, 'volume_generator.html')


class ChapterGeneratorView(View):
    '''章节生成器视图'''
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return render(request, 'chapter_generator.html')


class ContentManagerView(View):
    '''内容管理视图'''
    def get(self, request):
        return render(request, 'content_manager.html')


class ApiVolumeGenerateView(View):
    '''卷生成API'''
    def post(self, request):
        import json
        try:
            project_id = request.POST.get('project_id')
            outline_version_id = request.POST.get('outline_version_id')
            
            project = get_object_or_404(Project, pk=project_id, user=request.user)
            
            if outline_version_id:
                outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project=project, is_deleted=False)
            else:
                outline_version = project.outline_versions.filter(is_deleted=False, is_finalized=True).first()
                if not outline_version:
                    outline_version = project.outline_versions.filter(is_deleted=False).first()
            
            if not outline_version:
                return JsonResponse({'success': False, 'message': '没有找到可用的大纲版本'})
            
            from apps.ai.services import LLMService
            llm_service = LLMService()
            volumes = llm_service.generate_volumes(outline_version.content, user=request.user, project=project)
            
            if not volumes:
                volumes = generate_fallback_volumes(outline_version.content)
            
            return JsonResponse({'success': True, 'volumes': volumes})
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'message': 'AI返回格式错误'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


def generate_fallback_volumes(outline_content):
    '''生成备用卷结构'''
    volumes = [
        {'title': '初露锋芒', 'summary': '故事开端，主角登场，背景铺垫，主要人物亮相，引出核心矛盾。'},
        {'title': '暗流涌动', 'summary': '冲突逐渐升级，各方势力登场，主角面临挑战，阴谋初现端倪。'},
        {'title': '风起云涌', 'summary': '主角成长迅速，实力提升，关键转折出现，局势变得复杂。'},
        {'title': '决战前夕', 'summary': '各方势力汇聚，大战一触即发，主角准备迎接最终挑战。'},
        {'title': '巅峰对决', 'summary': '最终决战爆发，主角展现全部实力，揭开最终真相。'},
        {'title': '尘埃落定', 'summary': '战争结束，尘埃落定，主角迎来新的人生阶段。'}
    ]
    return volumes


class ApiVolumeChatView(View):
    '''卷聊天API'''
    def post(self, request):
        import json
        try:
            project_id = request.POST.get('project_id')
            message = request.POST.get('message')
            volume_version_id = request.POST.get('volume_version_id')
            
            project = get_object_or_404(Project, pk=project_id, user=request.user)
            
            outline_version = project.outline_versions.filter(is_deleted=False, is_finalized=True).first()
            if not outline_version:
                outline_version = project.outline_versions.filter(is_deleted=False).first()
            
            if not outline_version:
                return JsonResponse({'success': False, 'message': '没有找到可用的大纲版本'})
            
            version_context = ""
            if volume_version_id:
                try:
                    vol_version = VolumeVersion.objects.get(pk=volume_version_id, project=project, is_deleted=False)
                    version_context = f"当前正在讨论的是卷版本 v{vol_version.version_number}（共 {vol_version.volumes.count()} 卷）。\n"
                except VolumeVersion.DoesNotExist:
                    pass
            
            from apps.ai.services import LLMService
            llm_service = LLMService()
            
            current_volumes = llm_service.generate_volumes(outline_version.content, user=request.user, project=project)
            if not current_volumes:
                current_volumes = generate_fallback_volumes(outline_version.content)
            
            current_volumes_str = json.dumps({'volumes': current_volumes})
            
            prompt = f"{version_context}当前卷结构如下：\n{current_volumes_str}\n\n用户反馈：{message}\n\n请根据用户反馈优化卷结构。"
            
            optimized_volumes = llm_service.optimize_volumes(
                outline=outline_version.content,
                current_volumes=current_volumes_str,
                user_feedback=prompt,
                user=request.user,
                project=project
            )
            
            if not optimized_volumes:
                optimized_volumes = current_volumes
            
            return JsonResponse({
                'success': True,
                'response': '已根据您的建议优化了卷结构',
                'volumes': optimized_volumes
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class ApiVolumeVersionsView(View):
    '''卷版本列表API'''
    def get(self, request, project_id):
        try:
            project = get_object_or_404(Project, pk=project_id, user=request.user)
            volume_versions = project.volume_versions.filter(is_deleted=False).order_by('-version_number')
            
            versions_list = []
            for version in volume_versions:
                versions_list.append({
                    'id': version.id,
                    'version_number': version.version_number,
                    'outline_version_id': version.outline_version.id if version.outline_version else None,
                    'outline_version_number': version.outline_version.version_number if version.outline_version else None,
                    'is_finalized': version.is_finalized,
                    'created_at': version.created_at.strftime('%Y-%m-%d %H:%M') if version.created_at else None,
                    'volume_count': version.volumes.count()
                })
            
            return JsonResponse({'success': True, 'versions': versions_list})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class ApiVolumeVersionView(View):
    '''卷版本详情API'''
    def get(self, request, version_id):
        try:
            volume_version = get_object_or_404(VolumeVersion, pk=version_id)
            project = get_object_or_404(Project, pk=volume_version.project.id, user=request.user)
            
            volumes = []
            for volume in volume_version.volumes.order_by('volume_number'):
                volumes.append({
                    'id': volume.id,
                    'volume_number': volume.volume_number,
                    'title': volume.title,
                    'summary': volume.summary
                })
            
            return JsonResponse({
                'success': True,
                'version_number': volume_version.version_number,
                'outline_version_id': volume_version.outline_version.id if volume_version.outline_version else None,
                'outline_version_number': volume_version.outline_version.version_number if volume_version.outline_version else None,
                'is_finalized': volume_version.is_finalized,
                'volumes': volumes
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class ApiSaveVolumeVersionView(View):
    '''保存卷版本API'''
    def post(self, request):
        import json
        try:
            project_id = request.POST.get('project_id')
            outline_version_id = request.POST.get('outline_version_id')
            volumes_json = request.POST.get('volumes')
            is_finalize = request.POST.get('finalize', 'false').lower() == 'true'
            
            project = get_object_or_404(Project, pk=project_id, user=request.user)
            outline_version = None
            
            if outline_version_id:
                outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project=project, is_deleted=False)
            
            last_version = project.volume_versions.filter(is_deleted=False).order_by('-version_number').first()
            new_version_number = last_version.version_number + 1 if last_version else 1
            
            new_volume_version = VolumeVersion.objects.create(
                project=project,
                outline_version=outline_version,
                version_number=new_version_number,
                is_finalized=is_finalize
            )
            
            if is_finalize:
                project.volume_versions.filter(is_deleted=False, is_finalized=True).update(is_finalized=False)
                new_volume_version.is_finalized = True
                new_volume_version.save()
            
            volumes_data = json.loads(volumes_json)
            for idx, volume_data in enumerate(volumes_data):
                Volume.objects.create(
                    volume_version=new_volume_version,
                    volume_number=idx + 1,
                    title=volume_data.get('title', f'第{idx + 1}卷'),
                    summary=volume_data.get('summary', '')
                )
            
            return JsonResponse({
                'success': True,
                'version_id': new_volume_version.id,
                'version_number': new_version_number
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class ApiVolumeFinalizeView(View):
    '''卷版本定稿API'''
    def post(self, request):
        try:
            project_id = request.POST.get('project_id')
            version_id = request.POST.get('version_id')
            
            project = get_object_or_404(Project, pk=project_id, user=request.user)
            
            project.volume_versions.filter(is_deleted=False, is_finalized=True).update(is_finalized=False)
            
            if version_id:
                version = get_object_or_404(VolumeVersion, pk=version_id, project=project, is_deleted=False)
                version.is_finalized = True
                version.save()
            else:
                latest = project.volume_versions.filter(is_deleted=False).order_by('-version_number').first()
                if latest:
                    latest.is_finalized = True
                    latest.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class ApiVolumeDeleteView(View):
    '''卷版本删除API'''
    def post(self, request):
        try:
            project_id = request.POST.get('project_id')
            version_id = request.POST.get('version_id')
            
            project = get_object_or_404(Project, pk=project_id, user=request.user)
            version = get_object_or_404(VolumeVersion, pk=version_id, project=project, is_deleted=False)
            
            if version.is_finalized:
                return JsonResponse({'success': False, 'message': '无法删除已定稿的版本'})
            
            version.is_deleted = True
            version.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class OutlineBuilderView(View):
    '''大纲构建器视图'''
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        version_id = request.GET.get('version')
        
        outline_versions = project.outline_versions.filter(is_deleted=False).order_by('-created_at')
        latest_outline = None
        
        if version_id:
            latest_outline = get_object_or_404(OutlineVersion, pk=version_id, project=project, is_deleted=False)
        else:
            latest_outline = outline_versions.first()
        
        return render(request, 'outline_builder.html', {
            'project': project,
            'outline_versions': outline_versions,
            'latest_outline': latest_outline,
            'selected_version': int(version_id) if version_id else None,
            'hide_sidebar': True
        })


class OutlineVersionDetailView(View):
    '''大纲版本详情视图'''
    def get(self, request, pk, version_pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        outline_version = get_object_or_404(OutlineVersion, pk=version_pk, project=project, is_deleted=False)
        outline_messages = list(outline_version.messages.all())
        
        return render(request, 'outline_builder.html', {
            'project': project,
            'outline_version': outline_version,
            'outline_messages': outline_messages
        })


class VolumeBuilderView(View):
    '''卷构建器视图'''
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        outline_versions = project.outline_versions.filter(is_deleted=False).all()
        volume_versions = project.volume_versions.filter(is_deleted=False).all()

        finalized_outline = outline_versions.filter(is_finalized=True).first()
        latest_outline = outline_versions.first()

        outline_id = request.GET.get('outline_id')
        selected_outline = None
        if outline_id:
            selected_outline = get_object_or_404(OutlineVersion, pk=outline_id, project=project, is_deleted=False)
        elif finalized_outline:
            selected_outline = finalized_outline
        elif latest_outline:
            selected_outline = latest_outline

        return render(request, 'outline_builder.html', {
            'project': project,
            'outline_versions': outline_versions,
            'volume_versions': volume_versions,
            'finalized_outline': finalized_outline,
            'latest_outline': latest_outline,
            'selected_outline': selected_outline
        })


class VolumeVersionDetailView(View):
    '''卷版本详情视图'''
    def get(self, request, pk, version_pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        volume_version = get_object_or_404(VolumeVersion, pk=version_pk, project=project, is_deleted=False)
        volumes = volume_version.volumes.all()
        
        return render(request, 'outline_builder.html', {
            'project': project,
            'volume_version': volume_version,
            'volumes': volumes
        })


class ChapterSummaryView(View):
    '''章节摘要视图'''
    def get(self, request, pk, volume_pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        volume = get_object_or_404(Volume, pk=volume_pk)
        chapter_versions = volume.chapter_versions.filter(is_deleted=False).all()
        latest_version = chapter_versions.first()
        chapters = latest_version.chapters.all() if latest_version else []
        
        return render(request, 'outline_builder.html', {
            'project': project,
            'volume': volume,
            'chapter_versions': chapter_versions,
            'latest_version': latest_version,
            'chapters': chapters
        })


class ChapterVersionDetailView(View):
    '''章节版本详情视图'''
    def get(self, request, pk, volume_pk, version_pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        volume = get_object_or_404(Volume, pk=volume_pk)
        chapter_version = get_object_or_404(ChapterVersion, pk=version_pk, volume=volume, is_deleted=False)
        chapters = chapter_version.chapters.all()
        
        return render(request, 'outline_builder.html', {
            'project': project,
            'volume': volume,
            'chapter_version': chapter_version,
            'chapters': chapters
        })


class ChapterContentDetailView(View):
    '''章节内容详情视图'''
    def get(self, request, pk, volume_pk, chapter_pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        volume = get_object_or_404(Volume, pk=volume_pk)
        chapter = get_object_or_404(Chapter, pk=chapter_pk)
        
        return render(request, 'outline_builder.html', {
            'project': project,
            'volume': volume,
            'chapter': chapter
        })


class ProjectUpdateTitleView(View):
    '''项目更新标题视图'''
    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        title = request.POST.get('title')
        if title:
            project.title = title
            project.save()
        return JsonResponse({'success': True, 'title': project.title})


class ProjectUpdateInfoView(View):
    '''项目更新信息视图'''
    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        if title:
            project.title = title
        if description is not None:
            project.description = description
        
        project.save()
        return JsonResponse({'success': True})


class ChapterContentApiView(View):
    '''章节内容API视图'''
    def get(self, request, chapter_id):
        chapter = get_object_or_404(Chapter, pk=chapter_id)
        return JsonResponse({
            'success': True,
            'title': f"第 {chapter.chapter_number} 章: {chapter.title}",
            'content': chapter.content
        })


class OutlineVersionContentApiView(View):
    '''大纲版本内容API视图'''
    def get(self, request, version_id):
        outline_version = get_object_or_404(OutlineVersion, pk=version_id, is_deleted=False)
        return JsonResponse({
            'success': True,
            'version_number': outline_version.version_number,
            'content': outline_version.content,
            'is_finalized': outline_version.is_finalized,
            'created_at': outline_version.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': outline_version.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        })


class LLMConfigView(View):
    '''LLM配置视图'''
    def get(self, request):
        configs = LLMConfig.objects.filter(user=request.user)
        task_configs = UserLLMConfig.objects.filter(user=request.user)
        return render(request, 'llm_config.html', {
            'configs': configs,
            'task_configs': task_configs,
            'PROVIDER_CHOICES': LLMConfig.PROVIDER_CHOICES,
            'TASK_CHOICES': UserLLMConfig.TASK_CHOICES,
        })
    
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
            
            # 如果设为默认，先取消其他默认
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
            
            # 处理可选的温度和max_tokens
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
            config = get_object_or_404(LLMConfig, pk=config_id, user=request.user)
            config.delete()
        
        return redirect('llm_config')


class ApiUserView(View):
    '''获取当前用户信息API'''
    def get(self, request):
        if request.user.is_authenticated:
            return JsonResponse({
                'success': True,
                'user': {
                    'id': request.user.id,
                    'username': request.user.username,
                    'email': request.user.email
                }
            })
        return JsonResponse({'success': False, 'error': '未登录'}, status=401)


class ApiLoginView(View):
    '''登录API'''
    def post(self, request):
        try:
            data = request.body.decode('utf-8')
            if data.startswith('{'):
                data = json.loads(data)
                username = data.get('username')
                password = data.get('password')
            else:
                username = request.POST.get('username')
                password = request.POST.get('password')
            
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return JsonResponse({
                    'success': True,
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email
                    }
                })
            return JsonResponse({'success': False, 'message': '用户名或密码错误'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiLogoutView(View):
    '''登出API'''
    def post(self, request):
        logout(request)
        return JsonResponse({'success': True})


class ApiRegisterView(View):
    '''注册API'''
    def post(self, request):
        try:
            data = request.body.decode('utf-8')
            if data.startswith('{'):
                data = json.loads(data)
                username = data.get('username', '').strip()
                email = data.get('email', '').strip()
                password = data.get('password')
            else:
                username = request.POST.get('username', '').strip()
                email = request.POST.get('email', '').strip()
                password = request.POST.get('password')
            
            if not username or not email or not password:
                return JsonResponse({'success': False, 'message': '请填写所有必填字段'})
            
            if User.objects.filter(username=username).exists():
                return JsonResponse({'success': False, 'message': '用户名已被使用'})
            
            if User.objects.filter(email=email).exists():
                return JsonResponse({'success': False, 'message': '该邮箱已被注册'})
            
            user = User.objects.create_user(username=username, email=email, password=password)
            user.save()
            login(request, user)
            
            return JsonResponse({
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiProjectListView(View):
    '''项目列表API'''
    def get(self, request):
        projects = Project.objects.filter(user=request.user, is_deleted=False).order_by('-created_at')
        projects_data = []
        for project in projects:
            latest_outline = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
            projects_data.append({
                'id': project.id,
                'title': project.title,
                'description': project.description,
                'status': 'completed' if project.finalized else ('writing' if latest_outline and latest_outline.is_finalized else 'draft'),
                'created_at': project.created_at.strftime('%Y-%m-%d %H:%M'),
                'updated_at': project.updated_at.strftime('%Y-%m-%d %H:%M')
            })
        return JsonResponse({'success': True, 'projects': projects_data})


class ApiProjectCreateView(View):
    '''创建项目API'''
    def post(self, request):
        try:
            data = request.body.decode('utf-8')
            if data.startswith('{'):
                data = json.loads(data)
                title = data.get('title', '').strip()
                description = data.get('description', '')
            else:
                title = request.POST.get('title', '').strip()
                description = request.POST.get('description', '')
            
            if not title:
                title = generate_project_title()
            
            project = Project.objects.create(title=title, description=description, user=request.user)
            return JsonResponse({
                'success': True,
                'project': {
                    'id': project.id,
                    'title': project.title,
                    'description': project.description,
                    'created_at': project.created_at.strftime('%Y-%m-%d %H:%M')
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiProjectDeleteView(View):
    '''删除项目API（软删除）'''
    def delete(self, request, pk):
        try:
            project = get_object_or_404(Project, pk=pk, user=request.user)
            project.is_deleted = True
            project.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiProjectFinalizeView(View):
    '''项目定稿API'''
    def post(self, request, pk):
        try:
            project = get_object_or_404(Project, pk=pk, user=request.user)
            
            # 将所有其他版本设置为未定稿
            project.outline_versions.filter(is_deleted=False, is_finalized=True).update(is_finalized=False)
            
            # 获取最新版本并设置为定稿
            latest_version = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
            if latest_version:
                latest_version.is_finalized = True
                latest_version.save()
            
            project.finalized = True
            project.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiProjectUpdateView(View):
    '''更新项目API'''
    def post(self, request, pk):
        try:
            project = get_object_or_404(Project, pk=pk, user=request.user)
            
            data = request.body.decode('utf-8')
            if data.startswith('{'):
                data = json.loads(data)
                title = data.get('title', '').strip()
                description = data.get('description', '')
            else:
                title = request.POST.get('title', '').strip()
                description = request.POST.get('description', '')
            
            if title:
                project.title = title
            if description is not None:
                project.description = description
            
            project.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiOutlineFinalizeView(View):
    '''大纲定稿API'''
    def post(self, request):
        try:
            project_id = request.POST.get('project_id')
            version_id = request.POST.get('version_id')
            
            project = get_object_or_404(Project, pk=project_id, user=request.user)
            
            # 将所有其他版本设置为未定稿
            project.outline_versions.filter(is_deleted=False, is_finalized=True).update(is_finalized=False)
            
            if version_id:
                # 定稿指定版本
                version = get_object_or_404(OutlineVersion, pk=version_id, project=project, is_deleted=False)
                version.is_finalized = True
                version.save()
            else:
                # 定稿最新版本
                latest_version = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
                if latest_version:
                    latest_version.is_finalized = True
                    latest_version.save()
            
            project.finalized = True
            project.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiOutlineVersionsView(View):
    '''获取项目的大纲版本列表API'''
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        versions = project.outline_versions.filter(is_deleted=False).order_by('-version_number')
        deleted_versions = project.outline_versions.filter(is_deleted=True).order_by('-version_number')
        
        versions_data = []
        for v in versions:
            versions_data.append({
                'id': v.id,
                'version_number': v.version_number,
                'is_finalized': v.is_finalized,
                'created_at': v.created_at.strftime('%m-%d %H:%M') if v.created_at else '',
                'updated_at': v.updated_at.strftime('%Y-%m-%d %H:%M') if v.updated_at else ''
            })
        
        deleted_data = []
        for v in deleted_versions:
            deleted_data.append({
                'id': v.id,
                'version_number': v.version_number,
                'is_finalized': v.is_finalized,
                'created_at': v.created_at.strftime('%m-%d %H:%M') if v.created_at else '',
                'updated_at': v.updated_at.strftime('%Y-%m-%d %H:%M') if v.updated_at else ''
            })
        
        return JsonResponse({
            'success': True,
            'versions': versions_data,
            'deleted_versions': deleted_data
        })


class ApiOutlineDeleteView(View):
    '''大纲版本删除API'''
    def post(self, request):
        try:
            project_id = request.POST.get('project_id')
            version_id = request.POST.get('version_id')
            
            project = get_object_or_404(Project, pk=project_id, user=request.user)
            version = get_object_or_404(OutlineVersion, pk=version_id, project=project, is_deleted=False)
            
            if version.is_finalized:
                return JsonResponse({'success': False, 'message': '无法删除已定稿的版本'})
            
            version.is_deleted = True
            version.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})


class ApiLatestOutlineView(View):
    '''获取最新大纲版本内容API'''
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        latest_outline = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
        
        if latest_outline:
            return JsonResponse({
                'success': True,
                'outline': {
                    'id': latest_outline.id,
                    'version_number': latest_outline.version_number,
                    'content': latest_outline.content,
                    'is_finalized': latest_outline.is_finalized,
                    'updated_at': latest_outline.updated_at.strftime('%Y-%m-%d %H:%M')
                }
            })
        
        return JsonResponse({'success': True, 'outline': None})


class ApiLLMConfigView(View):
    '''LLM配置API'''
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
            data = request.body.decode('utf-8')
            if data.startswith('{'):
                data = json.loads(data)
            else:
                data = request.POST
            
            action = data.get('action')
            
            if action == 'create':
                name = data.get('name')
                provider = data.get('provider')
                api_key = data.get('api_key')
                base_url = data.get('base_url', '')
                model_name = data.get('model_name')
                temperature = float(data.get('temperature', 0.7))
                max_tokens = int(data.get('max_tokens', 4096))
                is_default = data.get('is_default') == True or data.get('is_default') == 'true'
                
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
                task_type = data.get('task_type')
                config_id = data.get('config_id')
                
                temperature = data.get('temperature')
                max_tokens = data.get('max_tokens')
                
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
                config_id = data.get('config_id')
                config = get_object_or_404(LLMConfig, pk=config_id, user=request.user)
                config.delete()
                return JsonResponse({'success': True})
            
            elif action == 'toggle_active':
                config_id = data.get('config_id')
                is_active = data.get('is_active')
                config = get_object_or_404(LLMConfig, pk=config_id, user=request.user)
                config.is_active = is_active
                config.save()
                return JsonResponse({'success': True})
            
            elif action == 'update':
                config_id = data.get('config_id')
                config = get_object_or_404(LLMConfig, pk=config_id, user=request.user)
                
                name = data.get('name')
                provider = data.get('provider')
                api_key = data.get('api_key')
                base_url = data.get('base_url', '')
                model_name = data.get('model_name')
                temperature = float(data.get('temperature', 0.7))
                max_tokens = int(data.get('max_tokens', 4096))
                is_default = data.get('is_default') == True or data.get('is_default') == 'true'
                
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
