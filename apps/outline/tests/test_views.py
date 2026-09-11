"""
outline 接口测试

运行命令:
    python manage.py test apps.outline.tests.test_views --keepdb -v2
    python manage.py test apps.outline.tests.test_views.OutlineModelTest --keepdb
    python manage.py test apps.outline.tests.test_views.OutlineApplyPatchesTest --keepdb
    python manage.py test apps.outline.tests.test_views.OutlineSaveApiTest --keepdb
    python manage.py test apps.outline.tests.test_views.OutlineVersionApiTest --keepdb
    python manage.py test apps.outline.tests.test_views.OutlineChatHistoryDeleteTest --keepdb
"""
import json
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from rest_framework.test import force_authenticate

from apps.project.models import ProjectList as Project
from apps.outline.models import Outline, OutlineChatHistory
from apps.outline.views import (
    _apply_patches,
    ApiSaveOutlineView,
    ApiLoadOutlineView,
    ApiOutlinesView,
    ApiOutlineDetailView,
    ApiLatestOutlineView,
    ApiOutlineFinalizeView,
    ApiOutlineLockView,
    ApiOutlineUnlockView,
    ApiOutlineDeleteView,
    ApiChatHistoryDeleteView,
    ApiFinalizeOutlineView,
    ApiRestoreOutlineView,
)


# ============ 辅助函数 ============

def _create_user(username='testuser'):
    return User.objects.create_user(username=username, password='testpass123')


def _create_project(user, title='测试项目', genre='xuanhuan'):
    return Project.objects.create(user=user, title=title, genre=genre, description='测试')


def _create_outline(project, version=1, content='大纲内容', is_finalized=False, is_deleted=False):
    return Outline.objects.create(
        project=project, version=version, content=content,
        is_finalized=is_finalized, is_deleted=is_deleted,
    )


def _create_chat_history(outline, role='user', content='test'):
    return OutlineChatHistory.objects.create(outline=outline, role=role, content=content)


# ============ 模型测试 ============

class OutlineModelTest(TestCase):
    """Outline 模型测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)

    def test_create_outline(self):
        """创建大纲并验证所有字段"""
        outline = _create_outline(self.project, version=1, content='# 大纲\n\n第一章')
        self.assertEqual(outline.project, self.project)
        self.assertEqual(outline.version, 1)
        self.assertEqual(outline.content, '# 大纲\n\n第一章')
        self.assertFalse(outline.is_finalized)
        self.assertFalse(outline.is_deleted)
        self.assertEqual(outline.last_question, '')
        self.assertEqual(outline.last_options, [])
        self.assertIsNotNone(outline.created_at)
        self.assertIsNotNone(outline.updated_at)

    def test_outline_str(self):
        """验证 __str__ 返回 '项目标题 - 大纲 v{version}'"""
        outline = _create_outline(self.project, version=3)
        self.assertEqual(str(outline), '测试项目 - 大纲 v3')

    def test_outline_ordering(self):
        """按 version 降序排列"""
        _create_outline(self.project, version=3, content='v3')
        _create_outline(self.project, version=1, content='v1')
        _create_outline(self.project, version=2, content='v2')
        versions = list(Outline.objects.filter(project=self.project).values_list('version', flat=True))
        self.assertEqual(versions, [3, 2, 1])

    def test_get_or_create_building_creates(self):
        """get_or_create_building 创建 version=0 的草稿版本"""
        outline = Outline.get_or_create_building(self.project)
        self.assertEqual(outline.version, 0)
        self.assertEqual(outline.content, '')
        self.assertFalse(outline.is_finalized)
        self.assertEqual(outline.project, self.project)

    def test_get_or_create_building_reuses(self):
        """get_or_create_building 重复调用返回同一实例"""
        outline1 = Outline.get_or_create_building(self.project)
        outline2 = Outline.get_or_create_building(self.project)
        self.assertEqual(outline1.pk, outline2.pk)
        self.assertEqual(Outline.objects.filter(project=self.project, version=0).count(), 1)

    def test_cascade_delete(self):
        """删除项目时大纲级联删除"""
        _create_outline(self.project)
        project_id = self.project.id
        self.assertEqual(Outline.objects.filter(project_id=project_id).count(), 1)
        self.project.delete()
        self.assertEqual(Outline.objects.filter(project_id=project_id).count(), 0)


class OutlineChatHistoryModelTest(TestCase):
    """OutlineChatHistory 模型测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.outline = _create_outline(self.project)

    def test_create_chat_history(self):
        """创建聊天历史"""
        msg = _create_chat_history(self.outline, role='user', content='帮我构建大纲')
        self.assertEqual(msg.outline, self.outline)
        self.assertEqual(msg.role, 'user')
        self.assertEqual(msg.content, '帮我构建大纲')
        self.assertFalse(msg.is_deleted)
        self.assertIsNotNone(msg.created_at)

    def test_chat_history_str(self):
        """验证 __str__"""
        msg = _create_chat_history(self.outline, role='assistant')
        self.assertEqual(str(msg), '测试项目 - assistant')

    def test_chat_history_ordering(self):
        """按 created_at 升序排列"""
        _create_chat_history(self.outline, role='user', content='msg1')
        _create_chat_history(self.outline, role='assistant', content='msg2')
        msgs = list(OutlineChatHistory.objects.filter(outline=self.outline).values_list('content', flat=True))
        self.assertEqual(msgs, ['msg1', 'msg2'])

    def test_cascade_delete(self):
        """删除大纲时聊天历史级联删除"""
        _create_chat_history(self.outline, role='user')
        _create_chat_history(self.outline, role='assistant')
        self.outline.delete()
        self.assertEqual(OutlineChatHistory.objects.count(), 0)


# ============ _apply_patches 测试 ============

class OutlineApplyPatchesTest(TestCase):
    """_apply_patches 补丁应用函数测试"""

    def test_empty_patch_list(self):
        """空 patch_list 返回原始内容"""
        result = _apply_patches({'patch_list': []}, '原始内容')
        self.assertEqual(result['new_content'], '原始内容')
        self.assertEqual(result['edits_applied'], 0)
        self.assertEqual(result['edits_total'], 0)

    def test_add_to_empty_content(self):
        """空内容时新增补丁"""
        data = {'patch_list': [{'old_snippet': '', 'new_snippet': '# 大纲\n\n内容'}]}
        result = _apply_patches(data, '')
        self.assertEqual(result['new_content'], '# 大纲\n\n内容')
        self.assertEqual(result['edits_applied'], 1)

    def test_append_to_existing_content(self):
        """有内容时追加"""
        data = {'patch_list': [{'old_snippet': '', 'new_snippet': '追加'}]}
        result = _apply_patches(data, '已有')
        self.assertEqual(result['new_content'], '已有\n\n追加')
        self.assertEqual(result['edits_applied'], 1)

    def test_replace_snippet(self):
        """精确替换"""
        data = {'patch_list': [{'old_snippet': '旧', 'new_snippet': '新'}]}
        result = _apply_patches(data, '这是旧文本')
        self.assertEqual(result['new_content'], '这是新文本')
        self.assertEqual(result['edits_summary'][0]['type'], 'replace')

    def test_replace_no_match(self):
        """未匹配时跳过"""
        data = {'patch_list': [{'old_snippet': '不存在', 'new_snippet': '新'}]}
        result = _apply_patches(data, '原始内容')
        self.assertEqual(result['new_content'], '原始内容')
        self.assertEqual(result['edits_summary'][0]['type'], 'failed')

    def test_replace_ambiguous(self):
        """多处匹配时跳过"""
        data = {'patch_list': [{'old_snippet': '重复', 'new_snippet': '新'}]}
        result = _apply_patches(data, '这里有重复，那里也有重复')
        self.assertEqual(result['edits_applied'], 0)
        self.assertEqual(result['edits_summary'][0]['type'], 'ambiguous')

    def test_multiple_patches(self):
        """多个补丁按顺序应用"""
        data = {
            'patch_list': [
                {'old_snippet': 'A', 'new_snippet': 'A2'},
                {'old_snippet': 'B', 'new_snippet': 'B2'},
            ]
        }
        result = _apply_patches(data, 'A and B')
        self.assertEqual(result['new_content'], 'A2 and B2')
        self.assertEqual(result['edits_applied'], 2)

    def test_extract_options_from_question(self):
        """从 question 中提取 👉 格式选项"""
        data = {
            'patch_list': [],
            'question': '请选择方向\n👉 选项A\n👉 选项B',
        }
        result = _apply_patches(data, '内容')
        self.assertIn('选项A', result['options'])
        self.assertIn('选项B', result['options'])
        # question 中的选项行被移除
        self.assertNotIn('👉', result['question'])

    def test_question_without_options(self):
        """question 中无选项时原样传递"""
        data = {
            'patch_list': [],
            'question': '你想要什么？',
            'options': ['预设选项'],
        }
        result = _apply_patches(data, '内容')
        self.assertEqual(result['question'], '你想要什么？')
        self.assertEqual(result['options'], ['预设选项'])

    def test_characters_passed_through(self):
        """characters 字段原样传递"""
        data = {
            'patch_list': [],
            'characters': [{'name': '张三'}],
        }
        result = _apply_patches(data, '内容')
        self.assertEqual(result['characters'], [{'name': '张三'}])


# ============ API 视图测试 ============

class OutlineSaveApiTest(TestCase):
    """POST /outline/versions/save/ 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def _post(self, data):
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/versions/save/',
            data=data,
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        return ApiSaveOutlineView.as_view()(request, project_id=self.project.id)

    def test_save_new_version(self):
        """new_version=true 创建新版本"""
        response = self._post({
            'content': '大纲内容v1',
            'new_version': 'true',
        })
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['version_number'], 1)
        self.assertTrue(Outline.objects.filter(project=self.project, version=1).exists())

    def test_save_new_version_increment(self):
        """new_version=true 时版本号递增"""
        _create_outline(self.project, version=1)
        response = self._post({
            'content': '大纲内容v2',
            'new_version': 'true',
        })
        data = json.loads(response.content)
        self.assertEqual(data['version_number'], 2)

    def test_save_update_existing_version(self):
        """指定 version_id 更新已有版本"""
        outline = _create_outline(self.project, version=1, content='旧内容')
        response = self._post({
            'content': '新内容',
            'version_id': outline.id,
        })
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        outline.refresh_from_db()
        self.assertEqual(outline.content, '新内容')

    def test_save_update_finalized_version(self):
        """已定稿版本不能修改"""
        outline = _create_outline(self.project, version=1, is_finalized=True)
        response = self._post({
            'content': '新内容',
            'version_id': outline.id,
        })
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('锁定', data['error'])

    def test_save_update_latest_version(self):
        """无 version_id 时更新最新版本"""
        _create_outline(self.project, version=1, content='旧内容')
        response = self._post({
            'content': '更新后的内容',
        })
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        outline = Outline.objects.filter(project=self.project).order_by('-version').first()
        self.assertEqual(outline.content, '更新后的内容')

    def test_save_create_when_no_outline(self):
        """无版本时自动创建 version=1"""
        response = self._post({
            'content': '首次创建的大纲',
        })
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['version_number'], 1)

    def test_save_empty_content_error(self):
        """空内容返回错误"""
        response = self._post({'content': ''})
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('不能为空', data['error'])

    def test_save_content_too_long(self):
        """超长内容返回错误"""
        response = self._post({'content': 'A' * 200001})
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('不能超过', data['error'])


class OutlineLoadApiTest(TestCase):
    """GET /outline/versions/<vid>/load/ 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def test_load_version(self):
        """正常加载版本"""
        outline = _create_outline(self.project, version=2, content='v2内容', is_finalized=True)
        outline.last_question = '下一步？'
        outline.last_options = ['A', 'B']
        outline.save()
        request = self.factory.get(f'/api/projects/{self.project.id}/outline/versions/{outline.id}/load/')
        force_authenticate(request, user=self.user)
        response = ApiLoadOutlineView.as_view()(request, project_id=self.project.id, version_id=outline.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['content'], 'v2内容')
        self.assertEqual(data['version_number'], 2)
        self.assertTrue(data['is_finalized'])
        self.assertEqual(data['last_question'], '下一步？')
        self.assertEqual(data['last_options'], ['A', 'B'])

    def test_load_nonexistent_version(self):
        """加载不存在的版本返回404"""
        request = self.factory.get(f'/api/projects/{self.project.id}/outline/versions/99999/load/')
        force_authenticate(request, user=self.user)
        response = ApiLoadOutlineView.as_view()(request, project_id=self.project.id, version_id=99999)
        self.assertEqual(response.status_code, 404)


class OutlineListApiTest(TestCase):
    """GET /outline/versions/ 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def test_list_empty(self):
        """无版本时返回空列表"""
        request = self.factory.get(f'/api/projects/{self.project.id}/outline/versions/')
        force_authenticate(request, user=self.user)
        response = ApiOutlinesView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['versions'], [])
        self.assertIsNone(data['latest'])

    def test_list_with_versions(self):
        """有版本时正确返回列表"""
        _create_outline(self.project, version=1, content='v1')
        _create_outline(self.project, version=2, content='v2')
        request = self.factory.get(f'/api/projects/{self.project.id}/outline/versions/')
        force_authenticate(request, user=self.user)
        response = ApiOutlinesView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['versions']), 2)
        self.assertEqual(data['latest']['version_number'], 2)

    def test_list_excludes_deleted(self):
        """排除已删除的版本"""
        _create_outline(self.project, version=1)
        _create_outline(self.project, version=2, is_deleted=True)
        request = self.factory.get(f'/api/projects/{self.project.id}/outline/versions/')
        force_authenticate(request, user=self.user)
        response = ApiOutlinesView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertEqual(len(data['versions']), 1)


class OutlineDetailApiTest(TestCase):
    """GET /outline/versions/<vid>/ 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def test_get_detail(self):
        """获取版本详情"""
        outline = _create_outline(self.project, version=1, content='详细内容')
        request = self.factory.get(f'/api/projects/{self.project.id}/outline/versions/{outline.id}/')
        force_authenticate(request, user=self.user)
        response = ApiOutlineDetailView.as_view()(request, project_id=self.project.id, version_id=outline.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['content'], '详细内容')
        self.assertEqual(data['version_number'], 1)
        self.assertFalse(data['is_finalized'])

    def test_get_detail_not_found(self):
        """不存在的版本返回500（视图捕获所有异常）"""
        request = self.factory.get(f'/api/projects/{self.project.id}/outline/versions/99999/')
        force_authenticate(request, user=self.user)
        response = ApiOutlineDetailView.as_view()(request, project_id=self.project.id, version_id=99999)
        self.assertEqual(response.status_code, 500)


class OutlineLatestApiTest(TestCase):
    """GET /outline/latest/ 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def test_get_latest_creates_building(self):
        """无草稿时自动创建 version=0 的草稿"""
        request = self.factory.get(f'/api/projects/{self.project.id}/outline/latest/')
        force_authenticate(request, user=self.user)
        response = ApiLatestOutlineView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['outline']['version_number'], 0)
        self.assertEqual(data['outline']['content'], '')

    def test_get_latest_existing_building(self):
        """已有草稿时直接返回"""
        outline = Outline.get_or_create_building(self.project)
        outline.content = '草稿内容'
        outline.save()
        request = self.factory.get(f'/api/projects/{self.project.id}/outline/latest/')
        force_authenticate(request, user=self.user)
        response = ApiLatestOutlineView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['outline']['content'], '草稿内容')
        self.assertEqual(data['outline']['version_number'], 0)


class OutlineFinalizeApiTest(TestCase):
    """POST /outline/finalize/ 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def _post(self, data):
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/finalize/',
            data=data,
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        return ApiOutlineFinalizeView.as_view()(request, project_id=self.project.id)

    def test_finalize_version(self):
        """定稿指定版本"""
        outline = _create_outline(self.project, version=1, content='大纲v1')
        response = self._post({'version_id': outline.id})
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        outline.refresh_from_db()
        self.assertTrue(outline.is_finalized)

    def test_finalize_unsets_previous(self):
        """定稿新版本时取消之前的定稿"""
        outline1 = _create_outline(self.project, version=1, content='v1', is_finalized=True)
        outline2 = _create_outline(self.project, version=2, content='v2')
        response = self._post({'version_id': outline2.id})
        self.assertEqual(response.status_code, 200)
        outline1.refresh_from_db()
        outline2.refresh_from_db()
        self.assertFalse(outline1.is_finalized)
        self.assertTrue(outline2.is_finalized)

    def test_finalize_missing_version_id(self):
        """缺少 version_id 返回错误"""
        response = self._post({})
        self.assertEqual(response.status_code, 400)

    def test_finalize_with_content_update(self):
        """定稿时可同时更新内容（ApiFinalizeOutlineView 支持 content 参数）"""
        outline = _create_outline(self.project, version=1, content='旧内容')
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/finalize/',
            data={'version_id': outline.id, 'content': '定稿最终版'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiFinalizeOutlineView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        outline.refresh_from_db()
        self.assertEqual(outline.content, '定稿最终版')
        self.assertTrue(outline.is_finalized)


class OutlineLockUnlockApiTest(TestCase):
    """锁定/解锁版本 API 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def test_lock_version(self):
        """POST 锁定版本"""
        outline = _create_outline(self.project, version=1)
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/lock/',
            data={'version_id': outline.id},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiOutlineLockView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        outline.refresh_from_db()
        self.assertTrue(outline.is_finalized)

    def test_unlock_version(self):
        """POST 解锁版本"""
        outline = _create_outline(self.project, version=1, is_finalized=True)
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/unlock/',
            data={'version_id': outline.id},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiOutlineUnlockView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        outline.refresh_from_db()
        self.assertFalse(outline.is_finalized)

    def test_lock_missing_params(self):
        """缺少 version_id 返回错误"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/lock/',
            data={},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiOutlineLockView.as_view()(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 400)


class OutlineDeleteApiTest(TestCase):
    """删除版本 API 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def test_delete_version(self):
        """POST 软删除版本"""
        outline = _create_outline(self.project, version=1)
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/delete/',
            data={'version_id': outline.id},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiOutlineDeleteView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        outline.refresh_from_db()
        self.assertTrue(outline.is_deleted)

    def test_delete_finalized_version(self):
        """定稿版本不能删除"""
        outline = _create_outline(self.project, version=1, is_finalized=True)
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/delete/',
            data={'version_id': outline.id},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiOutlineDeleteView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('锁定', data['message'])

    def test_delete_missing_version_id(self):
        """缺少 version_id 返回错误"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/delete/',
            data={},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiOutlineDeleteView.as_view()(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 400)


class OutlineRestoreApiTest(TestCase):
    """恢复版本 API 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def test_restore_version(self):
        """POST 恢复已删除版本"""
        outline = _create_outline(self.project, version=1, is_deleted=True)
        request = self.factory.post(
            '/api/projects/outline/restore/',
            data={'version_id': outline.id},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiRestoreOutlineView.as_view()(request)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        outline.refresh_from_db()
        self.assertFalse(outline.is_deleted)

    def test_restore_missing_version_id(self):
        """缺少 version_id 返回错误"""
        request = self.factory.post(
            '/api/projects/outline/restore/',
            data={},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiRestoreOutlineView.as_view()(request)
        self.assertEqual(response.status_code, 400)


class OutlineChatHistoryDeleteTest(TestCase):
    """批量删除聊天记录 API 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.outline = _create_outline(self.project)
        self.factory = RequestFactory()

    def test_batch_delete(self):
        """正常批量删除聊天记录"""
        msg1 = _create_chat_history(self.outline, role='user', content='msg1')
        msg2 = _create_chat_history(self.outline, role='assistant', content='msg2')
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/chat-history/delete/',
            data={'message_ids': json.dumps([msg1.id, msg2.id])},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiChatHistoryDeleteView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['deleted_count'], 2)
        self.assertFalse(OutlineChatHistory.objects.filter(pk=msg1.pk).exists())
        self.assertFalse(OutlineChatHistory.objects.filter(pk=msg2.pk).exists())

    def test_delete_empty_ids(self):
        """空 message_ids 返回错误"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/chat-history/delete/',
            data={'message_ids': '[]'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiChatHistoryDeleteView.as_view()(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 400)

    def test_delete_invalid_json(self):
        """无效 JSON 格式返回错误"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/chat-history/delete/',
            data={'message_ids': 'not_json'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiChatHistoryDeleteView.as_view()(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 400)

    def test_delete_non_integer_ids(self):
        """包含非整数 ID 返回错误"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/chat-history/delete/',
            data={'message_ids': json.dumps(['abc', 123])},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiChatHistoryDeleteView.as_view()(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 400)

    def test_delete_exceeds_max_count(self):
        """超过最大删除数量返回错误"""
        ids = list(range(1, 102))
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/chat-history/delete/',
            data={'message_ids': json.dumps(ids)},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiChatHistoryDeleteView.as_view()(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 400)

    def test_delete_only_user_messages(self):
        """只能删除属于当前用户的消息"""
        other_user = _create_user('other')
        other_project = _create_project(other_user, title='其他项目')
        other_outline = _create_outline(other_project)
        other_msg = _create_chat_history(other_outline, role='user', content='其他用户的消息')
        my_msg = _create_chat_history(self.outline, role='user', content='我的消息')

        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/chat-history/delete/',
            data={'message_ids': json.dumps([other_msg.id, my_msg.id])},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiChatHistoryDeleteView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['deleted_count'], 1)  # 只删了自己的
        self.assertTrue(OutlineChatHistory.objects.filter(pk=other_msg.pk).exists())  # 别人的还在

    def test_delete_missing_message_ids(self):
        """缺少 message_ids 返回错误"""
        request = self.factory.post(
            f'/api/projects/{self.project.id}/outline/chat-history/delete/',
            data={},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiChatHistoryDeleteView.as_view()(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 400)
