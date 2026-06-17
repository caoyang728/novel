"""
消息历史滚动压缩模块。
使用 LLM 按时间远近逐层压缩：越远的消息权重越低、细节越少，越新的保留越完整。
通用设计，适用于各类对话场景。
"""

from langchain_core.prompts import ChatPromptTemplate


def compress_history(messages, llm, keep_full=10):
    """滚动压缩历史消息。

    最近 keep_full 组完整保留 → 更早的由 LLM 按远近分层压缩，一次调用完成。
    权重递减：较新对话保留更多细节，较老对话仅保留关键要点。

    Args:
        messages: [{'role': 'user'|'assistant', 'content': '...'}, ...]
        llm: LangChain ChatOpenAI 实例
        keep_full: 完整保留的最近 N 组对话，默认 10

    Returns:
        压缩后的历史文本字符串
    """
    if not messages or llm is None:
        return ''

    # 分组为 (user, assistant) 对
    pairs = []
    pending_user = None
    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '').strip()
        if not content:
            continue
        if role == 'user':
            pending_user = content
        elif role == 'assistant' and pending_user is not None:
            pairs.append((pending_user, content))
            pending_user = None

    if not pairs:
        return '\n'.join(f'{m.get("role")}: {m.get("content")}' for m in messages)

    keep_full = min(keep_full, len(pairs))
    lines = []

    # 最新 N 组：完整保留原文
    for user_msg, ai_msg in pairs[-keep_full:]:
        lines.append(f'user: {user_msg}')
        lines.append(f'assistant: {ai_msg}')

    # 更早的消息：交给 LLM 按远近分层压缩
    older = pairs[:-keep_full]
    if older:
        older_text_parts = []
        for i, (user_msg, ai_msg) in enumerate(older):
            older_text_parts.append(f'[第{i+1}组] user: {user_msg}')
            older_text_parts.append(f'[第{i+1}组] assistant: {ai_msg}')
        older_text = '\n'.join(older_text_parts)

        summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一个对话压缩器。请按时间远近分层压缩以下对话，权重递减：

- **较近对话**（后半段）：保留主要讨论内容、关键决策，可适当简化
- **较远对话**（中段）：压缩为一两句核心要点
- **最远对话**（开头段）：仅保留最重要的结论或产出，忽略过程

压缩须知：
1. 保留对话中达成的决定、关键信息、重要结论
2. 去掉闲聊、重复、已被后续推翻的内容
3. 按时间顺序输出，体现对话推进脉络
4. 总字数不超过 500 字
5. 纯文本输出，不要 Markdown 格式"""),
            ("user", "对话历史（按时间顺序，越靠前越早）：\n\n{history}\n\n请压缩。")
        ])

        try:
            result = (summary_prompt | llm).invoke({"history": older_text})
            summary = result.content if hasattr(result, 'content') else str(result)
            lines.insert(0, f'[历史摘要] {summary.strip()}')
        except Exception:
            lines.insert(0, f'[更早的 {len(older)} 组对话]')

    return '\n'.join(lines)
