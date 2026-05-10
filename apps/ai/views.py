"""
AI views - 通用 AI 功能视图
"""
import json
from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404
from apps.core.models import OutlineVersion, Project
from apps.ai.services import LLMService

llm_service = LLMService()


class GenerateProjectInfoView(View):
    def post(self, request):
        project_id = request.POST.get('project_id')
        project = get_object_or_404(Project, pk=project_id, user=request.user)
        
        finalized_outline = project.outline_versions.filter(is_deleted=False, is_finalized=True).order_by('-version_number').first()
        
        if not finalized_outline:
            latest_outline = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
            if not latest_outline:
                return JsonResponse({'success': False, 'message': '暂无大纲，无法生成项目名和简介'})
            outline_content = latest_outline.content
        else:
            outline_content = finalized_outline.content
        
        if not outline_content or outline_content.strip() == "":
            return JsonResponse({'success': False, 'message': '大纲内容为空，无法生成项目名和简介'})
        
        result = llm_service.generate_project_info(outline_content, user=request.user, project=project)
        
        if result:
            titles = []
            if 'titles' in result and isinstance(result['titles'], list):
                titles = result['titles']
            elif 'title' in result:
                titles = [result['title']]
            
            if titles and 'description' in result:
                return JsonResponse({
                    'success': True,
                    'titles': titles,
                    'description': result['description']
                })
        
        return JsonResponse({'success': False, 'message': '生成失败，请重试'})


class SuggestTitleView(View):
    def post(self, request):
        outline_version_id = request.POST.get('outline_version_id')
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project__user=request.user)
        
        suggestions = llm_service.suggest_title(outline_version.content)
        
        return JsonResponse({'success': True, 'suggestions': suggestions})


class RewriteTitleView(View):
    def post(self, request):
        original_title = request.POST.get('original_title')
        
        suggestions = llm_service.rewrite_title(original_title)
        
        return JsonResponse({'success': True, 'suggestions': suggestions})


class OptimizeDescriptionView(View):
    def post(self, request):
        description = request.POST.get('description')
        
        optimized = llm_service.optimize_description(description)
        
        return JsonResponse({'success': True, 'optimized': optimized})