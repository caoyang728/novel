"""
项目公共工具函数

全局共享的辅助函数，供 worldview、outline 等模块调用。
"""
import json
from loguru import logger
from langchain_core.prompts import ChatPromptTemplate


# ============ JSON 解析辅助函数 ============

def strip_think(full_content):
    """去除可能残留的 thinking 标签"""
    if '</think>' in full_content:
        full_content = full_content[full_content.rfind('</think>') + len('</think>'):]
    return full_content


def extract_json_str(full_content):
    """从 LLM 输出中定位并提取 JSON 文本，返回 json_str 或 None"""
    full_content = strip_think(full_content)

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


def strict_parse(json_str):
    """标准 json.loads 解析，成功返回 data，失败返回 None"""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f'json.loads 失败: {e}')
        return None


def validate_patch_data(data):
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


def detect_truncated(json_str, finish_reason=None):
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




# ============ 三轮容错机制 ============

def run_retry_loop(
    *,
    chain,
    prompt,
    user_input,
    scene,
    apply_fn,
    base_content,
    sse_event_fn,
    get_chunk_text_fn,
    log_token_usage_fn,
    user,
    project,
    log_prefix='[APP]',
    max_rounds=3,
    get_stream_input=None,
    wrap_stream_fn=None,
    json_repair_prompt=None,
):
    """三轮容错机制：解析 → 失败则重新生成

    Args:
        chain: LangChain chain (prompt | llm)
        prompt: ChatPromptTemplate（重试时用于重建 chain）
        user_input: 用户输入
        scene: LLM 场景名
        apply_fn: 补丁应用回调 (data, base_content) -> result dict
        base_content: 基准内容
        sse_event_fn: SSE 事件发送函数 (event_type, data) -> event
        get_chunk_text_fn: chunk 文本提取函数 (chunk) -> str
        log_token_usage_fn: token 统计函数 (scene, result, usage_result, user, project)
        user: 当前用户
        project: 当前项目
        log_prefix: 日志前缀
        max_rounds: 最大轮数
        get_stream_input: 获取 stream 输入的回调 (round_input) -> dict，默认 {}
        wrap_stream_fn: 包装 stream 的回调 (stream) -> wrapped_stream，默认不包装
        json_repair_prompt: JSON 修复提示词模板（含 {error} 和 {raw_content} 占位符），为 None 时跳过修复

    Yields:
        SSE 事件

    Returns:
        (result, full_content) 或 (None, '') 如果失败
    """
    from agent.llm import get_llm

    result = None
    last_error = ''
    full_content = ''

    for round_idx in range(1, max_rounds + 1):
        chunk_full_content = ''
        last_chunk = None
        usage_chunk = None
        finish_reason = None

        # 重试时降温度 + 附带错误反馈
        round_chain = chain
        round_input = user_input
        if round_idx > 1:
            round_llm = get_llm(user=user, scene=scene, temperature=0.4)
            round_chain = prompt | round_llm
            round_input = (
                f'{user_input}\n\n'
                f'[系统提醒] 你上一次的输出无法被解析（原因：{last_error or "JSON格式错误"}）。'
                f'本次务必严格只输出合法 JSON：以 {{"patch_list": 开头、字段完整、'
                f'字符串内部的引号必须转义、不要输出 JSON 以外的任何文字。'
            )
            yield sse_event_fn('status', {
                'message': f'输出格式异常，正在重新生成（第 {round_idx}/{max_rounds} 次）…',
            })

        # 流式收集 LLM 输出
        stream_input = get_stream_input(round_input) if get_stream_input else {}
        stream = round_chain.stream(stream_input)
        if wrap_stream_fn:
            stream = wrap_stream_fn(stream)
        for chunk in stream:
            piece = get_chunk_text_fn(chunk)
            if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                usage_chunk = chunk
            meta = getattr(chunk, 'response_metadata', None) or {}
            fr = meta.get('finish_reason') or meta.get('stop_reason')
            if fr:
                finish_reason = fr
            last_chunk = chunk
            if piece:
                chunk_full_content += piece
                yield sse_event_fn('reply_chunk', {'chunk': piece})

        full_content = chunk_full_content

        # token 统计
        try:
            log_token_usage_fn(scene, result=last_chunk,
                               usage_result=usage_chunk, user=user, project=project)
        except Exception as log_err:
            logger.warning(f'{log_prefix} token 记录失败: {log_err}')

        # ---- 标准解析 ----
        json_str = extract_json_str(full_content)
        parse_error = ''
        data = None

        if json_str is None:
            parse_error = '输出中未找到 JSON 内容'
            logger.warning(f'{log_prefix} 第{round_idx}轮: 未找到JSON, 输出前200字: {full_content[:200]}')
        else:
            data = strict_parse(json_str)
            if data is None:
                try:
                    json.loads(json_str)
                except json.JSONDecodeError as je:
                    parse_error = str(je)

        # 解析成功 + 结构校验通过 → 应用补丁
        if data is not None and validate_patch_data(data):
            result = apply_fn(data, base_content)
            logger.info(f'{log_prefix} 第{round_idx}轮解析成功')
            break

        # ---- 截断判定 ----
        if detect_truncated(json_str or full_content, finish_reason):
            last_error = '输出被截断（内容不完整）'
            logger.warning(f'{log_prefix} 第{round_idx}轮输出截断: finish_reason={finish_reason}')
            continue

        # 完全没有 JSON → 记录错误，下轮重新生成
        if json_str is None:
            last_error = parse_error
            continue

        # JSON 存在但解析失败 → 尝试 JSON 修复
        last_error = parse_error or 'JSON 格式错误'
        logger.warning(f'{log_prefix} 第{round_idx}轮JSON解析失败: {last_error}')

        # ---- JSON 修复尝试（仅当有修复提示词且非截断时） ----
        if json_repair_prompt is not None and json_str is not None:
            try:
                repair_llm = get_llm(user=user, scene=scene, temperature=0.2)
                repair_prompt_text = json_repair_prompt.format(
                    error=last_error, raw_content=json_str
                )
                repair_messages = [
                    ("system", "你是 JSON 格式修复专家，只输出修复后的 JSON，不要输出任何解释。"),
                    ("user", repair_prompt_text),
                ]
                repair_chain = ChatPromptTemplate.from_messages(repair_messages) | repair_llm
                repair_result = repair_chain.invoke({})
                repair_text = repair_result.content if hasattr(repair_result, 'content') else str(repair_result)
                repair_text = strip_think(repair_text).strip()

                # 检查修复结果是否为不可修复标记
                if repair_text in ('{"status": "truncated"}', '{"status": "unrepairable"}'):
                    logger.info(f'{log_prefix} 第{round_idx}轮JSON修复判定为不可修复: {repair_text}')
                    continue

                # 解析修复后的 JSON
                repair_data = strict_parse(repair_text)
                if repair_data is not None and validate_patch_data(repair_data):
                    result = apply_fn(repair_data, base_content)
                    logger.info(f'{log_prefix} 第{round_idx}轮JSON修复成功并应用补丁')
                    full_content = repair_text
                    break
                else:
                    logger.warning(f'{log_prefix} 第{round_idx}轮JSON修复后仍无法解析')
            except Exception as repair_err:
                logger.warning(f'{log_prefix} 第{round_idx}轮JSON修复调用失败: {repair_err}')

    # 所有轮次均失败
    if result is None:
        yield sse_event_fn('error', {
            'message': 'AI 多次输出格式异常，请重新发送消息或稍后再试'
        })
        return None, ''

    return result, full_content


# ============ 题材相关函数 ============

def get_genre_label(genre):
    """
    获取题材中文名，全局唯一定义。
    支持子题材 fallback：'history/chuan_yue' → 'history' → '通用'
    """
    from apps.project.models import GENRE_CHOICES
    genre_labels = dict(GENRE_CHOICES)
    # 精确匹配
    if genre in genre_labels:
        return genre_labels[genre]
    # 回退到父题材
    parent = genre.split('/')[0]
    return genre_labels.get(parent, '通用')


def get_genre_guide(genre, prompts_dict):
    """
    获取题材构建指引，三级 fallback：精确匹配 → 父题材 → general
    例：'history/chuan_yue' → 'history' → 'general'

    Args:
        genre: 题材代码（如 'history/chuan_yue'）
        prompts_dict: 题材提示词字典（WORLDVIEW_GENRE_PROMPTS_DICT 或 OUTLINE_GENRE_PROMPTS_DICT）
    """
    # 1. 精确匹配
    if genre in prompts_dict:
        return prompts_dict[genre]
    # 2. 回退到父题材
    parent = genre.split('/')[0]
    if parent in prompts_dict:
        return prompts_dict[parent]
    # 3. 兜底
    return prompts_dict['general']
