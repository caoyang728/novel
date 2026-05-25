"""
Volume views - 卷相关视图
"""
import json
import time
from loguru import logger
from django.http import JsonResponse
from django.views import View
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from apps.project.models import ProjectList
from apps.outline.models import OutlineVersion
from apps.volume.models import VolumeVersion, VolumeList
from apps.ai.llm import get_llm
from apps.ai.prompts import VOLUME_GENERATION_PROMPT, VOLUME_OPTIMIZE_PROMPT
from apps.user.models import TokenUsageLog


def log_token_usage(task_type: str, prompt_tokens: int, completion_tokens: int, user=None, project=None):
    try:
        TokenUsageLog.objects.create(
            user=user,
            project=project,
            model_name='',
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
    except Exception as e:
        logger.error(f"记录Token使用失败: {e}")


def _call_with_retry(messages, stream=False, timeout=None, user=None, scene="default"):
    from django.conf import settings
    
    max_retries = settings.LLM_RETRY
    retry_interval = settings.LLM_RETRY_INTERVAL

    llm = get_llm(user=user, scene=scene, timeout=timeout)

    prompt_messages = []
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            prompt_messages.append((role, content))
        else:
            if hasattr(msg, 'content'):
                if hasattr(msg, 'role'):
                    prompt_messages.append((msg.role, msg.content))
                elif isinstance(msg, SystemMessage):
                    prompt_messages.append(('system', msg.content))
                elif isinstance(msg, HumanMessage):
                    prompt_messages.append(('user', msg.content))
    
    prompt = ChatPromptTemplate.from_messages(prompt_messages)
    chain = prompt | llm

    for retry_count in range(max_retries):
        try:
            if stream:
                def gen():
                    for chunk in chain.stream({}):
                        if hasattr(chunk, 'content'):
                            yield chunk.content
                        else:
                            yield str(chunk)
                    return gen()
            else:
                result = chain.invoke({})
                if hasattr(result, 'content'):
                    return result.content
                return str(result)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"LLM调用失败: {error_msg}, 重试 {retry_count + 1}/{max_retries}")
            if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                retry_interval *= 2
            if retry_count < max_retries - 1:
                time.sleep(retry_interval)

    raise Exception(f"LLM调用失败，已重试 {max_retries} 次")


def generate_volumes(outline, user=None, project=None):
    prompt = VOLUME_GENERATION_PROMPT.format(outline=outline)
    
    messages = [
        SystemMessage(content="你是一位专业的小说结构设计助手，请严格按照JSON格式返回。"),
        HumanMessage(content=prompt)
    ]
    
    response = _call_with_retry(messages, user=user, scene="volume_generate")
    
    if hasattr(response, 'usage_metadata'):
        log_token_usage('volume', 
                      response.usage_metadata.get('input_tokens', 0),
                      response.usage_metadata.get('output_tokens', 0),
                      user, project)
    
    try:
        result = json.loads(response)
        return result.get('volumes', [])
    except json.JSONDecodeError:
        logger.error(f"解析卷生成响应失败: {response}")
        return []


def optimize_volumes(outline, current_volumes, user_feedback, user=None, project=None):
    prompt = VOLUME_OPTIMIZE_PROMPT.format(
        current_volumes=current_volumes,
        outline=outline,
        user_feedback=user_feedback
    )
    
    messages = [
        SystemMessage(content="你是一位专业的小说结构设计助手，请严格按照JSON格式返回。"),
        HumanMessage(content=prompt)
    ]
    
    response = _call_with_retry(messages, user=user, scene="volume_generate")
    
    if hasattr(response, 'usage_metadata'):
        log_token_usage('volume', 
                      response.usage_metadata.get('input_tokens', 0),
                      response.usage_metadata.get('output_tokens', 0),
                      user, project)
    
    try:
        result = json.loads(response)
        return result.get('volumes', [])
    except json.JSONDecodeError:
        logger.error(f"解析卷优化响应失败: {response}")
        return []


class GenerateVolumesView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        project_id = request.data.get('project_id') or request.POST.get('project_id')
        outline_version_id = request.data.get('outline_version_id') or request.POST.get('outline_version_id')
        
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project=project)
        
        volumes_data = generate_volumes(outline_version.content, user=request.user, project=project)
        
        latest_version = project.volume_versions.filter(is_deleted=False).order_by('-version_number').first()
        new_version_number = latest_version.version_number + 1 if latest_version else 1
        
        volume_version = VolumeVersion.objects.create(
            project=project,
            outline_version=outline_version,
            version_number=new_version_number
        )
        
        for vol_data in volumes_data:
            VolumeList.objects.create(
                volume_version=volume_version,
                volume_number=vol_data['volume_number'],
                title=vol_data['title'],
                summary=vol_data['summary']
            )
        
        return JsonResponse({
            'success': True,
            'version_id': volume_version.pk,
            'version_number': volume_version.version_number,
            'volumes': volumes_data
        })


class SaveVolumeVersionView(View):
    def post(self, request):
        project_id = request.POST.get('project_id')
        outline_version_id = request.POST.get('outline_version_id')
        volumes_json = request.POST.get('volumes', '[]')
        
        try:
            volumes_data = json.loads(volumes_json)
        except json.JSONDecodeError:
            volumes_data = []
        
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project=project)
        
        latest_version = project.volume_versions.filter(is_deleted=False).order_by('-version_number').first()
        new_version_number = latest_version.version_number + 1 if latest_version else 1
        
        volume_version = VolumeVersion.objects.create(
            project=project,
            outline_version=outline_version,
            version_number=new_version_number
        )
        
        for vol_data in volumes_data:
            VolumeList.objects.create(
                volume_version=volume_version,
                volume_number=vol_data['volume_number'],
                title=vol_data['title'],
                summary=vol_data['summary']
            )
        
        return JsonResponse({
            'success': True,
            'version_id': volume_version.pk,
            'version_number': volume_version.version_number
        })


class LoadVolumeVersionView(View):
    def get(self, request, version_id):
        volume_version = get_object_or_404(VolumeVersion, pk=version_id, project__user=request.user)
        
        volumes = []
        for vol in volume_version.volumes.all():
            volumes.append({
                'id': vol.id,
                'volume_number': vol.volume_number,
                'title': vol.title,
                'summary': vol.summary
            })
        
        return JsonResponse({
            'success': True,
            'volumes': volumes,
            'outline_version_id': volume_version.outline_version.pk
        })


class OptimizeVolumesView(View):
    def post(self, request):
        project_id = request.POST.get('project_id')
        volume_version_id = request.POST.get('volume_version_id')
        user_feedback = request.POST.get('feedback')
        
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        volume_version = get_object_or_404(VolumeVersion, pk=volume_version_id, project=project)
        
        current_volumes = []
        for vol in volume_version.volumes.all():
            current_volumes.append({
                'volume_number': vol.volume_number,
                'title': vol.title,
                'summary': vol.summary
            })
        
        volumes_data = optimize_volumes(
            volume_version.outline_version.content,
            json.dumps(current_volumes),
            user_feedback,
            user=request.user,
            project=project
        )
        
        latest_version = project.volume_versions.filter(is_deleted=False).order_by('-version_number').first()
        new_version_number = latest_version.version_number + 1 if latest_version else 1
        
        new_volume_version = VolumeVersion.objects.create(
            project=project,
            outline_version=volume_version.outline_version,
            version_number=new_version_number
        )
        
        for vol_data in volumes_data:
            VolumeList.objects.create(
                volume_version=new_volume_version,
                volume_number=vol_data['volume_number'],
                title=vol_data['title'],
                summary=vol_data['summary']
            )
        
        return JsonResponse({
            'success': True,
            'version_id': new_volume_version.pk,
            'version_number': new_volume_version.version_number,
            'volumes': volumes_data
        })


class FinalizeVolumeVersionView(View):
    def post(self, request):
        version_id = request.POST.get('version_id')
        volume_version = get_object_or_404(VolumeVersion, pk=version_id, project__user=request.user)
        volume_version.is_finalized = True
        volume_version.save()
        return JsonResponse({'success': True})


# ========== API Views ==========

class ApiVolumeVersionsView(APIView):
    """获取项目的卷版本列表"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, project_id):
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        versions = project.volume_versions.filter(is_deleted=False).order_by('-created_at')
        
        versions_data = []
        for v in versions:
            versions_data.append({
                'id': v.id,
                'version_number': v.version_number,
                'is_finalized': v.is_finalized,
                'created_at': v.created_at.strftime('%Y-%m-%d %H:%M'),
                'outline_version_number': v.outline_version.version_number,
                'volume_count': v.volumes.count()
            })
        
        return JsonResponse({'success': True, 'versions': versions_data})


class ApiVolumeVersionView(APIView):
    """获取单个卷版本详情"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request, version_id):
        volume_version = get_object_or_404(VolumeVersion, pk=version_id, project__user=request.user)
        
        volumes = []
        for vol in volume_version.volumes.all():
            volumes.append({
                'id': vol.id,
                'volume_number': vol.volume_number,
                'title': vol.title,
                'summary': vol.summary
            })
        
        return JsonResponse({
            'success': True,
            'volumes': volumes,
            'outline_version_id': volume_version.outline_version.pk,
            'is_finalized': volume_version.is_finalized
        })


class ApiSaveVolumeVersionView(APIView):
    """保存卷版本"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        project_id = request.data.get('project_id') or request.POST.get('project_id')
        outline_version_id = request.data.get('outline_version_id') or request.POST.get('outline_version_id')
        volumes_json = request.data.get('volumes') or request.POST.get('volumes', '[]')
        
        try:
            volumes_data = json.loads(volumes_json)
        except json.JSONDecodeError:
            volumes_data = []
        
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project=project)
        
        latest_version = project.volume_versions.filter(is_deleted=False).order_by('-version_number').first()
        new_version_number = latest_version.version_number + 1 if latest_version else 1
        
        volume_version = VolumeVersion.objects.create(
            project=project,
            outline_version=outline_version,
            version_number=new_version_number
        )
        
        for vol_data in volumes_data:
            VolumeList.objects.create(
                volume_version=volume_version,
                volume_number=vol_data['volume_number'],
                title=vol_data['title'],
                summary=vol_data['summary']
            )
        
        return JsonResponse({
            'success': True,
            'version_id': volume_version.pk,
            'version_number': volume_version.version_number
        })


class ApiVolumeFinalizeView(APIView):
    """定稿卷版本"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        project_id = request.data.get('project_id') or request.POST.get('project_id')
        version_id = request.data.get('version_id') or request.POST.get('version_id')
        
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        volume_version = get_object_or_404(VolumeVersion, pk=version_id, project=project)
        
        # 取消其他版本的定稿状态
        project.volume_versions.filter(is_finalized=True).update(is_finalized=False)
        
        volume_version.is_finalized = True
        volume_version.save()
        
        return JsonResponse({'success': True})


class ApiVolumeDeleteView(APIView):
    """删除卷版本"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        project_id = request.data.get('project_id') or request.POST.get('project_id')
        version_id = request.data.get('version_id') or request.POST.get('version_id')
        
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        volume_version = get_object_or_404(VolumeVersion, pk=version_id, project=project)
        
        volume_version.is_deleted = True
        volume_version.save()
        
        return JsonResponse({'success': True})


class ApiVolumeChatView(APIView):
    """卷对话 API"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        project_id = request.data.get('project_id') or request.POST.get('project_id')
        message = request.data.get('message') or request.POST.get('message')
        volume_version_id = request.data.get('volume_version_id') or request.POST.get('volume_version_id')
        
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        
        # 获取当前卷数据
        current_volumes = []
        if volume_version_id:
            try:
                volume_version = VolumeVersion.objects.get(pk=volume_version_id, project=project)
                for vol in volume_version.volumes.all():
                    current_volumes.append({
                        'volume_number': vol.volume_number,
                        'title': vol.title,
                        'summary': vol.summary
                    })
            except VolumeVersion.DoesNotExist:
                pass
        
        # 简单的响应，后续可以完善 AI 对话
        return JsonResponse({
            'success': True,
            'response': '好的，我收到了您的消息。卷对话功能正在完善中...',
            'volumes': current_volumes
        })
