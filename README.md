# Novel Agent - 智能小说创作助手

一个基于 Django 5.2 和 LLM 的智能小说创作辅助工具，帮助作者高效完成从世界观构建到章节内容生成的完整创作流程。

## 创作工作流

```
创建项目 → 世界观构建 → 人物清单 → 时间线 → 大纲构建 → 生成卷 → 生成章节
```

## 功能特性

### 创作前准备

1. **用户认证系统** - 支持注册、登录、密码重置、JWT 认证，多用户独立管理项目
2. **项目创建** - 创建小说项目，填写名称和简介，支持 AI 协助生成标题和简介
3. **LLM 配置管理** - 支持多种 LLM 提供商（OpenAI、Anthropic、DeepSeek、通义千问、Ollama 等），不同创作任务可配置不同模型参数
4. **Token 用量统计** - 记录和统计 LLM 调用 Token 消耗

### 创作核心流程

5. **世界观构建** - 结构化世界观设定工具，涵盖基础设定、世界基础、力量体系、种族族群、社会结构、文化人文、历史进程、特殊规则等 8 个维度。支持分层 AI 生成、深度追问完善、一致性校验和冲突自动修复，可导出 Markdown
6. **人物角色管理** - AI 辅助生成角色设定，管理角色的外貌、性格、背景故事、核心动机、阵营等信息，支持 AI 润色优化
7. **时间线管理** - 管理故事时间线事件，支持按章节范围标记事件，AI 生成、合并、拆分、润色事件描述
8. **大纲构建** - 聊天式交互界面，与 AI 对话迭代完善小说大纲，支持多版本管理和版本定稿，支持大纲扩展（世界观、设定体系、历史背景等分类）
9. **卷结构设计** - 基于大纲生成卷的结构和摘要，支持调整卷的数量和内容，支持版本管理
10. **章节概要生成** - 为每一卷生成详细的章节概要（流式输出）
11. **章节内容生成** - 批量生成章节内容，支持连续性参考上下文（流式输出）
12. **章节编辑增强** - 支持章节续写、拆分、校验、内容优化、AI 聊天协作写作

### 辅助工具

13. **随手记** - 创作过程中随时记录灵感，支持 AI 润色整理
14. **自我优化接口** - 预留自我优化/自我审阅功能接口

## 技术栈

- **后端**: Django 5.2 + Django REST Framework
- **数据库**: MySQL 8.0+
- **缓存**: Redis
- **AI**: LangChain + OpenAI-compatible LLM API（默认 DeepSeek）
- **前端**: Django Templates + Bootstrap 5
- **流式输出**: Server-Sent Events (SSE)
- **认证**: JWT（djangorestframework-simplejwt）
- **日志**: Loguru

## 项目结构

```
novel-agent/
├── .env                      # 环境配置文件（从 .env.example 复制）
├── .env.example              # 环境配置模板
├── requirements.txt          # Python 依赖
├── manage.py                 # Django 管理脚本
├── novel_agent/              # 项目配置目录
│   ├── settings.py           # 配置文件
│   ├── urls.py               # 主路由
│   ├── wsgi.py / asgi.py
│   ├── middleware.py          # JWT 认证中间件
│   └── authentication.py     # 自定义 JWT 认证
├── agent/                    # CLI 代理模块
├── apps/
│   ├── user/                 # 用户认证 & LLM 配置 & Token 统计
│   │   ├── models.py         # User, LLMConfig, UserLLMConfig, TokenUsageLog
│   │   ├── views.py          # 登录/注册/重置密码/Token 用量/LLM 配置页面
│   │   └── urls.py
│   ├── project/              # 项目管理
│   │   ├── models.py         # ProjectList
│   │   ├── views.py          # 项目列表/创建/详情页面
│   │   └── urls.py
│   ├── worldview/            # 世界观构建
│   │   ├── models.py         # WorldView, WorldViewChatHistory
│   │   ├── views.py          # 多维度世界观设定/AI 生成/深度追问/一致性校验
│   │   ├── prompts.py        # 世界观生成提示词
│   │   └── urls.py
│   ├── characters/           # 人物角色管理
│   │   ├── models.py         # Character
│   │   ├── views.py          # 角色列表/详情/AI 生成/润色
│   │   ├── prompts.py        # 角色生成提示词
│   │   └── urls.py
│   ├── timeline/             # 时间线管理
│   │   ├── models.py         # TimelineEvent, TimelineChatHistory
│   │   ├── views.py          # 时间线事件/AI 生成/合并/拆分
│   │   ├── prompts.py        # 时间线提示词
│   │   └── urls.py
│   ├── outline/              # 大纲构建
│   │   ├── models.py         # OutlineVersion, OutlineChatHistory, OutlineExpansion
│   │   ├── views.py          # 大纲聊天/版本管理（流式 SSE）
│   │   ├── prompts.py        # 大纲构建提示词
│   │   └── urls.py
│   ├── volume/               # 卷结构设计
│   │   ├── models.py         # VolumeVersion, VolumeList
│   │   ├── views.py          # 卷生成/版本管理
│   │   └── urls.py
│   ├── chapter/              # 章节管理
│   │   ├── models.py         # ChapterVersion, ChapterList
│   │   ├── views.py          # 章节概要/内容生成（流式 SSE）/续写/拆分/校验
│   │   └── urls.py
│   ├── note/                 # 随手记
│   │   ├── models.py         # Note
│   │   ├── views.py          # 笔记管理/AI 润色
│   │   └── urls.py
│   └── ai/                   # AI 服务层
│       ├── llm.py            # LLM 封装（LangChain ChatOpenAI）
│       ├── llm_scenes.py     # 场景化 LLM 配置
│       ├── services.py       # LLMService 中央 AI 服务
│       ├── prompts.py        # 所有提示词模板
│       └── urls.py
├── templates/                # 页面模板
│   ├── index.html            # 首页（项目列表）
│   ├── login.html            # 登录
│   ├── register.html         # 注册
│   ├── reset_password.html   # 重置密码
│   ├── new_project.html      # 创建项目
│   ├── project.html          # 项目详情
│   ├── worldview.html        # 世界观构建
│   ├── worldview_chat.html   # 世界观聊天
│   ├── character.html        # 角色管理
│   ├── timeline.html         # 时间线
│   ├── outline.html          # 大纲构建
│   ├── volume.html           # 卷结构
│   ├── chapter.html          # 章节管理
│   ├── content.html          # 内容管理
│   ├── note.html             # 随手记
│   ├── token.html            # Token 用量
│   └── llm_config.html       # LLM 配置
└── static/                   # 静态文件
    ├── css/                  # 各页面样式
    └── js/                   # 各页面脚本
```

## 安装和配置

### 1. 环境要求

- Python 3.8+
- MySQL 8.0+
- Redis

### 2. 复制环境配置模板

```bash
cp .env.example .env
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

编辑 `.env` 文件，根据实际情况配置以下内容：

```env
# Django 密钥
DJANGO_SECRET_KEY=your_secret_key

# 数据库配置
MYSQL_DB_DATABASE=novel_agent
MYSQL_DB_USER=root
MYSQL_DB_PASSWORD=your_password
MYSQL_DB_HOST=localhost
MYSQL_DB_PORT=3306

# Redis 配置
REDIS_DB_PASSWORD=
REDIS_DB_HOST=localhost
REDIS_DB_PORT=6379
REDIS_DB_DB=0

# LLM 配置（默认使用 DeepSeek）
LLM_API_KEY=your_api_key
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
LLM_TIMEOUT=600
LLM_OUTLINE_TIMEOUT=300
LLM_RETRY=3
LLM_RETRY_INTERVAL=5
```

### 5. 数据库迁移

```bash
python manage.py makemigrations
python manage.py migrate
```

### 6. 创建超级用户

```bash
python manage.py createsuperuser
```

### 7. 运行开发服务器

```bash
python manage.py runserver
```

访问 http://127.0.0.1:8000/ 开始使用。

## 使用说明

### 1. 用户注册与登录

首次使用需注册账号，登录后可创建和管理多个小说项目。

### 2. 创建项目

登录后点击"新建项目"，填写小说名称和简介，也可让 AI 协助生成标题和简介。

### 3. 世界观构建

进入项目后，首先构建故事的世界观。结构化设定涵盖 8 个维度：
- **基础设定** - 世界名称、类型、风格定位
- **世界基础** - 地理、历法、自然规则、平衡机制
- **力量体系** - 能量类型、等级体系、宝物、灵兽
- **种族族群** - 种族分类、特征、关系
- **社会结构** - 朝廷、宗门、阵营、阶层、货币
- **文化人文** - 习俗、语言、日常生活、宗教信仰
- **历史进程** - 远古、近代、危机、命运
- **特殊规则** - 禁忌、秘密、轮回、穿越、系统

支持分层 AI 生成、深度追问完善、一致性校验和冲突自动修复。

### 4. 人物角色管理

AI 辅助生成角色设定，管理角色的：
- 角色类型（主角/配角/反派/路人）
- 外貌特征、性格特点、背景故事
- 核心动机、势力/阵营归属

支持 AI 润色优化角色描述。

### 5. 时间线管理

管理故事的时间线事件，按章节范围标记事件的发生区间。支持 AI 生成事件、合并/拆分事件、AI 辅助润色事件描述，梳理故事脉络。

### 6. 构建大纲

通过聊天式界面与 AI 交互，逐步完善小说大纲。支持多版本管理，可随时保存、加载、定稿不同版本的大纲。支持大纲扩展功能，可将世界观、设定体系、历史背景等详细记录纳入大纲管理。

### 7. 设计卷结构

大纲定稿后，设置卷的数量，让 AI 自动生成各卷的标题和摘要。支持与 AI 对话调整卷结构，支持版本管理。

### 8. 生成章节概要

进入某一卷，让 AI 为该卷生成详细的章节概要（流式输出）。

### 9. 生成章节内容

支持单章生成或批量生成，流式输出实时展示生成进度。批量生成时自动参考上一章内容保持连续性。支持章节续写、拆分、内容优化和 AI 聊天协作写作。

### 10. 随手记

创作过程中随时记录灵感，支持 AI 润色整理，系统化管理创作笔记。

### 11. LLM 配置管理

支持多种 LLM 提供商和模型。不同创作任务（世界观、角色、大纲、卷、章节、内容）可配置不同模型和参数，灵活适配各环节需求。

## 数据模型

### ProjectList（项目）
- `user` - 所属用户
- `title` - 小说名称
- `description` - 小说简介
- `status` - 状态（draft）
- `finalized` - 是否定稿
- `created_at` / `updated_at` - 时间戳

### WorldView（世界观）
- `project` - 关联项目
- `setting` - 基础设定（JSON）
- `foundation` - 世界基础（JSON）
- `power` - 力量体系（JSON）
- `races` - 种族族群（JSON）
- `society` - 社会结构（JSON）
- `culture` - 文化人文（JSON）
- `history` - 历史进程（JSON）
- `special` - 特殊规则（JSON）

### WorldViewChatHistory（世界观聊天历史）
- `worldview` - 关联世界观
- `role` - 角色（user/assistant）
- `content` - 内容
- `is_deleted` - 是否删除

### Character（人物角色）
- `project` - 关联项目
- `name` - 姓名
- `role_type` - 角色类型（主角/配角/反派/路人）
- `gender` - 性别
- `appearance` - 外貌特征
- `personality` - 性格特点
- `backstory` - 背景故事
- `motivation` - 核心动机
- `faction` - 势力/阵营

### TimelineEvent（时间线事件）
- `project` - 关联项目
- `title` - 事件标题
- `description` - 事件描述
- `start_chapter` / `end_chapter` - 起止章节
- `event_order` - 排序

### TimelineChatHistory（时间线聊天历史）
- `project` - 关联项目
- `role` - 角色（user/assistant）
- `content` - 内容

### OutlineVersion（大纲版本）
- `project` - 关联项目
- `version_number` - 版本号（0 表示构建中版本）
- `content` - 大纲内容
- `is_finalized` - 是否定稿
- `is_current` - 是否为当前版本
- `snapshot` - 内容快照

### OutlineChatHistory（大纲聊天历史）
- `outline_version` - 关联大纲版本
- `role` - 角色（user/assistant）
- `content` - 内容

### OutlineExpansion（大纲扩展）
- `outline_version` - 关联大纲版本
- `category` - 扩展分类（世界观/设定体系/历史背景/文化风俗/地点场景/规则设定/情节伏笔）
- `key_name` - 关键词
- `content` - 扩展内容

### VolumeVersion（卷版本）
- `project` - 关联项目
- `outline_version` - 关联大纲版本
- `version_number` - 版本号

### VolumeList（卷）
- `volume_version` - 关联卷版本
- `volume_number` - 卷号
- `title` - 卷标题
- `summary` - 卷摘要

### ChapterVersion（章节版本）
- `volume` - 关联卷
- `version_number` - 版本号
- `is_finalized` - 是否定稿
- `is_current` - 是否为当前版本

### ChapterList（章节）
- `chapter_version` - 关联章节版本
- `chapter_number` - 章节号
- `title` - 章节标题
- `summary` - 章节摘要
- `content` - 章节内容
- `status` - 状态（draft/published/archived）
- `word_count` - 字数

### Note（随手记）
- `user` - 用户
- `project` - 关联项目
- `content` - 笔记内容
- `status` - 状态（未使用/已使用/已发布）

### LLMConfig（LLM 配置）
- `user` - 用户
- `provider` - 提供商（OpenAI/Anthropic/DeepSeek/通义千问/Ollama 等）
- `model_name` - 模型名称
- `api_key` - API 密钥（Base64 编码存储）
- `base_url` - API 地址
- `max_tokens` / `temperature` - 模型参数

### UserLLMConfig（用户任务 LLM 配置）
- `user` - 用户
- `llm_config` - 关联 LLM 配置
- `task_type` - 任务类型（世界观/角色/大纲/卷/章节/内容/默认）
- `max_tokens` / `temperature` - 任务级参数覆盖

### TokenUsageLog（Token 使用日志）
- `user` - 用户
- `project` - 关联项目
- `llm_config` - 使用的 LLM 配置
- `model_name` - 模型名称
- `prompt_tokens` / `completion_tokens` / `total_tokens` - Token 数量
- `cost` - 费用
- `task_type` - 任务类型

## API 接口

### 认证相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/auth/user/` | GET | 获取当前用户信息 |
| `/api/auth/refresh/` | POST | 刷新 JWT Token |

### 项目相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/projects/` | GET | 项目列表 |
| `/api/projects/<id>/` | GET | 项目详情 |
| `/api/projects/<id>/delete/` | POST | 删除项目 |
| `/api/projects/<id>/update/` | POST | 更新项目 |
| `/api/projects/<id>/stats/` | GET | 项目统计 |
| `/api/title/suggest/` | POST | AI 建议标题 |
| `/api/description/suggest/` | POST | AI 建议简介 |

### 世界观相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/worldview/` | POST | 创建/获取世界观 |
| `/api/worldview/<id>/` | GET/PUT | 世界观数据 |
| `/api/worldview/<id>/delete/` | POST | 删除世界观 |
| `/api/worldview/<id>/deepening/questions/` | GET | 深度追问问题 |
| `/api/worldview/<id>/deepening/submit/` | POST | 提交追问回答 |
| `/api/worldview/<id>/deepening/apply/` | POST | 应用追问结果 |
| `/api/worldview/<id>/consistency/check/` | POST | 一致性校验 |
| `/api/worldview/<id>/consistency/fix/` | POST | 自动修复冲突 |
| `/api/worldview/<id>/export/markdown/` | GET | 导出 Markdown |
| `/api/worldview/<id>/chat/stream/` | POST | 世界观聊天（流式 SSE） |
| `/api/worldview/<id>/chat/history/` | GET | 聊天历史 |
| `/api/worldview/<id>/chat/history/delete/` | POST | 删除聊天记录 |

### 角色相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/projects/<id>/characters/` | GET | 角色列表 |
| `/api/projects/<id>/characters/<cid>/` | GET/PUT/DELETE | 角色详情 |
| `/api/projects/<id>/characters/generate/` | POST | AI 生成角色 |
| `/api/projects/<id>/characters/polish/` | POST | AI 润色角色 |

### 时间线相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/projects/<id>/timeline/events/` | GET/POST | 事件列表/创建 |
| `/api/projects/<id>/timeline/events/<eid>/` | GET/PUT/DELETE | 事件详情 |
| `/api/projects/<id>/timeline/chat/` | POST | 时间线聊天 |
| `/api/projects/<id>/timeline/generate/` | POST | AI 生成事件 |
| `/api/projects/<id>/timeline/merge/` | POST | 合并事件 |
| `/api/projects/<id>/timeline/split/` | POST | 拆分事件 |
| `/api/projects/<id>/timeline/optimize-description/` | POST | AI 润色描述 |

### 大纲相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/chat/outline/stream/` | POST | 大纲聊天（流式 SSE） |
| `/api/projects/<id>/outline/versions/` | GET | 大纲版本列表 |
| `/api/projects/<id>/outline/latest/` | GET | 最新大纲内容 |
| `/api/outline/version/<id>/` | GET | 大纲版本详情 |
| `/api/outline/save/` | POST | 保存大纲版本 |
| `/api/outline/finalize/` | POST | 定稿大纲版本 |
| `/api/outline/delete/` | POST | 删除大纲版本 |
| `/api/chat-history/delete/` | POST | 删除聊天记录 |

### 卷相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/volume/generate/` | POST | 生成卷结构 |
| `/api/volume/chat/` | POST | 卷聊天调整 |
| `/api/projects/<id>/volume-versions/` | GET | 卷版本列表 |
| `/api/volume/version/<id>/` | GET | 卷版本详情 |
| `/api/volume/save/` | POST | 保存卷版本 |
| `/api/volume/finalize/` | POST | 定稿卷版本 |
| `/api/volume/delete/` | POST | 删除卷版本 |

### 章节相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/chapter/summaries/generate/stream/` | POST | 生成章节概要（流式 SSE） |
| `/chapter/content/stream/` | POST | 生成章节内容（流式 SSE） |
| `/chapter/save/` | POST | 保存章节 |
| `/chapter/publish/` | POST | 发布章节 |
| `/chapter/archive/` | POST | 归档章节 |
| `/chapter/verify/` | POST | 校验章节 |
| `/chapter/split/` | POST | 拆分章节 |
| `/chapter/continue/` | POST | 续写章节 |
| `/chapter/content/optimize/` | POST | 优化章节内容 |
| `/chapter/versions/<id>/load/` | GET | 加载章节版本列表 |
| `/chapter/version/current/` | POST | 设置当前版本 |
| `/ai/chat/chapter/write/` | POST | AI 聊天协作写作 |

### 随手记相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/projects/<id>/notes/` | GET/POST | 笔记列表/创建 |
| `/api/projects/<id>/notes/<nid>/` | GET/PUT/DELETE | 笔记详情 |
| `/api/projects/<id>/notes/<nid>/polish/` | POST | AI 润色笔记 |

### Token 用量相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/token-usage/today/` | GET | 今日 Token 用量 |
| `/api/token-usage/stats/` | GET | Token 用量统计 |

### LLM 配置相关
| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/llm-config/` | GET/POST | LLM 配置列表/创建 |

## 开发计划

- [ ] 实现自我优化/自我审阅功能
- [ ] 添加更多的自定义选项
- [ ] 添加导出功能（Word/EPUB/PDF）
- [ ] 添加版本管理功能
- [ ] 添加协作功能
- [ ] 连续性检查
- [ ] 章节冲突检查

