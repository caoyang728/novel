# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供在本仓库中工作的指导。

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
- **前端**: 原生 HTML、JavaScript、CSS，无构建工具，直接通过 Django 静态文件服务

### 前端文件组织规范

前端资源采用**分离式文件结构**，HTML、CSS、JavaScript 分别存放在独立文件中：

```
static/
├── css/           # 样式文件
│   ├── common.css     # 全局公共样式
│   ├── outline.css    # 大纲页面样式
│   ├── chapter.css    # 章节页面样式
│   ├── worldview.css  # 世界观页面样式
│   └── ...
├── js/            # 脚本文件
│   ├── common.js      # 全局公共脚本
│   ├── outline.js     # 大纲页面脚本
│   ├── chapter.js     # 章节页面脚本
│   ├── worldview.js   # 世界观页面脚本
│   └── ...
templates/         # HTML 模板
├── outline.html
├── chapter.html
├── worldview.html
└── ...
```

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
- **注意**: 项目**不使用** `services.py`，所有业务逻辑直接在视图层或工具函数中处理

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

### 核心模块

| 模块 | 用途 |
|-----|------|
| `agent/` | LLM 封装 (`llm.py`)、场景配置 (`llm_scenes.py`)、记忆模块 (`memory.py`) |
| `apps/` | Django 应用，包含业务逻辑 |

### Apps（`apps/` 中的 Django 应用）

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

### URL 和路由模式

所有视图使用 `apps/<app>/urls.py`，在根目录 `novel_agent/urls.py` 中通过 `path('', include(...))` 包含。前端 HTML 页面作为静态文件从 `templates/` 目录提供，通过主 URL 配置中的独立 `path()` 条目实现。API 端点位于 `/api/` 下。

### 数据模型约定

- **软删除**: 大多数模型使用 `is_deleted` 布尔字段而非硬删除
- **版本控制**: Outline、Volume 和 Chapter 有版本模型，支持每个父模型有多个版本，带有 `is_finalized`、`is_current` 和 `is_deleted` 标志。`version_number=0` 表示"构建/草稿"版本
- **聊天历史**: `OutlineChatHistory`、`WorldviewChatHistory`、`TimelineChatHistory` 存储与父模型关联的角色+内容对

### 认证

自定义 JWT 中间件 (`novel_agent/middleware.py`) 处理 API 请求（缺少令牌时返回 401）和页面请求（重定向到 `/login/`）。API 视图使用 DRF 的 `JWTAuthentication` + `IsAuthenticated`。

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

### 目录结构示例

```
apps/
├── project/
│   ├── base.py          # BaseAPIView 根基类
│   └── views.py         # Project 视图
├── worldview/
│   └── views.py         # BaseWorldAPIView + Worldview 视图
├── chapter/
│   └── views.py         # BaseChapterAPIView + Chapter 视图
└── ...
```

### 关键环境变量（`.env`）

- `PG_DB_*` — PostgreSQL 数据库连接
- `REDIS_DB_*` — Redis 缓存连接
- `CELERY_BROKER_URL` — Celery 消息代理（默认复用 Redis DB 1）

### 日志

全程使用 `loguru`（`from loguru import logger`），不使用 Django 标准日志系统。

## 开发规范

详细的开发流程、代码规范、公共方法列表、弹窗系统使用说明等，见 [AGENTS.md](./AGENTS.md)。
