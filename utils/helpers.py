"""
项目级公共工具函数
- safe_parse_json: 安全解析JSON，修复常见LLM输出错误
- format_worldview_context: 格式化世界观设定
- format_characters_context: 格式化人物设定
- format_timeline_context: 格式化时间线
"""
import re
import json
from loguru import logger


# ========== JSON 解析 ==========

def safe_parse_json(raw):
    """安全解析JSON，修复LLM输出中的常见错误（markdown代码块、尾随逗号、未转义控制字符、文本包裹）
    支持：
    1. 纯JSON: {"response": "..."}
    2. markdown包裹: ```json\\n{...}\\n```
    3. 文本前后有附加说明: 一些文字... ```json\\n{...}\\n``` 更多文字...
    4. 任意位置的最外层JSON对象
    """
    s = raw.strip()
    if not s:
        return None

    # 策略1: 尝试提取 markdown 代码块中的JSON（处理文本前有说明的情况）
    md_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', s, re.DOTALL)
    if md_match:
        s = md_match.group(1).strip()

    # 策略2: 尝试找到最外层的完整 JSON 对象 { ... }
    first_brace = s.find('{')
    if first_brace >= 0:
        # 从第一个 { 开始，匹配括号
        depth = 0
        in_string = False
        escape_next = False
        json_start = first_brace
        json_end = -1
        for i in range(first_brace, len(s)):
            c = s[i]
            if escape_next:
                escape_next = False
                continue
            if c == '\\':
                escape_next = True
                continue
            if c == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        json_end = i + 1
                        break
        if json_end > 0:
            s = s[json_start:json_end]

    # 修复尾随逗号
    s = re.sub(r',\s*}', '}', s)
    s = re.sub(r',\s*]', ']', s)

    # 转义字符串值中的真实换行（LLM 常见错误）
    # 在 "key": "value" 结构中，value 部分可能出现未转义的真实换行
    # 找到所有在 "": "" 内部的真实换行并转义
    def escape_newlines_in_strings(text):
        """遍历 JSON，将字符串值内部的真实换行转义为 \\n，保留已有的转义序列"""
        result = []
        i = 0
        in_string = False
        buf = []  # 当前字符串值的字符缓冲
        while i < len(text):
            c = text[i]
            if c == '"' and (i == 0 or text[i-1] != '\\'):
                if in_string:
                    # 字符串结束，转义 buf 中的真实换行，输出
                    escaped = []
                    j = 0
                    while j < len(buf):
                        ch = buf[j]
                        if ch == '\\' and j + 1 < len(buf):
                            # 保留已有转义序列
                            escaped.append('\\')
                            escaped.append(buf[j+1])
                            j += 2
                        elif ch == '\n':
                            escaped.append('\\n')
                            j += 1
                        elif ch == '\r':
                            escaped.append('\\r')
                            j += 1
                        elif ch == '\t':
                            escaped.append('\\t')
                            j += 1
                        elif ord(ch) < 0x20:
                            escaped.append(f'\\u{ord(ch):04x}')
                            j += 1
                        else:
                            escaped.append(ch)
                            j += 1
                    result.append(''.join(escaped))
                    result.append('"')
                    buf = []
                    in_string = False
                else:
                    result.append('"')
                    in_string = True
                i += 1
            elif in_string:
                buf.append(c)
                i += 1
            else:
                result.append(c)
                i += 1
        return ''.join(result)

    s = escape_newlines_in_strings(s)

    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON解析失败: {e}, 内容前500字符: {s[:500]}")
        return None


# ========== 上下文格式化 ==========

def format_worldview_context(project):
    """格式化项目世界观设定为文本（新版：直接返回 Markdown 内容）"""
    try:
        from apps.worldview.models import WorldView
        worldview = WorldView.objects.filter(
            project=project, is_deleted=False
        ).order_by('-version').first()
        if not worldview or not worldview.content:
            return '（暂无世界观设定）'
        return worldview.content
    except Exception as e:
        logger.error(f"格式化世界观上下文失败: {e}")
        return '（暂无世界观设定）'


def format_characters_context(project):
    """格式化项目人物清单为文本"""
    try:
        from apps.characters.models import Character
        characters = Character.objects.filter(project=project, is_deleted=False)
        if not characters.exists():
            return '（暂无人物设定）'

        parts = []
        for char in characters:
            char_info = f'【{char.name}】'
            details = []
            if char.role_type:
                details.append(f'角色：{char.role_type}')
            if char.gender and char.gender != '未知':
                details.append(f'性别：{char.gender}')
            if char.age:
                details.append(f'年龄：{char.age}')
            if char.identity:
                details.append(f'身份：{char.identity}')
            if char.faction:
                details.append(f'阵营：{char.faction}')
            if char.personality:
                details.append(f'性格：{char.personality}')
            if char.backstory:
                details.append(f'背景：{char.backstory}')
            if char.motivation:
                details.append(f'动机：{char.motivation}')
            if char.abilities:
                details.append(f'能力：{char.abilities}')
            if char.development:
                details.append(f'成长：{char.development}')
            if char.relationships:
                rel_list = []
                for rel in char.relationships:
                    if isinstance(rel, dict):
                        target = rel.get('targetName', '')
                        rel_type = rel.get('relationshipType', '')
                        if target and rel_type:
                            rel_list.append(f'{target}({rel_type})')
                if rel_list:
                    details.append(f'关系：{", ".join(rel_list)}')
            if details:
                char_info += ' ' + '；'.join(details)
            parts.append(char_info)

        return '\n'.join(parts)
    except Exception as e:
        logger.error(f"格式化人物上下文失败: {e}")
        return '（暂无人物设定）'


def format_timeline_context(project):
    """格式化项目时间线为文本"""
    try:
        from apps.timeline.models import TimelineEvent
        events = TimelineEvent.objects.filter(project=project, is_active=True).order_by('start_year', 'start_month', 'end_year', 'end_month')
        if not events.exists():
            return '（暂无时间线）'

        parts = []
        for event in events:
            time_range = event.format_time_range()
            event_text = f'【{event.title}】{time_range}'
            if event.description:
                event_text += f'：{event.description}'
            parts.append(event_text)

        return '\n'.join(parts)
    except Exception as e:
        logger.error(f"格式化时间线上下文失败: {e}")
        return '（暂无时间线）'
