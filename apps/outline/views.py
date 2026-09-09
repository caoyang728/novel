import json
from loguru import logger
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.db import transaction

from apps.project.base import BaseAPIView
from apps.outline.models import Outline, OutlineChatHistory
from agent.llm import make_thinking_handler, get_llm
from apps.project.utils import (
    get_genre_guide, get_genre_label, run_retry_loop,
)
from .prompts import (
    OUTLINE_CONTEXT_TEMPLATE,
    OUTLINE_BUILD_USER_PROMPT,
    OUTLINE_GENRE_PROMPTS_DICT,
)


class BaseOutlineAPIView(BaseAPIView):
    """大纲API基础类 - 继承项目基础类，添加大纲相关工具方法"""


# ============ 补丁应用 ============

def _apply_patches(data, base_content):
    """应用 patch_list 到大纲内容，返回结果字典"""
    patch_list = data.get('patch_list', [])
    question = data.get('question', '')
    options = data.get('options', [])
    characters = data.get('characters', [])

    result_text = base_content
    applied_count = 0
    edits_summary = []

    for patch in patch_list:
        old_snippet = patch.get('old_snippet', '')
        new_snippet = patch.get('new_snippet', '')

        if not old_snippet:
            # 新增内容（大纲为空或追加）
            if not result_text.strip():
                result_text = new_snippet
            else:
                result_text = result_text.rstrip('\n') + '\n\n' + new_snippet
            applied_count += 1
            edits_summary.append({'type': 'add', 'preview': new_snippet[:80]})
            continue

        count = result_text.count(old_snippet)
        if count == 0:
            logger.warning(f'[OUTLINE] Patch未匹配: old_snippet={old_snippet[:60]}...')
            edits_summary.append({'type': 'failed', 'preview': old_snippet[:60]})
            continue
        if count > 1:
            logger.warning(f'[OUTLINE] Patch多处匹配({count}次): old_snippet={old_snippet[:60]}...')
            edits_summary.append({'type': 'ambiguous', 'preview': old_snippet[:60]})
            continue

        result_text = result_text.replace(old_snippet, new_snippet, 1)
        applied_count += 1
        edits_summary.append({'type': 'replace', 'old': old_snippet[:60], 'new': new_snippet[:80]})

    # 从 question 中提取选项（👉 格式）
    parsed_options = list(options)
    question_text = question
    if question:
        for line in question.split('\n'):
            line = line.strip()
            if line.startswith('👉'):
                opt = line.lstrip('👉').strip()
                if opt and opt not in parsed_options:
                    parsed_options.append(opt)
        # 去除 question 中的选项部分
        if parsed_options:
            lines = question.split('\n')
            question_lines = [l for l in lines if not l.strip().startswith('👉')]
            question_text = '\n'.join(question_lines).strip()

    return {
        'new_content': result_text,
        'question': question_text or question,
        'options': parsed_options,
        'edits_applied': applied_count,
        'edits_total': len(patch_list),
        'edits_summary': edits_summary,
        'characters': characters,
    }


class ApiChatOutlineView(BaseOutlineAPIView):
    # 输入长度限制
    MAX_USER_INPUT_LENGTH = 5000
    MAX_OUTLINE_LENGTH = 200000
    MAX_ROUNDS = 3
    MAX_REPAIR_ATTEMPTS = 3

    def post(self, request, project_id):
        project_id = project_id or request.data.get('project_id')
        user_input = request.data.get('message', '')
        current_outline = request.data.get('current_outline', '')

        if not project_id:
            return JsonResponse({'success': False, 'error': 'project_id 参数不能为空'}, status=400)

        if not user_input.strip():
            return JsonResponse({'success': False, 'error': '消息内容不能为空'}, status=400)

        if len(user_input) > self.MAX_USER_INPUT_LENGTH:
            return JsonResponse({'success': False, 'error': f'消息内容不能超过{self.MAX_USER_INPUT_LENGTH}字符'}, status=400)

        if len(current_outline) > self.MAX_OUTLINE_LENGTH:
            return JsonResponse({'success': False, 'error': f'大纲内容不能超过{self.MAX_OUTLINE_LENGTH}字符'}, status=400)

        project = self.get_project_or_404(request, project_id)

        # 从 project 获取题材（不从子模型读取）
        genre = project.genre or 'general'

        # 前端传来的历史对话消息（避免从数据库读取已放弃的对话）
        history_messages = request.data.get('messages', [])

        # 获取上下文：分别调用，不走 get_project_context（去掉 timeline）
        worldview_context = self.get_worldview_context(project)
        characters_context = self.get_characters_context(project)
        logger.info(f'[OUTLINE] genre={genre}, worldview_len={len(worldview_context)}, characters_len={len(characters_context)}')

        def generate():
            try:
                from django.db import close_old_connections
                close_old_connections()

                # 持久化用户消息（始终操作构建版本 v0）
                outline = Outline.get_or_create_building(project)
                OutlineChatHistory.objects.create(
                    outline=outline, role='user', content=user_input
                )

                # 构建提示词
                genre_name_label = get_genre_label(genre)
                genre_guide_text = get_genre_guide(genre, OUTLINE_GENRE_PROMPTS_DICT).format(
                    genre_name=genre_name_label,
                )
                context_text = OUTLINE_CONTEXT_TEMPLATE.format(
                    worldview_context=worldview_context or '（暂无世界观设定）',
                    characters_context=characters_context or '（暂无人物清单）',
                    current_outline=current_outline or '（空，首次生成）',
                    novel_name=project.title or '小说',
                )
                system_prompt = genre_guide_text + '\n\n' + context_text

                # 构建消息列表：system + history + user
                messages = [("system", system_prompt)]
                # 使用前端传入的历史消息（格式：[{role: 'user'|'assistant', content: '...'}]）
                for msg in history_messages:
                    role = msg.get('role', 'user')
                    content = msg.get('content', '')
                    if role in ('user', 'assistant') and content:
                        messages.append((role, content))
                user_prompt = OUTLINE_BUILD_USER_PROMPT.format(
                    user_input=user_input,
                )
                messages.append(("user", user_prompt))

                from langchain_core.prompts import ChatPromptTemplate
                prompt = ChatPromptTemplate.from_messages(messages)

                llm = get_llm(user=request.user, scene="outline_build")
                chain = prompt | llm

                # ============ 三轮容错机制 ============
                result, full_content = yield from run_retry_loop(
                    chain=chain,
                    prompt=prompt,
                    user_input=user_input,
                    scene="outline_build",
                    apply_fn=_apply_patches,
                    base_content=current_outline,
                    sse_event_fn=self.sse_event,
                    get_chunk_text_fn=self.get_chunk_text,
                    log_token_usage_fn=self.log_token_usage,
                    user=request.user,
                    project=project,
                    log_prefix='[OUTLINE]',
                    max_rounds=self.MAX_ROUNDS,
                    wrap_stream_fn=lambda s: make_thinking_handler()(s),
                )

                # 三轮均失败（run_retry_loop 已发送 error 事件）
                if result is None:
                    return

                logger.info(f'[OUTLINE] patches: applied={result.get("edits_applied", 0)}/{result.get("edits_total", 0)}, '
                            f'question_len={len(result.get("question", ""))}, content_len={len(result.get("new_content", ""))}')

                new_content = result.get('new_content', '')
                assistant_reply = result.get('question', '')
                options = result.get('options', [])

                # 持久化助手消息
                OutlineChatHistory.objects.create(
                    outline=outline, role='assistant',
                    content=assistant_reply or '大纲已更新',
                )

                # 发送完成信号
                yield self.sse_event('complete', {
                    'reply': assistant_reply,
                    'content': new_content or current_outline,
                    'options': options,
                    'edits_applied': result.get('edits_applied', 0),
                    'edits_total': result.get('edits_total', 0),
                })

            except Exception as e:
                logger.error(f'[OUTLINE] 大纲构建异常: {e}', exc_info=True)
                yield self.sse_event('error', {'message': '大纲生成失败，请重试'})

        from django.http import StreamingHttpResponse
        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiSaveOutlineView(BaseOutlineAPIView):
    # 大纲内容最大长度限制
    MAX_CONTENT_LENGTH = 200000

    def post(self, request, project_id):
        project_id = project_id or request.data.get('project_id')
        content = request.data.get('content')
        new_version = request.data.get('new_version', 'false') == 'true'
        version_id = request.data.get('version_id')
        last_question = request.data.get('last_question', '')
        last_options = request.data.get('last_options', [])

        if not project_id:
            return JsonResponse({'success': False, 'error': 'project_id 参数不能为空'}, status=400)

        if not content or not content.strip():
            return JsonResponse({'success': False, 'error': '大纲内容不能为空'}, status=400)

        if len(content) > self.MAX_CONTENT_LENGTH:
            return JsonResponse({'success': False, 'error': f'大纲内容不能超过{self.MAX_CONTENT_LENGTH}字符'}, status=400)

        project = self.get_project_or_404(request, project_id)
        outline = None

        with transaction.atomic():
            if new_version:
                latest_version = project.outlines.filter(is_deleted=False).order_by('-version').first()
                new_version_number = latest_version.version + 1 if latest_version else 1

                outline = Outline.objects.create(
                    project=project,
                    version=new_version_number,
                    content=content,
                    last_question=last_question or '',
                    last_options=last_options or [],
                )
            elif version_id:
                outline = get_object_or_404(Outline, pk=version_id, project=project, is_deleted=False)
                
                # 检查版本是否被锁定
                if outline.is_finalized:
                    return JsonResponse({'success': False, 'error': '当前版本已被锁定，无法修改'}, status=400)
                
                outline.content = content
                if last_question:
                    outline.last_question = last_question
                if last_options is not None:
                    outline.last_options = last_options
                outline.save()
            else:
                outline = project.outlines.filter(is_deleted=False).order_by('-version').first()
                if outline:
                    outline.content = content
                    if last_question:
                        outline.last_question = last_question
                    if last_options is not None:
                        outline.last_options = last_options
                    outline.save()
                else:
                    outline = Outline.objects.create(
                        project=project,
                        version=1,
                        content=content,
                        last_question=last_question or '',
                        last_options=last_options or [],
                    )
        
        return JsonResponse({
            'success': True,
            'version_id': outline.pk,
            'version_number': outline.version
        })


class ApiLoadOutlineView(BaseOutlineAPIView):
    def get(self, request, project_id, version_id):
        outline = get_object_or_404(Outline, pk=version_id, is_deleted=False)
        # 校验版本属于当前用户
        self.get_project_or_404(request, outline.project_id)

        return JsonResponse({
            'success': True,
            'content': outline.content,
            'version_number': outline.version,
            'is_finalized': outline.is_finalized,
            'last_question': outline.last_question or '',
            'last_options': outline.last_options or [],
        })


class ApiFinalizeOutlineView(BaseOutlineAPIView):
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
        
        outline = None
        
        with transaction.atomic():
            project.outlines.filter(is_finalized=True, is_deleted=False).update(is_finalized=False)
            
            if version_id:
                outline = get_object_or_404(Outline, pk=version_id, project=project, is_deleted=False)
                if content:
                    outline.content = content
                outline.is_finalized = True
                outline.save()
            else:
                latest_version = project.outlines.filter(is_deleted=False).order_by('-version').first()
                if latest_version:
                    outline = latest_version
                    outline.content = content or latest_version.content
                    outline.is_finalized = True
                    outline.save()
                else:
                    outline = Outline.objects.create(
                        project=project,
                        version=1,
                        content=content,
                        is_finalized=True
                    )
        
        return JsonResponse({
            'success': True,
            'version_id': outline.pk,
            'version_number': outline.version
        })


class ApiDeleteOutlineView(BaseOutlineAPIView):
    def post(self, request):
        version_id = request.data.get('version_id')
        if not version_id:
            return JsonResponse({'success': False, 'error': 'version_id 参数不能为空'}, status=400)
        outline = get_object_or_404(Outline, pk=version_id)
        # 校验版本属于当前用户
        self.get_project_or_404(request, outline.project_id)

        if outline.is_finalized:
            return JsonResponse({
                'success': False,
                'message': '定稿版本不能删除'
            })
        
        outline.is_deleted = True
        outline.save()
        
        return JsonResponse({'success': True})


class ApiRestoreOutlineView(BaseOutlineAPIView):
    def post(self, request):
        version_id = request.data.get('version_id')
        if not version_id:
            return JsonResponse({'success': False, 'error': 'version_id 参数不能为空'}, status=400)
        outline = get_object_or_404(Outline, pk=version_id, is_deleted=True)
        # 校验版本属于当前用户
        self.get_project_or_404(request, outline.project_id)
        
        outline.is_deleted = False
        outline.save()
        
        return JsonResponse({'success': True})


class ApiOutlinesView(BaseOutlineAPIView):

    def get(self, request, project_id):
        try:
            project = self.get_project_or_404(request, project_id)

            outlines = Outline.objects.filter(
                project=project,
                is_deleted=False
            ).order_by('-version')

            versions = []
            latest_version = None

            for ver in outlines:
                version_data = {
                    'id': ver.pk,
                    'version_number': ver.version,
                    'is_finalized': ver.is_finalized,
                    'created_at': ver.created_at.strftime('%Y-%m-%d %H:%M') if ver.created_at else None,
                    'updated_at': ver.updated_at.strftime('%Y-%m-%d %H:%M') if ver.updated_at else None,
                }
                
                versions.append(version_data)
                
                if not latest_version or ver.version > latest_version['version_number']:
                    latest_version = version_data
            
            return JsonResponse({
                'success': True,
                'versions': versions,
                'latest': latest_version
            })
        except Exception as e:
            logger.error(f"获取大纲版本列表异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiOutlineDetailView(BaseOutlineAPIView):

    def get(self, request, project_id, version_id):
        try:
            outline = get_object_or_404(
                Outline,
                pk=version_id,
                is_deleted=False
            )
            # 校验版本属于当前用户
            self.get_project_or_404(request, outline.project_id)
            
            return JsonResponse({
                'success': True,
                'id': outline.pk,
                'version_number': outline.version,
                'content': outline.content,
                'is_finalized': outline.is_finalized,
                'last_question': outline.last_question or '',
                'last_options': outline.last_options or [],
                'created_at': outline.created_at.strftime('%Y-%m-%d %H:%M') if outline.created_at else None,
                'updated_at': outline.updated_at.strftime('%Y-%m-%d %H:%M') if outline.updated_at else None,
            })
        except Exception as e:
            logger.error(f"获取大纲版本详情异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiLatestOutlineView(BaseOutlineAPIView):

    def get(self, request, project_id):
        try:
            project = self.get_project_or_404(request, project_id)
            outline = Outline.get_or_create_building(project)
            
            return JsonResponse({
                'success': True,
                'outline': {
                    'id': outline.pk,
                    'version_number': outline.version,
                    'content': outline.content,
                    'is_finalized': outline.is_finalized,
                    'created_at': outline.created_at.strftime('%Y-%m-%d %H:%M') if outline.created_at else None,
                    'updated_at': outline.updated_at.strftime('%Y-%m-%d %H:%M') if outline.updated_at else None
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

            outline = get_object_or_404(
                Outline,
                pk=version_id,
                project__user=request.user,
                is_deleted=False
            )
            
            project = outline.project
            
            with transaction.atomic():
                project.outlines.filter(is_finalized=True, is_deleted=False).update(is_finalized=False)
                
                outline.is_finalized = True
                outline.save()
            
            return JsonResponse({
                'success': True,
                'version_id': outline.pk,
                'version_number': outline.version,
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

            outline = get_object_or_404(
                Outline,
                pk=version_id,
                project__user=request.user,
                is_deleted=False
            )
            
            outline.is_finalized = True
            outline.save()
            
            return JsonResponse({
                'success': True,
                'version_id': outline.pk,
                'version_number': outline.version
            })
        except Exception as e:
            logger.error(f"锁定大纲版本异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiOutlineUnlockView(BaseOutlineAPIView):

    def post(self, request, project_id):
        try:
            version_id = request.data.get('version_id')
            project_id = project_id or request.data.get('project_id')

            logger.info(f'[Unlock] user={request.user} project_id={project_id} version_id={version_id} data={request.data}')

            if not version_id or not project_id:
                return JsonResponse({'success': False, 'error': 'version_id 和 project_id 参数不能为空'}, status=400)

            outline = get_object_or_404(
                Outline,
                pk=version_id,
                project__user=request.user,
                is_deleted=False
            )
            
            outline.is_finalized = False
            outline.save()
            
            return JsonResponse({
                'success': True,
                'version_id': outline.pk,
                'version_number': outline.version
            })
        except Exception as e:
            logger.error(f"解锁大纲版本异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)


class ApiOutlineDeleteView(BaseOutlineAPIView):

    def post(self, request, project_id):
        try:
            version_id = request.data.get('version_id')

            if not version_id:
                return JsonResponse({'success': False, 'error': 'version_id 参数不能为空'}, status=400)

            outline = get_object_or_404(
                Outline,
                pk=version_id,
                project__user=request.user,
                is_deleted=False
            )

            if outline.is_finalized:
                return JsonResponse({
                    'success': False,
                    'message': '锁定版本不能删除'
                })
            
            outline.is_deleted = True
            outline.save()
            
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
                outline__project__user=request.user
            ).delete()[0]
            
            return JsonResponse({
                'success': True,
                'deleted_count': deleted_count
            })
        except Exception as e:
            logger.error(f"删除聊天记录异常: {e}")
            return JsonResponse({'success': False, 'error': 'internal server error'}, status=500)
