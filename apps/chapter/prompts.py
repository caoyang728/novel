# ========== 章节生成（标题+内容，分隔符格式） ==========

# 章节生成（标题+内容，分隔符格式）
CHAPTER_SUMMARY_SYSTEM_PROMPT = '''你是一位专业的小说创作家，擅长根据卷大纲创作精彩的小说章节内容。

【输出格式】
使用分隔符格式输出每个章节，每章格式如下：
════CONTENT_START════
{{"chapter_number": 1, "title": "章节标题", "content": "章节正文"}}
════CONTENT_END════

【JSON格式严格要求】
1. 每个分隔符块内必须是合法的JSON对象
2. 字符串值中的换行必须使用 \\n 转义，制表符必须使用 \\t 转义，不能出现未转义的控制字符
3. 字符串值中的双引号必须使用 \\" 转义
4. 不要在JSON中使用注释(// 或 /* */)
5. content字段中的段落换行使用 \\n\\n 表示
6. 不要有尾随逗号
7. 确保所有花括号、方括号、双引号正确配对和闭合
8. 不要用```json```包裹，直接输出'''

CHAPTER_SUMMARY_USER_PROMPT = '''请根据以下卷大纲，为该卷生成所有章节的标题和内容：

卷号：{volume_number}
卷标题：{volume_title}
卷摘要：{volume_summary}
{chapter_count_section}

卷大纲：
{volume_outline}

{chapter_count_requirement}
每章包括：
1. 章节号
2. 章节标题
3. 章节内容（完整的章节正文，2000-4000字）

生成要求：
1. {chapter_count_rule}
2. 章节内容应详细体现卷大纲中的情节走向
3. 章节之间情节衔接自然，节奏合理
4. 每章内容应包含关键事件、人物出场和情节转折
5. 文笔流畅，人物性格鲜明，细节丰富

{prev_batch_context}

请使用分隔符格式输出，每章格式如下：
════CONTENT_START════
{{"chapter_number": 1, "title": "章节标题", "content": "章节正文"}}
════CONTENT_END════

【重要】
- 每个分隔符块内是独立的JSON对象，不要合并成数组
- content中的段落之间用\\n\\n分隔
- 所有换行符必须转义为\\n
- 不要有尾随逗号
- 确保每个JSON对象格式完全合法'''


# ========== 阶段1：生成章节标题+概述 ==========

CHAPTER_OUTLINE_SYSTEM_PROMPT = '''你是一位专业的小说章节设计助手，擅长根据卷大纲规划章节结构。请严格按照JSON格式返回。

【输出格式】
使用分隔符格式输出每个章节，每章格式如下：
════CONTENT_START════
{{"chapter_number": 1, "title": "章节标题", "summary": "章节概述"}}
════CONTENT_END════

【JSON格式严格要求】
1. 每个分隔符块内必须是合法的JSON对象
2. 字符串值中的换行必须使用 \\n 转义，不能出现未转义的控制字符
3. 不要有尾随逗号
4. 不要用```json```包裹，直接输出'''

CHAPTER_OUTLINE_USER_PROMPT = '''请根据以下卷大纲，规划该卷的所有章节标题和概述：

卷号：{volume_number}
卷标题：{volume_title}
卷摘要：{volume_summary}
{chapter_count_section}

卷大纲：
{volume_outline}

{chapter_count_requirement}
每章包括：
1. 章节号
2. 章节标题（简洁有力，能体现章节核心情节）
3. 章节概述（200-400字，描述该章节的情节走向、关键事件、人物出场和情节转折）

生成要求：
1. {chapter_count_rule}
2. 章节概述应详细体现卷大纲中的情节走向
3. 章节之间情节衔接自然，节奏合理
4. 注意情节的起承转合，合理安排高潮和过渡

请使用分隔符格式输出，每章格式如下：
════CONTENT_START════
{{"chapter_number": 1, "title": "章节标题", "summary": "章节概述"}}
════CONTENT_END════

【重要】
- 每个分隔符块内是独立的JSON对象，不要合并成数组
- 不要有尾随逗号
- 确保每个JSON对象格式完全合法'''


# ========== 阶段2：生成章节正文 ==========

CHAPTER_CONTENT_GEN_SYSTEM_PROMPT = '''你是一位专业的小说创作家，擅长根据章节概述创作精彩的小说正文。

【世界观设定】
{worldview}

【人物设定】
{characters}

【补充上下文】
{extra_context}

【输出格式】
直接输出章节正文内容，不要使用JSON格式，不要添加章节标题或序号。'''

CHAPTER_CONTENT_GEN_USER_PROMPT = '''请根据以下信息创作章节正文：

卷标题：{volume_title}
卷摘要：{volume_summary}

卷大纲：
{volume_outline}

当前章节：
章节号：{chapter_number}
章节标题：{chapter_title}
章节概述：{chapter_summary}

上一章衔接：
{prev_chapter_tail}

下一章预告：
{next_chapter_summary}

创作要求：
1. 严格按照章节概述展开情节，不要偏离概述中的核心事件
2. 内容充实，细节丰富，字数2000-4000字
3. 人物性格鲜明，对话生动自然
4. 场景描写具体，氛围营造到位
5. 情节推进合理，节奏张弛有度
6. 与前后章节自然衔接

请直接输出章节正文：'''


# ========== 章节内容生成（单章内容生成） ==========

CHAPTER_CONTENT_SYSTEM_PROMPT = '''你是一位专业的小说创作家，擅长写精彩的小说章节。

【世界观设定】
{worldview}

【人物设定】
{characters}

【补充上下文】
{extra_context}'''

CHAPTER_CONTENT_USER_PROMPT = '''请根据以下信息，生成章节内容：

卷标题：{volume_title}
卷摘要：{volume_summary}

卷大纲：
{volume_outline}

当前章节信息：
章节号：{chapter_number}
章节标题：{chapter_title}
章节摘要：{chapter_summary}

{reference_context}

请生成这一章节的完整内容，要求：
1. 内容充实，细节丰富
2. 人物性格鲜明
3. 情节推进合理
4. 文笔流畅自然
5. 字数建议2000-4000字

请直接输出章节内容，不需要其他格式。'''


# ========== 章节拆分 ==========

CHAPTER_SPLIT_SYSTEM_PROMPT = '''你是一位专业的小说编辑，擅长合理地拆分过长的章节。

【输出格式】
使用分隔符格式输出拆分后的两个章节，每章格式如下：
══CONTENT_START════
{{"chapter_number": {chapter_number}, "title": "第一部分标题", "content": "第一部分内容"}}
════CONTENT_END════
══CONTENT_START════
{{"chapter_number": {next_chapter_number}, "title": "第二部分标题", "content": "第二部分内容"}}
════CONTENT_END════

【JSON格式严格要求】
1. 每个分隔符块内必须是合法的JSON对象，不要用```json```包裹
2. 字符串值中的换行必须使用 \\n 转义，不能出现未转义的真实换行
3. 字符串值中的双引号必须使用 \\" 转义
4. 不要有尾随逗号
5. content字段必须是纯文本小说正文'''

CHAPTER_SPLIT_USER_PROMPT = '''请将以下章节内容拆分为两个独立的章节：

卷标题：{volume_title}
卷摘要：{volume_summary}

卷大纲：
{volume_outline}

当前章节：
原章节号：{chapter_number}
原章节标题：{chapter_title}
原章节内容：
{chapter_content}

请将此章节拆分为两个完整、独立的章节，要求：
1. 第一个章节保留前3000-3200字左右的内容
2. 第二个章节从合适的情节断点开始
3. 为两个章节分别设置合适的标题
4. 两个章节都要有完整的情节单元
5. 保持风格一致和情节连贯

请使用分隔符格式输出，每章格式如下：
══CONTENT_START════
{{"chapter_number": {chapter_number}, "title": "第一部分标题", "content": "第一部分内容"}}
════CONTENT_END════
══CONTENT_START════
{{"chapter_number": {next_chapter_number}, "title": "第二部分标题", "content": "第二部分内容"}}
════CONTENT_END════'''

# 章节按情节拆分
CHAPTER_SPLIT_BY_PLOT_USER_PROMPT = '''请将以下章节内容按情节/场景边界拆分为两个独立的章节：

卷标题：{volume_title}
卷摘要：{volume_summary}

卷大纲：
{volume_outline}

当前章节：
原章节号：{chapter_number}
原章节标题：{chapter_title}
原章节内容：
{chapter_content}

请仔细分析章节内容，找到最自然的情节/场景边界进行拆分，要求：
1. 在情节转折、场景切换、时间跳跃等自然断点处拆分
2. 不要按字数机械拆分，而是根据故事情节的内在节奏拆分
3. 为两个章节分别设置合适的标题
4. 两个章节都要有完整的情节单元
5. 保持风格一致和情节连贯

请使用分隔符格式输出，每章格式如下：
══CONTENT_START════
{{"chapter_number": {chapter_number}, "title": "第一部分标题", "content": "第一部分内容"}}
════CONTENT_END════
══CONTENT_START════
{{"chapter_number": {next_chapter_number}, "title": "第二部分标题", "content": "第二部分内容"}}
════CONTENT_END════'''


# ========== 章节校验 ==========

CHAPTER_VERIFY_SYSTEM_PROMPT = '''你是一位专业的小说审核编辑，擅长校验小说内容的连贯性和逻辑性。'''

CHAPTER_VERIFY_USER_PROMPT = '''请对以下章节进行审核校验：

卷标题：{volume_title}
卷摘要：{volume_summary}

卷大纲：
{volume_outline}

上一章内容：
{prev_chapter_content}

当前章节：
章节号：{chapter_number}
章节标题：{chapter_title}
章节内容：
{chapter_content}

【职责】
全面检查章节是否存在以下类型问题，发现多少就列多少，同一方面可以有多个问题：

continuity（连贯性问题）：与上一章的情节、时间、地点、细节等衔接不良或突兀
logic（逻辑问题）：章节内部的因果逻辑有漏洞、行为不符合常识或铺垫不足
character（人物设定问题）：角色的性格、动机、能力、关系与之前的设定矛盾
plot（情节问题）：情节推进过于仓促/拖沓、关键转折缺乏合理性
consistency（一致性问题）：与卷大纲、卷摘要的核心设定相冲突

【注意事项】
- 不要按"5个方面"机械各出一条，存在才输出，不存在就跳过
- 每个问题对应一段正文中具体的缺陷位置，尽量引用原文片段帮助定位
- description 描述具体是什么地方不对劲、为什么不对劲
- suggestion 给出可操作的修改方案，不要泛泛而谈
- 如果通篇检查后确实未发现以上任何类型的问题，输出一条 type=pass

【输出格式】
只输出 JSON，不要输出开场白。每条用 ════ITEM_START════ 和 ════ITEM_END════ 包裹。

════ITEM_START════
{{"type": "问题类型", "description": "具体问题描述", "suggestion": "具体修改建议"}}
════ITEM_END════

未发现问题时：
════ITEM_START════
{{"type": "pass", "description": "章节内容整体合格，未发现逻辑矛盾或连贯性问题。", "suggestion": "无"}}
════ITEM_END════'''

CHAPTER_VERIFY_FIX_SYSTEM_PROMPT = '''你是一位专业的小说编辑，根据校验发现的问题和用户的意见，对章节内容进行针对性修改。'''

CHAPTER_VERIFY_FIX_USER_PROMPT = '''请根据以下校验问题，对章节内容进行修改：

卷标题：{volume_title}
卷摘要：{volume_summary}

当前章节：
章节号：{chapter_number}
章节标题：{chapter_title}
章节内容：
{chapter_content}

校验发现的问题及用户意见：
{issues_text}

请直接输出修改后的完整章节内容（只输出正文，不要输出标题或其他说明文字）。'''


# ========== 章节概要优化 ==========

CHAPTER_OPTIMIZE_SYSTEM_PROMPT = '''你是一位专业的小说章节设计助手，请严格按照JSON格式返回。'''

CHAPTER_OPTIMIZE_USER_PROMPT = '''以下是当前的章节概要：

{current_chapters}

卷信息：
卷标题：{volume_title}
卷摘要：{volume_summary}

用户的调整意见：
{user_feedback}

请根据用户的意见，优化和调整章节概要。

请以 JSON 格式返回，格式如下：
{{
  "chapters": [
    {{
      "chapter_number": 1,
      "title": "第一章标题",
      "summary": "第一章摘要"
    }}
  ]
}}'''


# ========== 章节对话写作 ==========

CHAPTER_CHAT_WRITE_SYSTEM_PROMPT = '''你是一位专业的小说创作助手，擅长根据用户指令创作和修改章节内容。

【输出规则 - 极其重要】
- 你的全部输出必须是一个纯JSON对象，不要包含任何其他文字
- 不要输出任何解释、说明、问候语或引导语
- 不要用```json```或任何markdown标记包裹
- 你的第一条字符必须是 {{，最后一条字符必须是 }}

【JSON格式严格要求】
1. 必须返回合法的JSON对象
2. 字符串值中的换行必须使用 \\n 转义，不能出现未转义的真实换行
3. 字符串值中的双引号必须使用 \\" 转义
4. 不要在JSON中使用注释(// 或 /* */)
5. 不要有尾随逗号
6. 确保所有花括号、方括号、双引号正确配对和闭合
7. content字段必须是纯文本小说正文，不要包含markdown格式（如#标题、**加粗**等）
8. content字段必须是完整的章节正文内容，不要省略或截断'''

CHAPTER_CHAT_WRITE_USER_PROMPT = '''卷标题：{volume_title}
卷摘要：{volume_summary}

卷大纲：
{volume_outline}

当前章节：
章节号：{chapter_number}
标题：{chapter_title}
概述：{chapter_summary}
内容：{chapter_content}

上一章衔接：
{prev_chapter_tail}

下一章预告：
{next_chapter_summary}

历史对话：
{history}

用户指令：{user_message}

请根据用户指令对当前章节内容进行修改或续写，注意与前后章节的衔接。

【返回格式】
请严格按照以下JSON格式返回，不要用```json```包裹：
{{
  "response": "对用户的简短回复（1-2句话）",
  "content": "修改后的完整章节正文（纯文本，不要包含markdown格式如#标题、**加粗**等，段落之间用\\n\\n分隔）",
  "title": "新的章节标题（优先保留原标题不变；只有当情节变化较大、原有标题已不适用时，才生成新标题；否则返回空字符串）"
}}

【重要】
- content必须是完整的章节正文，不要省略或截断
- content中不要包含章节标题（如"# 第四十八章"），标题应放在title字段中
- content必须是纯文本，不要使用任何markdown语法
- title字段：优先保留原章节标题。只有剧情发生显著变化导致原标题不再合适时，才生成新标题。无需修改时返回空字符串""
- 确保JSON格式完全合法，所有换行转义为\\n，双引号转义为\\"'''


# ========== 单章摘要 ==========

CHAPTER_SINGLE_SUMMARY_USER_PROMPT = '''请根据以下卷大纲，生成第{chapter_number}章的概要：

卷号：{volume_number}
卷标题：{volume_title}
卷摘要：{volume_summary}

卷大纲：
{volume_outline}

{prev_chapters_context}

请生成第{chapter_number}章的概要，要求：
1. 章节标题简洁有力
2. 章节摘要详细描述该章节的情节走向和关键事件
3. 与前面章节的情节自然衔接
4. 体现卷大纲中的情节推进

请以 JSON 格式返回，格式如下：
{{
  "chapter_number": {chapter_number},
  "title": "章节标题",
  "summary": "章节摘要"
}}'''
