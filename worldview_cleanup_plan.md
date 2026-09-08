# Worldview 旧版（表单填充）代码清理计划

## 背景

Worldview 模块存在两套并行实现：

| 维度 | 旧版（表单填充） | 新版（Markdown 对话） |
|------|-----------------|---------------------|
| 路由 | `/worldview` | `/worldview/chat` |
| 数据模型 | `WorldView`（10 个 JSONField 分层） | `WorldviewDoc`（Markdown 整体存储） |
| 交互方式 | 表单逐字段填写 + AI 辅助润色 | 对话式 AI 增量构建 |
| 版本管理 | 无 | `WorldviewDocVersion`（独立版本表） |
| 后端视图 | `views.py` | `views_doc.py` |
| 提示词 | `prompts.py` | `prompts_doc.py` |

新版已稳定运行，本次清理目标：
1. 移除旧版的表单填充体系
2. 去掉新版的 `Doc` 后缀，统一使用旧版简洁命名
3. **合并版本表**：`WorldviewDocVersion` 不再独立建表，版本内嵌到主模型（FK + (project, version) UNIQUE）
4. **去掉 `chat` 字段**：URL 路径、视图类名、API 方法名、变量名中不再出现 `chat`

### 设计决策

**模型：FK + (project, version) UNIQUE，单表**

一个项目最多十几个版本、一个用户最多十几个项目、未来最多不超过 10 个用户，总行数不超过 2000 行，无需独立版本表。每个版本就是主表的一行，通过 `WorldView.objects.filter(project=project, is_deleted=False).order_by('-version').first()` 取当前版本。

**去掉 `chat` 命名**：世界观本身就是通过对话构建的，`chat` 是多余的修饰词。

---

## 命名对照表

### 一、后端模型

| 类别 | 旧版名称（删除） | 新版名称（当前） | 最终名称 |
|------|-----------------|-----------------|---------|
| 主模型 | `WorldView` | `WorldviewDoc` | `WorldView` |
| 主模型 db_table | `worldview` | `worldview_doc` | `worldview` |
| 主模型 project 字段 | OneToOneField | OneToOneField | **ForeignKey**（一对多） |
| 主模型唯一约束 | （隐式 OneToOne） | （隐式 OneToOne） | **`UniqueConstraint(project, version)`** |
| 版本模型 | （无） | `WorldviewDocVersion` | **删除**（合并到主模型） |
| 版本模型 db_table | （无） | `worldview_doc_version` | **删除** |
| 聊天历史模型 | `WorldViewChatHistory` | `WorldviewDocChatHistory` | `WorldViewChatHistory` |
| 聊天历史 db_table | `worldview_chat_history` | `worldview_doc_chat_history` | `worldview_chat_history` |
| 聊天历史 FK 字段 | `worldview` → WorldView | `doc` → WorldviewDoc | `worldview` → WorldView（指向具体版本行） |

**最终 WorldView 模型字段：**

```python
class WorldView(models.Model):
    project = models.ForeignKey('project.ProjectList', on_delete=models.CASCADE, related_name='worldviews')
    version = models.PositiveIntegerField(default=1)
    genre = models.CharField(max_length=20, choices=GENRE_CHOICES, default='general')
    title = models.CharField(max_length=200, blank=True, default='')
    content = models.TextField(blank=True, default='')
    faction_index = models.JSONField(default=list, blank=True)
    is_finalized = models.BooleanField(default=False)       # 从版本表迁移
    is_deleted = models.BooleanField(default=False)
    last_question = models.TextField(blank=True, default='')  # 从版本表迁移
    last_options = models.JSONField(default=list, blank=True) # 从版本表迁移
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'worldview'
        constraints = [
            models.UniqueConstraint(fields=['project', 'version'], name='uq_worldview_project_version'),
        ]
        ordering = ['-version']
```

> 取当前版本：`WorldView.objects.filter(project=project, is_deleted=False).first()`（依赖 ordering）
> 不需要 `is_current` 字段，最新版本由 version 排序隐式确定。

**最终 WorldViewChatHistory 模型字段：**

```python
class WorldViewChatHistory(models.Model):
    worldview = models.ForeignKey(WorldView, on_delete=models.CASCADE, related_name='chat_histories')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    options = models.JSONField(default=list, blank=True)
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'worldview_chat_history'
```

> 保留 `chat` 在表名和模型名中，与 `WorldView` 主表区分，避免混淆。

### 二、后端视图类

| 旧版类名（删除） | 新版类名（当前） | 最终类名 |
|-----------------|-----------------|---------|
| `BaseWorldAPIView` | `BaseWorldAPIView`（复用） | `BaseWorldAPIView`（不变） |
| `ApiWorldviewDataView` | — | 删除 |
| `ApiWorldviewDeepeningQuestionsView` | — | 删除 |
| `ApiWorldviewDeepeningSubmitView` | — | 删除 |
| `ApiWorldviewDeepeningApplyView` | — | 删除 |
| `ApiWorldviewConsistencyView` | — | 删除 |
| `ApiWorldviewConsistencyFixView` | — | 删除 |
| `ApiWorldviewOptimizeView` | — | 删除 |
| `ApiWorldviewLayerView` | — | 删除 |
| `ApiWorldviewExportMarkdownView` | — | 删除 |
| `ApiWorldviewChatOpenView` | `ApiWorldviewDocChatOpenView` | `ApiWorldviewOpenView` |
| `ApiWorldviewChatStreamView` | `ApiWorldviewDocChatStreamView` | `ApiWorldviewStreamView` |
| — | `ApiWorldviewDocView` | `ApiWorldviewView` |
| — | `ApiWorldviewDocFactionExtractView` | `ApiWorldviewFactionExtractView` |
| — | `ApiWorldviewDocChatHistoryView` | `ApiWorldviewChatHistoryView` |
| — | `ApiWorldviewDocVersionsView` | `ApiWorldviewVersionsView` |
| — | `ApiWorldviewDocVersionLoadView` | `ApiWorldviewVersionLoadView` |
| — | `ApiWorldviewDocVersionSaveView` | `ApiWorldviewVersionSaveView` |
| — | `ApiWorldviewDocVersionUpdateView` | `ApiWorldviewVersionUpdateView` |
| — | `ApiWorldviewDocVersionLockView` | `ApiWorldviewVersionLockView` |
| — | `ApiWorldviewDocVersionUnlockView` | `ApiWorldviewVersionUnlockView` |
| — | `ApiWorldviewDocVersionDeleteView` | `ApiWorldviewVersionDeleteView` |

### 三、后端文件名

| 旧版文件（删除） | 新版文件（当前） | 最终文件 |
|-----------------|-----------------|---------|
| `views.py` | `views_doc.py` | `views.py` |
| `prompts.py` | `prompts_doc.py` | `prompts.py` |
| `serializers.py` | — | 删除 |
| `models.py`（含旧模型） | `models.py`（含新模型） | `models.py`（仅保留新模型，重命名） |
| `utils.py` | `utils.py` | `utils.py`（保留 SSE 工具，重写 get_worldview_context） |
| `urls.py`（含旧路由） | `urls.py`（含新旧路由） | `urls.py`（仅保留新版路由） |
| `admin.py` | `admin.py` | `admin.py`（更新注册） |

### 四、后端 URL 路径

| 旧版路径（删除） | 新版路径（当前） | 最终路径 |
|-----------------|-----------------|---------|
| `worldviews/` | — | 删除 |
| `worldviews/<pk>/` | — | 删除 |
| `worldviews/<pk>/layer/<layer>/` | — | 删除 |
| `worldviews/<pk>/optimize/<layer>/` | — | 删除 |
| `worldviews/<pk>/deepening/questions/` | — | 删除 |
| `worldviews/<pk>/deepening/submit/` | — | 删除 |
| `worldviews/<pk>/deepening/apply/` | — | 删除 |
| `worldviews/<pk>/consistency/check/` | — | 删除 |
| `worldviews/<pk>/consistency/fix/` | — | 删除 |
| `worldviews/export/markdown/` | — | 删除 |
| `worldviews/chat/open/` | `worldview-doc/chat/open/` | `worldviews/open/` |
| `worldviews/chat/stream/` | `worldview-doc/chat/stream/` | `worldviews/stream/` |
| — | `worldview-doc/` | `worldviews/` |
| — | `worldview-doc/chat/history/` | `worldviews/chat/history/` |
| — | `worldview-doc/factions/extract/` | `worldviews/factions/extract/` |
| — | `worldview-doc/versions/` | `worldviews/`（GET 列表） |
| — | `worldview-doc/versions/save/` | `worldviews/save/` |
| — | `worldview-doc/versions/update/` | `worldviews/update/` |
| — | `worldview-doc/versions/<id>/load/` | `worldviews/<id>/`（GET 加载） |
| — | `worldview-doc/versions/<id>/lock/` | `worldviews/<id>/lock/` |
| — | `worldview-doc/versions/<id>/unlock/` | `worldviews/<id>/unlock/` |
| — | `worldview-doc/versions/<id>/delete/` | `worldviews/<id>/delete/` |

### 五、后端提示词常量（prompts_doc.py → prompts.py）

| 旧版常量（删除） | 新版常量（当前） | 最终常量 |
|-----------------|-----------------|---------|
| `WORLDVIEW_STRUCTURE` | — | 删除 |
| `WORLDVIEW_BUILD_SYSTEM_PROMPT` | — | 删除 |
| `WORLDVIEW_BUILD_USER_PROMPT` | — | 删除 |
| `WORLDVIEW_CHAT_SYSTEM_PROMPT` | — | 删除 |
| `WORLDVIEW_CHAT_USER_PROMPT` | — | 删除 |
| `WORLDVIEW_GAP_DETECTION_*` (6个) | — | 删除 |
| `WORLDVIEW_MACRO_CONSISTENCY_*` (4个) | — | 删除 |
| `WORLDVIEW_INIT_QUESTION_*` (2个) | — | 删除 |
| — | `GENRE_GUIDES` | `GENRE_GUIDES`（不变） |
| — | `WV_DOC_SYSTEM_PROMPT` | `WORLDVIEW_SYSTEM_PROMPT` |
| — | `WV_DOC_BUILD_PROMPT` | `WORLDVIEW_BUILD_PROMPT` |
| — | `WV_DOC_JSON_REPAIR_PROMPT` | `WORLDVIEW_JSON_REPAIR_PROMPT` |
| — | `DOC_WELCOME_PROMPT` | `WORLDVIEW_WELCOME_PROMPT` |
| — | `DOC_FACTION_EXTRACT_PROMPT` | `WORLDVIEW_FACTION_EXTRACT_PROMPT` |
| — | `GENRE_CHOICES` / `GENRE_LABELS` | 不变 |

### 六、后端 Token Usage category

| 旧版 category（保留历史） | 新版 category（当前） | 最终 category |
|--------------------------|---------------------|--------------|
| `worldview_deepen` | — | 保留历史，不再新增 |
| `worldview_deepen_integrate` | — | 保留历史，不再新增 |
| `worldview_consistency` | — | 保留历史，不再新增 |
| `worldview_consistency_fix` | — | 保留历史，不再新增 |
| `worldview_{layer}_field` (10种) | — | 保留历史，不再新增 |
| `worldview_init_question` | — | 保留历史，不再新增 |
| `worldview_chat` | — | 保留历史，不再新增 |
| — | `worldview_doc_welcome` | `worldview_welcome` |
| — | `worldview_doc_build` | `worldview_build` |
| — | `worldview_doc_faction_extract` | `worldview_faction_extract` |

### 七、前端 API 对象与方法

| 旧版（删除） | 新版（当前） | 最终 |
|-------------|------------|------|
| `worldviewApi` 对象 | `worldviewDocApi` 对象 | `worldviewApi` |
| `worldviewApi.get()` | `worldviewDocApi.get()` | `worldviewApi.get()` |
| `worldviewApi.getById()` | — | 删除 |
| `worldviewApi.generateDeepeningQuestions()` | — | 删除 |
| `worldviewApi.submitDeepening()` | — | 删除 |
| `worldviewApi.applyDeepening()` | — | 删除 |
| `worldviewApi.checkConsistency()` | — | 删除 |
| `worldviewApi.fixConsistency()` | — | 删除 |
| `worldviewApi.getLayer()` | — | 删除 |
| `worldviewApi.updateLayer()` | — | 删除 |
| `worldviewApi.exportMarkdown()` | — | 删除 |
| `worldviewApi.openChat()` | `worldviewDocApi.openChat()` | `worldviewApi.open()` |
| — | `worldviewDocApi.save()` | `worldviewApi.save()` |
| — | `worldviewDocApi.getChatHistory()` | `worldviewApi.getChatHistory()` |
| — | `worldviewDocApi.extractFactions()` | `worldviewApi.extractFactions()` |
| — | `worldviewDocApi.getVersions()` | `worldviewApi.getList()` |
| — | `worldviewDocApi.loadVersion()` | `worldviewApi.get(id)` |
| — | `worldviewDocApi.saveVersion()` | `worldviewApi.saveVersion()` |
| — | `worldviewDocApi.updateVersion()` | `worldviewApi.updateVersion()` |
| — | `worldviewDocApi.lockVersion()` | `worldviewApi.lock(id)` |
| — | `worldviewDocApi.unlockVersion()` | `worldviewApi.unlock(id)` |
| — | `worldviewDocApi.deleteVersion()` | `worldviewApi.remove(id)` |

### 八、前端 SSE URL 构建器

| 旧版（删除） | 新版（当前） | 最终 |
|-------------|------------|------|
| `worldviewUrls.optimize()` | — | 删除 |
| `worldviewUrls.chatStream()` | `worldviewUrls.docChatStream()` | `worldviewUrls.stream()` |

### 九、前端路由

| 旧版（删除） | 新版（当前） | 最终 |
|-------------|------------|------|
| `path: 'worldview'` / `name: 'Worldview'` | `path: 'worldview/chat'` / `name: 'WorldviewChat'` | `path: 'worldview'` / `name: 'Worldview'` |

### 十、前端页面组件文件

| 旧版（删除） | 新版（当前） | 最终 |
|-------------|------------|------|
| `WorldviewView.vue`（表单版） | `WorldviewChatView.vue`（聊天版） | `WorldviewView.vue`（重命名） |
| `components/WorldviewSuggestionList.vue` | — | 删除 |

### 十一、前端变量名/函数名中的 chat 清理

| 当前名称 | 最终名称 | 所在文件 |
|---------|---------|---------|
| `worldviewDocApi.openChat()` | `worldviewApi.open()` | `api/worldview.js` |
| `worldviewDocApi.getChatHistory()` | `worldviewApi.getChatHistory()` | `api/worldview.js` |
| `worldviewUrls.docChatStream()` | `worldviewUrls.stream()` | `api/worldview.js` |
| `goChat()` | `goBuild()` 或 `goWorldview()` | `WorldviewChatView.vue` |
| `openChat()` | `openSession()` | `WorldviewChatView.vue` |

---

## 一、前端清理

### 1.1 删除旧版页面组件

| 文件 | 行数 | 说明 |
|------|------|------|
| `frontend/src/views/worldview/WorldviewView.vue` | 1548 行 | **整文件删除** — 旧版表单填充页面 |
| `frontend/src/views/worldview/components/WorldviewSuggestionList.vue` | 179 行 | **整文件删除** — 旧版缺口/一致性修改建议组件 |

### 1.2 清理 API 模块

**文件**: `frontend/src/api/worldview.js`

需要删除的部分：

| 行号 | 内容 | 说明 |
|------|------|------|
| 9-12 | `worldviewUrls.optimize()` | SSE URL — 旧版分层 AI 润色 |
| 11 | `worldviewUrls.chatStream()` | SSE URL — 旧版聊天流 |
| 56-96 | 整个 `worldviewApi` 对象 | 旧版结构化 API |

保留并重命名的部分：

| 行号 | 当前 | 最终 |
|------|------|------|
| 13 | `docChatStream: (pid) => .../worldview-doc/chat/stream/` | `stream: (pid) => .../worldviews/stream/` |
| 30 | `worldviewDocApi` 对象 | `worldviewApi` 对象，方法名去掉 chat |
| 38 | `openChat: ...worldview-doc/chat/open/` | `open: .../worldviews/open/` |
| 41 | `getChatHistory: ...worldview-doc/chat/history/` | `getHistory: .../worldviews/history/` |
| 其余 | URL 中 `worldview-doc/` → `worldviews/` | 逐条替换 |

### 1.3 清理路由配置

**文件**: `frontend/src/router/index.js`

- 删除旧版路由定义（`path: 'worldview', name: 'Worldview', component: WorldviewView`）
- 删除对应的 `import WorldviewView`
- 将新版路由改为 `path: 'worldview'`, `name: 'Worldview'`

### 1.4 清理项目首页导航

**文件**: `frontend/src/views/project/ProjectHomeView.vue`

- 删除旧版入口 `{ name: 'Worldview', label: '世界观', ... }`
- 更新新版入口：`name: 'Worldview'`, `label: '世界观'`

### 1.5 重命名页面组件

将 `WorldviewChatView.vue` 重命名为 `WorldviewView.vue`，内部变量名中的 `chat` 清理：
- `goChat` → `goBuild`
- `openChat` / `handleOpenChat` → `openSession`
- `ChatPanel` 等公共组件引用保持不变（它们是通用组件）

### 1.6 清理 Token 用量页面（可选）

**文件**: `frontend/src/views/home/TokenUsageView.vue`

- 第 397-398 行的旧版 category 标签保留历史数据展示，不再新增

---

## 二、后端清理

### 2.1 删除旧版视图

**文件**: `apps/worldview/views.py`（**整文件约 1539 行，整文件删除**）

### 2.2 删除旧版提示词

**文件**: `apps/worldview/prompts.py`（**整文件删除**）

### 2.3 删除旧版序列化器

**文件**: `apps/worldview/serializers.py`（**整文件删除**）

### 2.4 清理路由

**文件**: `apps/worldview/urls.py`

删除所有旧版路由，将新版路由路径从 `worldview-doc/` 改为 `worldviews/`，去掉 `chat/` 层级。

最终路由表：

```python
urlpatterns = [
    # 文档 CRUD + 版本列表
    path('api/projects/<int:project_id>/worldviews/', ApiWorldviewView.as_view()),
    # 版本操作（save/update 无 id，需排在 <int:pk>/ 之前）
    path('api/projects/<int:project_id>/worldviews/save/', ApiWorldviewVersionSaveView.as_view()),
    path('api/projects/<int:project_id>/worldviews/update/', ApiWorldviewVersionUpdateView.as_view()),
    # 单个版本操作
    path('api/projects/<int:project_id>/worldviews/<int:pk>/', ApiWorldviewVersionLoadView.as_view()),
    path('api/projects/<int:project_id>/worldviews/<int:pk>/lock/', ApiWorldviewVersionLockView.as_view()),
    path('api/projects/<int:project_id>/worldviews/<int:pk>/unlock/', ApiWorldviewVersionUnlockView.as_view()),
    path('api/projects/<int:project_id>/worldviews/<int:pk>/delete/', ApiWorldviewVersionDeleteView.as_view()),
    # 会话
    path('api/projects/<int:project_id>/worldviews/open/', ApiWorldviewOpenView.as_view()),
    path('api/projects/<int:project_id>/worldviews/stream/', ApiWorldviewStreamView.as_view()),
    path('api/projects/<int:project_id>/worldviews/chat/history/', ApiWorldviewChatHistoryView.as_view()),
    # 阵营提取
    path('api/projects/<int:project_id>/worldviews/factions/extract/', ApiWorldviewFactionExtractView.as_view()),
]
```

### 2.5 模型重构

**文件**: `apps/worldview/models.py`

**删除的模型：**
- `WorldView`（旧版，10 个 JSONField）— 待依赖迁移后删除
- `WorldViewChatHistory`（旧版）— 无外部引用，可直接删除
- `WorldviewDocVersion`（独立版本表）— 合并到主模型

**新建/重构的模型：**
- `WorldView`（从 WorldviewDoc 重构）：
  - `project` 改为 `ForeignKey`（一对多）
  - 新增 `UniqueConstraint(project, version)`
  - 合并版本表字段：`is_finalized`、`last_question`、`last_options`、`is_current`
  - `related_name='worldviews'`（复数，因为是一对多）
- `WorldViewChatHistory`（从 WorldviewDocChatHistory 重构）：
  - FK 改为指向 `WorldView`（具体版本行）
  - 去掉 `version` FK（不再需要，直接通过 worldview FK 定位版本）
  - `related_name='chat_histories'`

### 2.6 清理 admin.py

更新注册为新模型。

### 2.7 清理 views_doc.py 中的 chat 命名

**文件**: `apps/worldview/views_doc.py`（最终重命名为 `views.py`）

| 当前名称 | 最终名称 |
|---------|---------|
| `ApiWorldviewDocChatOpenView` | `ApiWorldviewOpenView` |
| `ApiWorldviewDocChatStreamView` | `ApiWorldviewStreamView` |
| `ApiWorldviewDocChatHistoryView` | `ApiWorldviewChatHistoryView` |
| `WorldviewDocChatHistory` 引用 | `WorldViewChatHistory` |
| `WorldviewDocVersion` 引用 | `WorldView`（查询具体版本行） |
| `worldview_doc_welcome` (token category) | `worldview_welcome` |
| `worldview_doc_build` (LLM scene) | `worldview_build` |
| `worldview_doc_chat` (LLM scene) | `worldview_chat` |

### 2.8 清理 utils.py 中的 chat 命名

**文件**: `apps/worldview/utils.py`

- `get_worldview_context(project)` 函数：改为查询新版 `WorldView` 模型，取当前版本的 Markdown content

---

## 三、跨模块依赖迁移

### 3.1 `utils/helpers.py` — `format_worldview_context()`

| 行号 | 说明 |
|------|------|
| 130-200+ | 直接查询旧版 `WorldView` 模型，遍历 10 个 JSONField |

**迁移方案**: 改为 `WorldView.objects.filter(project=project, is_deleted=False).order_by('-version').first()`，返回 Markdown content。

### 3.2 `apps/project/base.py` — `get_worldview_context()`

| 行号 | 说明 |
|------|------|
| 46-49 | 委托给 `helpers.format_worldview_context` |
| 64 | `get_project_context` 中调用 |
| 103 | `get_knowledge_context` 降级逻辑中调用 |

**迁移方案**: 修改 `helpers.format_worldview_context` 即可，base.py 无需改动。

### 3.3 `apps/knowledge/` — 世界观索引

| 文件 | 行号 | 说明 |
|------|------|------|
| `signals.py` | 54-61 | 监听旧版 `WorldView` 的 `post_save` / `post_delete` |
| `tasks.py` | 68-88 | `index_worldview_task` / `delete_worldview_task` |
| `indexer.py` | 66-112 | `index_worldview()` 按 8 类分条索引 |
| `indexer.py` | 498-503 | `rebuild_project` 中索引世界观 |

**迁移方案**: 
- 信号改为监听新 `WorldView` 模型，仅对 `is_current=True` 的行触发索引
- `index_worldview()` 改为索引 Markdown 全文（按 chunk 分块），替换旧版 8 类分条
- 更新 tasks

### 3.4 `apps/characters/views.py` — `project.worldview` 反向引用

| 行号 | 说明 |
|------|------|
| 86 | `wv = project.worldview` |

**迁移方案**: 改为 `project.worldviews.filter(is_deleted=False).order_by('-version').first()`。

### 3.5 `apps/timeline/views.py` — `get_worldview_context` 导入

| 行号 | 说明 |
|------|------|
| 7 | `from apps.worldview.utils import get_worldview_context` |
| 42, 131, 272 | 直接访问旧版 JSON 字段 |

**迁移方案**: `get_worldview_context` 返回值改为 `(worldview_obj, content_text)` 格式，timeline 调用方适配。

### 3.6 `apps/project/views.py` — `WorldView` 查询

| 行号 | 说明 |
|------|------|
| 21 | `from apps.worldview.models import WorldView, WorldviewDoc` |
| 722 | `WorldView.objects.filter(project=project)` |

**迁移方案**: 改为 `WorldView.objects.filter(project=project, is_deleted=False).order_by('-version').first()`。

---

## 四、清理后的文件状态

### 删除的文件（5 个）

| 文件 | 行数 |
|------|------|
| `apps/worldview/views.py`（旧版） | ~1539 |
| `apps/worldview/prompts.py`（旧版） | ~770 |
| `apps/worldview/serializers.py`（旧版） | ~330 |
| `frontend/src/views/worldview/WorldviewView.vue`（旧版表单） | 1548 |
| `frontend/src/views/worldview/components/WorldviewSuggestionList.vue` | 179 |

### 重命名的文件

| 原文件 | 新文件 |
|--------|--------|
| `views_doc.py` | `views.py` |
| `prompts_doc.py` | `prompts.py` |
| `WorldviewChatView.vue` | `WorldviewView.vue` |

### 修改的文件（~10 个）

| 文件 | 改动内容 |
|------|---------|
| `frontend/src/api/worldview.js` | 重写：worldviewDocApi → worldviewApi，去掉 chat，URL 换路径 |
| `frontend/src/router/index.js` | 删除旧版路由，新版改路径 |
| `frontend/src/views/project/ProjectHomeView.vue` | 删除旧版入口，更新新版入口 |
| `apps/worldview/urls.py` | 重写：仅保留新版路由，路径改为 worldviews/ |
| `apps/worldview/models.py` | 删除旧模型+版本表，重构新模型 |
| `apps/worldview/utils.py` | 重写 get_worldview_context |
| `apps/worldview/admin.py` | 更新注册 |
| `utils/helpers.py` | format_worldview_context 适配新模型 |
| `apps/knowledge/` (signals/tasks/indexer) | 适配新模型，改索引方式 |
| `apps/characters/views.py` | 替换 project.worldview 引用 |
| `apps/timeline/views.py` | 适配新数据格式 |
| `apps/project/views.py` | 替换 WorldView 查询 |

---

## 五、执行计划

### 第一步：前端页面清理（低风险）

**完成内容：**

| 序号 | 操作 | 文件 | 说明 |
|------|------|------|------|
| 1.1 | 删除 | `frontend/src/views/worldview/WorldviewView.vue` | 旧版表单页面 |
| 1.2 | 删除 | `frontend/src/views/worldview/components/WorldviewSuggestionList.vue` | 旧版建议组件 |
| 1.3 | 重命名 | `WorldviewChatView.vue` → `WorldviewView.vue` | 新版页面接管 |
| 1.4 | 重写 | `frontend/src/api/worldview.js` | worldviewDocApi → worldviewApi，去掉 chat，URL 改为 worldviews/ |
| 1.5 | 修改 | `frontend/src/router/index.js` | 删除旧版路由，新版改为 `path: 'worldview'` / `name: 'Worldview'` |
| 1.6 | 修改 | `frontend/src/views/project/ProjectHomeView.vue` | 删除旧版入口，更新新版入口 name |
| 1.7 | 修改 | `WorldviewView.vue` 内部 | `goChat` → `goWorldview`，`openChat` → `openSession` |

**浏览器检查清单：**

| 检查项 | 操作步骤 | 预期结果 |
|--------|---------|---------|
| 页面加载 | 访问项目首页，点击"世界观"入口 | 跳转到 `/worldview`，页面正常加载 |
| 会话打开 | 点击"开始构建"或"继续"按钮 | 调用 `worldviews/open/`，返回欢迎消息 |
| 流式对话 | 输入内容发送 | 调用 `worldviews/stream/`，流式返回 AI 回复 |
| 聊天历史 | 关闭会话后重新打开 | 调用 `worldviews/chat/history/`，历史消息正确加载 |
| 版本列表 | 点击版本管理 | 调用 `worldviews/`（GET），版本列表显示 |
| 版本保存 | 保存当前版本 | 调用 `worldviews/save/`，新版本出现在列表中 |
| 版本加载 | 点击某个版本 | 调用 `worldviews/<id>/`（GET），内容切换 |
| 版本锁定/解锁 | 点击锁定按钮 | 调用 `worldviews/<id>/lock/`，状态切换 |
| 阵营提取 | 使用阵营提取功能 | 调用 `worldviews/factions/extract/`，正常返回 |
| 页面导航 | 从世界观页面跳转到其他页面再返回 | 无报错，状态正确 |
| 浏览器控制台 | 全程观察 | 无 404、无 JS 报错、无 undefined 错误 |

---

### 第二步：后端视图/路由/提示词清理（中风险）

**完成内容：**

| 序号 | 操作 | 文件 | 说明 |
|------|------|------|------|
| 2.1 | 删除 | `apps/worldview/views.py`（旧版） | 整文件删除 ~1539 行 |
| 2.2 | 删除 | `apps/worldview/prompts.py`（旧版） | 整文件删除 ~770 行 |
| 2.3 | 删除 | `apps/worldview/serializers.py` | 整文件删除 ~330 行 |
| 2.4 | 重命名 | `views_doc.py` → `views.py` | 新版视图接管 |
| 2.5 | 重命名 | `prompts_doc.py` → `prompts.py` | 新版提示词接管 |
| 2.6 | 重写 | `urls.py` | 仅保留新版路由，路径改为 `worldviews/` |
| 2.7 | 修改 | `views.py` 内部 | 视图类名去掉 Doc/chat：`ApiWorldviewOpenView`、`ApiWorldviewStreamView`、`ApiWorldviewChatHistoryView` 等 |
| 2.8 | 修改 | `views.py` 内部 | Token category: `worldview_doc_welcome` → `worldview_welcome`，LLM scene: `worldview_doc_build` → `worldview_build` |
| 2.9 | 修改 | `views.py` 内部 | 模型引用: `WorldviewDoc` → `WorldView`，`WorldviewDocChatHistory` → `WorldViewChatHistory`，`WorldviewDocVersion` → `WorldView` |
| 2.10 | 修改 | `views.py` 内部 | 提示词引用: `WV_DOC_*` → `WORLDVIEW_*`，`DOC_*` → `WORLDVIEW_*` |
| 2.11 | 修改 | `apps/worldview/utils.py` | 保留 SSE 工具，`get_worldview_context` 改为查新模型 |
| 2.12 | 修改 | `apps/worldview/admin.py` | 注册新模型 |

**浏览器检查清单（与第一步完全相同）：**

| 检查项 | 操作步骤 | 预期结果 |
|--------|---------|---------|
| 页面加载 | 访问 `/worldview` | 页面正常，无白屏 |
| 会话打开 | 点击"开始构建" | `worldviews/open/` 返回 200，欢迎消息正确 |
| 流式对话 | 输入内容发送 | SSE 流正常，AI 回复逐字出现 |
| 聊天历史 | 重新打开已有会话 | 历史消息完整加载 |
| 版本操作 | 保存/加载/锁定/解锁 | 全部正常 |
| 阵营提取 | 触发阵营提取 | 正常返回阵营列表 |
| 后端日志 | 观察 Django 终端 | 无 500 错误、无 ImportError、无 AttributeError |
| Token 用量 | 完成一次对话后查看用量页面 | 新 category `worldview_welcome` / `worldview_build` 正确记录 |

---

### 第三步：模型重构 + 数据库迁移（高风险）

**完成内容：**

| 序号 | 操作 | 文件 | 说明 |
|------|------|------|------|
| 3.1 | 重构 | `apps/worldview/models.py` | 删除旧 `WorldView` + `WorldViewChatHistory` + `WorldviewDocVersion`，新建 `WorldView`（FK + UNIQUE）和 `WorldViewChatHistory` |
| 3.2 | 写数据迁移 | `apps/worldview/migrations/` | 将 `worldview_doc` + `worldview_doc_version` 数据合并写入新 `worldview` 表 |
| 3.3 | 执行迁移 | `makemigrations` + `migrate` | 数据库表结构更新 |

**迁移脚本要点：**
- `worldview_doc` 表 → `worldview` 表：project 字段从 OneToOne 改为 FK，version 字段保留
- `worldview_doc_version` 表 → `worldview` 表：每条版本记录写入一行，content/snapshot/last_question/last_options/is_finalized 全部迁移
- `worldview_doc_chat_history` 表 → `worldview_chat_history` 表：FK 从 doc_id 改为 worldview_id（指向具体版本行）
- 如果同一 project 的 WorldviewDoc 和 WorldviewDocVersion 都有数据，以 WorldviewDoc 的当前内容为准创建新行

**浏览器检查清单：**

| 检查项 | 操作步骤 | 预期结果 |
|--------|---------|---------|
| 页面加载 | 访问 `/worldview` | 页面正常，已有数据不丢失 |
| 历史数据 | 打开已有世界观项目 | Markdown 内容完整显示，版本列表正确 |
| 聊天历史 | 重新打开会话 | 历史消息仍在 |
| 新建对话 | 发送新消息 | AI 正常回复，数据写入新表 |
| 版本操作 | 保存新版本 | 新版本行正确创建 |
| 数据库检查 | `python manage.py shell` 查询 | `WorldView.objects.count()` > 0，`WorldViewChatHistory.objects.count()` > 0 |
| Django Admin | 访问 `/admin/worldview/worldview/` | 能看到数据，编辑正常 |

---

### 第四步：跨模块依赖迁移（中风险）

**完成内容：**

| 序号 | 操作 | 文件 | 说明 |
|------|------|------|------|
| 4.1 | 修改 | `utils/helpers.py` | `format_worldview_context` 改为查 `WorldView` 新模型，返回 Markdown content |
| 4.2 | 修改 | `apps/project/views.py` | `WorldView` 查询改为 `filter(project=project, is_deleted=False).order_by('-version').first()` |
| 4.3 | 修改 | `apps/characters/views.py` | `project.worldview` 改为 `project.worldviews.filter(is_deleted=False).order_by('-version').first()` |
| 4.4 | 修改 | `apps/timeline/views.py` | `get_worldview_context` 返回值适配，不再访问 JSON 字段 |

**浏览器检查清单：**

| 检查项 | 操作步骤 | 预期结果 |
|--------|---------|---------|
| 世界观页面 | 完整对话流程 + 版本管理 | 与第二步一致 |
| 角色页面 | 进入角色页面，触发依赖世界观的逻辑 | 页面正常，世界观上下文正确传递 |
| 大纲页面 | 进入大纲页面，触发世界观上下文 | 页面正常，`format_worldview_context` 返回 Markdown |
| 时间线页面 | 进入时间线页面 | 页面正常，不再报 JSON 字段访问错误 |
| 项目首页 | 查看项目详情 | 世界观信息正确显示 |

---

### 第五步：知识库索引迁移（需测试）

**完成内容：**

| 序号 | 操作 | 文件 | 说明 |
|------|------|------|------|
| 5.1 | 修改 | `apps/knowledge/signals.py` | 信号改为监听新 `WorldView` 模型，对最新版本行触发索引 |
| 5.2 | 修改 | `apps/knowledge/tasks.py` | `index_worldview_task` / `delete_worldview_task` 适配新模型 |
| 5.3 | 修改 | `apps/knowledge/indexer.py` | `index_worldview()` 改为 Markdown 全文分块索引，替换旧版 8 类分条 |
| 5.4 | 重建 | 管理命令 | `python manage.py rebuild_knowledge` 全量重建 |

**浏览器检查清单：**

| 检查项 | 操作步骤 | 预期结果 |
|--------|---------|---------|
| 知识检索 | 在大纲/章节中触发世界观相关的知识检索 | 返回相关 Markdown 片段 |
| 新增世界观 | 构建新世界观后，查看知识库 | 新内容已被索引 |
| 修改世界观 | 修改世界观后，查看知识库 | 索引已更新 |
| 语义搜索 | 使用知识搜索功能 | 能搜到世界观相关内容 |

---

### 最终检查（全流程端到端）

| 检查项 | 操作步骤 | 预期结果 |
|--------|---------|---------|
| **新建项目** | 创建新项目 | 项目创建成功 |
| **构建世界观** | 进入世界观，开始对话，发送多轮消息 | AI 正常回复，Markdown 内容逐步丰富 |
| **版本管理** | 保存版本 → 锁定 → 解锁 → 加载旧版本 → 删除版本 | 全部操作正常 |
| **阵营提取** | 触发阵营提取功能 | 正确识别阵营并显示 |
| **关闭重开** | 关闭浏览器，重新打开项目 | 世界观数据、版本、聊天历史全部保留 |
| **角色联动** | 进入角色页面，依赖世界观上下文的功能 | 上下文正确传递 |
| **大纲联动** | 进入大纲页面，依赖世界观上下文的功能 | 上下文正确传递 |
| **时间线联动** | 进入时间线页面 | 不报错 |
| **知识库** | 全量重建后语义搜索 | 能搜到世界观内容 |
| **Token 用量** | 完成全流程后查看用量页面 | 新 category 正确记录 |
| **Django Admin** | 访问 admin 页面 | 新模型可查看、可编辑 |
| **浏览器控制台** | 全流程观察 | 无 404、无 500、无 JS 报错 |
| **后端日志** | 全流程观察 | 无异常堆栈、无 ImportError |
| **数据库** | `manage.py shell` 检查 | 新表有数据，旧表已删除，迁移历史完整 |

---

## 六、风险点

1. **模型重构 + 数据库迁移**: 从 `WorldviewDoc` + `WorldviewDocVersion` 两张表合并为一张 `WorldView` 表，需要写数据迁移脚本（将 WorldviewDoc 的数据 + WorldviewDocVersion 的当前版本合并写入新表）
2. **`related_name` 变化**: 旧版 `project.worldview`（单对象）→ 新版 `project.worldviews`（Manager），所有反向引用都需要加查询条件
3. **知识库索引**: 从 8 类分条索引改为 Markdown 全文索引，需要全量重建
4. **timeline 模块**: 从访问 JSON 字段改为读取 Markdown，需要适配
5. **Token 用量历史**: 旧版 category 数据保留展示，新版 category 去掉 doc 前缀
6. **静态遗留代码**: `static/` 目录为历史遗留，禁止修改，不受影响
