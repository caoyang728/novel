"""
大纲构建提示词

设计要点：
1. 大纲以 Markdown 整体存储，通过 patch_list 增量补丁更新
2. 按题材（genre）提供不同的构建指引（侧重模块、关键要素）
3. 输出协议：JSON，包含 patch_list、question、options、characters
4. 结构与 worldview/prompts.py 对齐

文件职责：
- 本文件存放提示词模板
- 题材相关的提示词数据存放在 prompts_outline_genre.py
- 题材指引/中文名查询函数定义在 project.utils
"""

from .prompts_outline_genre import OUTLINE_GENRE_SYSTEM_PROMPT, OUTLINE_GENRE_PROMPTS_DICT  # noqa: F401

# ============ 上下文模板 ============
# 仅包含项目上下文部分，genre_guide 由 views.py 拼接在前面
# 格式化时传入：worldview_context, characters_context, current_outline, novel_name
OUTLINE_CONTEXT_TEMPLATE = """\

# 当前项目上下文

## 已有世界观设定
{worldview_context}

## 已有人物清单
{characters_context}

## 当前大纲内容
{current_outline}

## 基本规则
- 大纲的 H1 标题（首行 `# xxx`）使用「{novel_name} 大纲」格式，不要写其他通用标题
- 已有世界观设定为固定基底，大纲全程100%贴合，不得与世界观冲突
- 已有人物清单中的角色，自动映射到大纲对应位置"""


# ============ 构建/修改大纲的用户提示词 ============
OUTLINE_BUILD_USER_PROMPT = """\
{user_input}"""


# ============ JSON 修复提示词（解析失败时由修复 LLM 使用） ============
OUTLINE_JSON_REPAIR_PROMPT = """\
你是 JSON 修复专家。下面是 AI 生成大纲补丁时输出的内容，但其中的 JSON 存在语法错误，无法被 Python json.loads 解析。

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
- **只修语法，不改业务内容**：严禁改写、补写、虚构任何大纲内容、old_snippet、new_snippet、question、options、characters 的内容
- patch_list 中每个元素必须包含 old_snippet 和 new_snippet 两个字符串字段
- question 为字符串，options 和 characters 为数组
- 宁可返回 truncated/unrepairable，也不要编造内容

## 输出示例

语法可修复（多余的逗号）时，返回修复后的纯 JSON：
{{"patch_list": [{{"old_snippet": "故事背景：近未来都市\\n核心规则", "new_snippet": "故事背景：近未来都市\\n核心规则：系统发布任务"}}], "question": "已补充核心规则。主角的金手指是什么类型？", "options": ["系统流", "老爷爷流", "血脉觉醒"], "characters": []}}

无法修复（严重混乱）时，返回：
{{"status": "unrepairable"}}

被截断（内容在半句话中断）时，返回：
{{"status": "truncated"}}"""
