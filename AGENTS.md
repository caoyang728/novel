# AGENTS.md

开发规范与公共方法参考文档，供 AI Agent 在本仓库中工作时遵循。

## 项目概述

Novel Agent 是一个 Django 5.2 Web 应用，帮助作者通过聊天式 AI 交互构建小说大纲、卷、章节、角色、世界观设定和时间线。它通过 LangChain 使用兼容 OpenAI 的 LLM API（默认为 DeepSeek）实现所有 AI 功能，使用 Server-Sent Events (SSE) 实现流式响应。

- **数据库**: PostgreSQL 16 + pgvector（业务数据 + 向量存储一库两用）
- **缓存 & 消息队列**: Redis（缓存 + Celery Broker）
- **异步任务**: Celery Worker + Celery Beat（定时调度）
- **向量检索**: pgvector HNSW 索引 + cosine 相似度搜索
- **Embedding**: DeepSeek API / 本地 sentence-transformers（可切换）

## 技术架构

### 前后端分离架构

- **后端**: Django + DRF (Django REST Framework)，提供 RESTful API
- **前端**: Vue 3 SPA（`frontend/`），使用 Vite 构建，Element Plus 组件库，Pinia 状态管理，Vue Router 路由
- **遗留代码**: `static/` 目录下的原生 HTML/JS/CSS 和 `templates/` 目录下的 HTML 模板为历史遗留代码，**仅作为参考，禁止修改**

### 暗色主题规范

项目采用暗色风格设计，核心颜色变量定义如下：

| 颜色类别 | 变量名 | 值 | 用途 |
|---------|--------|-----|------|
| 主色调 | `--primary` | #818cf8 | 主要交互元素 |
| 主色调深 | `--primary-dark` | #6366f1 | 悬停/激活状态 |
| 页面背景 | `--bg-page` | #0f172a | 页面主背景 |
| 表面背景 | `--surface` | #1f2937 | 卡片/容器背景 |
| 深层背景 | `--surface-dark` | #111827 | 输入框/模态框 |
| 文字主色 | `--text-primary` | #f9fafb | 主要文本 |
| 文字次要 | `--text-secondary` | #d1d5db | 次要文本 |
| 文字暗淡 | `--text-muted` | #9ca3af | 辅助文本 |
| 边框颜色 | `--border` | #4b5563 | 分隔线/边框 |

### LLM 层架构

- **`agent/llm.py`**: LangChain 的 `ChatOpenAI` 轻量级封装，处理配置合并、流式/非流式调用和重试逻辑
- **`agent/llm_scenes.py`**: 场景配置管理，定义不同使用场景的 LLM 参数
- **`agent/memory.py`**: 记忆模块，管理对话上下文
- **`prompts.py`**: **每个应用独立维护**提示模板，位于各自的 APP 目录下（如 `apps/outline/prompts.py`、`apps/worldview/prompts.py`）
- **注意**: 鼓励使用 `services.py` 封装业务逻辑，新接口应直接使用 `services.py`；已有视图中的逻辑可在接口重构时顺带迁移到 `services.py`

### 认证

自定义 JWT 中间件 (`novel_agent/middleware.py`) 处理 API 请求（缺少令牌时返回 401）和页面请求（重定向到 `/login/`）。API 视图使用 DRF 的 `JWTAuthentication` + `IsAuthenticated`。

### 日志

全程使用 `loguru`（`from loguru import logger`），不使用 Django 标准日志系统。

## 命令

```bash
# 数据库迁移
docker compose exec django python manage.py makemigrations
docker compose exec django python manage.py migrate

# 创建超级用户
docker compose exec django python manage.py createsuperuser

# 运行单个测试文件
docker compose exec django python manage.py test apps.<app_name>.tests --keepdb

# 运行单个测试类
docker compose exec django python manage.py test apps.<app_name>.tests.<TestClass> --keepdb

# 运行单个测试方法
docker compose exec django python manage.py test apps.<app_name>.tests.<TestClass>.<test_method> --keepdb

# 运行多个 app 的测试
docker compose exec django python manage.py test apps.characters.tests apps.graph.tests apps.timeline.tests apps.chapter.tests --keepdb -v2

# 运行全部测试
docker compose exec django python manage.py test --keepdb -v2

# 运行测试并生成覆盖率报告
docker compose exec django coverage run --source='apps' manage.py test --keepdb
docker compose exec django coverage report -m --fail-under=90
docker compose exec django coverage html

# 管理命令
docker compose exec django python manage.py rebuild_graph       # 重建知识图谱
docker compose exec django python manage.py rebuild_knowledge   # 重建知识库向量索引
docker compose exec django python manage.py rebuild_trajectories  # 重建角色轨迹
```

### Docker Compose 操作

项目使用 Docker Compose 部署，服务包括：redis、postgres（pgvector）、django、celery-worker、celery-beat、nginx。

```bash
# 重新构建并重启所有服务
docker compose up -d --build

# 仅重启特定服务（如 django、celery-worker）
docker compose restart django celery-worker

# 重新构建并重启特定服务
docker compose up -d --build django

# 查看服务日志
docker compose logs -f django
docker compose logs -f celery-worker

# 停止所有服务
docker compose down

# 停止并删除数据卷（慎用，会清除数据库）
docker compose down -v
```

#### 操作规范

1. **需要重新构建/重启前后端时**: 自行操作 Docker Compose，仅限必要服务（如 `django`、`celery-worker`、`nginx`），无需等待用户确认
2. **修改数据库模型后**: 必须执行迁移命令
   ```bash
   docker compose exec django python manage.py makemigrations
   docker compose exec django python manage.py migrate
   ```
3. **修改前端代码后**: 需主动尝试在浏览器中验证效果（如果能力允许），确保修改生效且无明显错误

## 应用结构

### 后端应用（`apps/`）

| 应用 | 用途 |
|-----|------|
| `project` | 核心 ProjectList 模型、BaseAPIView 根基类、项目 CRUD API |
| `outline` | Outline、OutlineChatHistory — 聊天驱动的大纲构建，支持 SSE 流式传输 |
| `volume` | VolumeVersion、VolumeList — 从大纲生成卷结构 |
| `chapter` | ChapterList — 章节摘要、内容生成、流式传输、校验、评分、拆分 |
| `worldview` | WorldView、WorldViewChatHistory — 结构化世界观设定，支持版本管理、聊天式 AI 构建 |
| `characters` | Character、CharacterTrajectory 模型，角色 CRUD/生成/润色/校验/轨迹 API，序列化器、常量、管理命令 |
| `timeline` | TimelineEvent、TimelineChatHistory — 基于章节范围的故事时间线 |
| `note` | Note — 自由形式的"随手记"，支持 AI 润色 |
| `user` | 用户 LLM 配置（LLMConfig、UserLLMConfig）、TokenUsageLog、JWT 认证视图 |
| `knowledge` | KnowledgeVector（pgvector 向量存储）、embedder、indexer、retriever、reranker，语义检索全链路 |
| `graph` | GraphNode、GraphEdge 模型，GraphService 同步逻辑、序列化器、signals、tasks、management command rebuild_graph |

### URL 和路由模式

所有视图使用 `apps/<app>/urls.py`，在根目录 `novel_agent/urls.py` 中通过 `path('', include(...))` 包含。API 端点位于 `/api/` 下。前端 Vue SPA 的路由由 Vue Router 管理。

### 数据模型约定

- **软删除**: 大多数模型使用 `is_deleted` 布尔字段而非硬删除
- **版本控制**: Outline（`version` 字段）和 Volume（`VolumeVersion` + `version_number` 字段）支持多版本管理，带有 `is_finalized`、`is_current`、`is_deleted` 标志。`version=0` 或 `version_number=0` 表示"构建中/草稿"版本
- **聊天历史**: `OutlineChatHistory`、`WorldviewChatHistory`、`TimelineChatHistory` 存储与父模型关联的角色+内容对

### 视图继承架构

```
project/base.py:BaseAPIView (根基类)
├── worldview/views.py:BaseWorldAPIView
├── chapter/views.py:BaseChapterAPIView
├── volume/views.py:BaseVolumeAPIView
├── timeline/views.py:BaseTimelineAPIView
├── outline/views.py:BaseOutlineAPIView
├── characters/views.py:BaseCharacterAPIView
└── (其他 app...)
```

- **`project/base.py:BaseAPIView`** — 根基类，提供鉴权、项目查询、SSE工具、Token统计等公共方法
- **每个app的`views.py`** — 定义`Base*APIView`继承`BaseAPIView`，封装该app特有的公共方法
- **App视图** — 继承app的base视图，实现具体业务逻辑
- **注意**: `graph`、`note`、`user`、`project` 的视图直接继承 `BaseAPIView`，未定义中间 base 类

### 关键环境变量（`.env`）

- `PG_DB_*` — PostgreSQL 数据库连接
- `REDIS_DB_*` — Redis 缓存连接
- `CELERY_BROKER_URL` — Celery 消息代理（默认复用 Redis DB 1）

---

## 开发流程规范

### 需求分析与执行流程

1. **需求分析**: 接到任务后，首先分析需求，明确目标和范围
2. **计划制定**: 列出详细的执行计划和任务清单
3. **代码实现**: 按照计划进行代码开发和修改
4. **测试验证**: 代码修改完成后，必须检查测试用例是否完善，执行测试并确保覆盖率达标（详见「测试规范」）
5. **代码审查**: 提交代码前进行自我审查，确保符合项目规范

### 测试规范

#### 测试工具

- **框架**: Django 内置 `django.test.TestCase`（基于 unittest）
- **覆盖率工具**: `coverage.py`（需安装：`pip install coverage`）
- **测试数据库**: 使用 `--keepdb` 复用已有测试数据库，避免每次重建

#### 覆盖率要求

| 维度 | 最低要求 | 说明 |
|------|---------|------|
| **单个接口/方法** | ≥ 80% | 新增或修改的 API 视图、服务方法、工具函数 |
| **单个文件** | ≥ 90% | 整个 `.py` 文件的行覆盖率 |
| **整体项目** | ≥ 80% | `apps/` 目录下所有代码的平均覆盖率 |

#### 测试编写流程

修改接口或功能后，必须执行以下步骤：

1. **检查现有测试**: 查看 `apps/<app_name>/tests/` 目录或 `tests.py` 中是否已有相关测试（如 `characters` 使用 `tests/` 目录包含多个测试文件）
2. **补充测试用例**: 如果测试不完善，补充以下类型的测试：
   - **模型测试**: 字段创建、约束、`__str__`、级联删除、JSON 字段
   - **API 测试**: 正常请求、参数校验、权限校验、边界条件
   - **服务方法测试**: 核心逻辑、异常处理、边界情况
3. **执行测试**: `docker compose exec django python manage.py test apps.<app_name>.tests --keepdb -v2`
4. **检查覆盖率**: `docker compose exec django coverage run --source='apps/<app_name>' manage.py test apps.<app_name>.tests --keepdb && docker compose exec django coverage report -m`
5. **不达标则补充**: 如果文件覆盖率未达 90%，补充测试用例直到达标

#### 测试命名规范

- **文件**: `apps/<app_name>/tests.py`
- **类名**: `<功能>Test`（如 `CharacterModelTest`、`BuildTrajectoriesTest`）
- **方法名**: `test_<行为描述>`（如 `test_create_character`、`test_batch_create_empty_list`）

#### 测试编写参考

参考 `apps/worldview/tests.py` 的风格：
- 使用辅助函数 `_create_test_data()` 创建测试数据
- API 测试使用 `APIRequestFactory` + `force_authenticate`
- 手动调用 `View.as_view()(request, **url_kwargs)` 并检查 `response.status_code` 和 `json.loads(response.content)`

## 开发规范

### 语言规范

- **优先使用中文**: AI Agent 的思考过程、回答内容、注释说明等均优先使用中文显示

### 代码维护规范

1. **禁止删除注释代码**: 不要删除任何注释的代码，包括已注释的 logger 语句，它们可能在后续调试中有用
2. **禁止删除 logger**: 保留所有 logger 语句，即使是暂时不需要的，以便于问题排查

### 文件操作规范

1. **禁止使用脚本批量操作**: 不要使用 PowerShell、bash 等脚本进行批量文件操作
2. **禁止使用 git 恢复**: 不要依赖 git reset/hard 等命令恢复文件，应手动处理
3. **删除文件前必须备份**: 在删除任何文件之前，必须先创建备份副本，即使文件已经乱码或损坏

### 前端开发规范

**适用范围说明**:
- 以下前端规范**仅适用于** `frontend` 目录下的 Vue 3 SPA 项目
- `static/` 目录中的原生 HTML/JS/CSS 文件和 `templates/` 目录中的 HTML 模板为**历史遗留代码，仅作为参考，禁止修改**
- **任何涉及前端的修改，必须且只能在 `frontend/` 目录下的 Vue 项目中进行**

1. **单文件组件 (SFC)**: 使用 `.vue` 单文件组件开发，`<template>`、`<script setup>`、`<style lang="scss" scoped>` 分区书写
2. **API 请求封装**: 前端所有请求必须使用 `frontend/src/api/` 下封装的模块，统一处理认证、错误和重连逻辑
3. **组件库**: 基于 Element Plus 组件库，暗色主题覆写在 `element-dark.scss`
4. **状态管理**: 使用 Pinia（`frontend/src/stores/`），按功能域划分 store
5. **路由**: 使用 Vue Router（`frontend/src/router/index.js`），所有路由定义集中管理

### CSS 规范

**样式体系**: Vue 前端使用 SCSS + Element Plus，全局变量定义在 `frontend/src/styles/variables.scss`。

1. **设计变量优先**: 使用 SCSS 变量（如 `$primary`、`$text-primary`、`$surface` 等）和 CSS 自定义属性
2. **全局工具类**（定义在 `index.scss`）:
   - `.glass-panel` — 毛玻璃面板容器
   - `.glass-panel-hover` — 带悬停效果的毛玻璃面板
   - `.glass-surface` — 轻量毛玻璃表面
   - `.glass-input` — 毛玻璃输入框
   - `.text-ellipsis` — 文字截断省略
3. **公共组件样式**: 优先使用公共组件自带的 class，如需覆盖使用更具体的选择器
4. **Scoped 样式**: 组件私有样式必须加 `scoped`，避免全局污染
5. **弹窗 Footer 布局约定**:
   - `.modal-footer-content` — footer 内容布局容器
   - `.footer-right` — 右侧按钮组
   - `.footer-btn` — 统一 footer 按钮尺寸

### 前端模块组织

```
frontend/src/
├── api/            # API 请求封装（按功能域分文件）
│   ├── request.js  # 核心请求工具（api.get/post/put/del）
│   └── sse.js      # SSE 流式请求封装
├── components/     # 公共组件
│   ├── common/     # AppModal / AppButton / EmptyState / PageHeader 等
│   ├── chat/       # ChatInput / ChatMessage / ChatPanel / ChatSelectionBar
│   └── project/    # ProjectCard / ProjectFormModal
├── composables/    # Vue 组合式函数（复用有状态逻辑）
│   ├── useChat.js  # 聊天消息管理、SSE 收发、选择模式
│   ├── useProjectId.js  # 从路由获取项目 ID
│   ├── useVersions.js   # 版本管理
│   ├── useAiAction.js   # AI 按钮 loading/防重入
│   ├── useDiffBaseline.js # content/baseline 双状态（未保存变更高亮）
│   └── useTokenUsage.js # Token 用量查询
├── layouts/        # 布局组件（AuthLayout / MainLayout / ProjectLayout）
├── router/         # Vue Router 路由配置
├── stores/         # Pinia 状态管理（auth / project / ui）
├── styles/         # 全局 SCSS（variables / index / element-dark / transitions）
├── utils/          # 工具函数（按功能域分文件）
│   ├── crypto.js   # RSA 加密（node-forge，密码加密）
│   ├── diff.js     # 文本对比（jsdiff，Markdown 感知的 diff）
│   ├── format.js   # 日期、Token 数量、HTML 转义、文本截断
│   ├── json.js     # JSON 提取与安全解析
│   ├── loading.js  # 全局 Loading（基于 ElLoading）
│   ├── markdown.js # 安全 Markdown 解析
│   ├── modal.js    # 命令式弹窗（showModal / showConfirmModal）
│   ├── notify.js   # Toast 通知（showToast / showSuccess / showError / showWarning）
│   └── storage.js  # localStorage 数据迁移工具
└── views/          # 页面视图（按功能域分目录）
```

### JS 规范 — 公共模块列表

#### API 请求 (`api/request.js`)

| 方法 | 说明 |
|------|------|
| `api.get(url, options)` | GET 请求 |
| `api.post(url, body, options)` | POST 请求 |
| `api.put(url, body, options)` | PUT 请求 |
| `api.del(url, options)` | DELETE 请求 |

> 认证和 401 自动刷新在 `request.js` 内部自动处理，无需手动管理 token。

#### SSE 流式请求 (`api/sse.js`)

| 方法 | 说明 |
|------|------|
| `streamRequest(url, options)` | 流式请求（聚合返回完整文本） |
| `streamRequestRaw(url, options, onChunk)` | 流式请求（实时逐块回调） |
| `createSseController()` | 创建可复用的 SSE 控制器，返回 `{ stream, abort }` |

#### 认证 Store (`stores/auth.js`)

| 方法/属性 | 说明 |
|-----------|------|
| `useAuthStore().isAuthenticated` | computed，检查是否已登录 |
| `useAuthStore().user` | ref，当前用户信息 |
| `useAuthStore().login(username, password)` | 登录（自动加密密码） |
| `useAuthStore().logout()` | 退出登录（清除状态 + 跳转登录页） |
| `useAuthStore().fetchUser()` | 获取用户信息（1小时缓存） |
| `useAuthStore().fetchTodayUsage()` | 获取今日 Token 用量 |

#### 项目 Store (`stores/project.js`)

| 方法/属性 | 说明 |
|-----------|------|
| `useProjectStore().currentProject` | ref，当前项目 |
| `useProjectStore().fetchProject(id)` | 获取单个项目详情 |
| `useProjectStore().fetchProjects()` | 获取项目列表 |
| `useProjectStore().createProject(data)` | 创建项目 |
| `useProjectStore().updateProject(id, data)` | 更新项目 |
| `useProjectStore().deleteProject(id)` | 删除项目 |

#### 通知 (`utils/notify.js`)

| 方法 | 说明 |
|------|------|
| `showToast(message, type, duration)` | 显示提示消息 |
| `showSuccess(message, duration)` | 显示成功提示 |
| `showError(message, duration)` | 显示错误提示 |
| `showWarning(message, duration)` | 显示警告提示 |
| `showInfo(message, duration)` | 显示信息提示 |

#### Loading (`utils/loading.js`)

| 方法 | 说明 |
|------|------|
| `showLoading(text)` | 显示全屏加载动画 |
| `hideLoading()` | 隐藏加载动画 |

#### 弹窗 (`utils/modal.js`)

| 方法 | 说明 |
|------|------|
| `showModal(options)` | 命令式通用弹窗（见下方说明） |
| `showConfirmModal(options)` | 命令式确认弹窗（见下方说明） |

#### 格式化 (`utils/format.js`)

| 方法 | 说明 |
|------|------|
| `formatDate(date, format)` | 格式化日期（format: 'datetime' / 'date' / 'time'） |
| `formatTokenCount(count)` | 格式化 Token 数量（如 1.2K、3.5M） |
| `escapeHtml(str)` | HTML 转义 |
| `truncate(text, maxLen)` | 截断文本 |

#### JSON 工具 (`utils/json.js`)

| 方法 | 说明 |
|------|------|
| `extractJsonFromString(str)` | 从字符串中提取 JSON（支持代码块/裸 JSON） |
| `safeJsonParse(str, fallback)` | 安全的 JSON 解析 |

#### Markdown (`utils/markdown.js`)

| 方法 | 说明 |
|------|------|
| `safeMarkdownParse(text)` | 安全的 Markdown 解析（DOMPurify 过滤） |

#### Diff 文本对比 (`diff` 库)

项目使用 [jsdiff](https://github.com/kpdecker/jsdiff)（npm 包名 `diff`）实现文本对比，**所有需要 diff 功能的场景统一使用此库**。

**核心方法**：

| 方法 | 用途 | 说明 |
|------|------|------|
| `diffArrays(oldArr, newArr)` | 数组级 diff | 用于行级/词级 token 对比，返回 `{added, removed, value}` |
| `diffWords(oldStr, newStr)` | 词级 diff | 用于计算两行相似度，自动处理中英文分词 |

**统一封装模块 `utils/diff.js`**（禁止在组件内自行实现 diff）：

| 方法 | 说明 |
|------|------|
| `computeMarkdownDiffGroups(oldText, newText)` | 主入口，按块分组返回 diff 结果，供渲染层直接消费 |
| `computeLineDiff(oldText, newText)` | 行级 diff，返回扁平的 equal/added/removed/replaced 项 |
| `computeWordDiff(oldLine, newLine)` | 行内词级 diff，返回 `{ oldPrefix, newPrefix, parts }` |
| `tokenizeInline(line)` | 把一行拆成 token，内联 Markdown 结构保持完整 |
| `lineSimilarity(a, b)` | 行级相似度（0~1），用于判定"替换"而非"新增+删除" |
| `escapeHtml(str)` | HTML 转义 |
| `SIMILARITY_THRESHOLD` | 相似度阈值常量（0.3） |

**两层 diff 策略**：

1. **行级**：`diffArrays` 按 `\n` 拆行对比，每行是一个原子；连续同类型行合并为一个 group，保证列表、段落等块级结构完整
2. **替换检测**：相邻 removed-group + added-group 的行两两配对，`lineSimilarity` ≥ 0.3 视为 replaced，否则保留为独立的 removed / added
3. **词级**：replaced 行调用 `computeWordDiff` 做行内高亮

**关键设计 — 内联 Markdown 原子化**：

词级 diff 前会先用 `tokenizeInline` 把行拆成 token，其中 `**粗体**`、`*斜体*`、`` `代码` ``、`~~删除~~` 整体作为一个原子 token，中文按单字、英文按单词切分。
这样可避免 `**` 标记被 diff 拆到不同片段里，导致渲染出字面星号。渲染时每个片段先 `marked.parseInline()` 再包 `<span>`，因此 `<span class="dw-r"><strong>文本</strong></span>` 是合法结构。

**块级前缀处理**：标题（`### `）、列表（`- `、`1. `）、引用（`> `）前缀由 `getLinePrefix` / `stripLinePrefix` 单独处理，不参与 diff，避免前缀变化被误标为内容变更。

**MarkdownRenderer diff 方案**（`frontend/src/components/common/MarkdownRenderer.vue`）：

- diff 计算全部委托给 `utils/diff.js`，组件只负责把 groups 渲染成 HTML
- 连续 equal 行合并为一个 Markdown 块用 `marked.parse()` 渲染；removed/added 各自成块；replaced 的 old/new 上下排列在同一个 diff-block 中

**样式 class**：
- `.diff-block.diff-added` — 新增内容（绿色左边框）
- `.diff-block.diff-removed` — 删除内容（红色左边框+删除线）
- `.diff-block.diff-replaced` — 替换内容（黄色左边框，内含 `.dw-old` 和 `.dw-new`）
- `.dw-a` — 行内新增词（绿色背景）
- `.dw-r` — 行内删除词（红色删除线）

#### 数据存储 (`utils/storage.js`)

| 方法 | 说明 |
|------|------|
| `savePendingData(key, data)` | 保存待恢复数据到 localStorage |
| `restorePendingData(key, clear)` | 恢复待处理数据 |
| `clearPendingData(key)` | 清除待处理数据 |

#### 聊天 Composable (`composables/useChat.js`)

| 方法/属性 | 说明 |
|-----------|------|
| `messages` | ref，消息列表 |
| `isStreaming` | ref，是否正在流式生成 |
| `sendMessage(url, body)` | 发送消息（自动添加用户/AI消息） |
| `stopStreaming()` | 停止生成 |
| `setMessages(msgs)` | 加载历史消息 |
| `clearMessages()` | 清空消息 |
| `enterSelectionMode()` | 进入选择模式 |
| `exitSelectionMode()` | 退出选择模式 |
| `toggleMessageSelect(msgId)` | 切换消息选中状态 |
| `getSelectedContent()` | 获取选中消息的合并文本 |

#### 项目 ID Composable (`composables/useProjectId.js`)

| 方法 | 说明 |
|------|------|
| `useProjectId()` | 从路由参数获取当前项目 ID |

#### AI Action Composable (`composables/useAiAction.js`)

| 方法 | 说明 |
|------|------|
| `useAiAction()` | 返回 `{ loading, wrapAction }`，AI 按钮 loading 状态管理和防重入 |

#### Token 用量 Composable (`composables/useTokenUsage.js`)

| 方法 | 说明 |
|------|------|
| `useTokenUsage()` | 返回 `{ loading, fetchTodayUsage }`，查询今日 Token 用量 |

#### Diff 基线 Composable (`composables/useDiffBaseline.js`)

管理 `content` / `baseline` 双状态，用于 Markdown 预览的未保存变更高亮（配合 `MarkdownRenderer` 的 `highlight-new` / `baseline` / `show-removed`）。

| 方法/属性 | 说明 |
|-----------|------|
| `content` | ref，当前文档内容 |
| `baseline` | ref，上次保存/加载时的快照 |
| `hasUnsavedChanges()` | 是否存在未保存变更（`content !== baseline`） |
| `reset()` | 清空两个状态（无版本 / 删除当前版本时） |
| `loadSnapshot(value)` | 加载版本或初始化：两者同时设为已保存内容（diff 消失） |
| `commit()` | 保存 / 另存后：baseline 追上 content（diff 消失） |
| `revert()` | 回滚：content 恢复为 baseline（如流式生成失败时） |

**baseline 同步规则**：仅在 `loadSnapshot` / `commit` 时同步；AI 流式返回和用户手动编辑**不同步**，因此 diff 会持续显示，直到保存。

#### 加密工具 (`utils/crypto.js`)

| 方法 | 说明 |
|------|------|
| `encryptPassword(password)` | 使用 RSA-OAEP 加密密码（自动获取并缓存公钥） |

**使用规则:**
1. 优先使用上述公共模块中的方法
2. 如果没有对应方法，再在自己的组件/composable 中构建
3. **复用规则**: 如果某个逻辑被 **3 个及以上组件**使用，应提取为 composable 或 utils 模块

### 公共组件清单

使用前请阅读组件文件头部注释了解详细用法。

| 组件 | 路径 | 用途 |
|------|------|------|
| `AppModal` | `frontend/src/components/common/AppModal.vue` | 声明式弹窗（v-model:visible 控制） |
| `AppButton` | `frontend/src/components/common/AppButton.vue` | 统一按钮（variant / size） |
| `ConfirmButton` | `frontend/src/components/common/ConfirmButton.vue` | 带二次确认的按钮 |
| `AppConfirmModal` | `frontend/src/components/common/AppConfirmModal.vue` | 确认弹窗 |
| `EmptyState` | `frontend/src/components/common/EmptyState.vue` | 空状态占位 |
| `PageHeader` | `frontend/src/components/common/PageHeader.vue` | 页面头部 |
| `VersionSidebar` | `frontend/src/components/common/VersionSidebar.vue` | 版本侧边栏 |
| `MarkdownRenderer` | `frontend/src/components/common/MarkdownRenderer.vue` | Markdown 渲染 |
| `ModalHost` | `frontend/src/components/common/ModalHost.vue` | 命令式弹窗宿主（配合 `utils/modal.js`） |
| `ChatInput` | `frontend/src/components/chat/ChatInput.vue` | 聊天输入框 |
| `ChatMessage` | `frontend/src/components/chat/ChatMessage.vue` | 聊天消息气泡 |
| `ChatPanel` | `frontend/src/components/chat/ChatPanel.vue` | 聊天面板 |
| `ChatSelectionBar` | `frontend/src/components/chat/ChatSelectionBar.vue` | 消息选择操作栏 |
| `GraphCanvas` | `frontend/src/components/graph/GraphCanvas.vue` | 知识图画布 |

### 按钮规范（AppButton）

前端按钮统一使用 `AppButton` 组件（`frontend/src/components/common/AppButton.vue`）。

| variant | 用途 | 颜色 |
|---------|------|------|
| `default` | 默认/取消按钮 | 无额外样式 |
| `accent` | 主操作（保存、提交） | 蓝色 #6366f1 |
| `ai` | AI 相关操作 | 蓝紫色 #8b5cf6 |
| `danger` | 危险操作（删除） | 红色 #f87171 |
| `success` | 成功操作（锁定版本） | 绿色 #34d399 |
| `warning` | 警告操作（解锁版本） | 琥珀色 #fbbf24 |
| `grey` | 低优先级操作 | 灰色 #64748b |

| size | 高度 | 用途 |
|------|------|------|
| `small` | 24px | 行内小按钮 |
| `medium` | 36px | 默认 |
| `large` | 44px | 突出按钮 |
| 具体值如 `'32px'` | 自定义 | 特殊场景 |

### API 请求规范

> 前端 API 方法列表见上方「JS 规范 — 公共模块列表」，使用 `frontend/src/api/` 下的封装模块。认证 token 自动注入，401 自动刷新重放，无需手动处理。

#### 环境变量配置规范

1. **敏感配置必须使用环境变量**: 数据库密码、Redis 密码等敏感配置统一写入 `.env` 文件，禁止硬编码到代码中
2. **后端通过 `settings.py` 读取**: 后端通过 `os.getenv()` 从环境变量读取配置
3. **前端通过 API 获取**: 前端不应直接读取环境变量，敏感配置应通过后端 API 接口获取

#### 请求参数校验规范

1. **空请求过滤**: 后端必须校验请求参数，过滤空请求和无效数据
2. **文本长度限制**: 对文本字段进行长度校验，防止超长非法文本提交
3. **格式校验**: 对日期、数字等字段进行格式校验
4. **错误响应**: 参数校验失败时，返回明确的错误信息和状态码

#### 流式响应超时处理

1. **后端配置超时时间**: 配置流式响应的超时时间，防止长连接挂起
2. **前端超时提示**: 前端应检测连接超时，并向用户显示提示信息
3. **自动重试机制**: 超时后提供重试选项，允许用户重新发起请求

### 代码审查要点

- 检查业务逻辑是否合理封装在 `services.py` 中，新接口应使用 `services.py`
- 确保 `prompts.py` 位于各自的 APP 目录下
- 验证 Vue 组件是否正确使用 SFC 格式（template / script setup / style scoped）
- 确认 SCSS 变量和 Element Plus 组件正确使用
- 检查是否有被删除的注释代码或 logger 语句
- 验证前端是否使用 `api/` 下的封装请求模块
- 检查敏感配置是否存在硬编码，应使用环境变量
- 确认请求参数校验逻辑是否完善
- 检查流式响应是否配置了超时机制
- 检查修改的接口是否有对应的测试用例，覆盖率是否达标（单接口 ≥ 80%，文件 ≥ 90%）
