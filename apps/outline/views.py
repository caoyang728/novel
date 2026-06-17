import json
import re
from loguru import logger
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db import transaction

from apps.project.base import BaseAPIView
from apps.project.models import ProjectList
from apps.outline.models import OutlineVersion, OutlineChatHistory
from agent.llm import stream_llm_response
from .prompts import OUTLINE_BUILD_SYSTEM_PROMPT, OUTLINE_BUILD_USER_PROMPT


class BaseOutlineAPIView(BaseAPIView):
    """大纲API基础类 - 继承项目基础类，添加大纲相关工具方法"""


class ApiChatOutlineView(BaseOutlineAPIView):
    # 输入长度限制
    MAX_USER_INPUT_LENGTH = 5000
    MAX_OUTLINE_LENGTH = 200000
    MAX_HISTORY_COUNT = 100

    def post(self, request, project_id):
        project_id = project_id or request.data.get('project_id')
        version_number = request.data.get('version_number', 0)
        user_input = request.data.get('message', '')
        current_outline = request.data.get('current_outline', '')
        history_messages_raw = request.data.get('messages', [])

        if not project_id:
            return JsonResponse({'success': False, 'error': 'project_id 参数不能为空'}, status=400)

        if not user_input.strip():
            return JsonResponse({'success': False, 'error': '消息内容不能为空'}, status=400)

        if len(user_input) > self.MAX_USER_INPUT_LENGTH:
            return JsonResponse({'success': False, 'error': f'消息内容不能超过{self.MAX_USER_INPUT_LENGTH}字符'}, status=400)

        if len(current_outline) > self.MAX_OUTLINE_LENGTH:
            return JsonResponse({'success': False, 'error': f'大纲内容不能超过{self.MAX_OUTLINE_LENGTH}字符'}, status=400)

        # 校验 version_number 为非负整数
        try:
            version_number = int(version_number)
            if version_number < 0:
                raise ValueError
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'version_number 必须为非负整数'}, status=400)

        # 解析 messages：form-urlencoded 时为 JSON 字符串，JSON body 时为列表
        history_messages = []
        if isinstance(history_messages_raw, str):
            try:
                history_messages = json.loads(history_messages_raw)
            except json.JSONDecodeError:
                history_messages = []
        elif isinstance(history_messages_raw, list):
            history_messages = history_messages_raw

        # 校验历史消息数量和结构
        if len(history_messages) > self.MAX_HISTORY_COUNT:
            return JsonResponse({'success': False, 'error': f'历史消息不能超过{self.MAX_HISTORY_COUNT}条'}, status=400)
        for i, msg in enumerate(history_messages):
            if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
                return JsonResponse({'success': False, 'error': f'历史消息第{i+1}条格式错误，必须包含role和content'}, status=400)

        project = self.get_project_or_404(request, project_id)

        # 查询项目的世界观、人物、时间线上下文
        worldview_context, characters_context, timeline_context = self.get_project_context(project)

        prompt_vars = {
            'worldview_context': worldview_context,
            'characters_context': characters_context,
            'timeline_context': timeline_context,
            'current_outline': current_outline,
            'history_messages': history_messages,
            'user_input': user_input,
        }

        # 后处理：解析大纲内容和问题，保存到数据库
        def post_process(full_content):
            CONTENT_START = '════CONTENT_START════'
            CONTENT_END = '════CONTENT_END════'
            QUESTION_START = '════QUESTION_START════'
            QUESTION_END = '════QUESTION_END════'

            content_pattern = re.compile(CONTENT_START + r'(.*?)' + CONTENT_END, re.DOTALL)
            question_pattern = re.compile(QUESTION_START + r'(.*?)' + QUESTION_END, re.DOTALL)

            content_match = content_pattern.search(full_content)
            question_match = question_pattern.search(full_content)

            final_content = content_match.group(1).strip() if content_match else ''
            final_question = question_match.group(1).strip() if question_match else ''

            if not final_content and CONTENT_START in full_content:
                content_start_idx = full_content.find(CONTENT_START) + len(CONTENT_START)
                question_start_idx = full_content.find(QUESTION_START)

                if question_start_idx > content_start_idx:
                    final_content = full_content[content_start_idx:question_start_idx].strip()
                else:
                    final_content = full_content[content_start_idx:].strip()

            if not final_question and QUESTION_START in full_content:
                question_start_idx = full_content.find(QUESTION_START) + len(QUESTION_START)
                final_question = full_content[question_start_idx:].strip()

            # 保存到数据库
            try:
                with transaction.atomic():
                    outline_version = OutlineVersion.objects.filter(project=project, version_number=version_number).first()
                    if final_content:
                        if outline_version:
                            outline_version.content = final_content
                            outline_version.save()
                        else:
                            outline_version = OutlineVersion.objects.create(project=project, version_number=version_number, content=final_content)
                    else:
                        logger.error('没有生成大纲')
                        logger.error(final_content)

                    # 确保 outline_version 存在后再创建聊天记录
                    if not outline_version:
                        outline_version = OutlineVersion.objects.create(
                            project=project,
                            version_number=version_number,
                            content=final_content or ''
                        )

                    OutlineChatHistory.objects.create(outline_version=outline_version, role='user', content=user_input)
                    OutlineChatHistory.objects.create(outline_version=outline_version, role='assistant', content=final_question)

                return {
                    'project_id': project.id,
                    'version_number': version_number,
                    'content': final_content,
                    'question': final_question,
                }
            except Exception as e:
                logger.error(f"大纲保存异常: {e}")
                return {
                    'content': final_content,
                    'question': final_question,
                    'save_error': str(e),
                }

        return stream_llm_response(
            system_prompt=OUTLINE_BUILD_SYSTEM_PROMPT,
            user_prompt=OUTLINE_BUILD_USER_PROMPT,
            prompt_vars=prompt_vars,
            user=request.user,
            scene="outline_optimize",
            timeout=300,
            error_msg='大纲生成失败，请重试',
            post_process=post_process,
            project=project,
            task_type='outline',
        )


class ApiSaveOutlineVersionView(BaseOutlineAPIView):
    # 大纲内容最大长度限制
    MAX_CONTENT_LENGTH = 200000

    def post(self, request, project_id):
        project_id = project_id or request.data.get('project_id')
        content = request.data.get('content')
        new_version = request.data.get('new_version', 'false') == 'true'
        version_id = request.data.get('version_id')

        if not project_id:
            return JsonResponse({'success': False, 'error': 'project_id 参数不能为空'}, status=400)

        if not content or not content.strip():
            return JsonResponse({'success': False, 'error': '大纲内容不能为空'}, status=400)

        if len(content) > self.MAX_CONTENT_LENGTH:
            return JsonResponse({'success': False, 'error': f'大纲内容不能超过{self.MAX_CONTENT_LENGTH}字符'}, status=400)

        project = self.get_project_or_404(request, project_id)
        outline_version = None

        with transaction.atomic():
            if new_version:
                latest_version = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
                new_version_number = latest_version.version_number + 1 if latest_version else 1

                outline_version = OutlineVersion.objects.create(
                    project=project,
                    version_number=new_version_number,
                    content=content,
                    snapshot=content[:500] + '...' if len(content) > 500 else content
                )
            elif version_id:
                outline_version = get_object_or_404(OutlineVersion, pk=version_id, project=project, is_deleted=False)
                
                # 检查版本是否被锁定
                if outline_version.is_finalized:
                    return JsonResponse({'success': False, 'error': '当前版本已被锁定，无法修改'}, status=400)
                
                outline_version.content = content
                outline_version.snapshot = content[:500] + '...' if len(content) > 500 else content
                outline_version.save()
            else:
                outline_version = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
                if outline_version:
                    outline_version.content = content
                    outline_version.snapshot = content[:500] + '...' if len(content) > 500 else content
                    outline_version.save()
                else:
                    outline_version = OutlineVersion.objects.create(
                        project=project,
                        version_number=1,
                        content=content,
                        snapshot=content[:500] + '...' if len(content) > 500 else content
                    )
        
        return JsonResponse({
            'success': True,
            'version_id': outline_version.pk,
            'version_number': outline_version.version_number
        })


class ApiLoadOutlineVersionView(BaseOutlineAPIView):
    def get(self, request, project_id, version_id):
        outline_version = get_object_or_404(OutlineVersion, pk=version_id, is_deleted=False)
        # 校验版本属于当前用户
        self.get_project_or_404(request, outline_version.project_id)

        return JsonResponse({
            'success': True,
            'content': outline_version.content,
            'version_number': outline_version.version_number,
            'is_finalized': outline_version.is_finalized,
        })


class ApiFinalizeOutlineVersionView(BaseOutlineAPIView):
    MAX_CONTENT_LENGTH = 200000

    def post(self, request, project_id):
        project_id = project_id or request.data.get('project_id')
        version_id = request.data.get('version_id')
        content = request.data.get('content')

        if not project_id:
            return JsonResponse({'success': False, 'error': 'project_id 参数不能为空'}, status=400)
        
        if content and len(content) > self.MAX_CONTENT_LENGTH:
            return JsonResponse({'success': False, 'error': f'大纲内容不能超过{self.MAX_CONTENT_LENGTH}字符'}, status=400)
        
        project = self.get_project_or_404(request, project_id)
        
        outline_version = None
        
        with transaction.atomic():
            project.outline_versions.filter(is_finalized=True, is_deleted=False).update(is_finalized=False)
            
            if version_id:
                outline_version = get_object_or_404(OutlineVersion, pk=version_id, project=project, is_deleted=False)
                if content:
                    outline_version.content = content
                    outline_version.snapshot = content[:500] + '...' if len(content) > 500 else content
                outline_version.is_finalized = True
                outline_version.save()
            else:
                latest_version = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
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


class ApiDeleteOutlineVersionView(BaseOutlineAPIView):
    def post(self, request):
        version_id = request.data.get('version_id')
        if not version_id:
            return JsonResponse({'success': False, 'error': 'version_id 参数不能为空'}, status=400)
        outline_version = get_object_or_404(OutlineVersion, pk=version_id)
        # 校验版本属于当前用户
        self.get_project_or_404(request, outline_version.project_id)

        if outline_version.is_finalized:
            return JsonResponse({
                'success': False,
                'message': '定稿版本不能删除'
            })
        
        outline_version.is_deleted = True
        outline_version.save()
        
        return JsonResponse({'success': True})


class ApiRestoreOutlineVersionView(BaseOutlineAPIView):
    def post(self, request):
        version_id = request.data.get('version_id')
        if not version_id:
            return JsonResponse({'success': False, 'error': 'version_id 参数不能为空'}, status=400)
        outline_version = get_object_or_404(OutlineVersion, pk=version_id, is_deleted=True)
        # 校验版本属于当前用户
        self.get_project_or_404(request, outline_version.project_id)
        
        outline_version.is_deleted = False
        outline_version.save()
        
        return JsonResponse({'success': True})


class ApiOutlineVersionsView(BaseOutlineAPIView):

    def get(self, request, project_id):
        try:
            project = self.get_project_or_404(request, project_id)

            outline_versions = OutlineVersion.objects.filter(
                project=project,
                is_deleted=False
            ).order_by('-version_number')

            versions = []
            latest_version = None

            for version in outline_versions:
                version_data = {
                    'id': version.pk,
                    'version_number': version.version_number,
                    'is_finalized': version.is_finalized,
                    'is_current': version.is_current,
                    'snapshot': version.snapshot,
                    'created_at': version.created_at.strftime('%Y-%m-%d %H:%M') if version.created_at else None,
                    'updated_at': version.updated_at.strftime('%Y-%m-%d %H:%M') if version.updated_at else None,
                }
                
                versions.append(version_data)
                
                if not latest_version or version.version_number > latest_version['version_number']:
                    latest_version = version_data
            
            return JsonResponse({
                'success': True,
                'versions': versions,
                'latest': latest_version
            })
        except Exception as e:
            logger.error(f"获取大纲版本列表异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiOutlineVersionDetailView(BaseOutlineAPIView):

    def get(self, request, project_id, version_id):
        try:
            outline_version = get_object_or_404(
                OutlineVersion,
                pk=version_id,
                is_deleted=False
            )
            # 校验版本属于当前用户
            self.get_project_or_404(request, outline_version.project_id)
            
            return JsonResponse({
                'success': True,
                'id': outline_version.pk,
                'version_number': outline_version.version_number,
                'content': outline_version.content,
                'is_finalized': outline_version.is_finalized,
                'is_current': outline_version.is_current,
                'snapshot': outline_version.snapshot,
                'created_at': outline_version.created_at.strftime('%Y-%m-%d %H:%M') if outline_version.created_at else None,
                'updated_at': outline_version.updated_at.strftime('%Y-%m-%d %H:%M') if outline_version.updated_at else None,
            })
        except Exception as e:
            logger.error(f"获取大纲版本详情异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiLatestOutlineView(BaseOutlineAPIView):

    def get(self, request, project_id):
        try:
            project = self.get_project_or_404(request, project_id)
            
            outline_version = OutlineVersion.objects.filter(
                project=project,
                version_number=0,
                is_deleted=False
            ).first()
            
            if not outline_version:
                outline_version = OutlineVersion.objects.create(
                    project=project,
                    version_number=0,
                    content='',
                    is_current=True
                )
            
            return JsonResponse({
                'success': True,
                'outline': {
                    'id': outline_version.pk,
                    'version_number': outline_version.version_number,
                    'content': outline_version.content,
                    'is_finalized': outline_version.is_finalized,
                    'is_current': outline_version.is_current,
                    'created_at': outline_version.created_at.strftime('%Y-%m-%d %H:%M') if outline_version.created_at else None,
                    'updated_at': outline_version.updated_at.strftime('%Y-%m-%d %H:%M') if outline_version.updated_at else None
                }
            })
        except Exception as e:
            logger.error(f"获取最新大纲异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiOutlineFinalizeView(BaseOutlineAPIView):

    def post(self, request, project_id):
        try:
            version_id = request.data.get('version_id')

            if not version_id:
                return JsonResponse({'success': False, 'error': 'version_id 参数不能为空'}, status=400)

            outline_version = get_object_or_404(
                OutlineVersion,
                pk=version_id,
                project__user=request.user,
                is_deleted=False
            )
            
            project = outline_version.project
            
            with transaction.atomic():
                project.outline_versions.filter(is_finalized=True, is_deleted=False).update(is_finalized=False)
                
                outline_version.is_finalized = True
                outline_version.save()
            
            return JsonResponse({
                'success': True,
                'version_id': outline_version.pk,
                'version_number': outline_version.version_number,
                'project_id': project.id
            })
        except Exception as e:
            logger.error(f"大纲定稿异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiOutlineLockView(BaseOutlineAPIView):

    def post(self, request, project_id):
        try:
            version_id = request.data.get('version_id')
            project_id = project_id or request.data.get('project_id')

            if not version_id or not project_id:
                return JsonResponse({'success': False, 'error': 'version_id 和 project_id 参数不能为空'}, status=400)

            outline_version = get_object_or_404(
                OutlineVersion,
                pk=version_id,
                project__user=request.user,
                is_deleted=False
            )
            
            outline_version.is_finalized = True
            outline_version.save()
            
            return JsonResponse({
                'success': True,
                'version_id': outline_version.pk,
                'version_number': outline_version.version_number
            })
        except Exception as e:
            logger.error(f"锁定大纲版本异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiOutlineDeleteView(BaseOutlineAPIView):

    def post(self, request, project_id):
        try:
            version_id = request.data.get('version_id')

            if not version_id:
                return JsonResponse({'success': False, 'error': 'version_id 参数不能为空'}, status=400)

            outline_version = get_object_or_404(
                OutlineVersion,
                pk=version_id,
                project__user=request.user,
                is_deleted=False
            )

            if outline_version.is_finalized:
                return JsonResponse({
                    'success': False,
                    'message': '锁定版本不能删除'
                })
            
            outline_version.is_deleted = True
            outline_version.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            logger.error(f"删除大纲版本异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiChatHistoryDeleteView(BaseOutlineAPIView):
    MAX_DELETE_COUNT = 100

    def post(self, request, project_id):
        try:
            message_ids_str = request.data.get('message_ids', '')
            
            if not message_ids_str:
                return JsonResponse({'success': False, 'error': 'message_ids 参数不能为空且必须是数组'}, status=400)
            
            try:
                message_ids = json.loads(message_ids_str)
            except json.JSONDecodeError:
                return JsonResponse({'success': False, 'error': 'message_ids 格式错误，必须是JSON数组'}, status=400)
            
            if not isinstance(message_ids, list) or len(message_ids) == 0:
                return JsonResponse({'success': False, 'error': 'message_ids 参数不能为空且必须是数组'}, status=400)

            if len(message_ids) > self.MAX_DELETE_COUNT:
                return JsonResponse({'success': False, 'error': f'单次最多删除{self.MAX_DELETE_COUNT}条记录'}, status=400)

            # 校验所有 ID 为整数
            valid_ids = []
            for mid in message_ids:
                try:
                    valid_ids.append(int(mid))
                except (ValueError, TypeError):
                    return JsonResponse({'success': False, 'error': f'message_ids 包含无效ID: {mid}'}, status=400)
            
            deleted_count = OutlineChatHistory.objects.filter(
                id__in=valid_ids,
                outline_version__project__user=request.user
            ).delete()[0]
            
            return JsonResponse({
                'success': True,
                'deleted_count': deleted_count
            })
        except Exception as e:
            logger.error(f"删除聊天记录异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)
