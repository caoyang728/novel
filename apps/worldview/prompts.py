"""
世界观文档提示词

设计要点：
1. 世界观以 Markdown 整体存储
2. LLM 输出 patch_list（增量补丁），后端应用补丁后返回完整文档
3. 按题材（genre）提供不同的章节骨架与构建指引
4. 输出协议：JSON，包含 patch_list、reply、options

文件职责：
- 本文件存放提示词模板
- 题材相关的提示词数据存放在 prompts_worldview_genre.py
- 题材元数据（GENRE_CHOICES）定义在 project.models
- 题材指引/中文名查询函数定义在 project.utils
"""

from .prompts_worldview_genre import WORLDVIEW_GENRE_SYSTEM_PROMPT, WORLDVIEW_GENRE_PROMPTS_DICT  # noqa: F401


# ============ 上下文模板 ============
# genre_guide 由 get_genre_guide(genre, WORLDVIEW_GENRE_PROMPTS_DICT) 获取后
# 在 views.py 中与本模板格式化结果拼接，不在模板内作为变量
# 格式化时传入：current_doc, novel_name
WORLDVIEW_CONTEXT_TEMPLATE = """\

# 当前项目上下文

## 当前世界观文档（Markdown）
{current_doc}

## 基本规则
- 世界观文档的 H1 标题（首行 `# xxx`）使用「{novel_name} 世界观」格式，不要写其他通用标题"""


# ============ 构建/修改文档的用户提示词 ============
# 格式化时传入：user_input
WORLDVIEW_BUILD_USER_PROMPT = """\
请根据以下用户指令，输出更新世界观文档的 JSON 补丁：

{user_input}"""


# ============ JSON 修复提示词（解析失败时由修复 LLM 使用） ============
WORLDVIEW_JSON_REPAIR_PROMPT = """\
你是 JSON 修复专家。下面是 AI 生成世界观补丁时输出的内容，但其中的 JSON 存在语法错误，无法被 Python json.loads 解析。

解析错误信息：
{error}

待修复内容：
---
{raw_content}
---

请按以下规则处理：

1. 如果内容是**被截断**的（JSON 的字符串/数组/对象没有正常闭合，内容在半句话或字段中途结束），**禁止猜测缺失内容**，直接只输出一行：
{{"status": "truncated"}}

2. 如果存在 JSON 但无法在**不虚构任何业务内容**的前提下修复（内容严重混乱、包含无法判断归属的残缺片段），直接只输出一行：
{{"status": "unrepairable"}}

3. 如果只是语法问题（字符串中未转义的引号、错误/多余的逗号、Markdown 代码块包裹、JSON 外混入解释文字等），修复为合法 JSON 后**只输出修复后的纯 JSON**（以 {{"patch_list": 开头），不要输出任何解释或 Markdown 标记。

修复时的硬性要求：
- **只修语法，不改业务内容**：严禁改写、补写、虚构任何世界观设定文字、old_snippet、new_snippet、question、options 的内容
- patch_list 中每个元素必须包含 old_snippet 和 new_snippet 两个字符串字段
- question 为字符串，options 为字符串数组
- 宁可返回 truncated/unrepairable，也不要编造内容

## 输出示例

语法可修复（多余的逗号）时，返回修复后的纯 JSON：
{{"patch_list": [{{"old_snippet": "灵气来源：天地灵脉\\n- 灵气等级", "new_snippet": "灵气来源：天地灵脉\\n- 灵气等级：凡灵→玄灵→天灵"}}], "question": "已补充灵气等级体系。修炼境界如何划分？", "options": ["练气→筑基→金丹", "自行设计"]}}

无法修复（严重混乱）时，返回：
{{"status": "unrepairable"}}

被截断（内容在半句话中断）时，返回：
{{"status": "truncated"}}"""


# ============ 阵营索引提取提示词 ============
WORLDVIEW_FACTION_EXTRACT_PROMPT = """\
从下面的世界观 Markdown 文档中提取所有阵营/势力信息，生成结构化索引，用于角色表单的阵营下拉选择。

提取规则：
1. 提取所有势力/阵营/门派/国家/组织的名称
2. 如果某阵营下有子派系（Markdown 中更深一级标题，如"蜀国"下的"主战派"、"投降派"），放入 subs 数组
3. 只提取名称，不要描述
4. 名称使用文档中的原始名称

严格输出 JSON 数组（不要输出其他内容）：
[
  {{"name": "蜀国", "subs": ["主战派", "投降派", "南中派"]}},
  {{"name": "曹魏", "subs": ["主战派", "保守派"]}},
  {{"name": "东吴", "subs": []}}
]

# 世界观文档
{doc_content}"""
