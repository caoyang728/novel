"""
graph 图谱测试

运行命令:
    python manage.py test apps.graph.tests.test_views --keepdb
    python manage.py test apps.graph.tests.test_views.BuildTrajectoriesTest --keepdb
    python manage.py test apps.graph.tests.test_views.GraphEdgeModelTest --keepdb
"""
from django.test import TestCase
from django.contrib.auth.models import User

from apps.project.models import ProjectList
from apps.characters.models import Character, CharacterTrajectory
from apps.graph.models import GraphNode, GraphEdge
from apps.graph.services import GraphService


def _create_user(username='testuser', password='testpass123'):
    """创建测试用户"""
    return User.objects.create_user(username=username, password=password)


def _create_project(user, title='测试项目', genre='xuanhuan'):
    """创建测试项目"""
    return ProjectList.objects.create(user=user, title=title, genre=genre)


def _create_character(project, name='林风', role_type='主角', gender='男'):
    """创建测试角色"""
    return Character.objects.create(project=project, name=name, role_type=role_type, gender=gender)


def _create_character_node(project, character, name='林风'):
    """创建角色图谱节点"""
    return GraphNode.objects.create(
        project=project,
        node_type='character',
        source_id=character.pk,
        name=name,
    )


def _create_trajectory(character, project, title='入门', source='chapter',
                       start_time='第五年', order=1, details=None):
    """创建角色轨迹"""
    if details is None:
        details = {'location': '青云城', 'key_events': ['考核']}
    return CharacterTrajectory.objects.create(
        character=character,
        project=project,
        title=title,
        source=source,
        start_time=start_time,
        order=order,
        details=details,
    )


class BuildTrajectoriesTest(TestCase):
    """图谱轨迹构建测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.character = _create_character(self.project)
        self.char_node = _create_character_node(self.project, self.character)

    def test_build_trajectories_creates_edges(self):
        """创建角色节点 + 轨迹，应生成 trajectory 类型的 GraphEdge"""
        _create_trajectory(self.character, self.project)

        GraphService.build_trajectories_for_project(self.project.pk)

        edges = GraphEdge.objects.filter(project=self.project, edge_type='trajectory')
        self.assertEqual(edges.count(), 1)
        edge = edges.first()
        self.assertIn('入门', edge.description)
        self.assertIn('青云城', edge.description)

    def test_build_trajectories_self_loop(self):
        """验证轨迹边是自环（source == target）"""
        _create_trajectory(self.character, self.project)

        GraphService.build_trajectories_for_project(self.project.pk)

        edge = GraphEdge.objects.filter(
            project=self.project, edge_type='trajectory'
        ).first()
        self.assertIsNotNone(edge)
        self.assertEqual(edge.source_id, edge.target_id)
        self.assertEqual(edge.source, edge.target)

    def test_build_trajectories_cleans_old(self):
        """重新调用 build 时应先清理旧的 trajectory 边"""
        _create_trajectory(self.character, self.project, title='入门', order=1)

        GraphService.build_trajectories_for_project(self.project.pk)
        self.assertEqual(
            GraphEdge.objects.filter(project=self.project, edge_type='trajectory').count(), 1
        )

        # 重新构建：不应叠加旧边
        GraphService.build_trajectories_for_project(self.project.pk)
        self.assertEqual(
            GraphEdge.objects.filter(project=self.project, edge_type='trajectory').count(), 1
        )

    def test_build_trajectories_skips_missing_node(self):
        """如果角色没有对应的GraphNode，跳过不报错"""
        # 创建第二个角色，但不创建对应的 GraphNode
        char2 = _create_character(self.project, name='苏瑶', role_type='配角', gender='女')
        _create_trajectory(char2, self.project, title='流离')

        # 只有第一个角色有 GraphNode
        GraphService.build_trajectories_for_project(self.project.pk)

        # 第一个角色的轨迹应生成边
        edges = GraphEdge.objects.filter(project=self.project, edge_type='trajectory')
        self.assertEqual(edges.count(), 0)  # 苏瑶 没有 node，被跳过

        # 确认没有异常，方法正常完成（如果抛异常则测试失败）

    def test_build_trajectories_empty_project(self):
        """无轨迹的项目不生成任何边"""
        GraphService.build_trajectories_for_project(self.project.pk)

        edges = GraphEdge.objects.filter(project=self.project, edge_type='trajectory')
        self.assertEqual(edges.count(), 0)


class GraphEdgeModelTest(TestCase):
    """GraphEdge 模型测试"""

    def test_trajectory_edge_type_in_choices(self):
        """验证 'trajectory' 在 EDGE_TYPE_CHOICES 中"""
        edge_types = [choice[0] for choice in GraphEdge.EDGE_TYPE_CHOICES]
        self.assertIn('trajectory', edge_types)

    def test_create_trajectory_edge(self):
        """创建 trajectory 类型的 GraphEdge 并验证"""
        user = _create_user(username='edgeuser')
        project = _create_project(user, title='边测试项目')
        character = _create_character(project, name='张三')
        char_node = _create_character_node(project, character, name='张三')

        edge = GraphEdge.objects.create(
            project=project,
            source=char_node,
            target=char_node,
            edge_type='trajectory',
            description='测试轨迹边',
            properties={'trajectory_id': 1, 'start_time': '第一年', 'order': 1},
        )

        self.assertEqual(edge.edge_type, 'trajectory')
        self.assertEqual(edge.source, char_node)
        self.assertEqual(edge.target, char_node)
        self.assertTrue(edge.source_id == edge.target_id)
        self.assertEqual(edge.description, '测试轨迹边')
        self.assertEqual(edge.properties['trajectory_id'], 1)
