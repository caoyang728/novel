# 自动写小说 Agent 系统 —— 完整设计文档

> 版本：V5.1（适配现有 Django + DRF 技术栈）

## 1. 项目简介

本项目旨在构建一个 **输入一句话描述，自动生成完整小说的 Agent 系统**。
系统基于多 LLM 协同，实现从世界观、大纲、人物、分篇到逐章生成、审核、修复、状态管理的全流程自动化。关键节点引入人工确认，确保创作方向符合预期，同时通过向量检索增强长程记忆，减少前后矛盾。

---

## 2. 核心目标与需求

| 需求 | 说明 |
|------|------|
| 输入 | 用户提供一段创意描述（可包含主角、风格、篇幅等） |
| 输出 | 完整小说（中篇或长篇），含分卷/篇、章节正文 |
| 人工干预 | 仅在世界观、大纲、每篇完成后各确认一次，其余全自动 |
| 多主角 | 自动识别单/多主角，支持多视角叙事 |
| 风格模仿 | 支持用户上传参考文本，或自动生成风格指南 |
| 一致性 | 通过结构化故事圣经 + 向量检索历史章节，减少设定冲突 |
| 容错与降级 | 审核失败自动重修，超过最大迭代次数则标记为需人工处理 |
| 成本优化 | 支持定时任务，在夜间低峰时段执行生成，节约 token 费用 |

---

## 3. 系统总体架构

```
用户输入描述
      │
      ▼
┌─────────────────────┐
│   总控 Agent        │  ← 状态机、人工确认调度、任务编排
│  (LangGraph)        │
└─────────┬───────────┘
          │ 调用各子 Agent
          ▼
┌──────────────────────────────────────────────────────────┐
│                     核心工作流                            │
│  ① 写作简报生成                                          │
│  ② 世界观生成 → 审核 → ⏸️人工确认①                       │
│  ③ 大纲生成 → 审核 → ⏸️人工确认②                         │
│  ④ 人物生成 → 审核                                       │
│  ⑤ 篇规划生成                                            │
│  ⑥ 按篇生成：                                            │
│       - 章节概要生成                                      │
│       - 逐章生成、审核、修复                              │
│       - 篇级审核 → ⏸️人工确认③                            │
│  ⑦ 全书终审                                              │
└──────────────────────────────────────────────────────────┘
          │
          ▼
     输出小说
```

### 3.1 人工确认节点

| 节点 | 确认内容 | 用户操作 |
|------|----------|----------|
| 世界观生成后 | 展示世界观设定书 | 点击"确认继续"或"重新生成" |
| 大纲生成后 | 展示完整大纲 | 点击"确认继续"或"重新生成" |
| 每篇章节完成后 | 展示该篇所有章节标题、摘要、字数 | 点击"继续下一篇"或"重新生成本篇" |

未点击确认时，系统挂起，不消耗额外资源。

---

## 4. 核心模块设计

### 4.1 总控 Agent（Orchestrator）

- **技术**：LangGraph 状态机
- **职责**：
  - 管理全局状态（`current_state`：`INIT`、`WAITING_WORLDVIEW`、`WAITING_OUTLINE`、`WRITING_PART`、`WAITING_PART` 等）
  - 调用各子 Agent，处理审核失败重试、降级策略
  - 处理人工确认中断与恢复
  - 记录预算与迭代次数
  - 定时任务调度（配合 Celery ETA）
- **关键机制**：
  - LangGraph `interrupt` 实现暂停等待人工确认
  - 检查点（checkpoint）保存流程状态，支持故障恢复
  - 节点内判断时间窗口，不在窗口则创建 Celery ETA 任务并挂起

### 4.2 生成类 Agent

| Agent | 输入 | 输出 | 场景标识 |
|-------|------|------|----------|
| 世界观生成 | 用户描述、风格指南 | 世界观设定书 | `worldview_build` |
| 大纲生成 | 世界观、人物雏形 | 故事大纲 | `outline_optimize` |
| 人物生成 | 世界观、大纲 | 人物清单（含弧光） | `character_design` |
| 篇规划生成 | 大纲、人物 | 每篇概要、章节数分配 | `volume_batch_generate` |
| 章节概要生成 | 篇概要、故事圣经、人物 | 每章概要 | `chapter_batch_generate` |
| 章节正文生成 | 上下文组装包 | 章节正文 | `chapter_batch_content` |
| 风格指南生成 | 用户描述、参考样本 | 风格指南 | `default` |

- **模型配置**：使用项目已有的 `agent/llm_scenes.py` 场景配置系统，通过 `get_llm(user, scene)` 获取 LLM 实例。

### 4.3 审核类 Agent（通用审核框架）

- **设计**：一个通用审核器，通过注入不同 `审核配置` 实现差异化审核。
- **审核配置**包含：
  - `审核对象`：世界观 / 大纲 / 人物 / 篇 / 章节概要 / 正文
  - `参考材料`：用户描述、世界观、大纲、人物、风格指南等
  - `审核维度`：评分项与权重（如逻辑一致性、节奏、吸引力等）
  - `通过阈值`：总分下限
  - `最大迭代次数`：审核-修复循环上限（默认 3 次）
  - `审核模型列表`：用户在 LLM 配置中选择的多个模型（至少 2 个）
- **多模型打分**：使用用户配置的多个 LLM 模型并行打分，取平均分或最低分，降低单一模型偏差。
- **输出格式**：统一 JSON，包含各维度分数、总体分、问题列表（严重等级、描述、修改建议）。
- **模型配置**：使用 `chapter_scoring` 场景（温度 0.3），通过 `call_llm_with_retry()` 调用。

**示例：章节正文审核配置（一致性方向）**

```yaml
审核对象: 章节正文
参考材料:
  - 故事圣经摘要
  - 当前章节概要
  - 前5章摘要
  - 前一章内容
  - 向量检索到的相关历史片段
审核维度:
  设定一致性: 权重 25%
  人物一致性: 权重 25%
  时间线逻辑: 权重 15%
  伏笔处理: 权重 15%
  文风统一性: 权重 20%
通过阈值: 总分 >= 85 且无 A 级错误
```

### 4.4 修复 Agent

- **职责**：根据审核意见进行局部修改或重写。
- **模型配置**：使用 `chapter_optimize` 场景（温度 0.5），通过 `call_llm_with_retry()` 调用。
- **修复策略**：
  - A级设定冲突 → 精准修改对应段落
  - B级人物崩坏 → 重写相关段落
  - C级节奏问题 → 调整章节结构或返回章节概要修改
  - D级结构问题 → 回溯至篇规划或大纲层
  - E级文笔问题 → 润色
  - F级体验问题 → 增强钩子/冲突

### 4.5 状态更新 Agent（故事圣经维护）

- 每章生成完成后，自动提取状态变化并更新 `books.global_bible`（JSONB 字段）。
- 更新内容：人物状态、关系、时间线、物品、伏笔、世界状态等。
- 实现：使用 `character_state_extract` 场景（温度 0.3），通过 `call_llm_with_retry()` 调用，输出 JSON 补丁。

### 4.6 上下文组装器（Context Assembler）

**目标**：为每一章生成提供最相关、最精简的上下文。

**组装内容**：

| 输入项 | 说明 |
|--------|------|
| 故事圣经摘要 | 当前关键状态（人物、地点、时间） |
| 前情提要 | 前5章摘要（每章100~200字） |
| 前一章全文 | 保证直接衔接 |
| 当前章节概要 | 本章要写什么 |
| 相关人物状态 | 本章出场人物最新状态 |
| 相关伏笔提示 | 本章需要埋设/回收的伏笔 |
| **向量检索相关历史片段** | 从历史章节中检索的语义相似段落（长程记忆） |
| 风格指南 | 文风要求 |

---

## 5. 向量检索模块（Embedding + pgvector）

### 5.1 目的

解决长篇小说"遗忘"问题：生成第 N 章时，通过语义检索召回久远但相关的情节、对话、设定，避免隐性冲突。

### 5.2 技术选型

- **存储**：PostgreSQL + `pgvector` 扩展（复用现有 `apps/knowledge` 应用）
- **嵌入模型**：SiliconFlow `Qwen/Qwen3-Embedding-8B`（通过 `UserEmbeddingConfig` 配置）
- **重排序模型**：SiliconFlow `BAAI/bge-reranker-v2-m3`（通过 `UserEmbeddingConfig` 配置）
- **向量维度**：2048
- **分块策略**：每 500~1000 字一个 chunk，记录所属章节和顺序

### 5.3 表结构

```sql
-- 章节块表
CREATE TABLE chapter_chunks (
    id UUID PRIMARY KEY,
    chapter_id UUID REFERENCES chapters(id),
    chunk_index INT,
    content TEXT,
    embedding vector(2048)
);

-- 索引（HNSW）
CREATE INDEX ON chapter_chunks USING hnsw (embedding vector_cosine_ops);
```

### 5.4 检索流程

1. 在生成第 N 章前，构建查询文本（可由本章概要 + 出场人物 + 关键词组成）。
2. 生成查询向量。
3. 执行余弦相似度搜索，返回 top-k（如 5 个）chunk。
4. 过滤低相似度结果（阈值可配置）。
5. 将召回片段拼入上下文组装器。

### 5.5 与故事圣经的关系

- 故事圣经：**精确状态**，如"主角当前是否受伤"
- 向量检索：**模糊记忆**，如"主角曾对某人说过一句重要的话"
两者互补，共同保障一致性。

---

## 6. 数据模型设计（PostgreSQL）

### 6.1 核心表

```sql
-- 书籍主表
CREATE TABLE books (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_prompt TEXT NOT NULL,
    style_guide JSONB,           -- 文风、视角、禁忌等
    global_bible JSONB,          -- 故事圣经（动态状态）
    current_state TEXT DEFAULT 'INIT',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 篇表
CREATE TABLE parts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID REFERENCES books(id),
    part_no INT,
    summary TEXT,
    target_chapters INT,
    status TEXT DEFAULT 'PLANNED'  -- PLANNED, WRITING, WAITING_CONFIRM, CONFIRMED
);

-- 章节表
CREATE TABLE chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_id UUID REFERENCES parts(id),
    chapter_no INT,
    title TEXT,
    summary TEXT,
    content TEXT,
    review_scores JSONB,         -- 审核记录
    status TEXT DEFAULT 'DRAFT', -- DRAFT, PASSED, FIXED
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 状态变化日志（审计/回溯）
CREATE TABLE state_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID REFERENCES chapters(id),
    change_type TEXT,            -- CHARACTER, TIMELINE, ITEM, FORESHADOWING
    delta JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 向量块表
CREATE TABLE chapter_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID REFERENCES chapters(id),
    chunk_index INT,
    content TEXT,
    embedding vector(2048)
);
```

### 6.2 `global_bible` 示例

```json
{
  "timeline": { "current_day": 15, "current_chapter": 12 },
  "protagonists": ["C001"],
  "characters": {
    "C001": {
      "name": "林逸",
      "status": "中毒，寻找解药",
      "location": "黑风岭",
      "relationships": { "C002": "亦敌亦友" },
      "arc_progress": "第二幕"
    }
  },
  "items": { "I001": { "name": "上古玉牌", "owner": "C001", "status": "未激活" } },
  "foreshadowing": [
    { "id": "F01", "desc": "主角身世之谜", "planted_at": "Ch3", "status": "pending" }
  ],
  "world_state": { "青云宗": "覆灭", "魔教": "势力扩张" }
}
```

---

## 7. 技术栈选型

### 7.1 后端

| 组件 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.11+ | AI 生态完善 |
| Web 框架 | Django 5.2 + DRF | 复用现有项目架构 |
| 任务队列 | Celery + Redis | 异步执行耗时任务，支持定时调度（Result Backend 使用 Django DB） |
| 工作流 | LangGraph | 有状态多 Agent 编排，支持循环、暂停 |
| LLM 调用 | LangChain + ChatOpenAI | 复用 `agent/llm.py` 封装，支持流式/非流式调用、思考模式 |
| Embedding | SiliconFlow Qwen/Qwen3-Embedding-8B | 通过 `UserEmbeddingConfig` 配置 |
| Rerank | SiliconFlow BAAI/bge-reranker-v2-m3 | 通过 `UserEmbeddingConfig` 配置 |
| 数据库 | PostgreSQL 16 + pgvector | 结构化数据 + JSONB + 向量检索 |
| 缓存/消息 | Redis | Celery broker、进度推送、分布式锁、限流 |
| 追踪调试 | TokenUsageLog | 复用现有 Token 使用量记录系统 |

### 7.2 前端（Vue）

| 组件 | 技术 | 说明 |
|------|------|------|
| 框架 | Vue 3 + Vite | 复用现有前端项目 |
| 状态管理 | Pinia | 管理书籍状态、确认流程 |
| UI 库 | Element Plus | 复用现有组件库，提供确认按钮、卡片、进度条等 |
| 路由 | Vue Router | 页面导航（新建书、详情、确认页） |
| HTTP 客户端 | 复用 `api/request.js` | 统一处理认证、错误和重连逻辑 |
| 实时通信 | SSE（Server-Sent Events） | 复用现有 `api/sse.js` 流式响应封装 |

**前端页面设计：**

- **首页**：输入描述，创建新书
- **书籍详情页**：展示当前阶段，世界观、大纲、篇列表等
- **确认对话框**：弹窗展示待确认内容（世界观/大纲/篇），提供"确认继续"和"重新生成"按钮
- **章节阅读页**：查看已生成章节正文

### 7.3 部署

- **容器化**：Docker Compose（开发/单机）或 Kubernetes（生产）
- **服务拆分**：
  - `api`：Django + DRF 服务（Gunicorn + Uvicorn）
  - `worker`：Celery workers（可多个，按功能拆分）
  - `beat`：Celery Beat 定时调度器
  - `redis`：缓存/队列
  - `postgres`：数据库（含 pgvector）
  - `frontend`：Vue 构建后的静态文件，Nginx 托管

---

## 8. 工作流程与人工确认状态机

### 8.1 状态机定义

```python
class BookState(Enum):
    INIT = "INIT"
    WAITING_WORLDVIEW = "WAITING_WORLDVIEW"
    WAITING_OUTLINE = "WAITING_OUTLINE"
    WRITING_PART = "WRITING_PART"
    WAITING_PART = "WAITING_PART"
    COMPLETED = "COMPLETED"
```

### 8.2 人工确认交互

1. 后端在对应节点生成完成后，将 `books.current_state` 更新为 `WAITING_*`，并通过 SSE 推送给前端。
2. 前端显示确认界面。
3. 用户点击"确认继续"：
   - 前端调用 `POST /api/books/{book_id}/confirm`，请求体包含确认类型。
   - 后端更新状态，触发 LangGraph 继续执行。
4. 用户点击"重新生成"：
   - 前端调用 `POST /api/books/{book_id}/regenerate`，指定阶段。
   - 后端重置该阶段之前的部分状态，重新进入生成流程。

---

## 9. LangGraph 工作流示例

### 9.1 状态定义

```python
from typing import TypedDict, Optional, List, Dict, Any

class NovelState(TypedDict):
    book_id: str
    user_prompt: str
    style_guide: Optional[Dict]
    worldview: Optional[str]
    worldview_score: Optional[float]
    outline: Optional[str]
    outline_score: Optional[float]
    characters: Optional[List[Dict]]
    parts: Optional[List[Dict]]
    current_part_index: int
    waiting_for: Optional[str]
    user_confirmed: bool
    regen_requested: bool
    regen_count: Dict[str, int]
    scheduled_task_id: Optional[str]  # 用于定时任务
```

### 9.2 节点函数示例

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver
from langgraph.types import interrupt
from agent.llm import call_llm_with_retry
from langchain_core.messages import SystemMessage, HumanMessage

def generate_worldview(state: NovelState) -> Dict:
    messages = [
        SystemMessage(content="你是一位专业的世界观设计师..."),
        HumanMessage(content=f"请根据以下描述构建世界观：{state['user_prompt']}")
    ]
    worldview_text = call_llm_with_retry(
        messages, user=state["user"], scene="worldview_build", project=state["project"]
    )
    return {"worldview": worldview_text, "waiting_for": "worldview", "user_confirmed": False}

def review_worldview(state: NovelState) -> Dict:
    messages = [
        SystemMessage(content="你是一位文学审核专家..."),
        HumanMessage(content=f"请审核以下世界观设定：{state['worldview']}")
    ]
    score_text = call_llm_with_retry(
        messages, user=state["user"], scene="chapter_scoring", project=state["project"]
    )
    return {"worldview_score": parse_score(score_text)}

def human_confirm_worldview(state: NovelState) -> Dict:
    decision = interrupt({
        "message": "请确认世界观设定",
        "worldview": state["worldview"],
        "options": ["confirm", "regenerate"]
    })
    if decision == "confirm":
        return {"user_confirmed": True, "regen_requested": False}
    else:
        return {"user_confirmed": False, "regen_requested": True,
                "regen_count": {**state["regen_count"], "worldview": state["regen_count"].get("worldview", 0)+1}}

def generate_outline(state: NovelState) -> Dict:
    messages = [
        SystemMessage(content="你是一位专业的故事大纲设计师..."),
        HumanMessage(content=f"世界观：{state['worldview']}\n\n请生成故事大纲")
    ]
    outline_text = call_llm_with_retry(
        messages, user=state["user"], scene="outline_optimize", project=state["project"]
    )
    return {"outline": outline_text, "waiting_for": "outline", "user_confirmed": False}
```

### 9.3 构建状态图

```python
workflow = StateGraph(NovelState)

# 添加节点
workflow.add_node("generate_worldview", generate_worldview)
workflow.add_node("review_worldview", review_worldview)
workflow.add_node("human_confirm_worldview", human_confirm_worldview)
workflow.add_node("generate_outline", generate_outline)
workflow.add_node("review_outline", review_outline)
workflow.add_node("human_confirm_outline", human_confirm_outline)
# ... 其他节点

workflow.set_entry_point("generate_worldview")

workflow.add_edge("generate_worldview", "review_worldview")

def decide_after_worldview_review(state):
    if state["worldview_score"] >= 75:
        return "human_confirm_worldview"
    else:
        return "generate_worldview"

workflow.add_conditional_edges(
    "review_worldview",
    decide_after_worldview_review,
    {
        "human_confirm_worldview": "human_confirm_worldview",
        "generate_worldview": "generate_worldview"
    }
)

def decide_after_worldview_confirm(state):
    if state["user_confirmed"]:
        return "generate_outline"
    else:
        return "generate_worldview"

workflow.add_conditional_edges(
    "human_confirm_worldview",
    decide_after_worldview_confirm,
    {
        "generate_outline": "generate_outline",
        "generate_worldview": "generate_worldview"
    }
)

# ... 继续添加其他边

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)
```

### 9.4 运行与恢复

```python
# 启动
config = {"configurable": {"thread_id": book_id}}
for event in app.stream(initial_state, config):
    print(event)

# 用户确认后恢复（通过 Command 传入决策）
from langgraph.types import Command

user_decision = "confirm"  # 或 "regenerate"
for event in app.stream(Command(resume=user_decision), config):
    print(event)
```

---

## 10. Redis 用途

| 用途 | 说明 |
|------|------|
| Celery broker | 任务队列核心（Result Backend 使用 Django DB） |
| 实时进度推送 | SSE 推送生成进度、状态变化 |

---

## 11. 定时任务实现（夜间低峰执行）

### 11.1 方案概述

使用 **Celery ETA** 延迟执行，在 LangGraph 节点中加入时间窗口判断，如果当前不在允许运行时间（如 0:00-7:00），则创建一个 Celery 任务并设定 ETA 为下一个窗口开始时刻，同时中断 LangGraph 流程。当 ETA 到达，worker 执行任务并恢复流程。

### 11.2 核心代码

```python
# 时间窗口判断
import datetime

def is_in_allowed_window():
    now = datetime.datetime.now()
    return now.hour >= 0 and now.hour < 7

def next_window_start():
    now = datetime.datetime.now()
    next_start = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), datetime.time(0, 0))
    return next_start

# Celery 任务
@celery_app.task(bind=True)
def execute_scheduled_generation(self, book_id, node_name, state_snapshot):
    # 从检查点恢复 LangGraph 流程
    config = {"configurable": {"thread_id": book_id}}
    # 可能需要更新 state 或直接继续
    for event in app.stream(None, config):
        pass
```

在需要延迟的节点中：

```python
def generate_chapter_node(state):
    if is_in_allowed_window():
        content = call_generation_model(...)
        return {"chapter_content": content}
    else:
        eta = next_window_start()
        task = execute_scheduled_generation.apply_async(
            args=[state["book_id"], "generate_chapter", state],
            eta=eta
        )
        # 中断流程，记录任务 ID
        return {"scheduled_task_id": task.id, "waiting_for": "schedule"}
```

然后通过条件边进入一个挂起状态，等待外部触发。

---

## 12. 关键实现细节

### 12.0 LLM 思考模式支持

不同 LLM 供应商的思考模式实现方式不同，需要适配：

| 供应商 | 思考模式参数 | 说明 |
|--------|-------------|------|
| DeepSeek | `enable_thinking=True` | 支持开关，默认开启 |
| Qwen | `enable_thinking=True` | 支持开关 |
| Claude | 无需配置 | 始终开启，无法关闭 |
| OpenAI | 无需配置 | o1/o3 系列自动开启 |
| SiliconFlow | 透传原模型参数 | 根据底层模型决定 |

**LLMConfig 模型扩展**（需迁移）：

```python
class LLMConfig(models.Model):
    # ... 现有字段 ...
    enable_thinking = models.BooleanField(
        null=True, blank=True,
        verbose_name='思考模式',
        help_text='null=使用供应商默认, True=强制开启, False=强制关闭'
    )
```

**请求时适配**：

```python
def get_llm(user=None, scene=None, **kwargs):
    # ... 现有逻辑 ...
    
    # 思考模式适配
    if config.get('enable_thinking') is not None:
        provider = config.get('provider', '')
        if provider in ['deepseek', 'qwen']:
            extra_kwargs['extra_body'] = {'enable_thinking': config['enable_thinking']}
        # Claude/OpenAI 不需要额外配置
    
    return ChatOpenAI(**final_params)
```

### 12.1 LLM 调用示例（复用项目现有封装）

```python
from agent.llm import call_llm_with_retry, get_llm
from langchain_core.messages import SystemMessage, HumanMessage

# 方式1：使用 call_llm_with_retry（推荐）
messages = [
    SystemMessage(content="你是一位专业的小说家..."),
    HumanMessage(content="请根据以下设定生成章节内容...")
]
result = call_llm_with_retry(
    messages,
    user=user,
    scene="chapter_batch_content",  # 使用场景配置
    stream=False,
    project=project
)

# 方式2：流式调用
def generate_stream():
    messages = [...]
    for chunk in call_llm_with_retry(
        messages,
        user=user,
        scene="chapter_batch_content",
        stream=True,
        project=project
    ):
        yield chunk
```

### 12.2 通用审核 Agent 伪代码

```python
from agent.llm import call_llm_with_retry
from langchain_core.messages import SystemMessage, HumanMessage

def review_with_config(obj_text, config, reference_materials, user, project):
    prompt = build_review_prompt(obj_text, config, reference_materials)
    messages = [
        SystemMessage(content="你是一位专业的文学审核专家..."),
        HumanMessage(content=prompt)
    ]
    result = call_llm_with_retry(
        messages,
        user=user,
        scene="chapter_scoring",  # 使用审核场景配置
        stream=False,
        project=project
    )
    scores = parse_json(result)
    avg_score = average(scores)
    return {
        "scores": scores,
        "overall": avg_score,
        "issues": collect_issues(scores),
        "passed": avg_score >= config["threshold"]
    }
```

### 12.3 向量检索集成（复用 `apps/knowledge` 应用）

```python
from apps.knowledge.models import KnowledgeVector
from pgvector.django import CosineDistance

def retrieve_relevant_chunks(query_text, book_id, top_k=5):
    # 使用项目现有的 embedding 服务
    from apps.knowledge.utils import get_embedding
    query_embedding = get_embedding(query_text)
    
    # 查询相关章节块
    results = KnowledgeVector.objects.filter(
        project_id=book_id
    ).annotate(
        distance=CosineDistance('embedding', query_embedding)
    ).order_by('distance')[:top_k]
    
    return results
```

---

## 13. 补充功能

### 13.1 持久化存储 - 复用现有模型

**设计原则**：手动写和自动写共用同一套数据模型，只是入口不同。

#### 需要扩展的现有模型

**ProjectList（`apps/project/models.py`）** - 增加自动写小说相关字段：

```python
class ProjectList(models.Model):
    # ... 现有字段 ...

    # ========== 自动写小说扩展字段 ==========
    GENERATION_MODE_CHOICES = [
        ('manual', '手动创作'),
        ('auto', '自动生成'),
    ]
    generation_mode = models.CharField(
        max_length=10, choices=GENERATION_MODE_CHOICES, default='manual',
        verbose_name='创作模式'
    )

    # 自动写小说状态（仅 auto 模式使用）
    AUTO_NOVEL_STATUS_CHOICES = [
        ('INIT', '初始化'),
        ('GENERATING_WORLDVIEW', '生成世界观'),
        ('WAITING_WORLDVIEW', '等待确认世界观'),
        ('GENERATING_OUTLINE', '生成大纲'),
        ('WAITING_OUTLINE', '等待确认大纲'),
        ('GENERATING_CHAPTERS', '生成章节'),
        ('WAITING_PART', '等待确认篇章'),
        ('COMPLETED', '已完成'),
        ('FAILED', '失败'),
    ]
    auto_novel_status = models.CharField(
        max_length=30, choices=AUTO_NOVEL_STATUS_CHOICES, default='INIT',
        verbose_name='自动写小说状态'
    )

    # 创意描述（auto 模式必填）
    prompt = models.TextField(blank=True, verbose_name='创意描述')

    # 故事圣经（JSONB）
    global_bible = models.JSONField(default=dict, blank=True, verbose_name='故事圣经')

    # LangGraph checkpoint thread_id
    thread_id = models.CharField(
        max_length=64, unique=True, null=True, blank=True,
        verbose_name='LangGraph线程ID'
    )

    # 审核配置
    review_model_ids = models.JSONField(
        default=list, blank=True,
        verbose_name='审核模型ID列表（关联LLMConfig）'
    )
    max_review_iterations = models.IntegerField(
        default=3, verbose_name='最大审核迭代次数'
    )
```

**ChapterList（`apps/chapter/models.py`）** - 增加审核相关字段：

```python
class ChapterList(models.Model):
    # ... 现有字段 ...

    # ========== 自动写小说扩展字段 ==========
    review_scores = models.JSONField(default=dict, blank=True, verbose_name='审核分数')
    review_iterations = models.IntegerField(default=0, verbose_name='已审核迭代次数')
```

#### 需要新建的模型

**ChapterChunk（`apps/auto_novel/models.py`）** - 章节向量块：

```python
from django.db import models
from pgvector.django import VectorField, HnswIndex

class ChapterChunk(models.Model):
    """章节向量块（用于向量检索）"""
    chapter = models.ForeignKey(
        'chapter.ChapterList', on_delete=models.CASCADE, related_name='chunks'
    )
    chunk_index = models.IntegerField(verbose_name='块序号')
    content = models.TextField(verbose_name='文本内容')
    # 向量维度 2048
    embedding = VectorField(dimensions=2048, verbose_name='embedding向量')

    class Meta:
        db_table = 'chapter_chunk'
        ordering = ['chunk_index']
        indexes = [
            HnswIndex(
                name='idx_chapter_chunk_embedding',
                fields=['embedding'],
                m=16,
                ef_construction=64,
                opclasses=['vector_cosine_ops'],
            ),
        ]
```

**AutoNovelStateChangeLog（`apps/auto_novel/models.py`）** - 状态变化日志：

```python
class AutoNovelStateChangeLog(models.Model):
    """自动写小说 - 状态变化日志"""
    chapter = models.ForeignKey(
        'chapter.ChapterList', on_delete=models.CASCADE, related_name='state_change_logs'
    )
    change_type = models.CharField(max_length=20)  # CHARACTER, TIMELINE, ITEM, FORESHADOWING
    delta = models.JSONField(verbose_name='变化内容')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auto_novel_state_change_log'
```

**AutoNovelChapterRevision（`apps/auto_novel/models.py`）** - 章节修订历史：

```python
class AutoNovelChapterRevision(models.Model):
    """章节修订历史（审核-修复循环）"""
    chapter = models.ForeignKey(
        'chapter.ChapterList', on_delete=models.CASCADE, related_name='revisions'
    )
    revision_no = models.IntegerField(verbose_name='修订版本号')
    content = models.TextField(verbose_name='修订内容')
    review_result = models.JSONField(default=dict, verbose_name='审核结果')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'auto_novel_chapter_revision'
        ordering = ['-revision_no']
```

### 13.2 进度追踪

通过 SSE 推送进度：

```python
# 进度事件格式
{
    "type": "progress",
    "data": {
        "step": "generating_chapter",  # 当前步骤
        "current": 5,                   # 当前第几章
        "total": 20,                    # 总章节数
        "percent": 25,                  # 进度百分比
        "message": "正在生成第5章..."    # 提示信息
    }
}
```

### 13.3 中断恢复

依赖 LangGraph checkpoint 实现：

```python
from langgraph.checkpoint.postgres import PostgresSaver

# 使用 PostgreSQL 作为 checkpoint 存储
checkpointer = PostgresSaver.from_conn_string(settings.DATABASE_URL)
app = workflow.compile(checkpointer=checkpointer)

# 恢复执行
config = {"configurable": {"thread_id": book.thread_id}}
for event in app.stream(None, config):
    # 继续执行
    pass
```

### 13.4 导出功能

```python
# apps/auto_novel/export.py
def export_to_txt(project):
    """导出为 TXT"""
    content = f"# {project.title}\n\n"
    for volume in project.volume_versions.filter(is_current=True).first().volumes.all():
        for chapter in volume.chapter_list.all():
            content += f"\n## {chapter.title}\n\n{chapter.content}\n"
    return content

def export_to_epub(project):
    """导出为 EPUB"""
    # 使用 ebooklib 库
    pass

def export_to_pdf(project):
    """导出为 PDF"""
    # 使用 reportlab 或 weasyprint
    pass
```

---

## 14. 与现有项目的集成

### 14.1 可复用的组件

| 组件 | 路径 | 复用方式 |
|------|------|----------|
| **数据模型** | | |
| 项目模型 | `apps/project/models.py` | 复用 `ProjectList`，增加自动写小说字段 |
| 卷模型 | `apps/volume/models.py` | 复用 `VolumeVersion`、`VolumeList` |
| 章节模型 | `apps/chapter/models.py` | 复用 `ChapterList`，增加审核字段 |
| **后端服务** | | |
| LLM 调用封装 | `agent/llm.py` | 直接调用 `call_llm_with_retry()` |
| 场景配置 | `agent/llm_scenes.py` | 增加新场景配置 |
| Embedding 服务 | `apps/knowledge/embedder.py` | 复用 `get_embedding()` |
| Rerank 服务 | `apps/knowledge/reranker.py` | 复用重排序逻辑 |
| LLM 配置模型 | `apps/user/models.py` | 复用 `LLMConfig`、`UserEmbeddingConfig` |
| Token 统计 | `apps/user/models.py` | 复用 `TokenUsageLog` |
| 基础视图 | `apps/project/base.py` | 继承 `BaseAPIView` |
| **前端** | | |
| 前端请求 | `frontend/src/api/request.js` | 直接复用 |
| 前端 SSE | `frontend/src/api/sse.js` | 直接复用 |
| 前端组件 | `frontend/src/components/` | 复用 AppModal、ChatPanel 等 |

### 14.2 需要修改的文件

| 文件 | 修改内容 |
|------|----------|
| `apps/project/models.py` | `ProjectList` 增加自动写小说扩展字段 |
| `apps/chapter/models.py` | `ChapterList` 增加审核相关字段 |
| `settings.py` | INSTALLED_APPS 增加 `'apps.auto_novel'` |
| `agent/llm_scenes.py` | 增加自动写小说相关场景（见下方） |
| `novel_agent/urls.py` | include auto_novel 的 urls |
| `frontend/src/router/index.js` | 增加自动写小说页面路由 |

### 14.3 需要新增的场景配置

在 `agent/llm_scenes.py` 中增加：

```python
# ==================== 自动写小说 ====================
"novel_worldview_build": {
    "name": "自动小说-世界观构建",
    "group": "auto_novel",
    "group_name": "自动写小说",
    "default_temperature": 0.8,
    "default_max_tokens": 100000,
},
"novel_outline_generate": {
    "name": "自动小说-大纲生成",
    "group": "auto_novel",
    "group_name": "自动写小说",
    "default_temperature": 0.7,
    "default_max_tokens": 100000,
},
"novel_character_design": {
    "name": "自动小说-人物设计",
    "group": "auto_novel",
    "group_name": "自动写小说",
    "default_temperature": 0.75,
    "default_max_tokens": 64000,
},
"novel_chapter_generate": {
    "name": "自动小说-章节正文生成",
    "group": "auto_novel",
    "group_name": "自动写小说",
    "default_temperature": 0.8,
    "default_max_tokens": 32000,
},
"novel_chapter_review": {
    "name": "自动小说-章节审核",
    "group": "auto_novel",
    "group_name": "自动写小说",
    "default_temperature": 0.3,
    "default_max_tokens": 16000,
},
"novel_state_extract": {
    "name": "自动小说-状态提取",
    "group": "auto_novel",
    "group_name": "自动写小说",
    "default_temperature": 0.3,
    "default_max_tokens": 16000,
},
```

### 14.4 需要新增的 Django App

```
apps/auto_novel/
├── __init__.py
├── apps.py
├── models.py          # 新增模型（ChapterChunk、StateChangeLog、ChapterRevision）
├── views.py           # API 接口
├── urls.py            # 路由
├── serializers.py     # DRF 序列化器
├── tasks.py           # Celery 任务
├── prompts.py         # 提示词模板
├── export.py          # 导出功能
└── migrations/
    └── __init__.py
```

### 14.5 需要注意的兼容性问题

| 问题 | 说明 | 解决方案 |
|------|------|----------|
| Embedding 维度 | `knowledge_vector` 表是 1024 维，计划是 2048 维 | 新建 `chapter_chunk` 表，独立维护 |
| LLMConfig 扩展 | 需要增加 `enable_thinking` 字段 | 创建新迁移文件 |
| 用户配置关联 | 审核模型列表需要关联多个 LLMConfig | `review_model_ids` 存储 ID 列表 |

