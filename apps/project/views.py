import json
import traceback
from typing import Optional
from loguru import logger
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import JsonResponse, StreamingHttpResponse
from django.conf import settings
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.views import APIView, Response
from rest_framework import status
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from apps.project.models import ProjectList
from apps.outline.models import OutlineVersion, OutlineChatHistory
from apps.project.prompts import DESCRIPTION_ENHANCE_USER_PROMPT, DESCRIPTION_ENHANCE_SYSTEM_PROMPT
from apps.volume.models import VolumeVersion, VolumeList
from apps.chapter.models import ChapterList
from apps.user.models import TokenUsageLog
from apps.worldview.models import WorldView
from agent.llm import get_llm, call_llm_with_retry
from .prompts import (
    TITLE_SUGGESTION_JSON_PROMPT,
    PROJECT_INFO_GENERATION_PROMPT,
    TITLE_SUGGESTION_PROMPT,
    TITLE_REWRITE_PROMPT,
    DESCRIPTION_OPTIMIZE_PROMPT,
)
from apps.project.base import BaseAPIView


def suggest_title_from_outline(outline: str, user=None, project=None) -> list:
    """根据大纲生成书名建议（返回JSON数组）"""
    prompt = TITLE_SUGGESTION_JSON_PROMPT.format(outline=outline)

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长为小说起吸引人的书名。请严格按照JSON数组格式返回。"),
        HumanMessage(content=prompt)
    ]

    response = call_llm_with_retry(messages, user=user, scene="default", project=project, task_type='project_title_suggest_json')

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

    return call_llm_with_retry(messages, user=user, scene="default", project=project, task_type='project_description_suggest')


def generate_project_title():
    projects_count = ProjectList.objects.count() + 1
    return f"小说{projects_count}"


# ============ Project Views ============

class ProjectListView(View):
    '''项目列表视图 - 根路径重定向到 index.html'''

    def get(self, request):
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


class ApiAutoSaveChatView(BaseAPIView):
    '''自动保存聊天内容（已废弃，请使用 ApiSaveProjectView）'''

    def post(self, request):
        try:
            project_id = request.data.get('project_id')
            outline = request.data.get('outline', '')
            messages = request.data.get('messages', '[]')
            create_version = request.data.get('create_version', 'false').lower() == 'true'
            title = request.data.get('title', '')
            description = request.data.get('description', '')

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

class ApiProjectListView(BaseAPIView):
    '''项目列表API'''

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


class ApiProjectDetailView(BaseAPIView):
    '''项目详情API视图（GET/PUT/DELETE）'''

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
                    chapters = ChapterList.objects.filter(volume__volume_version=selected_volume).order_by('chapter_number')
                    chapter_versions = [{
                        'pk': c.pk,
                        'chapter_number': c.chapter_number,
                        'title': c.title,
                        'status': c.status,
                        'updated_at': c.updated_at.strftime('%Y-%m-%d %H:%M')
                    } for c in chapters]
                except VolumeVersion.DoesNotExist:
                    pass
            elif view_type == 'chapter' and version_id:
                try:
                    selected_chapter = ChapterList.objects.get(pk=version_id)
                except ChapterList.DoesNotExist:
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
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, request, pk):
        """更新项目"""
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            title = request.data.get('title', '').strip()
            description = request.data.get('description', '')

            if title and title != project.title:
                if ProjectList.objects.filter(user=request.user, title=title, is_deleted=False).exclude(pk=pk).exists():
                    return JsonResponse({'success': False, 'error': '该项目名称已存在'}, status=400)
                project.title = title
            if description is not None:
                project.description = description

            project.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    def delete(self, request, pk):
        """软删除项目"""
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            project.is_deleted = True
            project.save()
            return Response({'success': True})
        except Exception as e:
            return Response({'success': False, 'message': 'internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ApiProjectCreateView(BaseAPIView):
    '''创建项目API'''

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


class ApiProjectFinalizeView(BaseAPIView):
    '''项目定稿API'''

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


class ApiProjectStatsView(BaseAPIView):
    '''项目统计API视图'''

    def get(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            
            volume_count = VolumeList.objects.filter(
                volume_version__project=project,
                volume_version__is_deleted=False
            ).count()
            
            chapters = ChapterList.objects.filter(
                volume__volume_version__project=project,
                volume__volume_version__is_deleted=False
            )

            chapter_count = chapters.count()
            chapter_with_summary = chapters.exclude(summary__isnull=True).exclude(summary='').count()
            chapter_with_content = chapters.exclude(content__isnull=True).exclude(content='').count()
            chapter_finalized = chapters.filter(volume__volume_version__is_finalized=True).count()
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




class ApiTitleSuggestView(BaseAPIView):
    """AI生成书名建议API"""

    def post(self, request, pk):
        try:
            outline = request.data.get('outline', '')
            project_id = pk
            
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

            titles = suggest_title_from_outline(outline, user=request.user, project=project if project_id else None)
            
            return JsonResponse({'success': True, 'titles': titles})
        except Exception as e:
            logger.error(f"生成书名失败: {e}")
            return JsonResponse({'success': False, 'message': str(e)})


class ApiDescriptionSuggestView(BaseAPIView):
    """AI生成简介建议API"""

    def post(self, request, pk):
        try:
            outline = request.data.get('outline', '')
            project_id = pk
            
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

            description = suggest_description_from_outline(outline, user=request.user, project=project if project_id else None)
            
            return JsonResponse({'success': True, 'description': description})
        except Exception as e:
            logger.error(f"生成简介失败: {e}")
            return JsonResponse({'success': False, 'message': str(e)})


class ApiSaveProjectView(BaseAPIView):
    """保存项目API（创建或更新项目）"""

    def post(self, request):
        try:
            project_id = request.data.get('project_id')
            title = request.data.get('title', '')
            description = request.data.get('description', '')
            outline = request.data.get('outline', '')
            messages = request.data.get('messages', '[]')
            
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
            traceback.print_exc()
            logger.error(f"保存项目失败: {e}")
            return JsonResponse({'success': False, 'message': str(e)})


class ApiEnhanceDescriptionView(BaseAPIView):
    """AI完善描述API - 流式响应"""

    def post(self, request, pk=None):
        try:
            title = request.data.get('title', '').strip()
            description = request.data.get('description', '').strip()
            project_id = pk

            if not description:
                return JsonResponse({'success': False, 'error': '请提供描述内容'})

            worldview = ''
            outline = ''

            if project_id:
                try:
                    project = ProjectList.objects.get(pk=project_id, user=request.user)

                    latest_version = project.outline_versions.filter(
                        is_deleted=False
                    ).order_by('-version_number').first()

                    if latest_version:
                        outline = latest_version.content or ''

                    worldview = WorldView.objects.filter(
                        project=project
                    ).order_by('-created_at').first()

                    if worldview:
                        if isinstance(worldview, dict):
                            worldview = json.dumps(worldview, ensure_ascii=False, indent=2)
                        else:
                            worldview = str(worldview)

                except ProjectList.DoesNotExist:
                    return JsonResponse({'success': False, 'error': '项目不存在'})

            prompt_template = ChatPromptTemplate.from_messages([
                ("system", DESCRIPTION_ENHANCE_SYSTEM_PROMPT),
                ("user", DESCRIPTION_ENHANCE_USER_PROMPT)
            ])

            llm = get_llm(user=request.user, scene="default")
            chain = prompt_template | llm

            try:
                result = chain.invoke({
                    "title": title or '未命名小说',
                    "description": description,
                    "worldview": worldview,
                    "outline": outline
                })
                self.log_token_usage('project_enhance_description', result=result, user=request.user, project=project if project_id else None)

                full_content = result.content if hasattr(result, 'content') else str(result)

                try:
                    import re
                    json_match = re.search(r'\{.*\}', full_content, re.DOTALL)
                    if json_match:
                        parsed_result = json.loads(json_match.group())
                        return JsonResponse({
                            'success': True,
                            'title': parsed_result.get('title', ''),
                            'description': parsed_result.get('description', '')
                        })
                    else:
                        return JsonResponse({
                            'success': True,
                            'title': title or '',
                            'description': full_content
                        })
                except:
                    return JsonResponse({
                        'success': True,
                        'title': title or '',
                        'description': full_content
                    })

            except Exception as e:
                logger.error(f"AI完善描述生成失败: {e}")
                raise

        except Exception as e:
            traceback.print_exc()
            logger.error(f"AI完善描述失败: {e}")
            return JsonResponse({'success': False, 'error': str(e)})


# ============ 项目信息生成辅助函数（从 apps/ai 迁移） ============

def generate_project_info(outline: str, user=None, project=None) -> Optional[dict]:
    prompt = PROJECT_INFO_GENERATION_PROMPT.format(outline=outline)

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长为小说创作吸引人的书名和简介。请严格按照JSON格式返回。"),
        HumanMessage(content=prompt)
    ]

    response = call_llm_with_retry(messages, user=user, scene="default", project=project, task_type='project_info_generate')

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        logger.error(f"解析项目信息生成响应失败: {response}")
        return None


def suggest_title(outline: str, user=None, project=None) -> str:
    prompt = TITLE_SUGGESTION_PROMPT.format(outline=outline)

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长为小说起吸引人的书名。"),
        HumanMessage(content=prompt)
    ]

    return call_llm_with_retry(messages, user=user, scene="default", project=project, task_type='project_title_suggest')


def rewrite_title(original_title: str, user=None, project=None) -> list:
    prompt = TITLE_REWRITE_PROMPT.format(original_title=original_title)

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长为小说起吸引人的书名。请以JSON数组格式返回5个建议的书名。"),
        HumanMessage(content=prompt)
    ]

    response = call_llm_with_retry(messages, user=user, scene="default", project=project, task_type='project_title_rewrite')

    try:
        result = json.loads(response)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict):
            return result.get('titles', [])
        return []
    except json.JSONDecodeError:
        logger.error(f"解析重写标题响应失败: {response}")
        return []


def optimize_description(description: str, user=None, project=None) -> str:
    if not description or description.strip() == "":
        return "请输入小说简介"

    prompt = DESCRIPTION_OPTIMIZE_PROMPT.format(description=description)

    messages = [
        SystemMessage(content="你是一位专业的文学编辑，擅长优化和润色小说简介。"),
        HumanMessage(content=prompt)
    ]

    return call_llm_with_retry(messages, user=user, scene="default", project=project, task_type='project_description_optimize')


# ============ 项目信息生成视图（从 apps/ai 迁移） ============

class GenerateProjectInfoView(View):
    def post(self, request):
        project_id = request.POST.get('project_id')
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        
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
        
        result = generate_project_info(outline_content, user=request.user, project=project)
        
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


class SuggestTitleView(BaseAPIView):

    def post(self, request):
        outline_version_id = request.data.get('outline_version_id')
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project__user=request.user)
        
        suggestions = suggest_title(outline_version.content)
        
        return JsonResponse({'success': True, 'suggestions': suggestions})


class RewriteTitleView(View):
    def post(self, request):
        original_title = request.POST.get('original_title')
        
        suggestions = rewrite_title(original_title)
        
        return JsonResponse({'success': True, 'suggestions': suggestions})


class OptimizeDescriptionView(View):
    def post(self, request):
        description = request.POST.get('description')
        
        optimized = optimize_description(description)
        
        return JsonResponse({'success': True, 'optimized': optimized})
