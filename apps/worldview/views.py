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
import json
import re
import traceback

from django.db import close_old_connections, models
from django.http import JsonResponse, StreamingHttpResponse
from langchain_core.prompts import ChatPromptTemplate
from loguru import logger

from agent.llm import get_llm
from agent.memory import compress_history

from apps.project.base import BaseAPIView
from .models import WorldView, WorldViewChatHistory
from .prompts import (
    WORLDVIEW_SYSTEM_PROMPT,
    WORLDVIEW_BUILD_PROMPT,
    WORLDVIEW_JSON_REPAIR_PROMPT,
    WORLDVIEW_WELCOME_PROMPT,
    WORLDVIEW_FACTION_EXTRACT_PROMPT,
    GENRE_LABELS,
    get_genre_guide,
    get_genre_label,
)


class BaseWorldAPIView(BaseAPIView):
    """世界观模块基类（仅继承 BaseAPIView 的公共功能）"""

    def success_response(self, data, status=200):
        return JsonResponse({'success': True, **data}, status=status)

    def error_response(self, message, status=400):
        return JsonResponse({'success': False, 'error': message}, status=status)


def _get_or_create_doc(project):
    """获取项目的世界观文档（当前版本），不存在则创建 v1"""
    doc, created = WorldView.objects.get_or_create(
        project=project,
        version=1,
        defaults={'genre': project.genre or 'general', 'content': '', 'title': ''},
    )
    return doc


def _strip_think(full_content):
    """去除可能残留的 thinking 标签"""
    if '</think>' in full_content:
        full_content = full_content[full_content.rfind('</think>') + len('</think>'):]
    return full_content


def _extract_json_str(full_content):
    """从 LLM 输出中定位并提取 JSON 文本，返回 json_str 或 None"""
    full_content = _strip_think(full_content)

    json_start = full_content.find('{"patch_list"')
    if json_start == -1:
        json_start = full_content.find('{')
    if json_start == -1:
        return None

    json_str = full_content[json_start:]
    json_end = json_str.rfind('}')
    if json_end != -1:
        json_str = json_str[:json_end + 1]
    return json_str.strip()


def _strict_parse(json_str):
    """标准 json.loads 解析，成功返回 data，失败返回 None"""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f'[WV_DOC] json.loads 失败: {e}')
        return None


def _validate_patch_data(data):
    """结构校验：JSON 语法正确后，校验业务结构是否完整合法"""
    if not isinstance(data, dict):
        return False
    patch_list = data.get('patch_list')
    if not isinstance(patch_list, list):
        return False
    for p in patch_list:
        if not isinstance(p, dict):
            return False
        if not isinstance(p.get('old_snippet', ''), str):
            return False
        if not isinstance(p.get('new_snippet', ''), str):
            return False
    if data.get('question') is not None and not isinstance(data.get('question'), str):
        return False
    if data.get('options') is not None and not isinstance(data.get('options'), list):
        return False
    return True


def _detect_truncated(json_str, finish_reason=None):
    """截断判定：
    1. finish_reason/stop_reason == 'length'（上游 token 上限截断，最权威）
    2. 括号/引号配平检查（字符串状态机扫描，忽略转义）
    """
    if finish_reason == 'length':
        return True
    if not json_str:
        return False
    depth = 0
    in_str = False
    escape = False
    for ch in json_str:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch in '{[':
                depth += 1
            elif ch in '}]':
                depth -= 1
    return in_str or depth != 0


def _llm_repair_json(repair_llm, raw_content, error_msg):
    """让修复 LLM 修复损坏的 JSON（单次调用）。

    返回 (data, status)：
    - (data, 'ok')：修复成功且结构校验通过
    - (None, 'truncated')：LLM 判定内容被截断
    - (None, 'failed')：无法修复 / 修复后仍不合法
    """
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("human", WORLDVIEW_JSON_REPAIR_PROMPT),
        ])
        chain = prompt | repair_llm
        resp = chain.invoke({
            "error": str(error_msg)[:500],
            "raw_content": raw_content[:20000],
        })
        text = resp.content if hasattr(resp, 'content') else str(resp)
        text = _strip_think(text)

        data = _strict_parse(text.strip())
        if data is None:
            # 修复结果可能被 Markdown 代码块等包裹，再提取一次
            repaired_str = _extract_json_str(text)
            data = _strict_parse(repaired_str) if repaired_str else None

        if data is None:
            return None, 'failed'

        # LLM 明确返回状态标记
        if isinstance(data.get('status'), str):
            if data['status'] == 'truncated':
                return None, 'truncated'
            return None, 'failed'

        if _validate_patch_data(data):
            logger.info('[WV_DOC] LLM 修复 JSON 成功')
            return data, 'ok'
        return None, 'failed'
    except Exception as e:
        logger.warning(f'[WV_DOC] LLM 修复调用异常: {e}')
        return None, 'failed'


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
            'genre': doc.genre,
            'genre_label': get_genre_label(doc.genre),
            'title': doc.title,
            'content': doc.content,
            'version': doc.version,
            'faction_index': doc.faction_index or [],
            'updated_at': doc.updated_at.isoformat(),
        })

    def put(self, request, project_id):
        """手动保存文档（编辑/切换题材）"""
        project = self.get_project_or_404(request, project_id)
        doc = _get_or_create_doc(project)

        genre = request.data.get('genre')
        title = request.data.get('title')
        content = request.data.get('content')

        if genre is not None:
            genre = str(genre).strip()
            if genre not in GENRE_LABELS:
                return self.error_response('不支持的题材类型')
            doc.genre = genre
        if title is not None:
            doc.title = str(title).strip()[:200]
        if content is not None:
            doc.content = str(content)[:500000]  # 限制文档最大 500KB
            doc.version = (doc.version or 1) + 1

        close_old_connections()
        doc.save()

        return self.success_response({
            'exists': True,
            'id': doc.id,
            'genre': doc.genre,
            'genre_label': get_genre_label(doc.genre),
            'title': doc.title,
            'content': doc.content,
            'version': doc.version,
        })


class ApiWorldviewOpenView(BaseWorldAPIView):
    """打开世界观文档聊天：返回开场引导问题（非流式）"""

    def post(self, request, project_id):
        project = self.get_project_or_404(request, project_id)
        doc = _get_or_create_doc(project)

        has_content = bool((doc.content or '').strip())

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位资深小说世界观架构师，协助作者构建世界观。"),
            ("human", WORLDVIEW_WELCOME_PROMPT),
        ])

        try:
            llm = get_llm(user=request.user, scene="worldview_chat")
            chain = prompt | llm
            current_doc_section = ''
            if has_content and doc.content:
                current_doc_section = f'当前文档内容（前 3000 字）：\n---\n{doc.content[:3000]}\n---'

            result = chain.invoke({
                "genre_label": get_genre_label(doc.genre),
                "doc_status": "已有内容" if has_content else "空白（尚未开始构建）",
                "current_doc_section": current_doc_section,
            })
            self.log_token_usage('worldview_welcome', result=result,
                                 user=request.user, project=project)

            text = result.content if hasattr(result, 'content') else str(result)

            question = ''
            options = []
            try:
                m = re.search(r'```(?:json)?\s*(\{[\s\S]*\})\s*```', text, re.DOTALL)
                if m:
                    data = json.loads(m.group(1))
                else:
                    m = re.search(r'\{[\s\S]*\}', text, re.DOTALL)
                    data = json.loads(m.group(0)) if m else {}
                question = data.get('question', '')
                options = data.get('options', [])
            except Exception:
                logger.warning(f'世界观文档开场 JSON 解析失败: {text[:200]}')
                question = text

            return self.success_response({
                'has_content': has_content,
                'genre': doc.genre,
                'genre_label': get_genre_label(doc.genre),
                'question': question,
                'options': options,
            })
        except Exception as e:
            logger.error(f'世界观文档开场问题失败: {e}')
            logger.error(traceback.format_exc())
            return self.success_response({
                'has_content': has_content,
                'genre': doc.genre,
                'genre_label': get_genre_label(doc.genre),
                'question': '',
                'options': [],
            })


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

        history_messages = request.data.get('messages') or []
        genre = (request.data.get('genre') or '').strip()
        # 前端传来的当前工作内容（未持久化的最新版本），作为补丁基准
        current_content = request.data.get('current_content')

        def generate():
            try:
                close_old_connections()
                doc = _get_or_create_doc(project)

                # 题材：请求指定 > 文档已存 > 通用
                # 仅在本地变量中使用，待生成成功后再持久化（避免用户中断时产生副作用）
                if genre and genre in GENRE_LABELS and doc.genre != genre:
                    effective_genre = genre
                else:
                    effective_genre = doc.genre

                # 持久化用户消息
                WorldViewChatHistory.objects.create(
                    worldview=doc, role='user', content=user_input
                )

                prompt = ChatPromptTemplate.from_messages([
                    ("system", WORLDVIEW_SYSTEM_PROMPT),
                    ("human", WORLDVIEW_BUILD_PROMPT),
                ])

                llm = get_llm(user=request.user, scene="worldview_build")
                # 修复用 LLM：低温度，输出更稳定
                repair_llm = get_llm(user=request.user, scene="worldview_chat", temperature=0.1)

                # 压缩历史对话
                history_for_llm = [
                    m for m in history_messages
                    if isinstance(m, dict) and m.get('role') in ('user', 'assistant') and m.get('content')
                ]
                history_text = compress_history(history_for_llm, llm)

                chain = prompt | llm

                # 确定补丁基准：前端传来的当前工作内容 > 数据库持久化内容
                base_content = current_content if current_content is not None else (doc.content or '')

                # ============ 三轮容错机制 ============
                # 第1步：json.loads 直接解析
                # 第2步：解析失败 → LLM 修复（内部最多 3 次），LLM 判定截断则跳过
                # 第3步：修复失败/截断 → 从头重新生成（附带错误反馈、降低温度）
                MAX_ROUNDS = 3
                MAX_REPAIR_ATTEMPTS = 3

                result = None
                last_error = ''

                for round_idx in range(1, MAX_ROUNDS + 1):
                    full_content = ''
                    last_chunk = None
                    usage_chunk = None
                    finish_reason = None

                    # 重试时使用更低温度，减少跑偏
                    round_chain = chain
                    if round_idx > 1:
                        round_llm = get_llm(user=request.user, scene="worldview_build", temperature=0.4)
                        round_chain = prompt | round_llm
                        yield self.sse_event('status', {
                            'message': f'输出格式异常，正在重新生成（第 {round_idx}/{MAX_ROUNDS} 次）…',
                        })

                    round_input = user_input
                    if round_idx > 1:
                        round_input = (
                            f'{user_input}\n\n'
                            f'[系统提醒] 你上一次的输出无法被解析（原因：{last_error or "JSON格式错误"}）。'
                            f'本次务必严格只输出合法 JSON：以 {{"patch_list": 开头、字段完整、'
                            f'字符串内部的引号必须转义、不要输出 JSON 以外的任何文字。'
                        )

                    # 流式收集 LLM 的 JSON 输出（增量补丁协议不逐 chunk 解析，整体收集后应用）
                    for chunk in round_chain.stream({
                        "genre_guide": get_genre_guide(effective_genre),
                        "current_doc": base_content,
                        "history_messages": history_text or '（无）',
                        "user_input": round_input,
                    }):
                        piece = self.get_chunk_text(chunk)
                        if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                            usage_chunk = chunk
                        # 捕获上游截断信号（OpenAI 兼容接口 finish_reason=length）
                        meta = getattr(chunk, 'response_metadata', None) or {}
                        fr = meta.get('finish_reason') or meta.get('stop_reason')
                        if fr:
                            finish_reason = fr
                        last_chunk = chunk
                        if piece:
                            full_content += piece
                            # 流式发送原始 LLM 输出到思考区（打字机效果）
                            yield self.sse_event('reply_chunk', {'chunk': piece})

                    # token 统计
                    try:
                        self.log_token_usage('worldview_build', result=last_chunk,
                                             usage_result=usage_chunk, user=request.user, project=project)
                    except Exception as log_err:
                        logger.warning(f'世界观文档 token 记录失败: {log_err}')

                    # ---- 第1步：标准解析 ----
                    json_str = _extract_json_str(full_content)
                    parse_error = ''
                    data = None

                    if json_str is None:
                        parse_error = '输出中未找到 JSON 内容'
                        logger.warning(f'[WV_DOC] 第{round_idx}轮: 未找到JSON, 输出前200字: {full_content[:200]}')
                    else:
                        data = _strict_parse(json_str)
                        if data is None:
                            # 记录具体解析错误供修复 LLM 参考
                            try:
                                json.loads(json_str)
                            except json.JSONDecodeError as je:
                                parse_error = str(je)

                    # 标准解析 + 结构校验通过 → 应用补丁
                    if data is not None and _validate_patch_data(data):
                        result = _apply_patch_data(data, base_content)
                        logger.info(f'[WV_DOC] 第{round_idx}轮直接解析成功')
                        break

                    # ---- 截断判定：finish_reason=length 或括号/引号未配平 → 直接重新生成 ----
                    if _detect_truncated(json_str or full_content, finish_reason):
                        last_error = '输出被截断（内容不完整）'
                        logger.warning(f'[WV_DOC] 第{round_idx}轮输出截断: finish_reason={finish_reason}')
                        continue

                    # 完全没有 JSON（模型跑题/拒绝）→ 修复无意义，直接重新生成
                    if json_str is None:
                        last_error = parse_error
                        continue

                    # ---- 第2步：LLM 修复（内部最多 3 次）----
                    yield self.sse_event('status', {
                        'message': '输出格式异常，正在尝试修复…',
                    })
                    repaired = False
                    for repair_idx in range(1, MAX_REPAIR_ATTEMPTS + 1):
                        repaired_data, repair_status = _llm_repair_json(
                            repair_llm, full_content, parse_error or 'JSON 解析失败'
                        )
                        if repair_status == 'ok' and repaired_data is not None:
                            result = _apply_patch_data(repaired_data, base_content)
                            logger.info(f'[WV_DOC] 第{round_idx}轮 LLM修复成功(第{repair_idx}次尝试)')
                            repaired = True
                            break
                        if repair_status == 'truncated':
                            last_error = '输出被截断（内容不完整）'
                            logger.warning(f'[WV_DOC] 第{round_idx}轮修复LLM判定截断')
                            break
                        # failed → 继续重试修复
                        logger.warning(f'[WV_DOC] 第{round_idx}轮修复第{repair_idx}次失败')

                    if repaired:
                        break

                    # ---- 第3步：修复失败 → 从头重新生成 ----
                    last_error = last_error or 'JSON 格式错误且修复失败'
                    logger.warning(f'[WV_DOC] 第{round_idx}轮修复失败，准备重新生成')

                # 三轮均失败
                if result is None:
                    yield self.sse_event('error', {
                        'message': 'AI 多次输出格式异常，请重新发送消息或稍后再试'
                    })
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

                # 成功后才持久化题材变更（避免中断时产生副作用）
                if effective_genre != doc.genre:
                    doc.genre = effective_genre
                    doc.save(update_fields=['genre', 'updated_at'])

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
            close_old_connections()
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

        # 从请求中获取题材，若未提供则继承当前版本
        genre = (request.data.get('genre') or '').strip()
        current_doc = WorldView.objects.filter(
            project=project, is_deleted=False
        ).first()
        if not genre and current_doc:
            genre = current_doc.genre

        version = WorldView.objects.create(
            project=project,
            version=next_vn,
            genre=genre or 'general',
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


class ApiWorldviewChatHistoryView(BaseWorldAPIView):
    """获取最近的聊天历史"""

    def get(self, request, project_id):
        project = self.get_project_or_404(request, project_id)
        doc = WorldView.objects.filter(project=project, is_deleted=False).first()
        if not doc:
            return self.success_response({'messages': []})

        try:
            limit = max(1, min(50, int(request.query_params.get('limit', 10))))
        except (ValueError, TypeError):
            limit = 10
        histories = WorldViewChatHistory.objects.filter(
            worldview=doc, is_deleted=False
        ).order_by('-created_at')[:limit]

        messages = []
        for h in reversed(list(histories)):
            msg = {'role': h.role, 'content': h.content}
            if h.role == 'assistant' and h.options:
                msg['options'] = h.options
            messages.append(msg)

        return self.success_response({'messages': messages})
