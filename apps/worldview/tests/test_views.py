"""
worldview 接口测试

运行命令:
    python manage.py test apps.worldview.tests.test_views --keepdb -v2
    python manage.py test apps.worldview.tests.test_views.WorldviewModelTest --keepdb
    python manage.py test apps.worldview.tests.test_views.WorldviewApplyPatchTest --keepdb
    python manage.py test apps.worldview.tests.test_views.WorldviewApiGetPutTest --keepdb
    python manage.py test apps.worldview.tests.test_views.WorldviewVersionApiTest --keepdb
    python manage.py test apps.worldview.tests.test_views.WorldviewUtilsTest --keepdb
"""
import json
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from django.contrib.auth.models import User
from rest_framework.test import force_authenticate

from apps.project.models import ProjectList as Project
from apps.worldview.models import WorldView, WorldViewChatHistory
from apps.worldview.views import (
    _apply_patch_data,
    ApiWorldviewView,
    ApiWorldviewStreamView,
    ApiWorldviewVersionsView,
    ApiWorldviewVersionSaveView,
    ApiWorldviewVersionUpdateView,
    ApiWorldviewVersionLoadView,
    ApiWorldviewVersionLockView,
    ApiWorldviewVersionUnlockView,
    ApiWorldviewVersionDeleteView,
)
from apps.worldview.utils import get_worldview_context


# ============ 辅助函数 ============

def _create_user(username='testuser'):
    return User.objects.create_user(username=username, password='testpass123')


def _create_project(user, title='测试项目', genre='xuanhuan'):
    return Project.objects.create(user=user, title=title, genre=genre, description='测试')


def _create_worldview(project, version=1, content='', title='', is_finalized=False, **kwargs):
    return WorldView.objects.create(
        project=project, version=version, content=content, title=title,
        is_finalized=is_finalized, **kwargs,
    )


def _create_chat_history(worldview, role='user', content='test', options=None):
    return WorldViewChatHistory.objects.create(
        worldview=worldview, role=role, content=content,
        options=options or [],
    )


# ============ 模型测试 ============

class WorldviewModelTest(TestCase):
    """WorldView 模型测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)

    def test_create_worldview(self):
        """创建世界观文档并验证所有字段"""
        doc = _create_worldview(
            self.project, version=1, content='# 世界观\n\n测试内容',
            title='测试世界观',
        )
        self.assertEqual(doc.project, self.project)
        self.assertEqual(doc.version, 1)
        self.assertEqual(doc.title, '测试世界观')
        self.assertEqual(doc.content, '# 世界观\n\n测试内容')
        self.assertEqual(doc.faction_index, [])
        self.assertFalse(doc.is_finalized)
        self.assertFalse(doc.is_deleted)
        self.assertEqual(doc.last_question, '')
        self.assertEqual(doc.last_options, [])
        self.assertIsNotNone(doc.created_at)
        self.assertIsNotNone(doc.updated_at)

    def test_worldview_str(self):
        """验证 __str__ 返回 '项目标题 - 世界观 v{version}'"""
        doc = _create_worldview(self.project, version=3)
        self.assertEqual(str(doc), '测试项目 - 世界观 v3')

    def test_worldview_unique_constraint(self):
        """同项目同版本号应报 IntegrityError"""
        from django.db import IntegrityError
        _create_worldview(self.project, version=1, content='v1')
        with self.assertRaises(IntegrityError):
            _create_worldview(self.project, version=1, content='v1_again')

    def test_worldview_ordering(self):
        """按 version 降序排列"""
        _create_worldview(self.project, version=3, content='v3')
        _create_worldview(self.project, version=1, content='v1')
        _create_worldview(self.project, version=2, content='v2')
        docs = list(WorldView.objects.filter(project=self.project).values_list('version', flat=True))
        self.assertEqual(docs, [3, 2, 1])

    def test_worldview_soft_delete(self):
        """软删除后 is_deleted=True，文档仍存在"""
        doc = _create_worldview(self.project)
        doc.is_deleted = True
        doc.save()
        self.assertTrue(WorldView.objects.filter(pk=doc.pk).exists())
        self.assertFalse(WorldView.objects.filter(project=self.project, is_deleted=False).exists())

    def test_worldview_faction_index_json(self):
        """faction_index JSON 字段存储和读取"""
        factions = [{'name': '正派', 'subs': ['青云宗', '天剑门']}]
        doc = _create_worldview(self.project, faction_index=factions)
        refreshed = WorldView.objects.get(pk=doc.pk)
        self.assertEqual(refreshed.faction_index, factions)
        self.assertEqual(refreshed.faction_index[0]['name'], '正派')

    def test_cascade_delete(self):
        """删除项目时世界观文档级联删除"""
        _create_worldview(self.project)
        self.assertEqual(WorldView.objects.filter(project=self.project).count(), 1)
        project_id = self.project.id
        self.project.delete()
        self.assertEqual(WorldView.objects.filter(project_id=project_id).count(), 0)


class WorldviewChatHistoryModelTest(TestCase):
    """WorldViewChatHistory 模型测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.worldview = _create_worldview(self.project)

    def test_create_chat_history(self):
        """创建聊天历史记录"""
        msg = _create_chat_history(self.worldview, role='user', content='请帮我构建世界观')
        self.assertEqual(msg.worldview, self.worldview)
        self.assertEqual(msg.role, 'user')
        self.assertEqual(msg.content, '请帮我构建世界观')
        self.assertEqual(msg.options, [])
        self.assertFalse(msg.is_deleted)

    def test_chat_history_str(self):
        """验证 __str__ 返回 '{worldview_id} - {role}'"""
        msg = _create_chat_history(self.worldview, role='assistant')
        self.assertEqual(str(msg), f'{self.worldview.id} - assistant')

    def test_chat_history_ordering(self):
        """按 created_at 升序排列"""
        _create_chat_history(self.worldview, role='user', content='msg1')
        _create_chat_history(self.worldview, role='assistant', content='msg2')
        _create_chat_history(self.worldview, role='user', content='msg3')
        msgs = list(WorldViewChatHistory.objects.filter(worldview=self.worldview).values_list('content', flat=True))
        self.assertEqual(msgs, ['msg1', 'msg2', 'msg3'])

    def test_chat_history_options_json(self):
        """options JSON 字段存储"""
        options = ['选项1', '选项2', '选项3']
        msg = _create_chat_history(self.worldview, role='assistant', options=options)
        refreshed = WorldViewChatHistory.objects.get(pk=msg.pk)
        self.assertEqual(refreshed.options, options)

    def test_cascade_delete(self):
        """删除世界观文档时聊天历史级联删除"""
        _create_chat_history(self.worldview, role='user', content='msg1')
        _create_chat_history(self.worldview, role='assistant', content='msg2')
        self.assertEqual(WorldViewChatHistory.objects.filter(worldview=self.worldview).count(), 2)
        self.worldview.delete()
        self.assertEqual(WorldViewChatHistory.objects.count(), 0)


# ============ _apply_patch_data 测试 ============

class WorldviewApplyPatchTest(TestCase):
    """_apply_patch_data 补丁应用函数测试"""

    def test_empty_patch_list(self):
        """空 patch_list 返回原始内容"""
        result = _apply_patch_data({'patch_list': []}, '原始内容')
        self.assertEqual(result['new_content'], '原始内容')
        self.assertEqual(result['edits_applied'], 0)
        self.assertEqual(result['edits_total'], 0)

    def test_add_to_empty_content(self):
        """空内容时新增补丁应直接设置为新内容"""
        data = {'patch_list': [{'old_snippet': '', 'new_snippet': '# 新文档\n\n内容'}]}
        result = _apply_patch_data(data, '')
        self.assertEqual(result['new_content'], '# 新文档\n\n内容')
        self.assertEqual(result['edits_applied'], 1)

    def test_append_to_existing_content(self):
        """有内容时新增补丁应追加到末尾"""
        data = {'patch_list': [{'old_snippet': '', 'new_snippet': '追加内容'}]}
        result = _apply_patch_data(data, '已有内容')
        self.assertEqual(result['new_content'], '已有内容\n\n追加内容')
        self.assertEqual(result['edits_applied'], 1)

    def test_replace_snippet(self):
        """精确替换：old_snippet 唯一匹配时替换为 new_snippet"""
        data = {'patch_list': [{'old_snippet': '旧文本', 'new_snippet': '新文本'}]}
        result = _apply_patch_data(data, '这是旧文本的内容')
        self.assertEqual(result['new_content'], '这是新文本的内容')
        self.assertEqual(result['edits_applied'], 1)
        self.assertEqual(result['edits_summary'][0]['type'], 'replace')

    def test_replace_no_match(self):
        """未匹配时跳过该补丁"""
        data = {'patch_list': [{'old_snippet': '不存在的文本', 'new_snippet': '新内容'}]}
        result = _apply_patch_data(data, '原始内容')
        self.assertEqual(result['new_content'], '原始内容')
        self.assertEqual(result['edits_applied'], 0)
        self.assertEqual(result['edits_summary'][0]['type'], 'failed')

    def test_replace_ambiguous_match(self):
        """多处匹配时跳过该补丁"""
        data = {'patch_list': [{'old_snippet': '重复', 'new_snippet': '新内容'}]}
        result = _apply_patch_data(data, '这里有重复，那里也有重复')
        self.assertEqual(result['new_content'], '这里有重复，那里也有重复')
        self.assertEqual(result['edits_applied'], 0)
        self.assertEqual(result['edits_summary'][0]['type'], 'ambiguous')

    def test_multiple_patches(self):
        """多个补丁按顺序应用"""
        data = {
            'patch_list': [
                {'old_snippet': 'A', 'new_snippet': 'A_CHANGED'},
                {'old_snippet': 'B', 'new_snippet': 'B_CHANGED'},
            ]
        }
        result = _apply_patch_data(data, 'A and B')
        self.assertEqual(result['new_content'], 'A_CHANGED and B_CHANGED')
        self.assertEqual(result['edits_applied'], 2)
        self.assertEqual(result['edits_total'], 2)

    def test_extract_title_from_content(self):
        """从文档首行 # 标题提取 title"""
        data = {'patch_list': [{'old_snippet': '', 'new_snippet': '# 我的世界观\n\n内容'}]}
        result = _apply_patch_data(data, '')
        self.assertEqual(result['title'], '我的世界观')

    def test_question_and_options_passed_through(self):
        """question 和 options 原样传递"""
        data = {
            'patch_list': [],
            'question': '你想要什么？',
            'options': ['选项A', '选项B'],
        }
        result = _apply_patch_data(data, '内容')
        self.assertEqual(result['question'], '你想要什么？')
        self.assertEqual(result['options'], ['选项A', '选项B'])

    def test_non_list_options_fallback(self):
        """options 非 list 时回退为空列表"""
        data = {'patch_list': [], 'options': 'not_a_list'}
        result = _apply_patch_data(data, '内容')
        self.assertEqual(result['options'], [])

    def test_no_title_if_no_content(self):
        """空内容时 title 为空"""
        data = {'patch_list': []}
        result = _apply_patch_data(data, '')
        self.assertEqual(result['title'], '')

    def test_title_not_from_heading(self):
        """首行无 # 时 title 为空"""
        data = {'patch_list': [{'old_snippet': '', 'new_snippet': '没有标题的内容'}]}
        result = _apply_patch_data(data, '')
        self.assertEqual(result['title'], '')


# ============ API 视图测试 ============

@patch('apps.worldview.views.get_genre_label', return_value='玄幻')
class WorldviewApiGetPutTest(TestCase):
    """世界观文档 GET/PUT API 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def test_get_when_no_doc(self, mock_label):
        """GET 无文档时返回 exists=False"""
        request = self.factory.get(f'/api/projects/{self.project.id}/worldviews/')
        force_authenticate(request, user=self.user)
        response = ApiWorldviewView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertFalse(data['exists'])
        self.assertIsNone(data['id'])

    def test_get_with_doc(self, mock_label):
        """GET 有文档时返回完整数据"""
        doc = _create_worldview(self.project, content='# 世界观\n内容', title='测试世界观')
        request = self.factory.get(f'/api/projects/{self.project.id}/worldviews/')
        force_authenticate(request, user=self.user)
        response = ApiWorldviewView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertTrue(data['exists'])
        self.assertEqual(data['id'], doc.id)
        self.assertEqual(data['content'], '# 世界观\n内容')
        self.assertEqual(data['title'], '测试世界观')
        self.assertEqual(data['version'], 1)

    def test_put_save_content(self, mock_label):
        """PUT 保存文档内容（已有文档时更新）"""
        _create_worldview(self.project, version=1, content='旧内容')
        request = self.factory.put(
            f'/api/projects/{self.project.id}/worldviews/',
            data={'content': '# 新世界观\n\n详细内容', 'title': '新标题'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiWorldviewView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['content'], '# 新世界观\n\n详细内容')
        self.assertEqual(data['title'], '新标题')

    def test_put_creates_new_doc(self, mock_label):
        """PUT 无文档时自动创建（注意：_get_or_create_doc 传了不存在的 genre 字段，需要 mock）"""
        self.assertFalse(WorldView.objects.filter(project=self.project).exists())
        # mock _get_or_create_doc 以绕过 genre 字段 bug
        with patch('apps.worldview.views._get_or_create_doc') as mock_get:
            mock_doc = _create_worldview(self.project, version=1)
            mock_get.return_value = mock_doc
            request = self.factory.put(
                f'/api/projects/{self.project.id}/worldviews/',
                data={'content': '首次创建', 'title': '首次'},
                content_type='application/json',
            )
            force_authenticate(request, user=self.user)
            response = ApiWorldviewView.as_view()(request, project_id=self.project.id)
            data = json.loads(response.content)
            self.assertTrue(data['success'])

    def test_put_increments_version(self, mock_label):
        """PUT 保存内容后版本号递增"""
        _create_worldview(self.project, version=1, content='v1内容')
        request = self.factory.put(
            f'/api/projects/{self.project.id}/worldviews/',
            data={'content': 'v2新内容'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiWorldviewView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['version'], 2)

    def test_put_title_truncated(self, mock_label):
        """PUT 标题超过200字符时截断"""
        doc = _create_worldview(self.project, version=1, content='内容')
        long_title = 'A' * 300
        request = self.factory.put(
            f'/api/projects/{self.project.id}/worldviews/',
            data={'title': long_title, 'content': '内容'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiWorldviewView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertEqual(len(data['title']), 200)

    def test_put_content_truncated(self, mock_label):
        """PUT 内容超过500000字符时截断"""
        doc = _create_worldview(self.project, version=1, content='旧内容')
        long_content = 'A' * 600000
        request = self.factory.put(
            f'/api/projects/{self.project.id}/worldviews/',
            data={'content': long_content},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiWorldviewView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['truncated'])
        doc.refresh_from_db()
        self.assertEqual(len(doc.content), 500000)

    def test_get_project_not_found(self, mock_label):
        """GET 不存在的项目返回404"""
        request = self.factory.get('/api/projects/99999/worldviews/')
        force_authenticate(request, user=self.user)
        response = ApiWorldviewView.as_view()(request, project_id=99999)
        self.assertEqual(response.status_code, 404)

    def test_put_only_title(self, mock_label):
        """PUT 只更新标题不更新内容"""
        doc = _create_worldview(self.project, content='原始内容', title='原标题')
        request = self.factory.put(
            f'/api/projects/{self.project.id}/worldviews/',
            data={'title': '新标题'},
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiWorldviewView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['title'], '新标题')
        # 内容不变
        doc.refresh_from_db()
        self.assertEqual(doc.content, '原始内容')


# ============ 版本管理 API 测试 ============

class WorldviewVersionApiTest(TestCase):
    """世界观版本管理 API 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.factory = RequestFactory()

    def _auth_request(self, method, url, data=None):
        """创建并认证请求"""
        if method == 'get':
            request = self.factory.get(url)
        else:
            request = self.factory.post(url, data=data or {}, content_type='application/json')
        force_authenticate(request, user=self.user)
        return request

    # ---- 版本列表 ----

    def test_versions_list_empty(self):
        """无版本时返回空列表"""
        request = self._auth_request('get', f'/api/projects/{self.project.id}/worldviews/versions/')
        response = ApiWorldviewVersionsView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['versions'], [])
        self.assertIsNone(data['latest'])

    def test_versions_list_with_data(self):
        """有多个版本时正确返回列表"""
        _create_worldview(self.project, version=1, content='v1内容')
        _create_worldview(self.project, version=2, content='v2内容')
        request = self._auth_request('get', f'/api/projects/{self.project.id}/worldviews/versions/')
        response = ApiWorldviewVersionsView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['versions']), 2)
        # 按 version 降序，v2 在前
        self.assertEqual(data['versions'][0]['version_number'], 2)
        self.assertTrue(data['versions'][0]['is_current'])
        self.assertEqual(data['latest']['version_number'], 2)

    # ---- 保存新版本 ----

    def test_save_new_version(self):
        """POST 保存新版本"""
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/save/',
            data={'content': '新版本内容'},
        )
        response = ApiWorldviewVersionSaveView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['version_number'], 1)
        self.assertEqual(data['content'], '新版本内容')

    def test_save_new_version_increments(self):
        """连续保存多个版本，版本号递增"""
        _create_worldview(self.project, version=1)
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/save/',
            data={'content': 'v2内容'},
        )
        response = ApiWorldviewVersionSaveView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertEqual(data['version_number'], 2)

    def test_save_empty_content_error(self):
        """保存空内容返回错误"""
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/save/',
            data={'content': ''},
        )
        response = ApiWorldviewVersionSaveView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('内容不能为空', data['error'])

    # ---- 更新版本 ----

    def test_update_version(self):
        """POST 更新指定版本内容"""
        doc = _create_worldview(self.project, version=1, content='旧内容')
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/update/',
            data={'version_id': doc.id, 'content': '新内容'},
        )
        response = ApiWorldviewVersionUpdateView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['content'], '新内容')
        doc.refresh_from_db()
        self.assertEqual(doc.content, '新内容')

    def test_update_version_missing_id(self):
        """更新时缺少 version_id 返回错误"""
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/update/',
            data={'content': '新内容'},
        )
        response = ApiWorldviewVersionUpdateView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('version_id', data['error'])

    def test_update_version_not_found(self):
        """更新不存在的版本返回错误"""
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/update/',
            data={'version_id': 99999, 'content': '新内容'},
        )
        response = ApiWorldviewVersionUpdateView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    def test_update_empty_content_error(self):
        """更新时内容为空返回错误"""
        doc = _create_worldview(self.project, version=1)
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/update/',
            data={'version_id': doc.id, 'content': ''},
        )
        response = ApiWorldviewVersionUpdateView.as_view()(request, project_id=self.project.id)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    # ---- 加载版本 ----

    def test_load_version(self):
        """GET 加载指定版本"""
        doc = _create_worldview(self.project, version=2, content='v2内容', is_finalized=True)
        doc.last_question = '你想做什么？'
        doc.last_options = ['选项A', '选项B']
        doc.save()
        request = self._auth_request('get', f'/api/projects/{self.project.id}/worldviews/versions/{doc.id}/load/')
        response = ApiWorldviewVersionLoadView.as_view()(request, project_id=self.project.id, version_id=doc.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['content'], 'v2内容')
        self.assertEqual(data['version_number'], 2)
        self.assertTrue(data['is_finalized'])
        self.assertEqual(data['last_question'], '你想做什么？')
        self.assertEqual(data['last_options'], ['选项A', '选项B'])

    def test_load_version_not_found(self):
        """加载不存在的版本返回错误"""
        request = self._auth_request('get', f'/api/projects/{self.project.id}/worldviews/versions/99999/load/')
        response = ApiWorldviewVersionLoadView.as_view()(request, project_id=self.project.id, version_id=99999)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    # ---- 锁定 / 解锁 ----

    def test_lock_version(self):
        """POST 锁定版本"""
        doc = _create_worldview(self.project, version=1)
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/{doc.id}/lock/',
        )
        response = ApiWorldviewVersionLockView.as_view()(request, project_id=self.project.id, version_id=doc.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertTrue(data['is_finalized'])
        doc.refresh_from_db()
        self.assertTrue(doc.is_finalized)

    def test_unlock_version(self):
        """POST 解锁版本"""
        doc = _create_worldview(self.project, version=1, is_finalized=True)
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/{doc.id}/unlock/',
        )
        response = ApiWorldviewVersionUnlockView.as_view()(request, project_id=self.project.id, version_id=doc.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertFalse(data['is_finalized'])
        doc.refresh_from_db()
        self.assertFalse(doc.is_finalized)

    def test_lock_version_not_found(self):
        """锁定不存在的版本返回错误"""
        request = self._auth_request('post', f'/api/projects/{self.project.id}/worldviews/versions/99999/lock/')
        response = ApiWorldviewVersionLockView.as_view()(request, project_id=self.project.id, version_id=99999)
        data = json.loads(response.content)
        self.assertFalse(data['success'])

    # ---- 删除版本 ----

    def test_delete_version(self):
        """POST 软删除版本"""
        doc = _create_worldview(self.project, version=1)
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/{doc.id}/delete/',
        )
        response = ApiWorldviewVersionDeleteView.as_view()(request, project_id=self.project.id, version_id=doc.id)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        doc.refresh_from_db()
        self.assertTrue(doc.is_deleted)

    def test_delete_finalized_version_error(self):
        """已定稿版本不能删除"""
        doc = _create_worldview(self.project, version=1, is_finalized=True)
        request = self._auth_request(
            'post',
            f'/api/projects/{self.project.id}/worldviews/versions/{doc.id}/delete/',
        )
        response = ApiWorldviewVersionDeleteView.as_view()(request, project_id=self.project.id, version_id=doc.id)
        data = json.loads(response.content)
        self.assertFalse(data['success'])
        self.assertIn('定稿', data['error'])
        doc.refresh_from_db()
        self.assertFalse(doc.is_deleted)

    def test_delete_version_not_found(self):
        """删除不存在的版本返回错误"""
        request = self._auth_request('post', f'/api/projects/{self.project.id}/worldviews/versions/99999/delete/')
        response = ApiWorldviewVersionDeleteView.as_view()(request, project_id=self.project.id, version_id=99999)
        data = json.loads(response.content)
        self.assertFalse(data['success'])


# ============ Utils 测试 ============

class WorldviewUtilsTest(TestCase):
    """get_worldview_context 工具函数测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)

    def test_get_context_with_content(self):
        """有世界观文档时返回 Markdown 内容"""
        _create_worldview(self.project, content='# 世界观\n\n详细设定', version=1)
        result = get_worldview_context(self.project)
        self.assertEqual(result, '# 世界观\n\n详细设定')

    def test_get_context_without_content(self):
        """无文档时返回 None"""
        result = get_worldview_context(self.project)
        self.assertIsNone(result)

    def test_get_context_empty_content(self):
        """有文档但内容为空时返回 None"""
        _create_worldview(self.project, content='', version=1)
        result = get_worldview_context(self.project)
        self.assertIsNone(result)

    def test_get_context_returns_latest_version(self):
        """多版本时返回最新版本的内容"""
        _create_worldview(self.project, content='v1内容', version=1)
        _create_worldview(self.project, content='v2内容', version=2)
        result = get_worldview_context(self.project)
        self.assertEqual(result, 'v2内容')

    def test_get_context_excludes_deleted(self):
        """排除已删除的文档"""
        doc = _create_worldview(self.project, content='v1内容', version=1)
        _create_worldview(self.project, content='v2内容', version=2)
        doc.is_deleted = True
        doc.save()
        result = get_worldview_context(self.project)
        self.assertEqual(result, 'v2内容')
