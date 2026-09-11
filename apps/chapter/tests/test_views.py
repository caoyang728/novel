"""
chapter 接口测试

运行命令:
    python manage.py test apps.chapter.tests.test_views --keepdb
    python manage.py test apps.chapter.tests.test_views.CharacterTrajectoriesContextTest --keepdb
    python manage.py test apps.chapter.tests.test_views.KnowledgeIndexerFormatTest --keepdb
"""
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth.models import User

from apps.project.models import ProjectList
from apps.characters.models import Character, CharacterTrajectory
from apps.chapter.views import BaseChapterAPIView
from apps.knowledge.indexer import KnowledgeIndexer


# ========================================================================
# 测试辅助类
# ========================================================================

class _TestHelper(BaseChapterAPIView):
    """测试辅助类，用于访问 BaseChapterAPIView 的方法"""
    pass


# ========================================================================
# 1. CharacterTrajectoriesContextTest — 角色轨迹上下文
# ========================================================================

class CharacterTrajectoriesContextTest(TestCase):
    """测试 get_character_trajectories_context 方法"""

    def setUp(self):
        """创建测试所需的基础数据"""
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.project = ProjectList.objects.create(
            user=self.user,
            title='测试项目',
            genre='xuanhuan',
        )

    def _create_trajectories(self, character, count=1, start_order=1):
        """批量创建轨迹记录"""
        trajectories = []
        for i in range(count):
            trajectories.append(CharacterTrajectory.objects.create(
                character=character,
                project=self.project,
                source='chapter',
                title=f'轨迹{i + 1}',
                start_time=f'第{i + 1}年',
                order=start_order + i,
                details={'location': f'地点{i + 1}', 'description': f'描述{i + 1}'},
            ))
        return trajectories

    def test_get_trajectories_context_empty(self):
        """无轨迹时返回空字符串"""
        helper = _TestHelper()
        result = helper.get_character_trajectories_context(self.project)
        self.assertEqual(result, "")

    def test_get_trajectories_context_single(self):
        """单个角色单条轨迹，验证返回包含角色名和标题的文本"""
        character = Character.objects.create(
            project=self.project,
            name='林风',
            role_type='主角',
            gender='男',
        )
        CharacterTrajectory.objects.create(
            character=character,
            project=self.project,
            source='chapter',
            title='入门',
            start_time='第五年',
            order=1,
            details={'location': '青云城', 'description': '通过考核'},
        )

        helper = _TestHelper()
        result = helper.get_character_trajectories_context(self.project)

        self.assertIn('林风', result)
        self.assertIn('入门', result)
        self.assertIn('第五年', result)
        self.assertIn('角色轨迹', result)

    def test_get_trajectories_context_multiple(self):
        """多个角色多条轨迹，验证按角色分组"""
        char1 = Character.objects.create(
            project=self.project,
            name='林风',
            role_type='主角',
            gender='男',
        )
        char2 = Character.objects.create(
            project=self.project,
            name='苏瑶',
            role_type='女主',
            gender='女',
        )
        CharacterTrajectory.objects.create(
            character=char1,
            project=self.project,
            source='chapter',
            title='入门',
            start_time='第一年',
            order=1,
            details={},
        )
        CharacterTrajectory.objects.create(
            character=char2,
            project=self.project,
            source='chapter',
            title='初遇',
            start_time='第二年',
            order=1,
            details={},
        )

        helper = _TestHelper()
        result = helper.get_character_trajectories_context(self.project)

        # 两个角色的轨迹都应出现
        self.assertIn('林风', result)
        self.assertIn('苏瑶', result)
        self.assertIn('入门', result)
        self.assertIn('初遇', result)
        # 两个角色轨迹段落用 \n\n 分隔
        self.assertIn('\n\n', result)

    def test_get_trajectories_context_details(self):
        """验证 details 中的 location 被正确提取"""
        character = Character.objects.create(
            project=self.project,
            name='林风',
            role_type='主角',
            gender='男',
        )
        CharacterTrajectory.objects.create(
            character=character,
            project=self.project,
            source='chapter',
            title='远行',
            start_time='第三年',
            order=1,
            details={'location': '青云城'},
        )

        helper = _TestHelper()
        result = helper.get_character_trajectories_context(self.project)

        # location 会被格式化为 @地点
        self.assertIn('@青云城', result)

    def test_get_trajectories_context_ordering(self):
        """验证轨迹按 order 排序"""
        character = Character.objects.create(
            project=self.project,
            name='林风',
            role_type='主角',
            gender='男',
        )
        # 先创建 order=3 的轨迹
        CharacterTrajectory.objects.create(
            character=character,
            project=self.project,
            source='chapter',
            title='后期',
            start_time='第三年',
            order=3,
            details={},
        )
        # 再创建 order=1 的轨迹
        CharacterTrajectory.objects.create(
            character=character,
            project=self.project,
            source='chapter',
            title='初期',
            start_time='第一年',
            order=1,
            details={},
        )

        helper = _TestHelper()
        result = helper.get_character_trajectories_context(self.project)

        # order=1 的轨迹（初期）应在 order=3 的轨迹（后期）之前
        pos_early = result.index('初期')
        pos_late = result.index('后期')
        self.assertLess(pos_early, pos_late)


# ========================================================================
# 2. KnowledgeIndexerFormatTest — 知识库索引格式化
# ========================================================================

class KnowledgeIndexerFormatTest(TestCase):
    """测试 KnowledgeIndexer._format_character 方法"""

    def _make_char(self, **kwargs):
        """构造一个模拟角色对象"""
        char = MagicMock()
        char.name = kwargs.get('name', '测试角色')
        char.role_type = kwargs.get('role_type', '配角')
        char.gender = kwargs.get('gender', '未知')
        char.age = kwargs.get('age', None)
        char.identity = kwargs.get('identity', '')
        char.faction = kwargs.get('faction', '')
        char.content = kwargs.get('content', '')
        char.relationships = kwargs.get('relationships', [])
        return char

    @patch('apps.knowledge.indexer.EmbedderFactory')
    @patch('apps.knowledge.indexer.ensure_backend_ready')
    def _get_indexer(self, mock_ready, mock_factory):
        """获取 indexer 实例（mock 掉初始化依赖）"""
        mock_factory.create.return_value = MagicMock()
        return KnowledgeIndexer()

    def test_format_character_with_content(self):
        """有 content 的角色，验证输出包含 "内容:" 和 content 内容"""
        indexer = self._get_indexer()
        char = self._make_char(
            name='林风',
            role_type='主角',
            content='一个来自青云城的少年，天资过人。',
        )

        result = indexer._format_character(char)

        self.assertIn('姓名: 林风', result)
        self.assertIn('角色类型: 主角', result)
        self.assertIn('内容:', result)
        self.assertIn('一个来自青云城的少年，天资过人。', result)

    def test_format_character_without_content(self):
        """无 content 的角色，验证只包含结构化字段"""
        indexer = self._get_indexer()
        char = self._make_char(
            name='林风',
            role_type='配角',
            content='',
        )

        result = indexer._format_character(char)

        self.assertIn('姓名: 林风', result)
        self.assertIn('角色类型: 配角', result)
        self.assertNotIn('内容:', result)

    def test_format_character_with_relationships(self):
        """有 relationships 的角色，验证输出包含关系信息"""
        indexer = self._get_indexer()
        char = self._make_char(
            name='林风',
            role_type='主角',
            gender='男',
            age=18,
            identity='剑修',
            faction='青云宗',
            relationships=[
                {'targetName': '苏瑶', 'relationshipType': '师妹'},
                {'targetName': '张三', 'relationshipType': '对手'},
            ],
        )

        result = indexer._format_character(char)

        self.assertIn('姓名: 林风', result)
        self.assertIn('角色类型: 主角', result)
        self.assertIn('性别: 男', result)
        self.assertIn('年龄: 18', result)
        self.assertIn('身份: 剑修', result)
        self.assertIn('阵营: 青云宗', result)
        self.assertIn('关系:', result)
        self.assertIn('苏瑶(师妹)', result)
        self.assertIn('张三(对手)', result)
