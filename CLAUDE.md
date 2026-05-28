# CLAUDE.md

本文件为 Claude Code (claude.ai/code) 提供在本仓库中工作的指导。

## 项目概述

Novel Agent 是一个 Django 5.2 Web 应用，帮助作者通过聊天式 AI 交互构建小说大纲、卷、章节、角色、世界观设定和时间线。它通过 LangChain 使用兼容 OpenAI 的 LLM API（默认为 DeepSeek）实现所有 AI 功能，使用 Server-Sent Events (SSE) 实现流式响应。

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

- **`llm.py`**: LangChain 的 `ChatOpenAI` 轻量级封装，处理配置合并、流式/非流式调用和重试逻辑
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
| `ai` | LLM 封装 (`llm.py`)、通用提示模板 |
| `user` | 用户 LLM 配置（LLMConfig、UserLLMConfig）、TokenUsageLog、JWT 认证视图 |

### URL 和路由模式

所有视图使用 `apps/<app>/urls.py`，在根目录 `novel_agent/urls.py` 中通过 `path('', include(...))` 包含。前端 HTML 页面作为静态文件从 `templates/` 目录提供，通过主 URL 配置中的独立 `path()` 条目实现。API 端点位于 `/api/` 下。

### 数据模型约定

- **软删除**: 大多数模型使用 `is_deleted` 布尔字段而非硬删除
- **版本控制**: Outline、Volume 和 Chapter 有版本模型，支持每个父模型有多个版本，带有 `is_finalized`、`is_current` 和 `is_deleted` 标志。`version_number=0` 表示"构建/草稿"版本
- **聊天历史**: `OutlineChatHistory`、`WorldviewChatHistory`、`TimelineChatHistory` 存储与父模型关联的角色+内容对

### 认证

自定义 JWT 中间件 (`novel_agent/middleware.py`) 处理 API 请求（缺少令牌时返回 401）和页面请求（重定向到 `/login/`）。API 视图使用 DRF 的 `JWTAuthentication` + `IsAuthenticated`。

### 关键环境变量（`.env`）

- `LLM_API_KEY`、`LLM_MODEL`、`LLM_BASE_URL` — LLM 配置
- `MYSQL_DB_*` — MySQL 数据库连接
- `REDIS_DB_*` — Redis 缓存连接

### 日志

全程使用 `loguru`（`from loguru import logger`），不使用 Django 标准日志系统。

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

1. **文件分离**: HTML、CSS、JavaScript 必须分别写在独立文件中，不允许混写在同一个文件内
2. **暗色风格**: 所有前端页面必须使用暗色主题，颜色配置参考上方的暗色主题规范
3. **样式一致性**: 使用 CSS 变量保持颜色、间距、阴影等视觉效果的一致性
4. **API 请求封装**: 前端所有请求必须使用 `common.js` 中封装的 `api` 对象，统一处理认证、错误和重连逻辑

### API 请求规范

#### 前端 API 使用规范

前端必须使用 `common.js` 中提供的封装方法进行 API 调用：

| 方法 | 说明 | 使用示例 |
|------|------|---------|
| `api.get(url, options)` | GET 请求 | `api.get('/api/projects/')` |
| `api.post(url, body, options)` | POST 请求 | `api.post('/api/outline/', { data })` |
| `api.put(url, body, options)` | PUT 请求 | `api.put('/api/chapter/1/', { data })` |
| `api.delete(url, options)` | DELETE 请求 | `api.delete('/api/note/1/')` |
| `api.streamRequest(url, options)` | 流式请求（聚合返回） | `api.streamRequest('/api/generate/')` |
| `api.streamRequestRaw(url, options, onChunk)` | 流式请求（实时回调） | `api.streamRequestRaw('/api/stream/', {}, callback)` |

#### 环境变量配置规范

1. **敏感配置必须使用环境变量**: 模型 Key、接口地址、超时时间等敏感配置统一写入 `.env` 文件，禁止硬编码到代码中
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

- 检查是否有不必要的 `services.py` 文件
- 确保 `prompts.py` 位于各自的 APP 目录下
- 验证前端文件是否正确分离（HTML/CSS/JS 独立）
- 确认暗色主题变量正确使用
- 检查是否有被删除的注释代码或 logger 语句
- 验证前端是否使用 `common.js` 中的封装 API
- 检查敏感配置是否存在硬编码，应使用环境变量
- 确认请求参数校验逻辑是否完善
- 检查流式响应是否配置了超时机制