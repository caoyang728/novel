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
- **注意**: 项目**不使用** `services.py`（仅 `graph` 应用例外），所有业务逻辑直接在视图层或工具函数中处理

### 认证

自定义 JWT 中间件 (`novel_agent/middleware.py`) 处理 API 请求（缺少令牌时返回 401）和页面请求（重定向到 `/login/`）。API 视图使用 DRF 的 `JWTAuthentication` + `IsAuthenticated`。

### 日志

全程使用 `loguru`（`from loguru import logger`），不使用 Django 标准日志系统。

## 命令

```bash
# 激活虚拟环境并运行开发服务器
source .venv/Scripts/activate
python manage.py runserver

# 数据库迁移
python manage.py makemigrations
python manage.py migrate

# 创建超级用户
python manage.py createsuperuser

# 运行单个测试文件
python manage.py test apps.<app_name>.tests

# 安装依赖
pip install -r requirements.txt
```

## 应用结构

### 后端应用（`apps/`）

| 应用 | 用途 |
|-----|------|
| `project` | 核心 ProjectList 模型、Character、Worldview、WorldviewChatHistory |
| `outline` | OutlineVersion、OutlineChatHistory、OutlineExpansion — 聊天驱动的大纲构建，支持 SSE 流式传输 |
| `volume` | VolumeVersion、VolumeList — 从大纲生成卷结构 |
| `chapter` | ChapterVersion、ChapterList — 章节摘要、内容生成、流式传输 |
| `worldview` | World — 结构化世界观设定，包含 JSON 字段和快照 |
| `characters` | 仅角色生成提示（模型位于 `project` 中） |
| `timeline` | TimelineEvent、TimelineChatHistory — 基于章节范围的故事时间线 |
| `note` | Note — 自由形式的"随手记"，支持 AI 润色 |
| `user` | 用户 LLM 配置（LLMConfig、UserLLMConfig）、TokenUsageLog、JWT 认证视图 |
| `knowledge` | KnowledgeVector（pgvector 向量存储）、向量索引、语义检索 |
| `graph` | 知识图谱模块（GraphEdge）、services.py 封装图谱逻辑、management command rebuild_graph |

### URL 和路由模式

所有视图使用 `apps/<app>/urls.py`，在根目录 `novel_agent/urls.py` 中通过 `path('', include(...))` 包含。API 端点位于 `/api/` 下。前端 Vue SPA 的路由由 Vue Router 管理。

### 数据模型约定

- **软删除**: 大多数模型使用 `is_deleted` 布尔字段而非硬删除
- **版本控制**: Outline、Volume 和 Chapter 有版本模型，支持每个父模型有多个版本，带有 `is_finalized`、`is_current` 和 `is_deleted` 标志。`version_number=0` 表示"构建/草稿"版本
- **聊天历史**: `OutlineChatHistory`、`WorldviewChatHistory`、`TimelineChatHistory` 存储与父模型关联的角色+内容对

### 视图继承架构

```
project/base.py:BaseAPIView (根基类)
├── worldview/views.py:BaseWorldAPIView
├── chapter/views.py:BaseChapterAPIView
├── volume/views.py:BaseVolumeAPIView
├── timeline/views.py:BaseTimelineAPIView
├── outline/views.py:BaseOutlineAPIView
└── (其他 app...)
```

- **`project/base.py:BaseAPIView`** — 根基类，提供鉴权、项目查询、SSE工具、Token统计等公共方法
- **每个app的`views.py`** — 定义`Base*APIView`继承`BaseAPIView`，封装该app特有的公共方法
- **App视图** — 继承app的base视图，实现具体业务逻辑

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
4. **测试验证**: 代码修改完成后，必须编写并执行单元测试用例，确保功能正确性
5. **代码审查**: 提交代码前进行自我审查，确保符合项目规范

## 开发规范

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
│   └── useVersions.js   # 版本管理
├── layouts/        # 布局组件（AuthLayout / MainLayout / ProjectLayout）
├── router/         # Vue Router 路由配置
├── stores/         # Pinia 状态管理（auth / project / ui）
├── styles/         # 全局 SCSS（variables / index / element-dark / transitions）
├── utils/          # 工具函数（按功能域分文件）
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

- 检查是否有不必要的 `services.py` 文件（仅 `graph` 应用允许有）
- 确保 `prompts.py` 位于各自的 APP 目录下
- 验证 Vue 组件是否正确使用 SFC 格式（template / script setup / style scoped）
- 确认 SCSS 变量和 Element Plus 组件正确使用
- 检查是否有被删除的注释代码或 logger 语句
- 验证前端是否使用 `api/` 下的封装请求模块
- 检查敏感配置是否存在硬编码，应使用环境变量
- 确认请求参数校验逻辑是否完善
- 检查流式响应是否配置了超时机制
