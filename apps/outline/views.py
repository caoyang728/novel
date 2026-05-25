import json
import re
import time
from loguru import logger
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from apps.project.models import ProjectList
from apps.outline.models import OutlineVersion, OutlineChatHistory
from apps.ai.llm import get_llm
from .prompts import OUTLINE_BUILD_PROMPT


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


class APIChatOutlineView(APIView):
    """
    大纲生成视图
    
    特点：
    - 支持新建模式和编辑模式
    - LLM 返回什么，后端直接转发什么
    - 流结束后统一保存
    - 前端和后端并行收集完整内容
    
    模式区分：
    - 新建模式：project_id为空或不存在，自动创建新项目，version_number固定为0
    - 编辑模式：project_id必须存在，version_number可指定（0为临时版本）
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        project_id = request.data.get('project_id')
        version_number = request.data.get('version_number', 0)
        user_input = request.data.get('message', '')
        current_outline = request.data.get('current_outline', '')
        history_messages = request.data.get('messages', [])

        response = StreamingHttpResponse(self.generate(request, project_id, version_number, user_input, current_outline, history_messages), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    def generate(self, request, project_id, version_number, user_input, current_outline, history_messages):
        CONTENT_START = '════CONTENT_START════'
        CONTENT_END = '════CONTENT_END════'
        QUESTION_START = '════QUESTION_START════'
        QUESTION_END = '════QUESTION_END════'
        
        prompt = OUTLINE_BUILD_PROMPT.format(
            current_outline=current_outline, 
            user_input=user_input, 
            history_messages=history_messages
        )

        try:
            messages = [
                SystemMessage(content="你是一位专业的小说大纲构建作者，擅长通过引导式对话帮助用户从零开始构建完整的小说大纲。请严格按照指定的分隔符格式返回。"),
                HumanMessage(content=prompt)
            ]
            
            stream_response = _call_with_retry(messages, stream=True, user=request.user, scene="outline_optimize", timeout=300)
            full_content = ""
            
            for content_chunk in stream_response:
                if content_chunk:
                    full_content += content_chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'data': content_chunk}, ensure_ascii=False)}\n\n"

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

            with transaction.atomic():
                project = None
                is_new_project = False
                
                if project_id:
                    try:
                        project = ProjectList.objects.get(pk=project_id)
                        if project.user != request.user:
                            raise Exception('非法访问')
                    except ProjectList.DoesNotExist:
                        project = None
                
                if not project:
                    project = ProjectList.objects.create(user=request.user)
                    project.title = f'小说{project.id}'
                    project.save()
                    is_new_project = True

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
                
                OutlineChatHistory.objects.create(outline_version=outline_version, role='user', content=user_input)
                OutlineChatHistory.objects.create(outline_version=outline_version, role='assistant', content=final_question)

            response_data = {'type': 'complete', 'project_id': project.id}
            if not is_new_project:
                response_data['version_number'] = version_number
            yield f"data: {json.dumps(response_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"大纲流式生成异常: {e}")
            yield f"data: {json.dumps({'error': 'internal server error'}, ensure_ascii=False)}\n\n"


class SaveOutlineVersionView(APIView):
    def post(self, request):
        project_id = request.POST.get('project_id')
        content = request.POST.get('content')
        messages_json = request.POST.get('messages', '[]')
        new_version = request.POST.get('new_version', 'false') == 'true'
        
        try:
            messages = json.loads(messages_json)
        except json.JSONDecodeError:
            messages = []
        
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
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
                    outline_version.outline_chat_histories.all().delete()
                else:
                    outline_version = OutlineVersion.objects.create(
                        project=project,
                        version_number=1,
                        content=content,
                        snapshot=content[:500] + '...' if len(content) > 500 else content
                    )
            
            for msg in messages:
                OutlineChatHistory.objects.create(
                    outline_version=outline_version,
                    role=msg['role'],
                    content=msg['content']
                )
        
        return JsonResponse({
            'success': True,
            'version_id': outline_version.pk,
            'version_number': outline_version.version_number
        })


class LoadOutlineVersionView(APIView):
    def get(self, request, version_id):
        outline_version = get_object_or_404(OutlineVersion, pk=version_id, project__user=request.user)
        
        messages = []
        for msg in outline_version.outline_chat_histories.order_by('created_at'):
            messages.append({
                'role': msg.role,
                'content': msg.content
            })
        
        return JsonResponse({
            'success': True,
            'content': outline_version.content,
            'messages': messages
        })


class FinalizeOutlineVersionView(APIView):
    def post(self, request):
        project_id = request.POST.get('project_id')
        version_id = request.POST.get('version_id')
        content = request.POST.get('content')
        messages_json = request.POST.get('messages', '[]')
        
        try:
            messages = json.loads(messages_json)
        except json.JSONDecodeError:
            messages = []
        
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        
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
                outline_version.outline_chat_histories.all().delete()
                for msg in messages:
                    OutlineChatHistory.objects.create(
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


class DeleteOutlineVersionView(APIView):
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


class RestoreOutlineVersionView(APIView):
    def post(self, request):
        version_id = request.POST.get('version_id')
        outline_version = get_object_or_404(OutlineVersion, pk=version_id, project__user=request.user, is_deleted=True)
        
        outline_version.is_deleted = False
        outline_version.save()
        
        return JsonResponse({'success': True})


class ApiOutlineVersionsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            
            outline_versions = OutlineVersion.objects.filter(
                project=project,
                is_deleted=False
            ).order_by('-version_number')
            
            versions = []
            latest_version = None
            
            for version in outline_versions:
                chat_histories = OutlineChatHistory.objects.filter(
                    outline_version=version,
                    is_deleted=False
                ).order_by('created_at')
                
                messages = []
                for msg in chat_histories:
                    messages.append({
                        'role': msg.role,
                        'content': msg.content,
                        'id': msg.id,
                        'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M') if msg.created_at else None
                    })
                
                version_data = {
                    'id': version.pk,
                    'pk': version.pk,
                    'version_number': version.version_number,
                    'content': version.content,
                    'is_finalized': version.is_finalized,
                    'is_current': version.is_current,
                    'snapshot': version.snapshot,
                    'created_at': version.created_at.strftime('%Y-%m-%d %H:%M') if version.created_at else None,
                    'updated_at': version.updated_at.strftime('%Y-%m-%d %H:%M') if version.updated_at else None,
                    'messages': messages
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
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiOutlineVersionDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, version_id):
        try:
            outline_version = get_object_or_404(
                OutlineVersion, 
                pk=version_id, 
                project__user=request.user,
                is_deleted=False
            )
            
            chat_histories = OutlineChatHistory.objects.filter(
                outline_version=outline_version,
                is_deleted=False
            ).order_by('created_at')
            
            messages = []
            for msg in chat_histories:
                messages.append({
                    'role': msg.role,
                    'content': msg.content,
                    'id': msg.id,
                    'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M') if msg.created_at else None
                })
            
            return JsonResponse({
                'success': True,
                'id': outline_version.pk,
                'pk': outline_version.pk,
                'version_number': outline_version.version_number,
                'content': outline_version.content,
                'is_finalized': outline_version.is_finalized,
                'is_current': outline_version.is_current,
                'snapshot': outline_version.snapshot,
                'created_at': outline_version.created_at.strftime('%Y-%m-%d %H:%M') if outline_version.created_at else None,
                'updated_at': outline_version.updated_at.strftime('%Y-%m-%d %H:%M') if outline_version.updated_at else None,
                'messages': messages
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiLatestOutlineView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            
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
            
            chat_histories = OutlineChatHistory.objects.filter(
                outline_version=outline_version,
                is_deleted=False
            ).order_by('created_at')
            
            messages = []
            for msg in chat_histories:
                messages.append({
                    'role': msg.role,
                    'content': msg.content,
                    'id': msg.id
                })
            
            return JsonResponse({
                'success': True,
                'outline': {
                    'pk': outline_version.pk,
                    'version_number': outline_version.version_number,
                    'content': outline_version.content,
                    'is_finalized': outline_version.is_finalized,
                    'is_current': outline_version.is_current,
                    'created_at': outline_version.created_at.strftime('%Y-%m-%d %H:%M') if outline_version.created_at else None,
                    'updated_at': outline_version.updated_at.strftime('%Y-%m-%d %H:%M') if outline_version.updated_at else None
                },
                'messages': messages
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiOutlineFinalizeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
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


class ApiOutlineDeleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
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
                    'message': '定稿版本不能删除'
                })
            
            outline_version.is_deleted = True
            outline_version.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            logger.error(f"删除大纲版本异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiChatHistoryDeleteView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
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
            
            deleted_count = OutlineChatHistory.objects.filter(
                id__in=message_ids,
                outline_version__project__user=request.user
            ).delete()[0]
            
            return JsonResponse({
                'success': True,
                'deleted_count': deleted_count
            })
        except Exception as e:
            logger.error(f"删除聊天记录异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)
