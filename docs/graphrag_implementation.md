# GraphRAG 实施方案

## 概述

为小说创作平台增加知识图谱功能，实现角色关系图可视化和 GraphRAG 上下文增强。

## 技术选型

| 项目 | 选择 | 说明 |
|------|------|------|
| 图存储 | PostgreSQL 专用表 (GraphNode + GraphEdge) | 复用现有基础设施，不引入 Neo4j |
| 图算法 | 不需要 NetworkX | 只做展示+简单查询，用 SQL 即可 |
| 可视化 | Cytoscape.js | 开箱即用，布局算法丰富，深色主题友好 |
| 范围 | 仅角色关系图 | 暂不支持世界观实体（种族、地点等） |
| 编辑能力 | 只读展示 | 留 TODO 后期扩展 |

## 涉及文件清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `apps/graph/__init__.py` | app 包 |
| `apps/graph/apps.py` | AppConfig，注册 signals |
| `apps/graph/models.py` | GraphNode + GraphEdge 模型 |
| `apps/graph/views.py` | 图谱 API 视图 |
| `apps/graph/serializers.py` | DRF 序列化器 |
| `apps/graph/urls.py` | API 路由 |
| `apps/graph/services.py` | 图谱构建/查询服务 |
| `apps/graph/tasks.py` | Celery 异步同步任务 |
| `apps/graph/signals.py` | 监听 Character 模型变更 |
| `apps/graph/admin.py` | Django Admin 注册 |
| `apps/graph/migrations/0001_initial.py` | 数据库迁移 |
| `templates/graph.html` | 图谱可视化页面 |
| `static/js/graph.js` | Cytoscape.js 图谱逻辑 |
| `static/css/graph.css` | 图谱页面样式 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `novel_agent/settings.py` | INSTALLED_APPS 增加 `apps.graph.apps.GraphConfig` |
| `novel_agent/urls.py` | 挂载 graph 路由 + 静态页面 |
| `apps/project/urls.py` | 增加图谱页面路由 |
| `apps/project/views.py` | 增加 GraphView 页面视图 |
| `templates/project.html` | 功能入口增加"知识图谱"卡片 |
| `templates/character.html` | header 增加"查看图谱"按钮；编辑弹窗增加"关系图谱" tab |
| `static/js/characters.js` | 图谱按钮跳转 + 编辑 tab 逻辑 + mini 图谱加载 |
| `static/js/project.js` | 增加 `openGraphManager()` 函数 |

---

## Phase 1: Graph App 模型 + 迁移

### 1.1 `apps/graph/__init__.py`

空文件。

### 1.2 `apps/graph/apps.py`

```python
from django.apps import AppConfig

class GraphConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.graph'
    verbose_name = '知识图谱'

    def ready(self):
        import apps.graph.signals  # noqa: F401
```

### 1.3 `apps/graph/models.py`

**GraphNode 模型：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BigAutoField | 主键 |
| project | FK(ProjectList, CASCADE) | 所属项目 |
| node_type | CharField(20) | 类型：character / faction |
| name | CharField(200) | 节点名称 |
| description | TextField(blank) | 描述 |
| properties | JSONField(default=dict) | 扩展属性 |
| source_id | PositiveIntegerField(null) | 关联源记录 PK（Character.id） |
| created_at | DateTimeField(auto_now_add) | 创建时间 |
| updated_at | DateTimeField(auto_now) | 更新时间 |

约束：`UniqueConstraint(fields=['project', 'node_type', 'name'])`

**GraphEdge 模型：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BigAutoField | 主键 |
| project | FK(ProjectList, CASCADE) | 所属项目 |
| source | FK(GraphNode, CASCADE, related_name='outgoing_edges') | 起点 |
| target | FK(GraphNode, CASCADE, related_name='incoming_edges') | 终点 |
| edge_type | CharField(30) | 关系类型 |
| description | TextField(blank) | 关系描述 |
| properties | JSONField(default=dict) | 扩展属性 |
| is_bidirectional | BooleanField(default=False) | 是否双向 |
| created_at | DateTimeField(auto_now_add) | 创建时间 |
| updated_at | DateTimeField(auto_now) | 更新时间 |

约束：`UniqueConstraint(fields=['source', 'target', 'edge_type'])`

### 1.4 `apps/graph/admin.py`

注册 GraphNode 和 GraphEdge 到 Django Admin。

### 1.5 数据库迁移

```bash
python manage.py makemigrations graph
python manage.py migrate
```

---

## Phase 2: 数据同步服务 + Celery 任务

### 2.1 `apps/graph/services.py`

**核心类 `GraphService`：**

方法：
- `sync_character(character_id)` — 同步单个角色到图谱
  - 创建/更新 character 类型 GraphNode（name, description, properties 包含 role_type/gender/age/faction 等）
  - 提取 Character.faction，创建/关联 faction 类型 GraphNode，创建 belongs_to 边
  - 遍历 Character.relationships，为每条关系创建/更新 GraphEdge
  - 同步反向边（利用 characters.constants.RELATIONSHIP_REVERSE）
  - 删除已不存在的关系边
- `delete_character(character_id)` — 删除角色对应的 GraphNode（CASCADE 自动清理边）
- `rebuild_project(project_id)` — 全量重建项目图谱
  - 删除项目所有 GraphNode/GraphEdge
  - 遍历所有角色调用 sync_character
- `get_graph_data(project_id, node_types=None, edge_types=None)` — 查询图谱数据供前端展示
  - 返回 `{nodes: [...], edges: [...]}`
- `get_character_subgraph(project_id, character_name, hops=1)` — 获取角色 N 跳子图

**边类型映射**（复用 characters.constants 中的类型）：

Character.relationships 中的 relationshipType → GraphEdge.edge_type 直接映射：
- 朋友/恋人/配偶/父母/子女/兄弟姐妹/师父/徒弟/敌人/对手/导师/门生/盟友/亲属/君主/臣子/其他 → 同名
- 新增：belongs_to（角色→势力）

### 2.2 `apps/graph/tasks.py`

复用 knowledge/tasks.py 的 `_enqueue` + `_sync_fallback` 模式。

任务列表：
- `graph.sync_character(character_id)` — 同步单个角色
- `graph.delete_character(character_id)` — 删除角色节点
- `graph.rebuild_project(project_id)` — 全量重建

### 2.3 `apps/graph/signals.py`

监听 Character 模型的 post_save 和 post_delete：

```python
@receiver(post_save, sender='characters.Character')
def on_character_saved(sender, instance, **kwargs):
    # 跳过软删除（is_deleted=True 时删除图谱节点）
    if instance.is_deleted:
        _enqueue(delete_character_task, instance.pk)
    else:
        _enqueue(sync_character_task, instance.pk)

@receiver(post_delete, sender='characters.Character')
def on_character_deleted(sender, instance, **kwargs):
    _enqueue(delete_character_task, instance.pk)
```

### 2.4 管理命令 `apps/graph/management/commands/rebuild_graph.py`

手动触发全量重建：
```bash
python manage.py rebuild_graph [--project-id=ID]
```

---

## Phase 3: 后端 API

### 3.1 `apps/graph/views.py`

所有视图继承 `apps.project.base.BaseAPIView`（封装鉴权、项目查询）。

**API 列表：**

| 视图类 | 路由 | 方法 | 说明 |
|--------|------|------|------|
| `ApiGraphDataView` | `/api/projects/<pk>/graph/` | GET | 获取完整图谱（节点+边），支持 query params 筛选 |
| `ApiGraphSubgraphView` | `/api/projects/<pk>/graph/subgraph/` | GET | 获取指定角色的子图，参数：name, hops |
| `ApiGraphRebuildView` | `/api/projects/<pk>/graph/rebuild/` | POST | 重建项目图谱 |
| `ApiGraphStatsView` | `/api/projects/<pk>/graph/stats/` | GET | 图谱统计信息 |

**`ApiGraphDataView` GET 响应格式：**

```json
{
    "success": true,
    "data": {
        "nodes": [
            {
                "id": 1,
                "node_type": "character",
                "name": "张三",
                "description": "主角",
                "properties": {"role_type": "主角", "gender": "男", "age": 18, "faction": "青云门"}
            },
            {
                "id": 10,
                "node_type": "faction",
                "name": "青云门",
                "description": "",
                "properties": {}
            }
        ],
        "edges": [
            {
                "id": 1,
                "source_id": 1,
                "target_id": 2,
                "edge_type": "朋友",
                "description": "从小一起长大",
                "is_bidirectional": true
            }
        ]
    }
}
```

**Query Params：**
- `node_types` — 逗号分隔的节点类型筛选，如 `character,faction`
- `edge_types` — 逗号分隔的边类型筛选，如 `朋友,师徒`

**`ApiGraphSubgraphView` GET 参数：**
- `name` — 角色名称（必填）
- `hops` — 跳数，默认 1

**`ApiGraphStatsView` GET 响应格式：**

```json
{
    "success": true,
    "data": {
        "total_nodes": 15,
        "total_edges": 28,
        "nodes_by_type": {"character": 12, "faction": 3},
        "edges_by_type": {"朋友": 5, "师徒": 3, "belongs_to": 12, ...}
    }
}
```

### 3.2 `apps/graph/serializers.py`

- `GraphNodeSerializer` — 序列化单个节点
- `GraphEdgeSerializer` — 序列化单个边
- `GraphDataSerializer` — 包装 nodes + edges 列表

### 3.3 `apps/graph/urls.py`

```python
urlpatterns = [
    path('projects/<int:pk>/graph/', ApiGraphDataView.as_view()),
    path('projects/<int:pk>/graph/subgraph/', ApiGraphSubgraphView.as_view()),
    path('projects/<int:pk>/graph/rebuild/', ApiGraphRebuildView.as_view()),
    path('projects/<int:pk>/graph/stats/', ApiGraphStatsView.as_view()),
]
```

---

## Phase 4: 注册 App + 路由

### 4.1 `novel_agent/settings.py`

INSTALLED_APPS 增加：
```python
'apps.graph.apps.GraphConfig',
```

### 4.2 `novel_agent/urls.py`

增加：
```python
# 图谱路由
path('', include('apps.graph.urls')),
```

frontend_files 列表增加 `'graph.html'`。

### 4.3 `apps/project/urls.py`

增加页面路由（在 character 路由附近）：
```python
path('<int:project_id>/graph/', GraphView.as_view(), name='graph'),
```

### 4.4 `apps/project/views.py`

增加页面视图：
```python
class GraphView(View):
    '''知识图谱页面视图'''
    def get(self, request, project_id):
        return render(request, 'graph.html')
```

---

## Phase 5: 前端 - 图谱可视化页面

### 5.1 `templates/graph.html`

页面结构：
- 引入 Cytoscape.js CDN
- 引入 common.js、graph.js、graph.css
- 布局：左侧筛选面板 + 右侧图谱画布 + 底部统计栏
- header 区域：返回按钮 + 标题"知识图谱" + 搜索框 + 重建按钮 + 全屏按钮

**左侧筛选面板：**
- 节点类型复选框（character、faction）— 默认全选
- 关系类型复选框（从 API 动态加载）— 默认全选
- 选中节点详情区（点击节点后显示）

**右侧画布：**
- Cytoscape.js 容器，占满剩余空间
- 支持缩放、拖拽、点击交互

**底部统计栏：**
- 节点总数、边总数、势力集群数

### 5.2 `static/js/graph.js`

**初始化流程：**
1. 从 URL 解析 `projectId`
2. 调用 `/api/projects/{id}/graph/` 获取图谱数据
3. 调用 `/api/projects/{id}/graph/stats/` 获取统计
4. 初始化 Cytoscape 实例

**Cytoscape 样式配置：**
- character 节点：蓝色圆形，大小按度数缩放（min 30, max 60）
- faction 节点：红色六边形，较大
- 边：灰色线条，带箭头，标签显示关系类型
- 选中节点：高亮边框 + 一度关系子图高亮
- 深色主题：背景 #1a1a2e，节点文字白色

**布局：**
- 使用 `cose-bilkent` 或 `fcose` 布局（效果最好，自动避让重叠）
- 备选 `cose` 布局（内置，无需额外扩展）

**交互：**
- 点击节点：高亮该节点及其一度关系，左侧面板显示详情
- 点击空白：取消高亮
- 鼠标悬停：tooltip 显示节点信息
- 搜索：按名称模糊匹配，定位到匹配节点并高亮
- 筛选：复选框控制节点/边类型显示
- 全屏：Fullscreen API

**颜色方案（与项目深色主题一致）：**
- character 节点：#6366f1 (indigo)
- faction 节点：#ef4444 (red)
- 边：#6b7280 (gray)
- 高亮边：#22d3ee (cyan)
- 背景：#111827 (gray-900)

### 5.3 `static/css/graph.css`

- 页面全高布局（page-full-height）
- 左侧筛选面板宽度 240px
- 图谱画布 flex: 1
- 底部统计栏高度 40px
- 节点详情卡片样式
- 搜索框样式
- 响应式：768px 以下隐藏左侧面板，改为顶部折叠

---

## Phase 6: 前端 - 角色页面改动

### 6.1 `templates/character.html` 改动

**改动 1：header 增加"查看图谱"按钮**

在"AI检测"按钮和"创建角色"按钮之间增加：
```html
<button class="btn btn-outline" onclick="openGraphView()">
    <i class="fas fa-diagram-project"></i> 查看图谱
</button>
```

**改动 2：编辑弹窗增加"关系图谱" tab**

在现有 5 个 tab（基础信息/人际关系/能力秘密/经历/其他）之后增加第 6 个 tab：
```html
<button class="edit-tab" onclick="switchEditTab('graph')">关系图谱</button>
```

对应内容区：
```html
<div id="editGraphTab" class="edit-tab-content" style="display:none;">
    <div id="miniGraphContainer" style="width:100%;height:400px;"></div>
    <div style="text-align:center;margin-top:10px;">
        <button class="btn btn-outline" onclick="openGraphView()">在图谱中查看</button>
    </div>
</div>
```

### 6.2 `static/js/characters.js` 改动

**增加函数：**
- `openGraphView()` — 跳转到 `/{projectId}/graph/` 页面
- `switchEditTab('graph')` — 在 tab 切换逻辑中处理 graph tab
- `loadMiniGraph(characterName)` — 在 `openEditDialog()` 中调用，加载该角色的一度子图

**`loadMiniGraph` 实现：**
- 调用 `/api/projects/{id}/graph/subgraph/?name={name}&hops=1`
- 使用 Cytoscape.js 渲染 mini 图（只读，无筛选面板）
- 节点可点击，点击后在新页面打开完整图谱

**`openEditDialog` 改动：**
- 在 switchEditTab 逻辑中，当切换到 graph tab 时调用 `loadMiniGraph(character.name)`

### 6.3 `static/css/characters.css` 改动

增加 mini 图谱容器样式。

---

## Phase 7: 前端 - 项目详情页改动

### 7.1 `templates/project.html` 改动

在"人物清单"卡片后面增加"知识图谱"卡片：

```html
<div class="col-md-6">
    <div class="action-card" id="action-graph" onclick="openGraphManager()">
        <div class="action-icon purple">
            <i class="fas fa-diagram-project"></i>
        </div>
        <div class="action-content">
            <div class="action-title">知识图谱</div>
            <div class="action-desc">可视化角色关系网络</div>
        </div>
        <div class="action-arrow">
            <i class="fas fa-chevron-right"></i>
        </div>
    </div>
</div>
```

### 7.2 `static/js/project.js` 改动（如需）

增加 `openGraphManager()` 函数（如果 project.html 的跳转逻辑在 JS 中定义）。

---

## 实施状态

**所有 Phase 已完成。** 部署后需执行以下命令：

```bash
# 1. 数据库迁移
python manage.py migrate

# 2. 重建图谱（从现有角色数据生成）
python manage.py rebuild_graph              # 重建所有项目
python manage.py rebuild_graph --project-id=1  # 重建指定项目
```

## 实施顺序

1. ~~Phase 1 — 模型 + 迁移~~ ✅
2. ~~Phase 2 — 服务层 + 任务 + Signal~~ ✅
3. ~~Phase 3 — API 视图 + 序列化器 + 路由~~ ✅
4. ~~Phase 4 — 注册 app + 路由配置~~ ✅
5. ~~Phase 5 — 图谱页面前端~~ ✅
6. ~~Phase 6 — 角色页面改动~~ ✅
7. ~~Phase 7 — 项目详情页改动~~ ✅

---

## TODO（后期扩展）

- [ ] 图谱页面增加编辑能力（拖拽创建关系、右键菜单删除节点/边）
- [ ] 世界观实体支持（种族、地点、法则节点）
- [ ] LLM 自动提取世界观实体
- [ ] GraphRAG 上下文注入到章节生成 prompt
- [ ] 图谱导出（PNG/SVG/JSON）
- [ ] 时间线事件节点
- [ ] 节点按社区着色（连通分量算法）
- [ ] 角色动态状态变化的时间轴展示
