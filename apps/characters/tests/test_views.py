"""
characters 视图 API 测试

运行命令:
    python manage.py test apps.characters.tests.test_views --keepdb -v2
"""
import json
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.characters.models import Character, CharacterTrajectory
from apps.characters.views import (
    ApiCharacterBatchCreateView,
    ApiCharacterListView,
    ApiCharacterDetailView,
    ApiCharacterRelationshipTypesView,
    ApiCharacterOptimizeSaveView,
    ApiCharacterTrajectoryView,
    ApiCharacterTrajectoryDetailView,
    ApiCharacterGenerateView,
    ApiCharacterCheckView,
    ApiCharacterOptimizeView,
    ApiCharacterPolishView,
)
from apps.characters.tests.conftest import _create_test_data


# ============ 批量创建 API 测试 ============

class CharacterBatchCreateApiTest(TestCase):
    """批量创建角色 API 测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.factory = APIRequestFactory()

    def test_batch_create_characters(self):
        """POST /api/projects/<pk>/characters/batch-create/ 验证返回 success 和创建的角色数量"""
        view = ApiCharacterBatchCreateView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/batch-create/',
            data={
                'characters': [
                    {
                        'name': '李四',
                        'role_type': '配角',
                        'gender': '女',
                        'age': 20,
                        'source': 'ai_generate',
                    },
                    {
                        'name': '王五',
                        'role_type': '反派',
                        'gender': '男',
                        'age': 30,
                        'content': '# 角色内容\n\n暗藏野心',
                        'source': 'ai_generate',
                    },
                ]
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.project.id)

        response.render()
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['created_count'], 2)
        self.assertEqual(len(data['created']), 2)

        self.assertTrue(Character.objects.filter(project=self.project, name='李四').exists())
        self.assertTrue(Character.objects.filter(project=self.project, name='王五').exists())

        lisi = Character.objects.get(project=self.project, name='李四')
        self.assertEqual(lisi.role_type, '配角')
        self.assertEqual(lisi.gender, '女')
        self.assertEqual(lisi.age, 20)
        self.assertEqual(lisi.source, 'ai_generate')

    def test_batch_create_empty_list(self):
        """空列表应返回错误"""
        view = ApiCharacterBatchCreateView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/batch-create/',
            data={'characters': []},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.project.id)

        response.render()
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('error', data)

    def test_batch_create_duplicate_name_skipped(self):
        """已存在的角色名应跳过"""
        view = ApiCharacterBatchCreateView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/batch-create/',
            data={
                'characters': [
                    {'name': '张三', 'role_type': '主角'},
                    {'name': '新角色', 'role_type': '配角'},
                ]
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.project.id)
        response.render()
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['created_count'], 1)
        self.assertEqual(len(data['errors']), 1)
        self.assertIn('张三', data['errors'][0])

    def test_batch_create_exceeds_max_count(self):
        """超过50个角色返回错误"""
        chars = [{'name': f'角色{i}'} for i in range(51)]
        view = ApiCharacterBatchCreateView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/batch-create/',
            data={'characters': chars},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)

    def test_batch_create_restores_deleted(self):
        """同名已删除角色应恢复而非重复创建"""
        char = Character.objects.create(
            project=self.project, name='李四', is_deleted=True,
        )
        view = ApiCharacterBatchCreateView.as_view()
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/batch-create/',
            data={
                'characters': [
                    {'name': '李四', 'role_type': '配角', 'source': 'ai_generate'},
                ]
            },
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = view(request, pk=self.project.id)
        response.render()
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['created_count'], 1)
        char.refresh_from_db()
        self.assertFalse(char.is_deleted)


# ============ 角色列表 API 测试 ============

class CharacterListApiTest(TestCase):
    """GET/POST /characters/ API 测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.factory = APIRequestFactory()

    def test_get_character_list(self):
        """获取角色列表"""
        request = self.factory.get(f'/api/projects/{self.project.id}/characters/')
        force_authenticate(request, user=self.user)
        response = ApiCharacterListView.as_view()(request, pk=self.project.id)
        data = response.data
        self.assertTrue(data['success'])
        self.assertEqual(len(data['characters']), 1)
        self.assertEqual(data['characters'][0]['name'], '张三')

    def test_get_character_list_includes_deleted(self):
        """列表包含已删除角色"""
        self.character.is_deleted = True
        self.character.save()
        request = self.factory.get(f'/api/projects/{self.project.id}/characters/')
        force_authenticate(request, user=self.user)
        response = ApiCharacterListView.as_view()(request, pk=self.project.id)
        data = response.data
        self.assertEqual(len(data['characters']), 1)
        self.assertTrue(data['characters'][0]['is_deleted'])

    def test_create_character(self):
        """创建角色"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/',
            data={'name': '李四', 'role_type': '配角', 'gender': '女'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterListView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertTrue(Character.objects.filter(project=self.project, name='李四').exists())

    def test_create_character_duplicate_name(self):
        """创建重名角色返回错误"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/',
            data={'name': '张三', 'role_type': '配角'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterListView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn('duplicate', response.data.get('error_type', ''))

    def test_project_not_found(self):
        """不存在的项目返回404"""
        request = self.factory.get('/api/projects/99999/characters/')
        force_authenticate(request, user=self.user)
        response = ApiCharacterListView.as_view()(request, pk=99999)
        self.assertEqual(response.status_code, 404)


# ============ 角色详情 API 测试 ============

class CharacterDetailApiTest(TestCase):
    """GET/PUT/DELETE /characters/<id>/ API 测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.factory = APIRequestFactory()

    def test_get_character_detail(self):
        """获取角色详情"""
        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/{self.character.id}/'
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterDetailView.as_view()(
            request, pk=self.project.id, character_id=self.character.id,
        )
        data = response.data
        self.assertTrue(data['success'])
        self.assertEqual(data['character']['name'], '张三')
        self.assertEqual(data['character']['role_type'], '主角')
        self.assertEqual(data['character']['content'], '# 性格\n\n勇敢果断')

    def test_get_character_not_found(self):
        """获取不存在的角色返回404"""
        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/99999/'
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterDetailView.as_view()(
            request, pk=self.project.id, character_id=99999,
        )
        self.assertEqual(response.status_code, 404)

    def test_update_character(self):
        """更新角色"""
        request = self.factory.put(
            f'/api/projects/{self.project.id}/characters/{self.character.id}/',
            data={'name': '张三', 'role_type': '反派', 'gender': '女'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterDetailView.as_view()(
            request, pk=self.project.id, character_id=self.character.id,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.character.refresh_from_db()
        self.assertEqual(self.character.role_type, '反派')
        self.assertEqual(self.character.gender, '女')

    def test_update_character_duplicate_name(self):
        """更新时重名返回错误"""
        Character.objects.create(project=self.project, name='李四')
        request = self.factory.put(
            f'/api/projects/{self.project.id}/characters/{self.character.id}/',
            data={'name': '李四'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterDetailView.as_view()(
            request, pk=self.project.id, character_id=self.character.id,
        )
        self.assertEqual(response.status_code, 400)

    def test_delete_character(self):
        """删除角色（软删除）"""
        request = self.factory.delete(
            f'/api/projects/{self.project.id}/characters/{self.character.id}/'
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterDetailView.as_view()(
            request, pk=self.project.id, character_id=self.character.id,
        )
        self.assertEqual(response.status_code, 200)
        self.character.refresh_from_db()
        self.assertTrue(self.character.is_deleted)

    def test_restore_character(self):
        """恢复已删除角色"""
        self.character.is_deleted = True
        self.character.save()
        request = self.factory.put(
            f'/api/projects/{self.project.id}/characters/{self.character.id}/',
            data={'action': 'restore'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterDetailView.as_view()(
            request, pk=self.project.id, character_id=self.character.id,
        )
        self.assertEqual(response.status_code, 200)
        self.character.refresh_from_db()
        self.assertFalse(self.character.is_deleted)


# ============ 关系类型 API 测试 ============

class CharacterRelationshipTypesApiTest(TestCase):
    """GET /characters/relationship-types/ 测试"""

    def setUp(self):
        from django.contrib.auth.models import User
        from apps.project.models import ProjectList as Project
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.project = Project.objects.create(
            user=self.user, title='测试项目', genre='xuanhuan', description='测试',
        )
        self.factory = APIRequestFactory()

    def test_get_relationship_types(self):
        """获取关系类型配置"""
        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/relationship-types/'
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterRelationshipTypesView.as_view()(request, pk=self.project.id)
        data = response.data
        self.assertIn('types', data)
        self.assertIn('reverse_map', data)
        self.assertIn('en_to_cn', data)
        self.assertEqual(len(data['types']), 17)
        self.assertEqual(data['reverse_map']['父母'], '子女')


# ============ 优化保存 API 测试 ============

class CharacterOptimizeSaveApiTest(TestCase):
    """POST /characters/optimize/save/ 测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.factory = APIRequestFactory()

    def _post(self, data):
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/optimize/save/',
            data=data,
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        return ApiCharacterOptimizeSaveView.as_view()(request, pk=self.project.id)

    def test_modify_character_field(self):
        """修改角色字段"""
        response = self._post({
            'optimizations': [{
                'name': '张三',
                'type': 'modify',
                'params': [{'param': '身份', 'new': '剑神'}],
            }]
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.character.refresh_from_db()
        self.assertEqual(self.character.identity, '剑神')

    def test_add_new_character(self):
        """新增角色"""
        response = self._post({
            'optimizations': [{
                'name': '新角色',
                'type': 'add',
                'params': [
                    {'param': '定位', 'new': '配角'},
                    {'param': '性别', 'new': '女'},
                ],
            }]
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['saved_count'], 1)
        self.assertTrue(Character.objects.filter(project=self.project, name='新角色').exists())

    def test_delete_character(self):
        """删除角色"""
        response = self._post({
            'optimizations': [{
                'name': '张三',
                'type': 'delete',
                'params': [],
            }]
        })
        self.assertEqual(response.status_code, 200)
        self.character.refresh_from_db()
        self.assertTrue(self.character.is_deleted)

    def test_empty_optimizations(self):
        """空优化列表返回错误"""
        response = self._post({'optimizations': []})
        self.assertEqual(response.status_code, 400)

    def test_modify_nonexistent_character(self):
        """修改不存在的角色跳过"""
        response = self._post({
            'optimizations': [{
                'name': '不存在的角色',
                'type': 'modify',
                'params': [{'param': '身份', 'new': '新身份'}],
            }]
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['saved_count'], 0)

    def test_add_duplicate_name(self):
        """新增重名角色返回警告"""
        response = self._post({
            'optimizations': [{
                'name': '张三',
                'type': 'add',
                'params': [{'param': '定位', 'new': '配角'}],
            }]
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('warnings', response.data)


# ============ 角色轨迹 API 测试 ============

class CharacterTrajectoryApiTest(TestCase):
    """角色轨迹 API 测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.factory = APIRequestFactory()

    def _create_trajectory(self, **kwargs):
        defaults = {
            'character': self.character,
            'project': self.project,
            'title': '默认轨迹',
            'order': 0,
        }
        defaults.update(kwargs)
        return CharacterTrajectory.objects.create(**defaults)

    def test_get_trajectories(self):
        """获取角色所有轨迹"""
        self._create_trajectory(title='轨迹1', order=1)
        self._create_trajectory(title='轨迹2', order=2)
        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/{self.character.id}/trajectories/'
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterTrajectoryView.as_view()(
            request, pk=self.project.id, character_id=self.character.id,
        )
        data = response.data
        self.assertTrue(data['success'])
        self.assertEqual(len(data['data']['trajectories']), 2)

    def test_get_trajectory_detail(self):
        """获取单个轨迹详情"""
        traj = self._create_trajectory(title='初入江湖')
        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/{self.character.id}/trajectories/{traj.id}/'
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterTrajectoryDetailView.as_view()(
            request, pk=self.project.id, character_id=self.character.id, trajectory_id=traj.id,
        )
        data = response.data
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['title'], '初入江湖')

    def test_update_trajectory(self):
        """更新轨迹"""
        traj = self._create_trajectory(title='旧标题')
        request = self.factory.put(
            f'/api/projects/{self.project.id}/characters/{self.character.id}/trajectories/{traj.id}/',
            data={'title': '新标题', 'start_time': '第一章'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterTrajectoryDetailView.as_view()(
            request, pk=self.project.id, character_id=self.character.id, trajectory_id=traj.id,
        )
        self.assertEqual(response.status_code, 200)
        traj.refresh_from_db()
        self.assertEqual(traj.title, '新标题')

    def test_delete_trajectory(self):
        """删除轨迹"""
        traj = self._create_trajectory(title='要删除的轨迹')
        traj_id = traj.pk
        request = self.factory.delete(
            f'/api/projects/{self.project.id}/characters/{self.character.id}/trajectories/{traj_id}/'
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterTrajectoryDetailView.as_view()(
            request, pk=self.project.id, character_id=self.character.id, trajectory_id=traj_id,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CharacterTrajectory.objects.filter(pk=traj_id).exists())

    def test_trajectory_not_found(self):
        """不存在的轨迹返回404"""
        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/{self.character.id}/trajectories/99999/'
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterTrajectoryDetailView.as_view()(
            request, pk=self.project.id, character_id=self.character.id, trajectory_id=99999,
        )
        self.assertEqual(response.status_code, 404)


# ============ LLM 视图早期返回测试 ============

class CharacterGenerateViewValidationTest(TestCase):
    """ApiCharacterGenerateView.post 参数校验测试（不触发 LLM 调用）"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.factory = APIRequestFactory()

    def test_empty_requirement_returns_400(self):
        """空需求返回 400"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/generate/',
            data={'requirement': ''},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterGenerateView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('error', response.data)

    def test_whitespace_only_requirement_returns_400(self):
        """纯空格需求返回 400"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/generate/',
            data={'requirement': '   '},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterGenerateView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)

    def test_too_long_requirement_returns_400(self):
        """超过 2000 字的需求返回 400"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/generate/',
            data={'requirement': 'a' * 2001},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterGenerateView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn('2000', response.data['error'])

    def test_project_not_found(self):
        """不存在的项目返回 404"""
        request = self.factory.post(
            '/api/projects/99999/characters/generate/',
            data={'requirement': '测试需求'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterGenerateView.as_view()(request, pk=99999)
        self.assertEqual(response.status_code, 404)


class CharacterCheckViewValidationTest(TestCase):
    """ApiCharacterCheckView.post 参数校验测试（不触发 LLM 调用）"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.factory = APIRequestFactory()

    def test_no_characters_returns_400(self):
        """无角色时返回 400"""
        Character.objects.filter(project=self.project).update(is_deleted=True)
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/check/',
            data={},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterCheckView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('暂无角色', response.data['error'])

    def test_project_not_found(self):
        """不存在的项目返回 404"""
        request = self.factory.post(
            '/api/projects/99999/characters/check/',
            data={},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterCheckView.as_view()(request, pk=99999)
        self.assertEqual(response.status_code, 404)


class CharacterOptimizeViewValidationTest(TestCase):
    """ApiCharacterOptimizeView.post 参数校验测试（不触发 LLM 调用）"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.factory = APIRequestFactory()

    def test_empty_issues_returns_400(self):
        """空问题列表返回 400"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/optimize/',
            data={'issues': []},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterOptimizeView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn('问题列表', response.data['error'])

    def test_no_matching_characters_returns_400(self):
        """问题涉及的角色不存在时返回 400"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/characters/optimize/',
            data={'issues': [{'characters': ['不存在的角色'], 'type': 'test'}]},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterOptimizeView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn('未找到相关角色', response.data['error'])

    def test_project_not_found(self):
        """不存在的项目返回 404"""
        request = self.factory.post(
            '/api/projects/99999/characters/optimize/',
            data={'issues': [{'characters': ['张三']}]},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterOptimizeView.as_view()(request, pk=99999)
        self.assertEqual(response.status_code, 404)


class CharacterPolishViewGetValidationTest(TestCase):
    """ApiCharacterPolishView.get 参数校验测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.factory = APIRequestFactory()

    def test_missing_task_id_returns_400(self):
        """缺少 task_id 返回 400"""
        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/polish/',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterPolishView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn('task_id', response.data['error'])

    def test_expired_result_returns_404(self):
        """结果不存在/已过期返回 404"""
        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/polish/?task_id=nonexistent_task',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterPolishView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 404)

    def test_error_status_returns_500(self):
        """缓存中状态为 error 时返回 500"""
        from django.core.cache import cache
        cache.set('polish_result:test_task', {'status': 'error', 'error': 'LLM 调用失败'}, 300)

        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/polish/?task_id=test_task',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterPolishView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 500)

    def test_completed_status_returns_data(self):
        """缓存中状态为 completed 时返回数据"""
        from django.core.cache import cache
        cache.set('polish_result:completed_task', {
            'status': 'completed',
            'parsed_data': {'name': '张三', 'content': '优化后的内容'},
            'full_content': '完整的优化结果',
        }, 300)

        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/polish/?task_id=completed_task',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterPolishView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['name'], '张三')

    def test_unknown_status_returns_500(self):
        """缓存中未知状态返回 500"""
        from django.core.cache import cache
        cache.set('polish_result:unknown_task', {'status': 'unknown'}, 300)

        request = self.factory.get(
            f'/api/projects/{self.project.id}/characters/polish/?task_id=unknown_task',
        )
        force_authenticate(request, user=self.user)
        response = ApiCharacterPolishView.as_view()(request, pk=self.project.id)
        self.assertEqual(response.status_code, 500)
