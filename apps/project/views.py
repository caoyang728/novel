import json
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from apps.core.models import Project, LLMConfig, UserLLMConfig, TokenUsageLog


class ProjectListView(View):
    def get(self, request):
        projects = Project.objects.filter(user=request.user).order_by('-created_at')
        return render(request, 'index.html', {'projects': projects})


class ProjectCreateView(View):
    def get(self, request):
        return render(request, 'create_project.html')
    
    def post(self, request):
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '')
        
        if not title:
            from apps.core.models import generate_project_title
            title = generate_project_title()
        
        project = Project.objects.create(
            title=title,
            description=description,
            user=request.user
        )
        
        return JsonResponse({'success': True, 'project_id': project.id})


class ProjectDetailView(View):
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        latest_outline = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
        outline_versions = project.outline_versions.filter(is_deleted=False).order_by('-version_number')
        deleted_versions = project.outline_versions.filter(is_deleted=True).order_by('-version_number')
        
        return render(request, 'project.html', {
            'project': project,
            'outline_versions': outline_versions,
            'deleted_versions': deleted_versions,
            'latest_outline': latest_outline,
        })


class ProjectUpdateTitleView(View):
    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        title = request.POST.get('title', '').strip()
        if title:
            project.title = title
            project.save()
        return JsonResponse({'success': True})


class ProjectUpdateInfoView(View):
    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        description = request.POST.get('description', '')
        project.description = description
        project.save()
        return JsonResponse({'success': True})


class TokenUsageView(View):
    def get(self, request):
        return render(request, 'token_usage.html')


class ApiTokenUsageToday(View):
    def get(self, request):
        today_usage = TokenUsageLog.get_daily_usage(request.user)
        return JsonResponse({
            'success': True,
            'usage': {
                'today': today_usage
            }
        })


class ApiTokenUsageStats(View):
    def get(self, request):
        range_type = request.GET.get('range', 'today')
        
        today = timezone.now().date()
        start_date = None
        
        if range_type == 'today':
            start_date = today
        elif range_type == 'week':
            start_date = today - timedelta(days=7)
        elif range_type == 'month':
            start_date = today - timedelta(days=30)
        
        if start_date:
            start_datetime = timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time()))
        else:
            start_datetime = None
        
        logs = TokenUsageLog.objects.filter(user=request.user)
        if start_datetime:
            logs = logs.filter(created_at__gte=start_datetime)
        
        logs = logs.order_by('-created_at')[:100]
        
        prompt_hit = 0
        prompt_miss = 0
        completion_tokens = 0
        total_tokens = 0
        
        logs_data = []
        for log in logs:
            prompt_tokens = log.prompt_tokens
            cache_hit = log.cache_hit
            
            if cache_hit:
                prompt_hit += prompt_tokens
            else:
                prompt_miss += prompt_tokens
            
            completion_tokens += log.completion_tokens
            total_tokens += log.total_tokens
            
            logs_data.append({
                'id': log.id,
                'created_at': log.created_at.strftime('%Y-%m-%d %H:%M'),
                'project': log.project.title if log.project else '未知项目',
                'task_type': log.task_type,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': log.completion_tokens,
                'total_tokens': log.total_tokens,
                'cache_hit': cache_hit,
            })
        
        project_stats = {}
        stats_logs = TokenUsageLog.objects.filter(user=request.user)
        if start_datetime:
            stats_logs = stats_logs.filter(created_at__gte=start_datetime)
        
        for log in stats_logs:
            project_title = log.project.title if log.project else '未知项目'
            if project_title not in project_stats:
                project_stats[project_title] = {
                    'project_title': project_title,
                    'total_tokens': 0,
                    'cache_hits': 0,
                    'cache_misses': 0,
                    'count': 0
                }
            
            project_stats[project_title]['total_tokens'] += log.total_tokens
            if log.cache_hit:
                project_stats[project_title]['cache_hits'] += 1
            else:
                project_stats[project_title]['cache_misses'] += 1
            project_stats[project_title]['count'] += 1
        
        project_stats = list(project_stats.values())
        
        return JsonResponse({
            'success': True,
            'usage': {
                'today': TokenUsageLog.get_daily_usage(request.user),
                'week': {
                    'prompt_hit': prompt_hit,
                    'prompt_miss': prompt_miss,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens,
                },
                'month': {
                    'prompt_hit': prompt_hit,
                    'prompt_miss': prompt_miss,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens,
                },
                'all': {
                    'prompt_hit': prompt_hit,
                    'prompt_miss': prompt_miss,
                    'completion_tokens': completion_tokens,
                    'total_tokens': total_tokens,
                },
                'logs': logs_data,
                'project_stats': project_stats
            }
        })


class ApiProjectListView(View):
    def get(self, request):
        projects = Project.objects.filter(user=request.user).order_by('-created_at')
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


class ApiProjectDetailView(View):
    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        latest_outline = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
        
        return JsonResponse({
            'success': True,
            'project': {
                'id': project.id,
                'title': project.title,
                'description': project.description,
                'status': 'completed' if project.finalized else ('writing' if latest_outline and latest_outline.is_finalized else 'draft'),
                'created_at': project.created_at.strftime('%Y-%m-%d %H:%M'),
                'updated_at': project.updated_at.strftime('%Y-%m-%d %H:%M')
            }
        })


class ApiProjectCreateView(View):
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
                from apps.core.models import generate_project_title
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
    def delete(self, request, pk):
        try:
            project = get_object_or_404(Project, pk=pk, user=request.user)
            project.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})