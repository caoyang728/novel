"""
Outline views - 大纲相关视图
"""
import json
from django.http import JsonResponse, StreamingHttpResponse
from django.views import View
from django.shortcuts import get_object_or_404
from django.db import transaction
from apps.core.models import Project, OutlineVersion, OutlineMessage
from apps.ai.services import LLMService

llm_service = LLMService()


class ChatOutlineView(View):
    def post(self, request):
        project_id = request.POST.get('project_id')
        user_input = request.POST.get('message')
        current_outline = request.POST.get('current_outline', '')
        messages_json = request.POST.get('messages', '[]')
        
        try:
            messages = json.loads(messages_json)
        except json.JSONDecodeError:
            messages = []
        
        project = get_object_or_404(Project, pk=project_id, user=request.user)
        
        response = llm_service.build_outline(user_input, current_outline, messages)
        
        return JsonResponse({'success': True, 'response': response})


class ChatOutlineStreamView(View):
    def post(self, request):
        project_id = request.POST.get('project_id')
        user_input = request.POST.get('message')
        current_outline = request.POST.get('current_outline', '')
        messages_json = request.POST.get('messages', '[]')
        
        try:
            messages = json.loads(messages_json)
        except json.JSONDecodeError:
            messages = []
        
        project = get_object_or_404(Project, pk=project_id, user=request.user)
        
        def generate():
            for chunk in llm_service.build_outline_stream(user_input, current_outline, messages):
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
        
        return StreamingHttpResponse(generate(), content_type='text/event-stream')


class SaveOutlineVersionView(View):
    def post(self, request):
        project_id = request.POST.get('project_id')
        content = request.POST.get('content')
        messages_json = request.POST.get('messages', '[]')
        new_version = request.POST.get('new_version', 'false') == 'true'
        
        try:
            messages = json.loads(messages_json)
        except json.JSONDecodeError:
            messages = []
        
        project = get_object_or_404(Project, pk=project_id, user=request.user)
        outline_version = None
        
        with transaction.atomic():
            if new_version:
                latest_version = project.outline_versions.order_by('-version_number').first()
                new_version_number = latest_version.version_number + 1 if latest_version else 1
                
                outline_version = OutlineVersion.objects.create(
                    project=project,
                    version_number=new_version_number,
                    content=content,
                    snapshot=content[:500] + '...' if len(content) > 500 else content
                )
            else:
                outline_version = project.outline_versions.order_by('-version_number').first()
                if outline_version:
                    outline_version.content = content
                    outline_version.snapshot = content[:500] + '...' if len(content) > 500 else content
                    outline_version.save()
                    outline_version.messages.all().delete()
                else:
                    outline_version = OutlineVersion.objects.create(
                        project=project,
                        version_number=1,
                        content=content,
                        snapshot=content[:500] + '...' if len(content) > 500 else content
                    )
            
            for msg in messages:
                OutlineMessage.objects.create(
                    outline_version=outline_version,
                    role=msg['role'],
                    content=msg['content']
                )
        
        return JsonResponse({
            'success': True,
            'version_id': outline_version.pk,
            'version_number': outline_version.version_number
        })


class LoadOutlineVersionView(View):
    def get(self, request, version_id):
        outline_version = get_object_or_404(OutlineVersion, pk=version_id, project__user=request.user)
        
        messages = []
        for msg in outline_version.messages.order_by('created_at'):
            messages.append({
                'role': msg.role,
                'content': msg.content
            })
        
        return JsonResponse({
            'success': True,
            'content': outline_version.content,
            'messages': messages
        })


class FinalizeOutlineVersionView(View):
    def post(self, request):
        project_id = request.POST.get('project_id')
        version_id = request.POST.get('version_id')
        content = request.POST.get('content')
        messages_json = request.POST.get('messages', '[]')
        
        try:
            messages = json.loads(messages_json)
        except json.JSONDecodeError:
            messages = []
        
        project = get_object_or_404(Project, pk=project_id, user=request.user)
        
        outline_version = None
        
        with transaction.atomic():
            project.outline_versions.filter(is_finalized=True, is_deleted=False).update(is_finalized=False)
            
            if version_id:
                outline_version = get_object_or_404(OutlineVersion, pk=version_id, project=project)
                if content:
                    outline_version.content = content
                    outline_version.snapshot = content[:500] + '...' if len(content) > 500 else content
                outline_version.is_finalized = True
                outline_version.save()
                outline_version.messages.all().delete()
                for msg in messages:
                    OutlineMessage.objects.create(
                        outline_version=outline_version,
                        role=msg['role'],
                        content=msg['content']
                    )
            else:
                latest_version = project.outline_versions.order_by('-version_number').first()
                if latest_version:
                    outline_version = latest_version
                    outline_version.content = content or latest_version.content
                    outline_version.snapshot = outline_version.content[:500] + '...' if len(outline_version.content) > 500 else outline_version.content
                    outline_version.is_finalized = True
                    outline_version.save()
                else:
                    outline_version = OutlineVersion.objects.create(
                        project=project,
                        version_number=1,
                        content=content,
                        snapshot=content[:500] + '...' if len(content) > 500 else content,
                        is_finalized=True
                    )
        
        return JsonResponse({
            'success': True,
            'version_id': outline_version.pk,
            'version_number': outline_version.version_number
        })


class DeleteOutlineVersionView(View):
    def post(self, request):
        version_id = request.POST.get('version_id')
        outline_version = get_object_or_404(OutlineVersion, pk=version_id, project__user=request.user)
        
        if outline_version.is_finalized:
            return JsonResponse({
                'success': False,
                'message': '定稿版本不能删除'
            })
        
        outline_version.is_deleted = True
        outline_version.save()
        
        return JsonResponse({'success': True})


class RestoreOutlineVersionView(View):
    def post(self, request):
        version_id = request.POST.get('version_id')
        outline_version = get_object_or_404(OutlineVersion, pk=version_id, project__user=request.user, is_deleted=True)
        
        outline_version.is_deleted = False
        outline_version.save()
        
        return JsonResponse({'success': True})