"""
全流程端到端测试 — 角色功能重构 Phase 8 #49

覆盖从项目创建 → 大纲定稿 → 角色提取/创建 → 章节定稿 →
状态提取 + 轨迹记录 + 时间线事件 + 图谱同步的完整链路。

运行命令:
    python manage.py test tests.test_character_pipeline --keepdb -v2
    python manage.py test tests --keepdb -v2
"""
import json
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.project.models import ProjectList
from apps.outline.models import Outline
from apps.outline.views import ApiSaveOutlineView, ApiOutlineFinalizeView
from apps.characters.models import Character, CharacterTrajectory
from apps.characters.views import (
    ApiCharacterBatchCreateView,
    ApiCharacterGenerateFromOutlineView,
)
from apps.chapter.models import ChapterList
from apps.chapter.views import ApiChapterSaveView, BaseChapterAPIView
from apps.timeline.models import TimelineEvent
from apps.graph.models import GraphNode, GraphEdge
from apps.graph.services import GraphService
from apps.volume.models import Volume


# ========================================================================
# 辅助函数
# ========================================================================

def _create_user(username='e2e_user', password='e2e_pass123'):
    """创建测试用户"""
    return User.objects.create_user(username=username, password=password)


def _create_project(user, title='E2E测试项目'):
    """创建测试项目"""
    return ProjectList.objects.create(
        user=user, title=title, genre='xuanhuan',
        description='端到端测试项目',
    )


def _create_outline(project, content='# 大纲\n\n测试大纲内容', version=1, is_finalized=False):
    """创建大纲版本"""
    return Outline.objects.create(
        project=project, content=content, version=version,
        is_finalized=is_finalized,
    )


def _create_character(project, name='林风', role_type='主角', gender='男',
                      faction='', source='manual', **kwargs):
    """创建测试角色"""
    return Character.objects.create(
        project=project, name=name, role_type=role_type,
        gender=gender, faction=faction, source=source, **kwargs,
    )


def _create_volume_data(project, outline):
    """创建卷数据（跳过 LLM 生成流程）"""
    volume = Volume.objects.create(
        project=project, outline=outline, version=1, volume_number=1,
        title='第一卷：启程', summary='测试卷摘要',
        content='## 第一章 诞生\n\n### 第二章 出发',
        chapter_count=2,
    )
    return volume


def _create_chapter(volume, chapter_number=1, title='第一章', content=''):
    """创建章节"""
    return ChapterList.objects.create(
        volume=volume, chapter_number=chapter_number,
        title=title, content=content, status='draft',
    )


def _mock_llm_result(parsed_dict):
    """构造模拟 LLM 返回对象（带 .content 属性）"""
    mock_result = MagicMock()
    mock_result.content = json.dumps(parsed_dict, ensure_ascii=False)
    return mock_result


def _parse_json_response(response):
    """解析 JsonResponse 或 DRF Response 的内容为 dict"""
    if hasattr(response, 'data'):
        return response.data
    return json.loads(response.content)


# ========================================================================
# 1. 项目 + 大纲 → 角色生成 → 批量创建 端到端测试
# ========================================================================

class OutlineToCharacterPipelineTest(TestCase):
    """测试从大纲提取角色并批量创建的完整流程"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = APIRequestFactory()

        # 创建并定稿大纲
        self.outline = _create_outline(
            self.project,
            content='# 小说大纲\n\n主角林风，修仙题材，青云宗弟子...',
            version=1,
            is_finalized=True,
        )

    def test_full_outline_to_character_flow(self):
        """
        完整流程：定稿大纲 → 从大纲提取角色（mock LLM） → 批量创建角色 → 验证数据库
        """
        # --- 步骤1：验证大纲已定稿 ---
        self.outline.refresh_from_db()
        self.assertTrue(self.outline.is_finalized)
        self.assertEqual(self.outline.version, 1)

        # --- 步骤2：模拟从大纲生成角色的 LLM 输出 ---
        mock_llm_output = json.dumps([
            {
                "name": "林风",
                "role_type": "主角",
                "gender": "男",
                "age": 18,
                "personality": "勇敢果断",
                "backstory": "青云宗外门弟子",
                "identity": "剑修",
                "faction": "青云宗",
            },
            {
                "name": "苏瑶",
                "role_type": "女主",
                "gender": "女",
                "age": 17,
                "personality": "温柔聪慧",
                "backstory": "苏家大小姐",
                "identity": "丹修",
                "faction": "青云宗",
            },
            {
                "name": "黑袍人",
                "role_type": "反派",
                "gender": "男",
                "personality": "阴沉狠辣",
                "backstory": "神秘势力首领",
                "identity": "魔修",
                "faction": "魔道",
            },
        ])

        # --- 步骤3：通过 _parse_candidates 静态方法解析候选列表 ---
        existing_names = list(
            Character.objects.filter(
                project=self.project, is_deleted=False
            ).values_list('name', flat=True)
        )
        candidates = ApiCharacterGenerateFromOutlineView._parse_candidates(
            mock_llm_output, existing_names,
        )

        # 验证解析出 3 个候选，全部标记为 is_new
        self.assertEqual(len(candidates), 3)
        names = [c['name'] for c in candidates]
        self.assertIn('林风', names)
        self.assertIn('苏瑶', names)
        self.assertIn('黑袍人', names)
        for c in candidates:
            self.assertTrue(c['is_new'])

        # --- 步骤4：调用批量创建 API ---
        batch_view = ApiCharacterBatchCreateView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/batch-create/',
            data={'characters': candidates},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = batch_view(request, pk=self.project.id)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue(data['success'])
        self.assertEqual(data['created_count'], 3)

        # --- 步骤5：验证数据库中角色已创建 ---
        characters = Character.objects.filter(project=self.project, is_deleted=False)
        self.assertEqual(characters.count(), 3)

        char_names = list(characters.values_list('name', flat=True))
        self.assertIn('林风', char_names)
        self.assertIn('苏瑶', char_names)
        self.assertIn('黑袍人', char_names)

        # 验证角色字段
        linfeng = Character.objects.get(project=self.project, name='林风')
        self.assertEqual(linfeng.role_type, '主角')
        self.assertEqual(linfeng.gender, '男')
        self.assertEqual(linfeng.faction, '青云宗')

    def test_batch_create_skips_duplicate_names(self):
        """批量创建时跳过已存在的角色名"""
        _create_character(self.project, name='林风', role_type='主角')

        batch_view = ApiCharacterBatchCreateView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/batch-create/',
            data={
                'characters': [
                    {'name': '林风', 'role_type': '主角'},
                    {'name': '新角色', 'role_type': '配角'},
                ]
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = batch_view(request, pk=self.project.id)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['created_count'], 1)
        self.assertTrue(Character.objects.filter(project=self.project, name='新角色').exists())

    def test_batch_create_empty_list_returns_error(self):
        """空列表应返回 400 错误"""
        batch_view = ApiCharacterBatchCreateView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/batch-create/',
            data={'characters': []},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = batch_view(request, pk=self.project.id)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data.get('success', True))


# ========================================================================
# 2. 角色 + 卷 → 从卷提取角色 端到端测试
# ========================================================================

class VolumeToCharacterPipelineTest(TestCase):
    """测试从卷版本提取角色的完整流程"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = APIRequestFactory()

        self.outline = _create_outline(self.project, version=1, is_finalized=True)
        self.volume = _create_volume_data(self.project, self.outline)

        # 已有角色（模拟从大纲提取阶段创建的角色）
        self.existing_char = _create_character(
            self.project, name='林风', role_type='主角', source='outline_extract',
        )

    def test_volume_extract_with_existing_characters(self):
        """
        流程：已有角色 + 卷内容 → 提取新角色（mock LLM） → 验证候选中标记已有角色
        """
        mock_llm_output = json.dumps([
            {
                "name": "林风",
                "role_type": "主角",
                "backstory": "更详细的背景",
            },
            {
                "name": "新反派",
                "role_type": "反派",
                "gender": "男",
                "personality": "狡猾阴险",
                "backstory": "来自魔道的强者",
            },
        ])

        existing_names = list(
            Character.objects.filter(
                project=self.project, is_deleted=False
            ).values_list('name', flat=True)
        )
        candidates = ApiCharacterGenerateFromOutlineView._parse_candidates(
            mock_llm_output, existing_names,
        )

        # 林风标记为 is_new=False，新反派标记为 is_new=True
        self.assertEqual(len(candidates), 2)
        linfeng = next(c for c in candidates if c['name'] == '林风')
        new_villain = next(c for c in candidates if c['name'] == '新反派')
        self.assertFalse(linfeng['is_new'])
        self.assertTrue(new_villain['is_new'])

    def test_create_character_from_volume_candidate(self):
        """从卷候选中创建新角色"""
        batch_view = ApiCharacterBatchCreateView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/batch-create/',
            data={
                'characters': [
                    {
                        'name': '新反派',
                        'role_type': '反派',
                        'gender': '男',
                        'faction': '魔道',
                        'source': 'volume_extract',
                    }
                ]
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = batch_view(request, pk=self.project.id)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])

        new_villain = Character.objects.get(project=self.project, name='新反派')
        self.assertEqual(new_villain.role_type, '反派')
        self.assertEqual(new_villain.source, 'volume_extract')


# ========================================================================
# 3. 章节定稿 → 状态提取 + 轨迹记录 + 时间线事件 端到端测试
# ========================================================================

class ChapterFinalizationPipelineTest(TestCase):
    """测试章节定稿后的合并提取流程：状态更新 + 新角色 + 事件 + 轨迹"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = APIRequestFactory()

        self.outline = _create_outline(self.project, version=1, is_finalized=True)
        self.volume = _create_volume_data(self.project, self.outline)

        self.character = _create_character(
            self.project, name='林风', role_type='主角',
            dynamic_states={'current_location': '青云城', 'power_level': '炼气期'},
        )

        self.chapter = _create_chapter(
            self.volume, chapter_number=1, title='第一章 入门',
            content='林风来到青云宗，通过了入门考核。他发现自己体内有一缕远古剑意。',
        )

    def test_state_extraction_updates_dynamic_states(self):
        """章节定稿合并提取 → 验证角色 dynamic_states 被更新"""
        mock_extract_result = {
            "state_updates": [
                {
                    "character_name": "林风",
                    "updates": {
                        "current_location": "青云宗内门",
                        "power_level": "炼气九层",
                        "emotional_state": "兴奋",
                    },
                }
            ],
            "new_characters": [],
            "timeline_events": [],
            "current_story_time": None,
        }

        helper = BaseChapterAPIView()
        mock_llm = MagicMock()
        with patch('apps.chapter.views.get_llm', return_value=mock_llm), \
             patch('apps.chapter.views.call_llm_with_retry', return_value=_mock_llm_result(mock_extract_result)):
            helper.extract_and_update_character_states(
                self.project, self.chapter.content, self.user, chapter=self.chapter,
            )

        self.character.refresh_from_db()
        self.assertEqual(self.character.dynamic_states['current_location'], '青云宗内门')
        self.assertEqual(self.character.dynamic_states['power_level'], '炼气九层')
        self.assertEqual(self.character.dynamic_states['emotional_state'], '兴奋')

    def test_state_extraction_creates_timeline_event(self):
        """合并提取后应创建时间线事件"""
        mock_extract_result = {
            "state_updates": [],
            "new_characters": [],
            "timeline_events": [
                {
                    "title": "入门考核通过",
                    "description": "林风通过入门考核",
                    "location": "青云宗",
                    "characters": ["林风"],
                    "event_type": "main",
                    "start_year": 1,
                    "start_month": 3,
                }
            ],
            "current_story_time": None,
        }

        helper = BaseChapterAPIView()
        mock_llm = MagicMock()
        with patch('apps.chapter.views.get_llm', return_value=mock_llm), \
             patch('apps.chapter.views.call_llm_with_retry', return_value=_mock_llm_result(mock_extract_result)):
            helper.extract_and_update_character_states(
                self.project, self.chapter.content, self.user, chapter=self.chapter,
            )

        events = TimelineEvent.objects.filter(project=self.project)
        self.assertEqual(events.count(), 1)
        event = events.first()
        self.assertEqual(event.title, '入门考核通过')
        self.assertEqual(event.location, '青云宗')
        self.assertEqual(event.start_year, 1)
        self.assertEqual(event.start_month, 3)
        self.assertEqual(event.event_type, 'main')
        self.assertIn(self.character, event.characters.all())

    def test_state_extraction_discovers_new_character(self):
        """合并提取发现新角色时应自动创建"""
        mock_extract_result = {
            "state_updates": [],
            "new_characters": [
                {
                    "name": "神秘长老",
                    "role_type": "配角",
                    "gender": "男",
                    "identity": "青云宗长老",
                    "backstory": "守护青云宗数百年的老者",
                }
            ],
            "timeline_events": [],
            "current_story_time": None,
        }

        helper = BaseChapterAPIView()
        mock_llm = MagicMock()
        with patch('apps.chapter.views.get_llm', return_value=mock_llm), \
             patch('apps.chapter.views.call_llm_with_retry', return_value=_mock_llm_result(mock_extract_result)):
            helper.extract_and_update_character_states(
                self.project, self.chapter.content, self.user, chapter=self.chapter,
            )

        new_char = Character.objects.get(project=self.project, name='神秘长老')
        self.assertEqual(new_char.role_type, '配角')
        self.assertEqual(new_char.source, 'chapter_discover')

    def test_state_extraction_creates_trajectory(self):
        """合并提取后应为涉及的角色创建轨迹记录"""
        mock_extract_result = {
            "state_updates": [
                {
                    "character_name": "林风",
                    "updates": {
                        "current_location": "青云宗",
                        "power_level": "炼气九层",
                    },
                }
            ],
            "new_characters": [],
            "timeline_events": [],
            "current_story_time": {"year": 1, "month": 3},
        }

        helper = BaseChapterAPIView()
        mock_llm = MagicMock()
        with patch('apps.chapter.views.get_llm', return_value=mock_llm), \
             patch('apps.chapter.views.call_llm_with_retry', return_value=_mock_llm_result(mock_extract_result)):
            helper.extract_and_update_character_states(
                self.project, self.chapter.content, self.user, chapter=self.chapter,
            )

        trajectories = CharacterTrajectory.objects.filter(
            character=self.character, project=self.project,
        )
        self.assertGreaterEqual(trajectories.count(), 1)
        trajectory = trajectories.first()
        self.assertEqual(trajectory.source, 'chapter')
        self.assertIn(self.chapter.id, trajectory.chapter_ids)

    def test_full_chapter_finalization_combined(self):
        """
        完整章节定稿合并提取：状态更新 + 新角色 + 事件 + 轨迹，一次 LLM 调用
        """
        mock_extract_result = {
            "state_updates": [
                {
                    "character_name": "林风",
                    "updates": {
                        "current_location": "青云宗内门",
                        "power_level": "炼气九层",
                        "emotional_state": "坚定",
                    },
                }
            ],
            "new_characters": [
                {
                    "name": "张长老",
                    "role_type": "配角",
                    "gender": "男",
                    "identity": "青云宗外门长老",
                    "backstory": "负责外门弟子考核",
                }
            ],
            "timeline_events": [
                {
                    "title": "入门考核",
                    "description": "林风通过入门考核",
                    "location": "青云宗",
                    "characters": ["林风"],
                    "event_type": "main",
                    "start_year": 1,
                    "start_month": 5,
                },
                {
                    "title": "张长老收徒",
                    "description": "张长老看中林风资质",
                    "location": "青云宗",
                    "characters": ["林风", "张长老"],
                    "event_type": "character",
                    "start_year": 1,
                    "start_month": 5,
                },
            ],
            "current_story_time": {"year": 1, "month": 5},
        }

        helper = BaseChapterAPIView()
        mock_llm = MagicMock()
        with patch('apps.chapter.views.get_llm', return_value=mock_llm), \
             patch('apps.chapter.views.call_llm_with_retry', return_value=_mock_llm_result(mock_extract_result)):
            helper.extract_and_update_character_states(
                self.project, self.chapter.content, self.user, chapter=self.chapter,
            )

        # 1. 角色状态更新
        self.character.refresh_from_db()
        self.assertEqual(self.character.dynamic_states['current_location'], '青云宗内门')
        self.assertEqual(self.character.dynamic_states['power_level'], '炼气九层')

        # 2. 新角色创建
        self.assertTrue(Character.objects.filter(project=self.project, name='张长老').exists())
        zhang = Character.objects.get(project=self.project, name='张长老')
        self.assertEqual(zhang.source, 'chapter_discover')

        # 3. 时间线事件
        events = list(TimelineEvent.objects.filter(project=self.project).order_by('start_month'))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].title, '入门考核')
        self.assertEqual(events[1].title, '张长老收徒')
        self.assertIn(self.character, events[0].characters.all())
        zhang_in_event = events[1].characters.filter(name='张长老').exists()
        self.assertTrue(zhang_in_event)

        # 4. 轨迹记录
        trajectories = CharacterTrajectory.objects.filter(project=self.project)
        self.assertGreaterEqual(trajectories.count(), 1)


# ========================================================================
# 4. 图谱同步 端到端测试
# ========================================================================

class GraphSyncPipelineTest(TestCase):
    """测试角色创建后的图谱同步流程"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)

    def test_character_sync_creates_node_and_edges(self):
        """角色同步到图谱：创建节点 + 势力边 + 关系边"""
        character = _create_character(
            self.project, name='林风', role_type='主角',
            faction='青云宗',
            relationships=[{'targetName': '苏瑶', 'relationshipType': '师妹'}],
        )
        _create_character(self.project, name='苏瑶', role_type='女主', gender='女')

        GraphService.sync_character(character.pk)

        # 角色节点
        char_node = GraphNode.objects.get(
            project=self.project, node_type='character', source_id=character.pk,
        )
        self.assertEqual(char_node.name, '林风')

        # 势力节点
        faction_node = GraphNode.objects.get(
            project=self.project, node_type='faction', name='青云宗',
        )
        self.assertIsNotNone(faction_node)

        # belongs_to 边
        belongs_edge = GraphEdge.objects.get(
            project=self.project, source=char_node, edge_type='belongs_to',
        )
        self.assertEqual(belongs_edge.target, faction_node)

    def test_location_upsert_creates_node(self):
        """地点节点幂等创建"""
        node1 = GraphService.upsert_location(self.project.pk, '青云城', '繁华的修仙城市')
        self.assertIsNotNone(node1)
        self.assertEqual(node1.node_type, 'location')
        self.assertEqual(node1.name, '青云城')

        # 幂等：再次创建不应报错
        node2 = GraphService.upsert_location(self.project.pk, '青云城', '更新描述')
        self.assertEqual(node1.pk, node2.pk)

    def test_timeline_event_sync_creates_node_and_edges(self):
        """时间线事件同步到图谱：创建事件节点 + occurs_at 边 + involves 边"""
        character = _create_character(self.project, name='林风')
        GraphService.sync_character(character.pk)

        GraphService.upsert_location(self.project.pk, '青云宗')

        event = TimelineEvent.objects.create(
            project=self.project,
            title='入门考核',
            description='林风通过入门考核',
            start_year=1, start_month=3,
            event_type='main',
            location='青云宗',
        )
        event.characters.add(character)

        GraphService.sync_timeline_event(event)

        # 事件节点
        event_node = GraphNode.objects.get(
            project=self.project, node_type='event', source_id=event.pk,
        )
        self.assertEqual(event_node.name, '入门考核')

        # occurs_at 边（事件 → 地点）
        location_node = GraphNode.objects.get(
            project=self.project, node_type='location', name='青云宗',
        )
        occurs_edge = GraphEdge.objects.get(
            project=self.project, source=event_node, edge_type='occurs_at',
        )
        self.assertEqual(occurs_edge.target, location_node)

        # involves 边（事件 → 人物）
        char_node = GraphNode.objects.get(
            project=self.project, node_type='character', source_id=character.pk,
        )
        involves_edge = GraphEdge.objects.get(
            project=self.project, source=event_node, edge_type='involves',
        )
        self.assertEqual(involves_edge.target, char_node)

    def test_trajectory_sync_creates_edges(self):
        """角色轨迹同步到图谱：创建 trajectory 自环边"""
        character = _create_character(self.project, name='林风')
        char_node = GraphNode.objects.create(
            project=self.project, node_type='character',
            source_id=character.pk, name='林风',
        )

        CharacterTrajectory.objects.create(
            character=character, project=self.project,
            title='入门修炼', source='chapter',
            start_time='第一年', order=1,
            details={'location': '青云城', 'key_events': ['考核通过']},
        )

        GraphService.build_trajectories_for_project(self.project.pk)

        edges = GraphEdge.objects.filter(project=self.project, edge_type='trajectory')
        self.assertEqual(edges.count(), 1)
        edge = edges.first()
        self.assertEqual(edge.source, char_node)
        self.assertEqual(edge.target, char_node)
        self.assertIn('入门修炼', edge.description)


# ========================================================================
# 5. 章节保存 + 流程串联 端到端测试
# ========================================================================

class ChapterSavePipelineTest(TestCase):
    """测试章节保存 API 的完整流程"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = APIRequestFactory()

        self.outline = _create_outline(self.project, version=1, is_finalized=True)
        self.volume = _create_volume_data(self.project, self.outline)

    def test_create_new_chapter_via_save_api(self):
        """通过 save API 创建新章节"""
        view = ApiChapterSaveView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/chapters/save/',
            data={
                'chapter_id': 0,
                'volume_id': self.volume.id,
                'chapter_number': 1,
                'title': '第一章 诞生',
                'content': '在青云山脚下，一个婴儿呱呱坠地...',
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = view(request, project_id=self.project.id)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(_parse_json_response(response)['success'])

        chapter = ChapterList.objects.get(volume=self.volume, chapter_number=1)
        self.assertEqual(chapter.title, '第一章 诞生')
        self.assertEqual(chapter.status, 'draft')

    def test_full_volume_to_chapter_flow(self):
        """完整流程：卷 → 创建多个章节 → 保存内容"""
        for i in range(1, 4):
            view = ApiChapterSaveView.as_view()
            request = self.factory.post(
                f'/api/projects/{self.project.id}/chapters/save/',
                data={
                    'chapter_id': 0,
                    'volume_id': self.volume.id,
                    'chapter_number': i,
                    'title': f'第{i}章',
                    'content': f'第{i}章的内容...',
                },
                content_type='application/json',
            )
            force_authenticate(request, user=self.user)
            response = view(request, project_id=self.project.id)
            self.assertEqual(response.status_code, 200)

        chapters = ChapterList.objects.filter(volume=self.volume).order_by('chapter_number')
        self.assertEqual(chapters.count(), 3)
        self.assertEqual(chapters[0].title, '第1章')
        self.assertEqual(chapters[1].title, '第2章')
        self.assertEqual(chapters[2].title, '第3章')


# ========================================================================
# 6. 大纲定稿 + 完整创作流程 端到端测试
# ========================================================================

class FullCreationWorkflowTest(TestCase):
    """
    最完整的端到端测试：覆盖从项目创建到章节创作的全流程

    流程：
    创建项目 → 保存大纲 → 定稿大纲 → 创建角色 →
    创建卷 → 创建章节 → 保存章节内容 → 章节定稿提取
    """

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = APIRequestFactory()

    def test_project_to_chapter_full_flow(self):
        """完整的创作流程端到端测试"""
        # --- 1. 保存大纲 ---
        save_view = ApiSaveOutlineView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/versions/save/',
            data={'content': '# 小说大纲\n\n修仙题材...\n\n主角林风，青云宗弟子'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = save_view(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 200)
        outline_version_id = _parse_json_response(response)['version_id']

        # --- 2. 定稿大纲 ---
        finalize_view = ApiOutlineFinalizeView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/finalize/',
            data={'version_id': outline_version_id},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = finalize_view(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(_parse_json_response(response)['success'])

        outline = Outline.objects.get(pk=outline_version_id)
        self.assertTrue(outline.is_finalized)

        # --- 3. 从大纲创建角色（批量创建 API） ---
        batch_view = ApiCharacterBatchCreateView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/batch-create/',
            data={
                'characters': [
                    {'name': '林风', 'role_type': '主角', 'gender': '男',
                     'faction': '青云宗', 'source': 'outline_extract',
                     'content': '## 性格\n\n勇敢果断'},
                    {'name': '苏瑶', 'role_type': '女主', 'gender': '女',
                     'faction': '青云宗', 'source': 'outline_extract'},
                ]
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = batch_view(request, pk=self.project.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(_parse_json_response(response)['created_count'], 2)

        # --- 4. 创建卷 ---
        volume = Volume.objects.create(
            project=self.project, outline=outline, version=1, volume_number=1,
            title='第一卷', summary='启程', chapter_count=2,
            content='## 第一章 入门\n\n### 第二章 修炼',
        )

        # --- 5. 创建章节 ---
        chapter_view = ApiChapterSaveView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/chapters/save/',
            data={
                'chapter_id': 0,
                'volume_id': volume.id,
                'chapter_number': 1,
                'title': '第一章 入门',
                'content': '林风来到青云宗...',
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = chapter_view(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 200)

        chapter = ChapterList.objects.get(volume=volume, chapter_number=1)

        # --- 6. 章节定稿：合并提取 ---
        mock_extract_result = {
            "state_updates": [
                {
                    "character_name": "林风",
                    "updates": {"current_location": "青云宗", "power_level": "炼气一层"},
                }
            ],
            "new_characters": [],
            "timeline_events": [
                {
                    "title": "入门考核",
                    "description": "林风通过入门考核",
                    "location": "青云宗",
                    "characters": ["林风"],
                    "event_type": "main",
                    "start_year": 1,
                }
            ],
            "current_story_time": {"year": 1, "month": 1},
        }

        helper = BaseChapterAPIView()
        mock_llm = MagicMock()
        with patch('apps.chapter.views.get_llm', return_value=mock_llm), \
             patch('apps.chapter.views.call_llm_with_retry', return_value=_mock_llm_result(mock_extract_result)):
            helper.extract_and_update_character_states(
                self.project, chapter.content, self.user, chapter=chapter,
            )

        # --- 7. 验证最终状态 ---
        linfeng = Character.objects.get(project=self.project, name='林风')
        self.assertEqual(linfeng.dynamic_states['current_location'], '青云宗')

        self.assertTrue(
            TimelineEvent.objects.filter(project=self.project, title='入门考核').exists()
        )

        self.assertGreaterEqual(
            CharacterTrajectory.objects.filter(
                character=linfeng, project=self.project,
            ).count(), 1
        )

        # 图谱同步
        GraphService.sync_character(linfeng.pk)
        self.assertTrue(
            GraphNode.objects.filter(
                project=self.project, node_type='character', source_id=linfeng.pk,
            ).exists()
        )
