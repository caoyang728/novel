"""
世界观文档 API

- 世界观以 Markdown 整体存储，对话式 AI 构建
- LLM 输出 patch_list（增量补丁），后端应用补丁后返回完整文档
- 按题材（genre）选择不同的提示词骨架
- SSE 流式协议：
    reply_chunk  对话回复分片（显示在聊天气泡）
    doc_chunk    文档分片（应用补丁后的完整 Markdown，分块发送）
    complete     完成（含引导问题、选项、补丁统计）
    error        错误
"""
import re
import traceback

from django.db import close_old_connections, models
from django.http import JsonResponse, StreamingHttpResponse
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from agent.llm import get_llm

from apps.project.base import BaseAPIView
from .models import WorldView, WorldViewChatHistory
from .prompts import (
    WORLDVIEW_CONTEXT_TEMPLATE,
    WORLDVIEW_BUILD_USER_PROMPT,
    WORLDVIEW_FACTION_EXTRACT_PROMPT,
    WORLDVIEW_GENRE_PROMPTS_DICT,
)
from apps.project.utils import (
    get_genre_guide, get_genre_label, run_retry_loop,
)


class BaseWorldAPIView(BaseAPIView):
    """世界观模块基类（仅继承 BaseAPIView 的公共功能）"""

    def success_response(self, data, status=200):
        return JsonResponse({'success': True, **data}, status=status)

    def error_response(self, message, status=400):
        return JsonResponse({'success': False, 'error': message}, status=status)


def _get_or_create_doc(project):
    """获取项目的世界观文档（当前版本），不存在则创建"""
    doc = WorldView.objects.filter(
        project=project, is_deleted=False
    ).first()  # Meta.ordering = ['-version']，first() 即最新版本
    if doc:
        return doc
    # 没有未删除的文档，计算下一个版本号（避免与已删除版本冲突）
    max_v = WorldView.objects.filter(project=project).aggregate(
        models.Max('version'))['version__max'] or 0
    doc = WorldView.objects.create(
        project=project,
        version=max_v + 1,
        genre=project.genre or 'general',
        content='',
        title='',
    )
    return doc


# ============ 补丁应用 ============

def _apply_patch_data(data, base_content):
    """将已校验的 patch data 应用到基准文档，返回结果 dict"""
    patch_list = data.get('patch_list', [])
    question = data.get('question', '')
    options = data.get('options', [])

    # 应用 patches
    result_text = base_content
    applied_count = 0
    edits_summary = []

    for patch in patch_list:
        old_snippet = patch.get('old_snippet', '')
        new_snippet = patch.get('new_snippet', '')

        if not old_snippet:
            # 首次生成 / 末尾追加
            if not result_text.strip():
                result_text = new_snippet
            else:
                result_text = result_text.rstrip('\n') + '\n\n' + new_snippet
            applied_count += 1
            edits_summary.append({'type': 'add', 'preview': new_snippet[:80]})
            continue

        count = result_text.count(old_snippet)
        if count == 0:
            logger.warning(f'[WV_DOC] Patch未匹配: old_snippet={old_snippet[:60]}...')
            edits_summary.append({'type': 'failed', 'preview': old_snippet[:60]})
            continue
        if count > 1:
            logger.warning(f'[WV_DOC] Patch多处匹配({count}次): old_snippet={old_snippet[:60]}...')
            edits_summary.append({'type': 'ambiguous', 'preview': old_snippet[:60]})
            continue

        result_text = result_text.replace(old_snippet, new_snippet, 1)
        applied_count += 1
        edits_summary.append({'type': 'replace', 'old': old_snippet[:60], 'new': new_snippet[:80]})

    # 从文档首行提取标题
    title = ''
    if result_text.strip():
        first_line = result_text.split('\n', 1)[0].strip()
        if first_line.startswith('#'):
            title = first_line.lstrip('#').strip()[:200]

    return {
        'new_content': result_text,
        'title': title,
        'question': question,
        'options': options if isinstance(options, list) else [],
        'edits_applied': applied_count,
        'edits_total': len(patch_list),
        'edits_summary': edits_summary,
    }


class ApiWorldviewView(BaseWorldAPIView):
    """世界观文档 GET/PUT"""

    def get(self, request, project_id):
        project = self.get_project_or_404(request, project_id)
        doc = WorldView.objects.filter(project=project, is_deleted=False).first()
        if not doc:
            return self.success_response({
                'exists': False,
                'id': None,
                'genre': 'general',
                'genre_label': '通用',
                'title': '',
                'content': '',
                'version': 0,
                'faction_index': [],
            })
        return self.success_response({
            'exists': True,
            'id': doc.id,
            'genre': project.genre or 'general',
            'genre_label': get_genre_label(project.genre),
            'title': doc.title,
            'content': doc.content,
            'version': doc.version,
            'faction_index': doc.faction_index or [],
            'updated_at': doc.updated_at.isoformat(),
        })

    def put(self, request, project_id):
        """手动保存文档"""
        project = self.get_project_or_404(request, project_id)
        doc = _get_or_create_doc(project)

        title = request.data.get('title')
        content = request.data.get('content')
        truncated = False

        if title is not None:
            doc.title = str(title).strip()[:200]
        if content is not None:
            raw = str(content)
            if len(raw) > 500000:
                truncated = True
                logger.warning(f'[WV_DOC] 文档内容被截断: 原始长度={len(raw)}, 限制=500000')
            doc.content = raw[:500000]
            doc.version = (doc.version or 1) + 1

        doc.save()

        resp = {
            'exists': True,
            'id': doc.id,
            'genre': project.genre or 'general',
            'genre_label': get_genre_label(project.genre),
            'title': doc.title,
            'content': doc.content,
            'version': doc.version,
        }
        if truncated:
            resp['truncated'] = True
            resp['truncated_message'] = '文档内容超过 500KB 限制，已自动截断'
        return self.success_response(resp)


class ApiWorldviewStreamView(BaseWorldAPIView):
    """世界观文档对话流式构建（patch_list 增量补丁协议）

    请求体：{ message: 用户输入, messages: [{role, content}...], genre?: 题材 }
    流程：LLM 输出 JSON patch → 后端应用补丁 → 分块返回完整文档
    输出协议：reply_chunk / doc_chunk / complete / error
    """

    def post(self, request, project_id):
        project = self.get_project_or_404(request, project_id)

        user_input = (request.data.get('message') or '').strip()
        if not user_input:
            return self.error_response('消息不能为空')

        # 前端传来的当前工作内容（未持久化的最新版本），作为补丁基准
        current_content = request.data.get('current_content')

        # 前端传来的历史对话消息（避免从数据库读取已放弃的对话）
        history_messages = request.data.get('messages', [])

        # 题材统一从 project 获取
        effective_genre = project.genre or 'general'

        def generate():
            try:
                close_old_connections()
                doc = _get_or_create_doc(project)

                # 持久化用户消息
                WorldViewChatHistory.objects.create(
                    worldview=doc, role='user', content=user_input
                )

                # 确定补丁基准：前端传来的当前工作内容 > 数据库持久化内容
                base_content = current_content if current_content is not None else (doc.content or '')

                # 构建提示词
                genre_name_label = get_genre_label(effective_genre)
                genre_guide_text = get_genre_guide(effective_genre, WORLDVIEW_GENRE_PROMPTS_DICT).format(
                    genre_name=genre_name_label,
                )
                context_text = WORLDVIEW_CONTEXT_TEMPLATE.format(
                    current_doc=base_content or '（空，首次生成）',
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
                messages.append(("user", WORLDVIEW_BUILD_USER_PROMPT.format(
                    user_input=user_input,
                )))

                prompt = ChatPromptTemplate.from_messages(messages)

                llm = get_llm(user=request.user, scene="worldview_build")
                chain = prompt | llm

                # ============ 三轮容错机制 ============
                result, full_content = yield from run_retry_loop(
                    chain=chain,
                    prompt=prompt,
                    user_input=user_input,
                    scene="worldview_build",
                    apply_fn=_apply_patch_data,
                    base_content=base_content,
                    sse_event_fn=self.sse_event,
                    get_chunk_text_fn=self.get_chunk_text,
                    log_token_usage_fn=self.log_token_usage,
                    user=request.user,
                    project=project,
                    log_prefix='[WV_DOC]',
                    max_rounds=3,
                    get_stream_input=lambda ri: {"user_input": ri},
                )

                # 三轮均失败（run_retry_loop 已发送 error 事件）
                if result is None:
                    return

                logger.info(f'[WV_DOC] patches: applied={result.get("edits_applied", 0)}/{result.get("edits_total", 0)}, '
                            f'question_len={len(result.get("question", ""))}, content_len={len(result.get("new_content", ""))}')

                new_content = result.get('new_content', '')
                assistant_reply = result.get('question', '')
                options = result.get('options', [])

                # 2. 仅流式发送文档内容（不自动保存，由用户手动触发保存）
                if new_content and new_content.strip() != base_content.strip():
                    # 分块发送文档内容（更新左侧预览）
                    chunk_size = 50
                    for i in range(0, len(new_content), chunk_size):
                        yield self.sse_event('doc_chunk', {'chunk': new_content[i:i + chunk_size]})

                # 持久化助手消息
                WorldViewChatHistory.objects.create(
                    worldview=doc, role='assistant',
                    content=assistant_reply or '世界观文档已更新',
                    options=options or []
                )

                # 3. 发送完成信号
                yield self.sse_event('complete', {
                    'reply': assistant_reply,
                    'content': new_content or base_content,
                    'options': options,
                    'edits_applied': result.get('edits_applied', 0),
                    'edits_total': result.get('edits_total', 0),
                })

            except Exception as e:
                logger.error(f'世界观文档流式生成异常: {e}')
                logger.error(traceback.format_exc())
                yield self.sse_event('error', {'message': str(e)})

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiWorldviewFactionExtractView(BaseWorldAPIView):
    """从世界观文档提取阵营索引（供角色表单下拉框使用）"""

    def post(self, request, project_id):
        project = self.get_project_or_404(request, project_id)
        doc = _get_or_create_doc(project)

        if not (doc.content or '').strip():
            return self.success_response({'faction_index': [], 'message': '文档为空，暂无阵营'})

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是信息提取助手，严格按要求输出 JSON。"),
            ("human", WORLDVIEW_FACTION_EXTRACT_PROMPT),
        ])

        try:
            llm = get_llm(user=request.user, scene="worldview_chat")
            chain = prompt | llm
            result = chain.invoke({"doc_content": doc.content})
            self.log_token_usage('worldview_faction_extract', result=result,
                                 user=request.user, project=project)

            text = result.content if hasattr(result, 'content') else str(result)
            factions = []
            try:
                m = re.search(r'\[.*\]', text, re.DOTALL)
                if m:
                    factions = json.loads(m.group(0))
            except Exception:
                factions = []

            # 清洗结构
            cleaned = []
            for item in factions if isinstance(factions, list) else []:
                if isinstance(item, dict) and item.get('name'):
                    cleaned.append({
                        'name': str(item['name']).strip(),
                        'subs': [str(s).strip() for s in (item.get('subs') or []) if str(s).strip()],
                    })

            doc.faction_index = cleaned
            doc.save(update_fields=['faction_index'])

            return self.success_response({'faction_index': cleaned})
        except Exception as e:
            logger.error(f'阵营索引提取失败: {e}')
            logger.error(traceback.format_exc())
            return self.error_response(f'提取失败：{e}')


# ============ 版本管理 API ============

class ApiWorldviewVersionsView(BaseWorldAPIView):
    """世界观文档版本列表"""

    def get(self, request, project_id):
        project = self.get_project_or_404(request, project_id)
        versions = WorldView.objects.filter(project=project, is_deleted=False)
        latest_id = versions.first().id if versions.exists() else None
        data = [{
            'id': v.id,
            'version_number': v.version,
            'snapshot': (v.content or '')[:500],
            'is_current': v.id == latest_id,
            'is_finalized': v.is_finalized,
            'created_at': v.created_at.strftime('%Y-%m-%d %H:%M'),
        } for v in versions]

        latest = data[0] if data else None
        return self.success_response({'versions': data, 'latest': latest})


class ApiWorldviewVersionLoadView(BaseWorldAPIView):
    """加载指定版本"""

    def get(self, request, project_id, version_id):
        project = self.get_project_or_404(request, project_id)
        version = WorldView.objects.filter(
            id=version_id, project=project, is_deleted=False
        ).first()
        if not version:
            return self.error_response('版本不存在')

        return self.success_response({
            'id': version.id,
            'version_number': version.version,
            'content': version.content,
            'is_finalized': version.is_finalized,
            'last_question': version.last_question,
            'last_options': version.last_options or [],
        })


class ApiWorldviewVersionSaveView(BaseWorldAPIView):
    """保存新版本（创建新的 WorldView 行）"""

    def post(self, request, project_id):
        project = self.get_project_or_404(request, project_id)

        content = (request.data.get('content') or '').strip()
        if not content:
            return self.error_response('内容不能为空')

        # 计算下一个版本号
        next_vn = (WorldView.objects.filter(project=project).aggregate(
            models.Max('version'))['version__max'] or 0) + 1

        last_question = (request.data.get('last_question') or '').strip()
        last_options = request.data.get('last_options') or []

        version = WorldView.objects.create(
            project=project,
            version=next_vn,
            content=content,
            last_question=last_question,
            last_options=last_options,
        )

        return self.success_response({
            'id': version.id,
            'version_number': version.version,
            'content': version.content,
        })


class ApiWorldviewVersionUpdateView(BaseWorldAPIView):
    """更新指定版本内容（不创建新版本）"""

    def post(self, request, project_id):
        project = self.get_project_or_404(request, project_id)
        version_id = request.data.get('version_id')

        if not version_id:
            return self.error_response('缺少 version_id')

        version = WorldView.objects.filter(
            id=version_id, project=project, is_deleted=False
        ).first()
        if not version:
            return self.error_response('版本不存在')

        content = (request.data.get('content') or '').strip()
        if not content:
            return self.error_response('内容不能为空')

        version.content = content
        version.last_question = (request.data.get('last_question') or '').strip()
        version.last_options = request.data.get('last_options') or []
        version.save(update_fields=['content', 'last_question', 'last_options', 'updated_at'])

        return self.success_response({
            'id': version.id,
            'version_number': version.version,
            'content': version.content,
        })


class ApiWorldviewVersionLockView(BaseWorldAPIView):
    """锁定版本（设为定稿）"""

    def post(self, request, project_id, version_id):
        project = self.get_project_or_404(request, project_id)
        version = WorldView.objects.filter(
            id=version_id, project=project, is_deleted=False
        ).first()
        if not version:
            return self.error_response('版本不存在')

        version.is_finalized = True
        version.save(update_fields=['is_finalized', 'updated_at'])
        return self.success_response({'id': version.id, 'is_finalized': True})


class ApiWorldviewVersionUnlockView(BaseWorldAPIView):
    """解锁版本"""

    def post(self, request, project_id, version_id):
        project = self.get_project_or_404(request, project_id)
        version = WorldView.objects.filter(
            id=version_id, project=project, is_deleted=False
        ).first()
        if not version:
            return self.error_response('版本不存在')

        version.is_finalized = False
        version.save(update_fields=['is_finalized', 'updated_at'])
        return self.success_response({'id': version.id, 'is_finalized': False})


class ApiWorldviewVersionDeleteView(BaseWorldAPIView):
    """删除版本（软删除）"""

    def post(self, request, project_id, version_id):
        project = self.get_project_or_404(request, project_id)
        version = WorldView.objects.filter(
            id=version_id, project=project, is_deleted=False
        ).first()
        if not version:
            return self.error_response('版本不存在')

        if version.is_finalized:
            return self.error_response('已定稿版本不能删除，请先解锁')

        version.is_deleted = True
        version.save(update_fields=['is_deleted', 'updated_at'])

        return self.success_response({'deleted': True})



