# Novel Agent - 智能小说创作助手

一个基于 Django 和 LLM 的智能小说创作辅助工具，帮助作者高效构建小说大纲、设计卷结构、生成章节概要和内容。

## 功能特性

1. **大纲构建** - 聊天式交互界面，根据用户输入智能生成和优化小说大纲
2. **卷结构设计** - 基于大纲生成卷的结构和摘要，支持调整卷的数量和内容
3. **章节概要生成** - 为每一卷生成详细的章节概要
4. **章节内容生成** - 批量生成章节内容，支持连续性和参考上下文（流式输出）
5. **自我优化接口** - 预留自我优化/自我审阅功能接口

## 技术栈

- **后端**: Django 5.2 + Django REST Framework
- **数据库**: MySQL
- **缓存**: Redis
- **AI**: LangChain + OpenAI-compatible LLM API
- **前端**: Django Templates + Bootstrap 5
- **流式输出**: Server-Sent Events (SSE)

## 项目结构

```
novel-agent/
├── .env                      # 环境配置文件
├── requirements.txt          # Python依赖
├── manage.py                 # Django管理脚本
├── novel_agent/              # 项目配置目录
│   ├── __init__.py
│   ├── settings.py           # 配置文件
│   ├── urls.py               # 主路由
│   └── wsgi.py
├── apps/
│   ├── core/                 # 核心应用
│   │   ├── models.py         # 数据模型
│   │   ├── views.py          # 页面视图
│   │   ├── urls.py           # 路由
│   │   └── admin.py          # 后台管理
│   └── ai/                   # AI应用
│       ├── prompts.py        # 提示词管理
│       ├── services.py       # LLM服务
│       ├── views.py          # API视图
│       └── urls.py           # API路由
├── templates/                # 模板目录
│   ├── base.html
│   └── core/                 # 页面模板
└── static/                   # 静态文件
```

## 安装和配置

### 1. 环境要求

- Python 3.8+
- MySQL 8.0+
- Redis

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置数据库

确保 `.env` 文件中的数据库配置正确：

```env
# 数据库配置
MYSQL_DB_DATABASE=novel_db
MYSQL_DB_USER=root
MYSQL_DB_PASSWORD=your_password
MYSQL_DB_HOST=localhost
MYSQL_DB_PORT=3306
```

### 4. 配置Redis

```env
# Redis配置
REDIS_DB_PASSWORD=your_redis_password
REDIS_DB_HOST=localhost
REDIS_DB_PORT=6379
REDIS_DB_DB=0
```

### 5. 配置LLM

```env
# LLM配置
LLM_API_KEY=your_api_key
LLM_MODEL=deepseek-v4-flash
LLM_BASE_URL=https://api.deepseek.com
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
```

### 6. 数据库迁移

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. 创建超级用户

```bash
python manage.py createsuperuser
```

### 8. 运行开发服务器

```bash
python manage.py runserver
```

访问 http://127.0.0.1:8000/ 开始使用。

## 使用说明

### 1. 创建项目

在首页点击"创建新项目"，填写小说名称和简介。

### 2. 构建大纲

进入项目后，点击"构建大纲"，通过聊天式界面与AI交互，完善小说大纲。

### 3. 设计卷结构

大纲完成后，点击"设计卷结构"，设置卷的数量，让AI自动生成各卷的内容规划。

### 4. 生成章节概要

进入某一卷，点击"AI生成章节"，让AI为这一卷生成详细的章节概要。

### 5. 生成章节内容

点击"生成内容"，可以单章生成或批量生成。批量生成时会自动使用上一章作为参考，保持内容连续性。

## 提示词管理

所有提示词都在 `apps/ai/prompts.py` 文件中，可以根据需要进行调整：

- `OUTLINE_SYSTEM_PROMPT` - 大纲构建的系统提示
- `OUTLINE_BUILD_PROMPT` - 初始大纲构建提示
- `OUTLINE_OPTIMIZE_PROMPT` - 大纲优化提示
- `VOLUME_GENERATION_PROMPT` - 卷生成提示
- `CHAPTER_SUMMARY_PROMPT` - 章节概要生成提示
- `CHAPTER_CONTENT_PROMPT` - 章节内容生成提示
- `SELF_OPTIMIZE_PROMPT` - 自我优化提示

## 数据模型

### Project（项目）
- `title` - 小说名称
- `description` - 小说简介
- `created_at` - 创建时间
- `updated_at` - 更新时间

### OutlineMessage（大纲消息）
- `project` - 关联项目
- `role` - 角色（user/assistant）
- `content` - 内容
- `created_at` - 创建时间

### Volume（卷）
- `project` - 关联项目
- `volume_number` - 卷号
- `title` - 卷标题
- `summary` - 卷摘要
- `created_at` - 创建时间

### Chapter（章节）
- `volume` - 关联卷
- `chapter_number` - 章节号
- `title` - 章节标题
- `summary` - 章节摘要
- `content` - 章节内容
- `created_at` - 创建时间
- `updated_at` - 更新时间

## API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/outline/stream/` | POST | 大纲生成流式接口 |
| `/api/volumes/generate/` | POST | 生成卷结构 |
| `/api/chapters/summaries/` | POST | 生成章节概要 |
| `/api/chapters/content/stream/` | POST | 章节内容生成流式接口 |
| `/api/volume/<id>/update/` | POST | 更新卷信息 |
| `/api/chapter/<id>/update/` | POST | 更新章节信息 |

## 开发计划

- [ ] 实现自我优化/自我审阅功能
- [ ] 添加更多的自定义选项
- [ ] 支持多语言
- [ ] 添加导出功能（Word/EPUB/PDF）
- [ ] 添加用户系统和数据持久化
- [ ] 添加版本管理功能
- [ ] 添加协作功能

## 许可证

MIT License
