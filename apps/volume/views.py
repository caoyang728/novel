"""
Volume views - 卷相关视图
"""
import json
from django.http import JsonResponse, StreamingHttpResponse
from django.views import View
from django.shortcuts import get_object_or_404
from apps.core.models import Project, VolumeVersion, Volume, OutlineVersion
from apps.ai.services import LLMService

llm_service = LLMService()


class GenerateVolumesView(View):
    def post(self, request):
        project_id = request.POST.get('project_id')
        outline_version_id = request.POST.get('outline_version_id')
        
        project = get_object_or_404(Project, pk=project_id, user=request.user)
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project=project)
        
        volumes_data = llm_service.generate_volumes(outline_version.content)
        
        latest_version = project.volume_versions.filter(is_deleted=False).order_by('-version_number').first()
        new_version_number = latest_version.version_number + 1 if latest_version else 1
        
        volume_version = VolumeVersion.objects.create(
            project=project,
            outline_version=outline_version,
            version_number=new_version_number
        )
        
        for vol_data in volumes_data:
            Volume.objects.create(
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
        
        project = get_object_or_404(Project, pk=project_id, user=request.user)
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project=project)
        
        latest_version = project.volume_versions.filter(is_deleted=False).order_by('-version_number').first()
        new_version_number = latest_version.version_number + 1 if latest_version else 1
        
        volume_version = VolumeVersion.objects.create(
            project=project,
            outline_version=outline_version,
            version_number=new_version_number
        )
        
        for vol_data in volumes_data:
            Volume.objects.create(
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
        
        project = get_object_or_404(Project, pk=project_id, user=request.user)
        volume_version = get_object_or_404(VolumeVersion, pk=volume_version_id, project=project)
        
        current_volumes = []
        for vol in volume_version.volumes.all():
            current_volumes.append({
                'volume_number': vol.volume_number,
                'title': vol.title,
                'summary': vol.summary
            })
        
        volumes_data = llm_service.optimize_volumes(
            volume_version.outline_version.content,
            json.dumps(current_volumes),
            user_feedback
        )
        
        latest_version = project.volume_versions.filter(is_deleted=False).order_by('-version_number').first()
        new_version_number = latest_version.version_number + 1 if latest_version else 1
        
        new_volume_version = VolumeVersion.objects.create(
            project=project,
            outline_version=volume_version.outline_version,
            version_number=new_version_number
        )
        
        for vol_data in volumes_data:
            Volume.objects.create(
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