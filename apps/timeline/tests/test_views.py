"""
timeline 图谱接口测试

运行命令:
    python manage.py test apps.timeline.tests.test_views --keepdb
    python manage.py test apps.timeline.tests.test_views.TimelineGraphApiTest --keepdb
    python manage.py test apps.timeline.tests.test_views.TimelineGraphStatsApiTest --keepdb
"""
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.project.models import ProjectList
from apps.characters.models import Character, CharacterTrajectory
from apps.timeline.models import TimelineEvent
from apps.timeline.views import ApiTimelineGraphView, ApiTimelineGraphStatsView


def _create_user(username='testuser', password='testpass123'):
    """创建测试用户"""
    return User.objects.create_user(username=username, password=password)


def _create_project(user, title='测试项目', genre='xuanhuan'):
    """创建测试项目"""
    return ProjectList.objects.create(user=user, title=title, genre=genre)


def _create_character(project, name='林风', role_type='主角'):
    """创建测试角色"""
    return Character.objects.create(project=project, name=name, role_type=role_type)


def _create_event(project, title='事件', start_year=1, event_type='main', location='', **kwargs):
    """创建测试时间线事件"""
    return TimelineEvent.objects.create(
        project=project, title=title, start_year=start_year,
        event_type=event_type, location=location, **kwargs
    )


def _create_trajectory(character, project, title='轨迹', **kwargs):
    """创建测试角色轨迹"""
    return CharacterTrajectory.objects.create(
        character=character, project=project, title=title, **kwargs
    )


class TimelineGraphApiTest(TestCase):
    """图谱聚合数据 API 测试"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.view = ApiTimelineGraphView.as_view()

    def test_graph_global_view(self):
        """GET /api/projects/<pk>/timeline/graph/ 返回全局视图数据"""
        event = _create_event(self.project, title='林风出生', start_year=1, location='青云城')
        character = _create_character(self.project)
        event.characters.add(character)

        request = self.factory.get(f'/api/projects/{self.project.pk}/timeline/graph/')
        force_authenticate(request, user=self.user)
        response = self.view(request, project_id=self.project.pk)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue(data['success'])
        self.assertIn('timeline', data['data'])
        self.assertIn('meta', data['data'])
        self.assertEqual(len(data['data']['timeline']), 1)
        self.assertEqual(data['data']['timeline'][0]['title'], '林风出生')
        self.assertEqual(data['data']['meta']['total_events'], 1)

    def test_graph_character_view(self):
        """带 ?view=character&character_id=<id> 参数，验证返回 trajectories"""
        character = _create_character(self.project, name='林风')
        event = _create_event(self.project, title='林风入门', start_year=1)
        event.characters.add(character)
        _create_trajectory(character, self.project, title='入门修炼')

        request = self.factory.get(
            f'/api/projects/{self.project.pk}/timeline/graph/',
            {'view': 'character', 'character_id': character.pk}
        )
        force_authenticate(request, user=self.user)
        response = self.view(request, project_id=self.project.pk)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue(data['success'])
        self.assertIn('trajectories', data['data'])
        self.assertEqual(len(data['data']['trajectories']), 1)
        self.assertEqual(data['data']['trajectories'][0]['title'], '入门修炼')

    def test_graph_location_view(self):
        """带 ?view=location&location_name=青云城 参数，验证只返回该地点事件"""
        _create_event(self.project, title='青云城事件', start_year=1, location='青云城')
        _create_event(self.project, title='帝都事件', start_year=2, location='帝都')

        request = self.factory.get(
            f'/api/projects/{self.project.pk}/timeline/graph/',
            {'view': 'location', 'location_name': '青云城'}
        )
        force_authenticate(request, user=self.user)
        response = self.view(request, project_id=self.project.pk)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']['timeline']), 1)
        self.assertEqual(data['data']['timeline'][0]['location'], '青云城')
        self.assertEqual(data['data']['meta']['total_events'], 1)

    def test_graph_time_filter(self):
        """带 ?start_year=1&end_year=5 参数，验证时间过滤"""
        _create_event(self.project, title='第1年事件', start_year=1)
        _create_event(self.project, title='第3年事件', start_year=3)
        _create_event(self.project, title='第8年事件', start_year=8)

        request = self.factory.get(
            f'/api/projects/{self.project.pk}/timeline/graph/',
            {'start_year': '1', 'end_year': '5'}
        )
        force_authenticate(request, user=self.user)
        response = self.view(request, project_id=self.project.pk)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']['timeline']), 2)
        titles = [e['title'] for e in data['data']['timeline']]
        self.assertIn('第1年事件', titles)
        self.assertIn('第3年事件', titles)
        self.assertNotIn('第8年事件', titles)


class TimelineGraphStatsApiTest(TestCase):
    """统计视图 API 测试"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.view = ApiTimelineGraphStatsView.as_view()

    def test_stats_returns_all_fields(self):
        """GET /api/projects/<pk>/timeline/graph/stats/ 返回所有统计字段"""
        _create_event(self.project, title='事件1', start_year=1, event_type='main')
        _create_character(self.project)

        request = self.factory.get(f'/api/projects/{self.project.pk}/timeline/graph/stats/')
        force_authenticate(request, user=self.user)
        response = self.view(request, project_id=self.project.pk)

        self.assertEqual(response.status_code, 200)
        data = response.data
        self.assertTrue(data['success'])
        stats = data['data']
        self.assertIn('total_events', stats)
        self.assertIn('event_type_counts', stats)
        self.assertIn('time_span', stats)
        self.assertIn('total_characters', stats)
        self.assertIn('total_trajectories', stats)
        self.assertIn('top_characters', stats)
        self.assertIn('top_locations', stats)

    def test_stats_event_type_counts(self):
        """创建不同类型事件，验证 counts 正确"""
        _create_event(self.project, title='主线1', start_year=1, event_type='main')
        _create_event(self.project, title='主线2', start_year=2, event_type='main')
        _create_event(self.project, title='支线1', start_year=3, event_type='side')
        _create_event(self.project, title='人物1', start_year=4, event_type='character')
        _create_event(self.project, title='世界1', start_year=5, event_type='world')
        _create_event(self.project, title='世界2', start_year=6, event_type='world')

        request = self.factory.get(f'/api/projects/{self.project.pk}/timeline/graph/stats/')
        force_authenticate(request, user=self.user)
        response = self.view(request, project_id=self.project.pk)

        self.assertEqual(response.status_code, 200)
        counts = response.data['data']['event_type_counts']
        self.assertEqual(counts['main'], 2)
        self.assertEqual(counts['side'], 1)
        self.assertEqual(counts['character'], 1)
        self.assertEqual(counts['world'], 2)
        self.assertEqual(response.data['data']['total_events'], 6)

    def test_stats_empty_project(self):
        """空项目返回全零/空数据"""
        request = self.factory.get(f'/api/projects/{self.project.pk}/timeline/graph/stats/')
        force_authenticate(request, user=self.user)
        response = self.view(request, project_id=self.project.pk)

        self.assertEqual(response.status_code, 200)
        stats = response.data['data']
        self.assertEqual(stats['total_events'], 0)
        self.assertEqual(stats['event_type_counts'], {})
        self.assertIsNone(stats['time_span']['earliest_year'])
        self.assertIsNone(stats['time_span']['latest_year'])
        self.assertEqual(stats['total_characters'], 0)
        self.assertEqual(stats['total_trajectories'], 0)
        self.assertEqual(stats['top_characters'], [])
        self.assertEqual(stats['top_locations'], [])
