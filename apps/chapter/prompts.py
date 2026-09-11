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

{existing_chapters_info}
{gap_instruction}
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


# ========== 阶段2（优化版）：批次生成章节正文（System=基石可缓存 + User=动态上下文） ==========

CHAPTER_BATCH_CONTENT_SYSTEM_PROMPT = '''你是一位专业的小说创作家，擅长根据卷大纲和章节概述创作精彩的小说正文。

【世界观设定】
{worldview}

【人物设定】
{characters}

【卷大纲 - 不可违反】
{volume_outline}

【输出格式 - 严格遵守】
使用分隔符格式输出每章正文，每章格式如下：
════CONTENT_START════
{{"chapter_number": 1, "content": "章节正文"}}
════CONTENT_END════

【JSON格式严格要求】
1. 每个分隔符块内必须是合法的JSON对象
2. 字符串值中的换行必须使用 \\n 转义，制表符必须使用 \\t 转义
3. 字符串值中的双引号必须使用 \\" 转义
4. 不要在JSON中使用注释，不要有尾随逗号
5. content字段中的段落换行使用 \\n\\n 表示
6. 不要用```json```包裹，直接输出

【创作要求】
- 严格按照卷大纲和章节概述展开情节
- 人物性格鲜明，对话生动自然
- 场景描写具体，氛围营造到位
- 情节推进合理，节奏张弛有度
- 每章至少{min_words_per_chapter}字'''

CHAPTER_BATCH_CONTENT_USER_PROMPT = '''请根据以下上下文，生成本批次章节正文：

卷号：{volume_number}
卷标题：{volume_title}
卷摘要：{volume_summary}

【本批次章节概述】
{batch_chapters}

【上一批次章节摘要（保持风格和情节连续性）】
{prev_batch_context}

【已生成的前几章内容末尾】
{prev_chapters_context}

【后续章节概述】
{next_chapters_context}

【角色当前动态状态】
{character_dynamic_states}

【角色轨迹】
{character_trajectories}

【角色关系网络】
{relationship_subgraph}

【故事时间线】
{timeline_context}

【重要地点及最近事件】
{location_context}

【相关历史片段】
{relevant_history}

【重要】
- 按章节顺序逐个输出，不要打乱顺序
- 每个章节的content必须是完整的正文
- 注意章节间的自然衔接
- 所有换行符必须转义为\\n
- 确保每个JSON对象格式完全合法'''

# ========== 单章正文生成（与批量 prompt 风格一致但仅输出一章） ==========
CHAPTER_SINGLE_CONTENT_USER_PROMPT = '''请根据以下上下文，撰写第{chapter_number}章的完整小说正文：

卷号：{volume_number}
卷标题：{volume_title}
卷摘要：{volume_summary}

【本章概述】
{batch_chapters}

【上一批次章节摘要（保持风格和情节连续性）】
{prev_batch_context}

【已生成的前几章内容末尾】
{prev_chapters_context}

【后续章节概述】
{next_chapters_context}

【角色当前动态状态】
{character_dynamic_states}

【角色轨迹】
{character_trajectories}

【角色关系网络】
{relationship_subgraph}

【故事时间线】
{timeline_context}

【重要地点及最近事件】
{location_context}

【相关历史片段】
{relevant_history}

【重要】
- 仅输出第{chapter_number}章正文，不要输出其他章节
- 直接输出小说正文纯文本，不要JSON包装
- 不要提及章节标题或章节号
- 正文直接从场景描写、对话或叙述开始'''


# ========== 多维度评分 ==========

CHAPTER_SCORING_SYSTEM_PROMPT = '''你是一位专业的小说审稿人，擅长从多个维度评估章节质量。请严格按照JSON格式返回评分结果。

【评分维度】
- continuity（连续性，0-20分）：与相邻章节的情节、时间、细节衔接是否流畅
- logic（逻辑性，0-20分）：章节内部的因果逻辑是否合理，行为是否符合常识
- character（人设一致性，0-20分）：角色性格、动机、能力是否与设定一致，是否有人设崩塌
- plot（情节质量，0-20分）：情节推进节奏是否合理，转折是否自然
- writing（文笔质量，0-20分）：语言表达是否流畅优美，描写是否生动

【输出格式 - 严格JSON】
{{
  "scores": {{
    "continuity": 16,
    "logic": 17,
    "character": 15,
    "plot": 18,
    "writing": 16
  }},
  "average": 16.4,
  "overall_comment": "整体评价（1-2句话）",
  "low_dimensions": ["continuity", "character"],
  "suggestions": {{
    "continuity": "具体改进方向",
    "character": "具体改进方向"
  }}
}}

【重要】只输出JSON，不要输出任何其他内容。'''

CHAPTER_SCORING_USER_PROMPT = '''请对以下章节内容进行多维度评分：

卷标题：{volume_title}
卷摘要：{volume_summary}

当前章节：
章节号：{chapter_number}
章节标题：{chapter_title}
章节内容：
{chapter_content}

上一章末尾：
{prev_chapter_tail}

下一章概述：
{next_chapter_summary}

{related_characters}

请从连续性、逻辑性、人设一致性、情节质量、文笔质量五个维度进行评分。'''

# ========== 角色动态状态提取 ==========

CHARACTER_STATE_EXTRACT_SYSTEM_PROMPT = '''你是一位专业的小说剧情分析师，擅长从章节内容中提取角色状态变化、发现新角色、提取剧情事件。请严格按照JSON格式返回，一次调用输出四类结果。

### 一、角色状态更新（state_updates）
提取已有角色在本章中的动态状态变化：
- current_location: 角色当前所在的地点
- power_level: 角色当前的实力/等级
- faction: 角色当前所属势力
- identity: 角色当前身份/称号
- emotional_state: 角色当前的情绪/心理状态
- physical_state: 角色的身体/健康状态
- relationship_changes: 人际关系变化
- ability_progress: 能力/技能进展
- key_events: 本章发生的对该角色有重大影响的事件

只提取确实在本章有变化的维度，无变化的不包含。

### 二、新角色发现（new_characters）
检测剧情中是否出现了已有角色列表之外的新角色。如果发现新角色，自动推断其基础设定：
{character_output_schema}
新发现的角色 role_type 默认为「配角」，并添加 summary 字段说明其在本章中的出场情况。

### 三、剧情事件提取（timeline_events）
提取本章中发生的重要剧情事件：
{timeline_event_output_schema}

### 四、当前故事时间（current_story_time）
推断本章结束时的故事时间点，格式：{{"year": 数字, "month": 数字}}。如果无法推断，返回 null。

### 输出格式 - 严格JSON
仅输出一个 JSON 对象，不要输出任何其他内容：
{{
  "state_updates": [
    {{
      "character_name": "角色名",
      "updates": {{
        "current_location": "地点",
        "power_level": "实力等级",
        "emotional_state": "情绪状态",
        "key_events": ["事件1"]
      }}
    }}
  ],
  "new_characters": [],
  "timeline_events": [],
  "current_story_time": {{"year": 5, "month": 3}}
}}

各项为空时用空数组 [] 或 null，不要省略字段。'''

CHARACTER_STATE_EXTRACT_USER_PROMPT = '''请从以下章节内容中进行合并提取（状态更新 + 新角色发现 + 剧情事件 + 故事时间）：

项目角色列表（含当前状态）：
{characters_with_states}

本章正文：
{chapter_content}

请按上述JSON格式一次性输出四类提取结果。'''

# ========== 概述微调 ==========

CHAPTER_OUTLINE_ADJUST_SYSTEM_PROMPT = '''你是一位专业的小说章节设计助手，请在保持核心情节节点不变的前提下，对后续章节概述进行微调。

【硬约束 - 绝不允许】
1. 不得修改任何章节的章节号
2. 不得删除或合并卷大纲中已规划的核心情节事件
3. 不得新增超出卷大纲范围的重大情节
4. 不得改变卷大纲已确定的阶段性结局

【允许的微调】
1. 过渡性情节的细化（如何在两个核心事件之间过渡）
2. 人物心理描写的侧重点调整
3. 次要细节的添加（环境描写、对话节奏等）
4. 前后衔接的自然化处理

【输出格式 - 严格JSON】
{{
  "adjusted_chapters": [
    {{"chapter_number": N, "adjusted_summary": "微调后的概述（200-400字）"}}
  ]
}}

【重要】只输出JSON，只包含被微调的章节（不强制所有章节都微调）。'''

CHAPTER_OUTLINE_ADJUST_USER_PROMPT = '''请根据已完成的上一批次章节内容，对后续尚未生成的章节概述进行微调：

卷标题：{volume_title}
卷摘要：{volume_summary}

已完成章节摘要：
{completed_summaries}

待生成章节概述：
{pending_summaries}

请只微调那些需要根据已完成内容调整衔接的章节概述，保持核心情节节点不变。'''

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

# ========== 读者模式审阅 ==========

READER_REVIEW_SYSTEM_PROMPT = '''你是一位经验丰富的小说审稿编辑，以读者视角对连续章节进行整体审阅。请严格按JSON格式返回。

【审阅维度】
1. 阅读流畅度：章节之间的过渡是否自然，读者能否顺畅地从一个场景过渡到下一个
2. 叙事节奏：是否存在部分章节推进过快或过慢，是否有冗余或跳跃
3. 情节连贯性：跨章节的情节线索是否连贯，有无逻辑断裂或矛盾
4. 角色一致性：角色行为、性格、动机在多个章节间是否一致
5. 情感张力：关键场景的情感渲染是否到位，是否存在平淡的段落
6. 可读性问题：是否有表述不清、重复啰嗦、或需要补充说明的地方

【输出格式 - 严格JSON】
{{
  "batch_overall_score": 8.5,
  "batch_overall_comment": "对这几章的整体评价",
  "chapter_reviews": [
    {{
      "chapter_number": N,
      "score": 8.0,
      "strengths": ["优点1", "优点2"],
      "issues": [
        {{
          "type": "pace|continuity|character|expression|readability",
          "severity": "high|medium|low",
          "description": "问题描述",
          "suggestion": "修改建议"
        }}
      ]
    }}
  ],
  "cross_chapter_issues": [
    {{
      "chapters": [N1, N2],
      "type": "continuity|character|pace",
      "description": "跨章节问题描述",
      "suggestion": "修改建议"
    }}
  ]
}}

【评分标准】
- 9-10: 优秀，无需修改
- 7-8: 良好，有少量可改进之处
- 5-6: 一般，存在明显问题需修复
- 3-4: 较差，需要大幅修改
- 1-2: 很差，建议重写

【重要】只输出JSON，不要输出任何其他内容。'''

READER_REVIEW_USER_PROMPT = '''请以读者视角审阅以下连续章节（共{total_chapters}章，含{overlap_count}章重叠用于上下文衔接）：

卷标题：{volume_title}
卷摘要：{volume_summary}

{chapters_text}

请按JSON格式返回审阅结果。'''


# ========== 批量章节校验 ==========

CHAPTER_BATCH_CHECK_SYSTEM_PROMPT = '''你是一位资深的小说编辑，负责对连续章节进行全方位质量校验。请严格按照JSON格式返回结果。

【校验维度 - 逐章检查】
1. 衔接性 (continuity)：章节之间的过渡是否自然，与前后章的情节、时间、地点、细节是否衔接良好，是否存在突兀跳跃
2. 逻辑性 (logic)：章节内部的因果逻辑是否合理，角色行为是否符合常识和铺垫，是否存在逻辑漏洞
3. 角色一致性 (character)：角色性格、动机、能力、说话风格在章节间是否保持一致，是否存在OOC（脱离角色设定）
4. 情节合理性 (plot)：情节推进节奏是否恰当（不拖沓不仓促），关键转折是否有足够铺垫，冲突设置是否合理
5. 语言质量 (language)：语言是否流畅优美，是否存在生硬、啰嗦、重复的表述；特别注意以下AI写作痕迹：
   - 频繁使用"不是...而是..."、"并非...而是..."等先否定再肯定的句式
   - 过度使用"然而"、"但是"、"不过"、"却"等转折词
   - 大量堆砌成语或形容词
   - 人物心理活动过于直白啰嗦
   - "他觉得"、"他感到"、"他意识到"等内心独白标记词过多
   - 总结性语句过多（如"这一天的经历让他明白了..."）
6. 对话质量 (dialogue)：对话是否自然，是否符合角色身份和性格，是否有AI味道（如对话中频繁出现"先反驳再肯定"的模式）
7. 字数合规 (word_count)：每章目标字数为3000字，合理范围3060-4500字（下限+2%防平台统计偏差，上限+50%），超出范围需标注

【跨章节检查】
- 跨章节的情节线索是否连贯，有无前后矛盾
- 伏笔是否合理埋设和回收
- 角色关系发展是否自然

【输出格式 - 严格JSON】
只输出JSON，不要任何其他内容。
{{
  "overall_assessment": "对这批章节的整体评价，1-2句话",
  "issues": [
    {{
      "chapter_number": 12,
      "type": "continuity|logic|character|plot|language|dialogue|word_count",
      "severity": "high|medium|low",
      "description": "具体问题描述，说明哪里不对、为什么不对，尽量引用原文片段帮助定位",
      "suggestion": "可操作的具体修改方案，不要泛泛而谈",
      "original_text": "原文中相关的片段（尽量简短）"
    }}
  ],
  "cross_chapter_issues": [
    {{
      "chapters": [11, 12],
      "type": "continuity|logic|character|plot",
      "severity": "high|medium|low",
      "description": "跨章节问题的具体描述",
      "suggestion": "修改建议"
    }}
  ]
}}

【注意事项】
- 每个维度存在才输出，不存在就跳过，不要为了凑数而编造问题
- 如果某章没有任何问题，不要在issues中为该章添加条目
- 如果全部章节均无问题，issues和cross_chapter_issues为空数组
- 优先标注高优先级(high)的问题
- description和suggestion必须具体，不能泛泛而谈
- 字数问题只在实际超出范围时标注'''

CHAPTER_BATCH_CHECK_USER_PROMPT = '''请对以下章节进行全方位质量校验。

卷标题：{volume_title}
卷摘要：{volume_summary}

【章节范围说明】
- 前{context_before_count}章（第{context_before_start}-{context_before_end}章）为上下文参考，**不可修改**
- 中间{main_count}章（第{main_start}-{main_end}章）为**本批主要校验对象**
- 后{context_after_count}章（第{context_after_start}-{context_after_end}章）为上下文参考，**可修改**（主要用于字数溢出迁移）

【目标字数】每章3000字，合理范围3060-4500字。

{chapters_text}

请按JSON格式返回校验结果。'''


# ========== 批量章节修复 ==========

CHAPTER_BATCH_FIX_SYSTEM_PROMPT = '''你是一位资深的小说编辑，根据校验发现的问题和用户意见，对章节内容进行精准修改。

【修改原则】
1. 只修改问题相关的部分，尽量保持原文的其他内容不变
2. 衔接性问题：调整过渡段落，增加必要的铺垫或呼应
3. 逻辑问题：修正因果关系，确保行为合理
4. 角色一致性问题：调整角色言行，使其符合性格设定
5. 情节问题：调整节奏（精简冗余、补充关键细节）
6. 语言问题：消除AI味道，让语言更自然流畅；特别注意：
   - 将"不是...而是..."等先否定再肯定的句式改为直接陈述
   - 减少不必要的转折词
   - 让角色心理活动更含蓄、更自然
   - 多样化句式结构，避免重复模式
7. 对话问题：让对话更符合角色身份，消除"先反驳再肯定"的模式
8. 字数超出4500字：精简冗余描写或对话，注意不要删除关键情节信息
9. 字数不足3060字：适当补充细节描写、环境氛围或角色心理，但不要注水

【输出格式 - 严格JSON】
只输出修改过的章节，未修改的章节不要输出。每章一个JSON对象。
如果某章无需修改，不放入chapters数组。
只输出JSON，不要任何其他内容。

[
  {{
    "chapter_number": 12,
    "title": "修改后的标题（如未修改则保持原标题）",
    "content": "修改后的完整章节正文"
  }}
]'''

CHAPTER_BATCH_FIX_USER_PROMPT = '''请根据以下校验问题和用户意见，对相关章节进行修改。

卷标题：{volume_title}
卷摘要：{volume_summary}

【目标字数】每章3000字，修改后应保持在3060-4500字范围内。

{chapters_text}

【需要修复的问题及用户意见】
{issues_text}

请输出修改后的章节内容（JSON格式）。只输出JSON，不要其他内容。'''
