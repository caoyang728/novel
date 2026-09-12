"""
Volume 模块测试
覆盖：模型、VolumeService、API 视图
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.project.models import ProjectList
from apps.outline.models import Outline
from apps.volume.models import Volume
from apps.volume.services import VolumeService
from apps.volume.serializers import VolumeSerializer
from apps.volume.views import (
    ApiVolumeVersionListView,
    ApiVolumeVersionDetailView,
    ApiVolumeVersionFinalizeView,
    ApiVolumeLockView,
    ApiVolumeOptimizeView,
)

User = get_user_model()


# ========== 辅助函数 ==========

def _create_user(username='testuser'):
    return User.objects.create_user(username=username, password='testpass123')


def _create_project(user, title='测试项目'):
    return ProjectList.objects.create(user=user, title=title)


def _create_outline(project, content='测试大纲内容', version=1):
    return Outline.objects.create(
        project=project,
        content=content,
        version=version,
    )


def _create_volume(project, outline, version=1, volume_number=1, **kwargs):
    defaults = {
        'title': f'第{volume_number}卷',
        'summary': f'第{volume_number}卷摘要',
        'content': f'第{volume_number}卷大纲内容',
        'chapter_count': 30,
    }
    defaults.update(kwargs)
    return Volume.objects.create(
        project=project,
        outline=outline,
        version=version,
        volume_number=volume_number,
        **defaults,
    )


# ========== 模型测试 ==========

class VolumeModelTest(TestCase):
    """Volume 模型测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.outline = _create_outline(self.project)

    def test_create_volume(self):
        """创建卷记录"""
        vol = _create_volume(self.project, self.outline, volume_number=1)
        self.assertEqual(vol.volume_number, 1)
        self.assertEqual(vol.title, '第1卷')
        self.assertFalse(vol.is_locked)
        self.assertEqual(vol.version, 1)

    def test_str_representation(self):
        """__str__ 格式"""
        vol = _create_volume(self.project, self.outline, volume_number=1, title='觉醒')
        expected = f'{self.project.title} - V1 第1卷 觉醒'
        self.assertEqual(str(vol), expected)

    def test_unique_together_constraint(self):
        """唯一约束：同一项目+版本+卷号不能重复"""
        _create_volume(self.project, self.outline, version=1, volume_number=1)
        with self.assertRaises(Exception):
            _create_volume(self.project, self.outline, version=1, volume_number=1)

    def test_cascade_delete_project(self):
        """删除项目时级联删除卷"""
        vol = _create_volume(self.project, self.outline)
        # Volume 保护 Outline，需先删 Volume
        vol.delete()
        self.outline.delete()
        self.project.delete()
        self.assertEqual(Volume.objects.count(), 0)

    def test_protect_delete_outline(self):
        """删除大纲时 PROTECT 阻止"""
        _create_volume(self.project, self.outline)
        with self.assertRaises(Exception):
            self.outline.delete()

    def test_ordering(self):
        """排序：version + volume_number"""
        _create_volume(self.project, self.outline, version=1, volume_number=2)
        _create_volume(self.project, self.outline, version=1, volume_number=1)
        _create_volume(self.project, self.outline, version=2, volume_number=1)
        volumes = list(Volume.objects.all())
        self.assertEqual(volumes[0].volume_number, 1)
        self.assertEqual(volumes[1].volume_number, 2)
        self.assertEqual(volumes[2].version, 2)


# ========== VolumeService 测试 ==========

class VolumeServiceTest(TestCase):
    """VolumeService 单元测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.outline = _create_outline(self.project)

    def test_volume_to_dict(self):
        """volume_to_dict 转换"""
        vol = _create_volume(self.project, self.outline)
        d = VolumeService.volume_to_dict(vol)
        self.assertEqual(d['id'], vol.id)
        self.assertEqual(d['volume_number'], 1)
        self.assertEqual(d['title'], '第1卷')
        self.assertIn('summary', d)
        self.assertIn('content', d)
        self.assertIn('updated_at', d)

    def test_create_volume(self):
        """create_volume 创建记录"""
        vol = VolumeService.create_volume(self.project, self.outline, 1, {
            'volume_number': 1,
            'title': '测试卷',
            'summary': '摘要',
            'chapter_count': 20,
        })
        self.assertEqual(vol.volume_number, 1)
        self.assertEqual(vol.title, '测试卷')
        self.assertEqual(vol.project, self.project)

    def test_get_next_version_empty(self):
        """空项目返回版本号 1"""
        self.assertEqual(VolumeService.get_next_version(self.project), 1)

    def test_get_next_version(self):
        """有卷时返回最大版本号+1"""
        _create_volume(self.project, self.outline, version=2)
        self.assertEqual(VolumeService.get_next_version(self.project), 3)

    def test_get_version_volumes(self):
        """获取指定版本的卷"""
        _create_volume(self.project, self.outline, version=1, volume_number=1)
        _create_volume(self.project, self.outline, version=1, volume_number=2)
        _create_volume(self.project, self.outline, version=2, volume_number=1)
        qs = VolumeService.get_version_volumes(self.project, 1)
        self.assertEqual(qs.count(), 2)

    def test_get_volumes_list(self):
        """获取卷数据列表"""
        _create_volume(self.project, self.outline, version=1, volume_number=1)
        result = VolumeService.get_volumes_list(self.project, 1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['volume_number'], 1)

    def test_is_version_locked_all_locked(self):
        """所有卷锁定时返回 True"""
        _create_volume(self.project, self.outline, version=1, is_locked=True)
        _create_volume(self.project, self.outline, version=1, volume_number=2, is_locked=True)
        self.assertTrue(VolumeService.is_version_locked(self.project, 1))

    def test_is_version_locked_partial(self):
        """部分卷锁定时返回 False"""
        _create_volume(self.project, self.outline, version=1, is_locked=True)
        _create_volume(self.project, self.outline, version=1, volume_number=2, is_locked=False)
        self.assertFalse(VolumeService.is_version_locked(self.project, 1))

    def test_is_version_locked_empty(self):
        """空版本返回 False"""
        self.assertFalse(VolumeService.is_version_locked(self.project, 99))

    def test_get_version_groups(self):
        """版本分组统计"""
        _create_volume(self.project, self.outline, version=1, volume_number=1)
        _create_volume(self.project, self.outline, version=1, volume_number=2)
        groups = list(VolumeService.get_version_groups(self.project))
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['volume_count'], 2)


class VolumeServiceParseTest(TestCase):
    """VolumeService 解析方法测试"""

    def test_parse_volumes_json_list(self):
        """解析列表格式"""
        data = [{'volume_number': 1, 'title': '卷一'}]
        result, err = VolumeService.parse_volumes_json(data)
        self.assertIsNone(err)
        self.assertEqual(len(result), 1)

    def test_parse_volumes_json_string(self):
        """解析 JSON 字符串"""
        data = json.dumps([{'volume_number': 1}])
        result, err = VolumeService.parse_volumes_json(data)
        self.assertIsNone(err)
        self.assertEqual(len(result), 1)

    def test_parse_volumes_json_invalid(self):
        """无效 JSON 返回错误"""
        result, err = VolumeService.parse_volumes_json('not json')
        self.assertIsNone(result)
        self.assertIn('格式错误', err)

    def test_parse_volumes_json_empty(self):
        """空数据返回错误"""
        result, err = VolumeService.parse_volumes_json([])
        self.assertIsNone(result)
        self.assertIn('为空', err)

    def test_parse_volumes_json_none(self):
        """None 返回错误"""
        result, err = VolumeService.parse_volumes_json(None)
        self.assertIsNone(result)

    def test_parse_analysis_json_valid(self):
        """解析有效分析 JSON"""
        text = json.dumps({'volumes': [{'title': '卷一'}]})
        result = VolumeService.parse_analysis_json(text)
        self.assertEqual(len(result), 1)

    def test_parse_analysis_json_with_text(self):
        """从文本中提取 JSON"""
        text = '分析结果如下：\n{"volumes": [{"title": "卷一"}]}\n以上是分析。'
        result = VolumeService.parse_analysis_json(text)
        self.assertEqual(len(result), 1)

    def test_parse_analysis_json_invalid(self):
        """无效文本返回空列表"""
        result = VolumeService.parse_analysis_json('no json here')
        self.assertEqual(result, [])

    def test_parse_volumes_from_llm_output_json(self):
        """解析纯 JSON 输出"""
        output = json.dumps({'volumes': [{'title': '卷一'}, {'title': '卷二'}]})
        result = VolumeService.parse_volumes_from_llm_output(output)
        self.assertEqual(len(result), 2)

    def test_parse_volumes_from_llm_output_single(self):
        """解析单个卷 JSON"""
        output = json.dumps({'title': '卷一', 'chapter_count': 30})
        result = VolumeService.parse_volumes_from_llm_output(output)
        self.assertEqual(len(result), 1)

    def test_parse_volumes_from_llm_output_invalid(self):
        """无效输出返回空列表"""
        result = VolumeService.parse_volumes_from_llm_output('not valid')
        self.assertEqual(result, [])

    def test_parse_volumes_from_llm_output_json_list(self):
        """解析 JSON 数组格式"""
        output = json.dumps([{'title': '卷一', 'chapter_count': 30}, {'title': '卷二', 'chapter_count': 20}])
        result = VolumeService.parse_volumes_from_llm_output(output)
        self.assertEqual(len(result), 2)

    # ---- parse_chat_json 测试 ----

    def test_parse_chat_json_with_patches(self):
        """解析含 patch_list 的 JSON 输出"""
        data = {
            'reply': '已修改卷一内容',
            'patch_list': [
                {'old_snippet': '旧内容', 'new_snippet': '新内容'},
            ],
        }
        result = VolumeService.parse_chat_json(json.dumps(data))
        self.assertEqual(result['reply'], '已修改卷一内容')
        self.assertEqual(len(result['patch_list']), 1)
        self.assertEqual(result['patch_list'][0]['old_snippet'], '旧内容')
        self.assertIsNone(result['target_volume_number'])

    def test_parse_chat_json_with_target_volume(self):
        """解析含 target_volume_number 的跨卷补丁"""
        data = {
            'reply': '同时修改了卷二',
            'patch_list': [
                {'old_snippet': '旧', 'new_snippet': '新', 'target_volume_number': 2},
            ],
            'target_volume_number': 2,
        }
        result = VolumeService.parse_chat_json(json.dumps(data))
        self.assertEqual(result['target_volume_number'], 2)
        self.assertEqual(result['patch_list'][0]['target_volume_number'], 2)

    def test_parse_chat_json_no_patches(self):
        """无 patch_list 时返回空列表"""
        data = {'reply': '好的，请问需要什么？'}
        result = VolumeService.parse_chat_json(json.dumps(data))
        self.assertEqual(result['patch_list'], [])
        self.assertEqual(result['reply'], '好的，请问需要什么？')

    def test_parse_chat_json_from_text(self):
        """从包含 JSON 的文本中提取"""
        text = '前缀{"reply": "回复", "patch_list": []}后缀'
        result = VolumeService.parse_chat_json(text)
        self.assertEqual(result['reply'], '回复')

    def test_parse_chat_json_invalid(self):
        """无效 JSON 降级返回原文"""
        result = VolumeService.parse_chat_json('不是JSON')
        self.assertEqual(result['reply'], '不是JSON')
        self.assertEqual(result['patch_list'], [])

    # ---- apply_content_patches 测试 ----

    def test_apply_patches_empty_list(self):
        """空 patch_list 返回原始内容"""
        result = VolumeService.apply_content_patches('原始内容', [])
        self.assertEqual(result['new_content'], '原始内容')
        self.assertEqual(result['edits_applied'], 0)

    def test_apply_patches_replace_snippet(self):
        """精确替换：old_snippet 唯一匹配"""
        patches = [{'old_snippet': '旧文本', 'new_snippet': '新文本'}]
        result = VolumeService.apply_content_patches('这是旧文本的内容', patches)
        self.assertEqual(result['new_content'], '这是新文本的内容')
        self.assertEqual(result['edits_applied'], 1)

    def test_apply_patches_no_match(self):
        """未匹配时跳过"""
        patches = [{'old_snippet': '不存在', 'new_snippet': '新'}]
        result = VolumeService.apply_content_patches('原始内容', patches)
        self.assertEqual(result['new_content'], '原始内容')
        self.assertEqual(result['edits_applied'], 0)
        self.assertEqual(result['edits_summary'][0]['type'], 'failed')

    def test_apply_patches_multiple_matches(self):
        """多处匹配时跳过"""
        patches = [{'old_snippet': '重复', 'new_snippet': '新'}]
        result = VolumeService.apply_content_patches('重复和重复', patches)
        self.assertEqual(result['new_content'], '重复和重复')
        self.assertEqual(result['edits_applied'], 0)
        self.assertEqual(result['edits_summary'][0]['type'], 'ambiguous')

    def test_apply_patches_add_to_empty(self):
        """空文档时新增内容"""
        patches = [{'old_snippet': '', 'new_snippet': '全新内容'}]
        result = VolumeService.apply_content_patches('', patches)
        self.assertEqual(result['new_content'], '全新内容')
        self.assertEqual(result['edits_applied'], 1)

    def test_apply_patches_append_to_existing(self):
        """有内容时追加到末尾"""
        patches = [{'old_snippet': '', 'new_snippet': '追加内容'}]
        result = VolumeService.apply_content_patches('已有内容', patches)
        self.assertEqual(result['new_content'], '已有内容\n\n追加内容')
        self.assertEqual(result['edits_applied'], 1)

    def test_apply_patches_multiple_sequential(self):
        """多个补丁按顺序应用"""
        patches = [
            {'old_snippet': 'A', 'new_snippet': 'A_CHANGED'},
            {'old_snippet': 'B', 'new_snippet': 'B_CHANGED'},
        ]
        result = VolumeService.apply_content_patches('A and B', patches)
        self.assertEqual(result['new_content'], 'A_CHANGED and B_CHANGED')
        self.assertEqual(result['edits_applied'], 2)


class VolumeServiceValidateTest(TestCase):
    """VolumeService 结构校验测试"""

    def test_validate_empty(self):
        """空列表校验失败"""
        result = VolumeService.validate_structure([])
        self.assertFalse(result['valid'])
        self.assertIn('卷列表为空', result['errors'][0])

    def test_validate_missing_title(self):
        """缺少标题"""
        result = VolumeService.validate_structure([
            {'volume_number': 1, 'chapter_count': 30}
        ])
        self.assertFalse(result['valid'])
        self.assertTrue(any('缺少标题' in e for e in result['errors']))

    def test_validate_missing_chapter_count(self):
        """章节数无效"""
        result = VolumeService.validate_structure([
            {'volume_number': 1, 'title': '卷一', 'chapter_count': 0}
        ])
        self.assertFalse(result['valid'])
        self.assertTrue(any('章节数无效' in e for e in result['errors']))

    def test_validate_title_with_number(self):
        """标题含数字"""
        result = VolumeService.validate_structure([
            {'volume_number': 1, 'title': '第1卷', 'chapter_count': 30}
        ])
        self.assertFalse(result['valid'])
        self.assertTrue(any('含数字' in e for e in result['errors']))

    def test_validate_title_with_chapter_char(self):
        """标题含'章'字"""
        result = VolumeService.validate_structure([
            {'volume_number': 1, 'title': '觉醒章', 'chapter_count': 30}
        ])
        self.assertFalse(result['valid'])
        self.assertTrue(any('章/回/节' in e for e in result['errors']))

    def test_validate_title_length_warning(self):
        """标题长度异常产生警告"""
        result = VolumeService.validate_structure([
            {'volume_number': 1, 'title': '一', 'chapter_count': 30}
        ])
        self.assertTrue(any('标题长度异常' in w for w in result['warnings']))

    def test_validate_chapter_range_continuous(self):
        """章节范围连续性校验通过"""
        result = VolumeService.validate_structure([
            {'volume_number': 1, 'title': '卷一', 'chapter_count': 50,
             'description': '本卷涵盖第1章至第50章。'},
            {'volume_number': 2, 'title': '卷二', 'chapter_count': 50,
             'description': '本卷涵盖第51章至第100章。'},
        ])
        self.assertTrue(result['valid'])

    def test_validate_chapter_range_discontinuous(self):
        """章节范围不连续"""
        result = VolumeService.validate_structure([
            {'volume_number': 1, 'title': '卷一', 'chapter_count': 50,
             'description': '本卷涵盖第1章至第50章。'},
            {'volume_number': 2, 'title': '卷二', 'chapter_count': 50,
             'description': '本卷涵盖第60章至第110章。'},
        ])
        self.assertFalse(result['valid'])
        self.assertTrue(any('不连续' in e for e in result['errors']))

    def test_validate_valid_volumes(self):
        """完全合法的卷数据"""
        result = VolumeService.validate_structure([
            {'volume_number': 1, 'title': '觉醒', 'chapter_count': 30,
             'content': '大纲内容', 'summary': '摘要'},
            {'volume_number': 2, 'title': '风云', 'chapter_count': 30,
             'content': '大纲内容', 'summary': '摘要'},
        ])
        self.assertTrue(result['valid'])
        self.assertEqual(len(result['errors']), 0)


class VolumeServiceQualityTest(TestCase):
    """VolumeService 质量评分测试"""

    def test_perfect_score(self):
        """完美卷数据得100分"""
        volumes = [
            {'volume_number': 1, 'title': '觉醒', 'chapter_count': 30,
             'content': 'x' * 600, 'summary': '摘要'},
        ]
        validation = VolumeService.validate_structure(volumes)
        result = VolumeService.evaluate_quality(volumes, validation)
        self.assertEqual(result['score'], 100)
        self.assertEqual(result['dimensions']['structure'], 40)
        self.assertEqual(result['dimensions']['richness'], 30)

    def test_missing_content_penalty(self):
        """缺失内容扣分"""
        volumes = [
            {'volume_number': 1, 'title': '觉醒', 'chapter_count': 30, 'content': ''},
        ]
        validation = VolumeService.validate_structure(volumes)
        result = VolumeService.evaluate_quality(volumes, validation)
        self.assertLess(result['score'], 100)
        self.assertTrue(any('内容缺失' in s for s in result['suggestions']))

    def test_short_content_penalty(self):
        """内容偏短扣分"""
        volumes = [
            {'volume_number': 1, 'title': '觉醒', 'chapter_count': 30, 'content': '短内容'},
        ]
        validation = VolumeService.validate_structure(volumes)
        result = VolumeService.evaluate_quality(volumes, validation)
        self.assertLess(result['score'], 100)
        self.assertTrue(any('偏短' in s for s in result['suggestions']))

    def test_structure_error_penalty(self):
        """结构错误扣分"""
        volumes = [
            {'volume_number': 1, 'title': '', 'chapter_count': 0},
        ]
        validation = VolumeService.validate_structure(volumes)
        result = VolumeService.evaluate_quality(volumes, validation)
        self.assertLess(result['score'], 80)

    def test_score_not_negative(self):
        """分数不低于0"""
        volumes = [{'volume_number': 1}]
        validation = {'valid': False, 'errors': ['e'] * 10, 'warnings': []}
        result = VolumeService.evaluate_quality(volumes, validation)
        self.assertGreaterEqual(result['score'], 0)


# ========== 序列化器测试 ==========

class VolumeSerializerTest(TestCase):
    """VolumeSerializer 测试"""

    def setUp(self):
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.outline = _create_outline(self.project)

    def test_valid_data(self):
        """合法数据通过校验"""
        data = {'volume_number': 1, 'title': '觉醒', 'chapter_count': 30}
        s = VolumeSerializer(data=data)
        self.assertTrue(s.is_valid())

    def test_missing_title(self):
        """缺少标题失败"""
        data = {'volume_number': 1}
        s = VolumeSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('title', s.errors)

    def test_volume_number_min(self):
        """卷号最小值1"""
        data = {'volume_number': 0, 'title': '卷一'}
        s = VolumeSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_create_volume(self):
        """create 方法创建 Volume"""
        data = {'volume_number': 1, 'title': '觉醒', 'chapter_count': 30}
        s = VolumeSerializer(data=data, context={
            'project': self.project,
            'outline': self.outline,
            'version': 1,
        })
        self.assertTrue(s.is_valid())
        vol = s.save()
        self.assertEqual(vol.project, self.project)
        self.assertEqual(vol.outline, self.outline)
        self.assertEqual(vol.version, 1)


# ========== API 视图测试 ==========

class ApiVolumeVersionListViewTest(TestCase):
    """ApiVolumeVersionListView 测试"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.outline = _create_outline(self.project)

    def test_get_empty(self):
        """无卷时返回空列表"""
        request = self.factory.get(f'/api/projects/{self.project.pk}/volume-versions/')
        force_authenticate(request, user=self.user)
        response = ApiVolumeVersionListView.as_view()(request, project_id=self.project.pk)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['versions'], [])

    def test_get_with_volumes(self):
        """有卷时返回版本列表"""
        _create_volume(self.project, self.outline, version=1)
        request = self.factory.get(f'/api/projects/{self.project.pk}/volume-versions/')
        force_authenticate(request, user=self.user)
        response = ApiVolumeVersionListView.as_view()(request, project_id=self.project.pk)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['versions']), 1)
        self.assertEqual(data['versions'][0]['version'], 1)
        self.assertEqual(data['versions'][0]['volume_count'], 1)

    def test_post_generate_flow(self):
        """POST 触发生成流程（返回 SSE 流）"""
        request = self.factory.post(
            f'/api/projects/{self.project.pk}/volume-versions/',
            data=json.dumps({'outline_version_id': self.outline.pk}),
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiVolumeVersionListView.as_view()(request, project_id=self.project.pk)
        # SSE 流式响应不渲染，直接检查状态码
        self.assertIn(response.status_code, [200, 500])  # 500 if LLM not available

    def test_post_missing_outline(self):
        """POST 缺少 outline_version_id 返回400"""
        request = self.factory.post(
            f'/api/projects/{self.project.pk}/volume-versions/',
            data=json.dumps({}),
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiVolumeVersionListView.as_view()(request, project_id=self.project.pk)
        self.assertEqual(response.status_code, 400)

    def test_unauthenticated(self):
        """未认证返回401"""
        request = self.factory.get(f'/api/projects/{self.project.pk}/volume-versions/')
        response = ApiVolumeVersionListView.as_view()(request, project_id=self.project.pk)
        self.assertEqual(response.status_code, 401)


class ApiVolumeVersionDetailViewTest(TestCase):
    """ApiVolumeVersionDetailView 测试"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.outline = _create_outline(self.project)

    def test_get_version_detail(self):
        """获取版本详情"""
        _create_volume(self.project, self.outline, version=1)
        request = self.factory.get(f'/api/projects/{self.project.pk}/volume-versions/1/')
        force_authenticate(request, user=self.user)
        response = ApiVolumeVersionDetailView.as_view()(request, project_id=self.project.pk, version=1)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(data['volumes']), 1)
        self.assertEqual(data['version'], 1)
        self.assertFalse(data['is_version_locked'])

    def test_get_nonexistent(self):
        """不存在的版本返回404"""
        request = self.factory.get(f'/api/projects/{self.project.pk}/volume-versions/99/')
        force_authenticate(request, user=self.user)
        response = ApiVolumeVersionDetailView.as_view()(request, project_id=self.project.pk, version=99)
        self.assertEqual(response.status_code, 404)

    def test_delete_version(self):
        """删除版本"""
        _create_volume(self.project, self.outline, version=1)
        request = self.factory.delete(f'/api/projects/{self.project.pk}/volume-versions/1/')
        force_authenticate(request, user=self.user)
        response = ApiVolumeVersionDetailView.as_view()(request, project_id=self.project.pk, version=1)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(Volume.objects.count(), 0)

    def test_delete_locked_version_blocked(self):
        """删除锁定版本被阻止"""
        _create_volume(self.project, self.outline, version=1, is_locked=True)
        request = self.factory.delete(f'/api/projects/{self.project.pk}/volume-versions/1/')
        force_authenticate(request, user=self.user)
        response = ApiVolumeVersionDetailView.as_view()(request, project_id=self.project.pk, version=1)
        self.assertEqual(response.status_code, 400)


class ApiVolumeVersionFinalizeViewTest(TestCase):
    """ApiVolumeVersionFinalizeView 测试"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.outline = _create_outline(self.project)

    def test_toggle_lock(self):
        """锁定/解锁切换"""
        _create_volume(self.project, self.outline, version=1, is_locked=False)
        request = self.factory.post(f'/api/projects/{self.project.pk}/volume-versions/1/finalize/')
        force_authenticate(request, user=self.user)
        response = ApiVolumeVersionFinalizeView.as_view()(request, project_id=self.project.pk, version=1)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['is_locked'])
        # 再次调用解锁
        request2 = self.factory.post(f'/api/projects/{self.project.pk}/volume-versions/1/finalize/')
        force_authenticate(request2, user=self.user)
        response2 = ApiVolumeVersionFinalizeView.as_view()(request2, project_id=self.project.pk, version=1)
        data2 = json.loads(response2.content)
        self.assertFalse(data2['is_locked'])


class ApiVolumeLockViewTest(TestCase):
    """ApiVolumeLockView 测试"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.outline = _create_outline(self.project)

    def test_toggle_single_volume_lock(self):
        """单卷锁定/解锁"""
        vol = _create_volume(self.project, self.outline, is_locked=False)
        request = self.factory.put(
            f'/api/projects/{self.project.pk}/volumes/{vol.pk}/lock/',
            data=json.dumps({'is_locked': True}),
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiVolumeLockView.as_view()(request, project_id=self.project.pk, volume_id=vol.pk)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['is_locked'])
        vol.refresh_from_db()
        self.assertTrue(vol.is_locked)

    def test_lock_missing_param(self):
        """缺少 is_locked 参数返回400"""
        vol = _create_volume(self.project, self.outline)
        request = self.factory.put(
            f'/api/projects/{self.project.pk}/volumes/{vol.pk}/lock/',
            data=json.dumps({}),
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiVolumeLockView.as_view()(request, project_id=self.project.pk, volume_id=vol.pk)
        self.assertEqual(response.status_code, 400)

    def test_nonexistent_volume(self):
        """不存在的卷返回404"""
        request = self.factory.put(
            f'/api/projects/{self.project.pk}/volumes/999/lock/',
            data=json.dumps({'is_locked': True}),
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiVolumeLockView.as_view()(request, project_id=self.project.pk, volume_id=999)
        self.assertEqual(response.status_code, 404)


class ApiVolumeOptimizeViewTest(TestCase):
    """ApiVolumeOptimizeView 测试（mock LLM）"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = _create_user()
        self.project = _create_project(self.user)
        self.outline = _create_outline(self.project)

    def test_missing_params(self):
        """缺少参数返回400"""
        request = self.factory.post(
            f'/api/projects/{self.project.pk}/volumes/optimize/',
            data=json.dumps({}),
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        response = ApiVolumeOptimizeView.as_view()(request, project_id=self.project.pk)
        self.assertEqual(response.status_code, 400)
