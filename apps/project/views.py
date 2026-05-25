import json
import time
from loguru import logger
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.views import APIView, Response
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from apps.project.models import ProjectList
from apps.outline.models import OutlineVersion
from apps.volume.models import VolumeVersion, VolumeList
from apps.chapter.models import ChapterVersion, ChapterList
from apps.user.models import TokenUsageLog
from apps.ai.llm import get_llm
from apps.ai.prompts import TITLE_SUGGESTION_JSON_PROMPT


def log_token_usage(task_type: str, prompt_tokens: int, completion_tokens: int, user=None, project=None):
    try:
        TokenUsageLog.objects.create(
            user=user,
            project=project,
            model_name=settings.LLM_MODEL,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
    except Exception as e:
        logger.error(f"记录Token使用失败: {e}")


def _call_with_retry(messages, stream=False, timeout=None, user=None, scene="default"):
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


def suggest_title_from_outline(outline: str, user=None, project=None) -> list:
    """根据大纲生成书名建议（返回JSON数组）"""
    prompt = TITLE_SUGGESTION_JSON_PROMPT.format(outline=outline)

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长为小说起吸引人的书名。请严格按照JSON数组格式返回。"),
        HumanMessage(content=prompt)
    ]

    response = _call_with_retry(messages, user=user, scene="default")

    try:
        result = json.loads(response)
        if isinstance(result, list):
            return result[:5]
        elif isinstance(result, dict) and 'titles' in result:
            return result['titles'][:5]
    except json.JSONDecodeError as e:
        logger.error(f"解析书名建议响应失败: {e}, 内容: {response[:200]}...")

    return []


def suggest_description_from_outline(outline: str, user=None, project=None) -> str:
    """根据大纲生成简介建议"""
    prompt = f"""请根据以下小说大纲，生成一个吸引人的小说简介（约100字）：

小说大纲：
{outline}

请直接返回简介内容，不需要其他格式。"""

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长为小说创作吸引人的简介。"),
        HumanMessage(content=prompt)
    ]

    return _call_with_retry(messages, user=user, scene="default")


def generate_project_title():
    projects_count = ProjectList.objects.count() + 1
    return f"小说{projects_count}"


# ============ Project Views ============

class ProjectListView(View):
    '''项目列表视图 - 根路径重定向到 index.html'''

    def get(self, request):
        from django.shortcuts import redirect
        return redirect('/index.html')


class ProjectCreateView(View):
    '''项目创建视图'''
    def get(self, request):
        return render(request, 'index.html')

    def post(self, request):
        title = request.POST.get('title', '')
        if not title or title.strip() == '':
            title = generate_project_title()
        description = request.POST.get('description', '')
        project = ProjectList.objects.create(title=title, description=description, user=request.user)
        return redirect('project_detail', pk=project.pk)


class ApiAutoSaveChatView(APIView):
    '''自动保存聊天内容（已废弃，请使用 ApiSaveProjectView）'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            project_id = request.POST.get('project_id')
            outline = request.POST.get('outline', '')
            messages = request.POST.get('messages', '[]')
            create_version = request.POST.get('create_version', 'false').lower() == 'true'
            title = request.POST.get('title', '')
            description = request.POST.get('description', '')

            messages_list = json.loads(messages) if messages else []

            if project_id:
                # 更新现有项目
                project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
            else:
                # 创建新项目
                project = ProjectList.objects.create(
                    title=title or generate_project_title(),
                    description=description or '',
                    user=request.user
                )

            # 更新项目标题和描述
            if title and project.title != title:
                project.title = title
                project.save()
            if description is not None and project.description != description:
                project.description = description
                project.save()

            # 只保存大纲内容到 OutlineVersion（聊天记录由 ChatNewOutlineStreamView 保存）
            from apps.outline.models import OutlineVersion
            building_version = OutlineVersion.get_or_create_building_version(project)
            building_version.content = outline
            building_version.save()

            # 如果是手动保存（create_version=true），创建新版本
            if create_version and outline:
                # 检查是否已存在 version_number=1 的版本
                existing_version = project.outline_versions.filter(
                    is_deleted=False,
                    version_number=1
                ).first()

                if existing_version:
                    # 更新现有版本
                    existing_version.content = outline
                    existing_version.is_current = True
                    existing_version.save()
                else:
                    # 创建新版本 version_number=1
                    OutlineVersion.objects.create(
                        project=project,
                        version_number=1,
                        content=outline,
                        is_current=True,
                        is_finalized=False
                    )
                # 将 version_number=0 的版本标记为已删除（如果存在）
                project.outline_versions.filter(
                    is_deleted=False,
                    version_number=0
                ).update(is_deleted=True)

            return JsonResponse({
                'success': True,
                'project_id': project.id
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})


class ProjectDetailView(View):
    '''项目详情视图'''
    def get(self, request, project_id):
        # 页面只负责渲染 HTML，数据由前端通过 API 获取
        # 这样未登录用户也能访问页面，然后由前端处理登录
        return render(request, 'project.html')


class ProjectUpdateTitleView(View):
    '''项目更新标题视图'''
    def post(self, request, project_id):
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        title = request.POST.get('title')
        if title:
            project.title = title
            project.save()
        return JsonResponse({'success': True, 'title': project.title})


class ProjectUpdateInfoView(View):
    '''项目更新信息视图'''
    def post(self, request, project_id):
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        if title:
            project.title = title
        if description is not None:
            project.description = description
        
        project.save()
        return JsonResponse({'success': True})


# ============ 新页面视图 ============

class OutlineBuilderView(View):
    '''大纲构建页面视图'''
    def get(self, request, project_id):
        return render(request, 'outline.html')


class TimelineView(View):
    '''时间线页面视图'''
    def get(self, request, project_id):
        return render(request, 'timeline.html')


class VolumeView(View):
    '''卷管理页面视图'''
    def get(self, request, project_id):
        return render(request, 'volume.html')


class ChapterGeneratorView(View):
    '''章节生成页面视图'''
    def get(self, request, project_id):
        return render(request, 'chapter_generator.html')


class ContentManagerView(View):
    '''内容管理页面视图'''
    def get(self, request, project_id):
        return render(request, 'content.html')


class NoteView(View):
    '''随手记页面视图'''
    def get(self, request, project_id):
        return render(request, 'note.html')


class CharacterView(View):
    '''人物管理页面视图'''
    def get(self, request, project_id):
        return render(request, 'character.html')


# ============ Project API Views ============

class ApiProjectListView(APIView):
    '''项目列表API'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        projects = ProjectList.objects.filter(user=request.user, is_deleted=False).order_by('-created_at')

        projects_data = []
        for project in projects:
            outline_versions = project.outline_versions.filter().order_by('-version_number')
            version_count = outline_versions.count()
            latest_outline = outline_versions.first()
            projects_data.append({
                'id': project.id,
                'title': project.title,
                'description': project.description,
                'status': 'completed' if project.finalized else ('writing' if latest_outline and latest_outline.is_finalized else 'draft'),
                'version_count': version_count,
                'latest_version_number': latest_outline.version_number if latest_outline else 0,
                'created_at': project.created_at.strftime('%Y-%m-%d %H:%M'),
                'updated_at': project.updated_at.strftime('%Y-%m-%d %H:%M')
            })
        return JsonResponse({'success': True, 'projects': projects_data})


class ApiProjectDetailView(APIView):
    '''项目详情API视图'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
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

            latest_outline = outline_versions.order_by('-version_number').first()
            return JsonResponse({
                'success': True,
                'project': {
                    'pk': project.pk,
                    'title': project.title,
                    'description': project.description,
                    'status': project.status,
                    'finalized': project.finalized,
                    'version_count': outline_versions.count(),
                    'latest_version_number': latest_outline.version_number if latest_outline else 0,
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
            return JsonResponse({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApiProjectCreateView(APIView):
    '''创建项目API'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            title = request.data.get('title', '').strip()
            description = request.data.get('description', '')

            if not title:
                title = generate_project_title()

            # 检查同名项目是否存在
            if ProjectList.objects.filter(user=request.user, title=title, is_deleted=False).exists():
                return JsonResponse({'success': False, 'error': '该项目名称已存在'}, status=400)

            project = ProjectList.objects.create(title=title, description=description, user=request.user)
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


class ApiProjectDeleteView(APIView):
    '''删除项目API（软删除）'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            project.is_deleted = True
            project.save()
            return Response({'success': True})
        except Exception as e:
            return Response({'success': False, 'message': 'internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApiProjectUpdateView(APIView):
    '''更新项目API'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)

            title = request.data.get('title', '').strip()
            description = request.data.get('description', '')

            if title and title != project.title:
                # 检查同名项目是否存在（排除自己）
                if ProjectList.objects.filter(user=request.user, title=title, is_deleted=False).exclude(pk=pk).exists():
                    return JsonResponse({'success': False, 'error': '该项目名称已存在'}, status=400)
                project.title = title
            if description is not None:
                project.description = description

            project.save()

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiProjectFinalizeView(APIView):
    '''项目定稿API'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            
            project.outline_versions.filter(is_deleted=False, is_finalized=True).update(is_finalized=False)
            
            latest_version = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
            if latest_version:
                latest_version.is_finalized = True
                latest_version.save()
            
            project.finalized = True
            project.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class ApiProjectStatsView(APIView):
    '''项目统计API视图'''
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            
            volume_count = VolumeList.objects.filter(
                volume_version__project=project,
                volume_version__is_deleted=False
            ).count()
            
            chapters = ChapterList.objects.filter(
                chapter_version__volume__volume_version__project=project,
                chapter_version__is_deleted=False
            )
            
            chapter_count = chapters.count()
            chapter_with_summary = chapters.exclude(summary__isnull=True).exclude(summary='').count()
            chapter_with_content = chapters.exclude(content__isnull=True).exclude(content='').count()
            chapter_finalized = chapters.filter(chapter_version__is_finalized=True).count()
            chapter_published = chapters.filter(status=ChapterList.STATUS_PUBLISHED).count()
            
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




class ApiTitleSuggestView(APIView):
    """AI生成书名建议API"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            outline = request.data.get('outline', '')
            project_id = request.data.get('project_id')
            
            # 如果提供了project_id，从项目获取大纲内容
            if project_id:
                try:
                    project = ProjectList.objects.get(pk=project_id, user=request.user)
                    # 获取项目的大纲内容（优先定稿版本，无定稿则取version_number最大的）
                    outline_version = project.outline_versions.filter(is_deleted=False).order_by('-is_finalized', '-version_number').first()
                    if outline_version and outline_version.content:
                        outline = outline_version.content
                except ProjectList.DoesNotExist:
                    return JsonResponse({'success': False, 'message': '项目不存在'})
            
            if not outline:
                return JsonResponse({'success': False, 'message': '请提供大纲内容'})

            titles = suggest_title_from_outline(outline, user=request.user)
            
            return JsonResponse({'success': True, 'titles': titles})
        except Exception as e:
            logger.error(f"生成书名失败: {e}")
            return JsonResponse({'success': False, 'message': str(e)})


class ApiDescriptionSuggestView(APIView):
    """AI生成简介建议API"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            outline = request.data.get('outline', '') or request.POST.get('outline', '')
            project_id = request.data.get('project_id') or request.POST.get('project_id')
            
            # 如果提供了project_id，从项目获取大纲内容
            if project_id:
                try:
                    project = ProjectList.objects.get(pk=project_id, user=request.user)
                    # 获取项目的大纲内容（优先定稿版本，无定稿则取version_number最大的）
                    outline_version = project.outline_versions.filter(is_deleted=False).order_by('-is_finalized', '-version_number').first()
                    
                    if outline_version and outline_version.content:
                        outline = outline_version.content
                except ProjectList.DoesNotExist:
                    return JsonResponse({'success': False, 'message': '项目不存在'})
            
            if not outline:
                return JsonResponse({'success': False, 'message': '请提供大纲内容'})

            description = suggest_description_from_outline(outline, user=request.user)
            
            return JsonResponse({'success': True, 'description': description})
        except Exception as e:
            logger.error(f"生成简介失败: {e}")
            return JsonResponse({'success': False, 'message': str(e)})


class ApiSaveProjectView(APIView):
    """保存项目API（创建或更新项目）"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            project_id = request.data.get('project_id') or request.POST.get('project_id')
            title = request.data.get('title') or request.POST.get('title', '')
            description = request.data.get('description') or request.POST.get('description', '')
            outline = request.data.get('outline') or request.POST.get('outline', '')
            messages = request.data.get('messages') or request.POST.get('messages', '[]')
            
            messages_list = json.loads(messages) if messages else []

            if project_id:
                project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
                if title and project.title != title:
                    project.title = title
                if description is not None and project.description != description:
                    project.description = description
                project.save()
            else:
                project = ProjectList.objects.create(
                    title=title or generate_project_title(),
                    description=description or '',
                    user=request.user
                )

            from apps.outline.models import OutlineVersion, OutlineChatHistory
            building_version = OutlineVersion.get_or_create_building_version(project)
            building_version.content = outline
            building_version.save()

            for msg in messages_list:
                OutlineChatHistory.objects.create(
                    outline_version=building_version,
                    role=msg.get('role', 'user'),
                    content=msg.get('content', '')
                )

            if outline:
                existing_version = project.outline_versions.filter(
                    is_deleted=False,
                    version_number=1
                ).first()

                if existing_version:
                    existing_version.content = outline
                    existing_version.is_current = True
                    existing_version.save()
                else:
                    OutlineVersion.objects.create(
                        project=project,
                        version_number=1,
                        content=outline,
                        is_current=True,
                        is_finalized=False
                    )
                project.outline_versions.filter(
                    is_deleted=False,
                    version_number=0
                ).update(is_deleted=True)

            return JsonResponse({
                'success': True,
                'project_id': project.id
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error(f"保存项目失败: {e}")
            return JsonResponse({'success': False, 'message': str(e)})
