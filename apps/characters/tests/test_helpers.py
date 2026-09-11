"""
characters 辅助方法测试

包含：静态方法、BaseCharacterAPIView 辅助方法、关系同步方法、
      _batch_sync_characters_to_graph、_parse_candidate_list

运行命令:
    python manage.py test apps.characters.tests.test_helpers --keepdb -v2
"""
import json
from django.test import TestCase

from apps.characters.models import Character
from apps.characters.views import (
    ApiCharacterGenerateFromOutlineView,
    ApiCharacterOptimizeView,
    ApiCharacterOptimizeSaveView,
    BaseCharacterAPIView,
)
from apps.characters.tests.conftest import _create_test_data


# ============ _parse_candidates 静态方法测试 ============

class ParseCandidatesStaticMethodTest(TestCase):
    """ApiCharacterGenerateFromOutlineView._parse_candidates 静态方法测试"""

    def test_parse_valid_json_array(self):
        """解析有效的 JSON 数组"""
        llm_content = json.dumps([
            {"name": "张三", "role_type": "主角", "gender": "男"},
            {"name": "李四", "role_type": "配角", "gender": "女"},
        ], ensure_ascii=False)
        result = ApiCharacterGenerateFromOutlineView._parse_candidates(llm_content, [])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], '张三')
        self.assertTrue(result[0]['is_new'])
        self.assertTrue(result[1]['is_new'])

    def test_parse_with_existing_names(self):
        """标记已有角色为非新建"""
        llm_content = json.dumps([
            {"name": "张三", "role_type": "主角"},
            {"name": "王五", "role_type": "配角"},
        ], ensure_ascii=False)
        result = ApiCharacterGenerateFromOutlineView._parse_candidates(llm_content, ['张三'])
        self.assertEqual(len(result), 2)
        self.assertFalse(result[0]['is_new'])
        self.assertTrue(result[1]['is_new'])

    def test_parse_from_markdown_code_block(self):
        """从 markdown 代码块中提取 JSON"""
        llm_content = '''以下是从大纲提取的角色列表：

```json
[
    {"name": "赵六", "role_type": "反派", "gender": "男"},
    {"name": "孙七", "role_type": "配角", "gender": "女"}
]
```

以上就是提取的角色。'''
        result = ApiCharacterGenerateFromOutlineView._parse_candidates(llm_content, [])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], '赵六')
        self.assertEqual(result[1]['name'], '孙七')

    def test_parse_from_code_block_without_json_label(self):
        """从无语言标签的代码块中提取 JSON"""
        llm_content = '''```
[
    {"name": "周八", "role_type": "主角"}
]
```'''
        result = ApiCharacterGenerateFromOutlineView._parse_candidates(llm_content, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], '周八')

    def test_parse_no_json_array(self):
        """没有 JSON 数组时返回空列表"""
        llm_content = "这是一段普通文本，没有 JSON 内容"
        result = ApiCharacterGenerateFromOutlineView._parse_candidates(llm_content, [])
        self.assertEqual(result, [])

    def test_parse_invalid_json(self):
        """JSON 解析失败时返回空列表"""
        llm_content = '[{"name": "张三", invalid json}]'
        result = ApiCharacterGenerateFromOutlineView._parse_candidates(llm_content, [])
        self.assertEqual(result, [])

    def test_parse_non_list_json(self):
        """JSON 不是数组时返回空列表"""
        llm_content = json.dumps({"name": "张三"})
        result = ApiCharacterGenerateFromOutlineView._parse_candidates(llm_content, [])
        self.assertEqual(result, [])

    def test_parse_skip_items_without_name(self):
        """跳过没有 name 字段的项"""
        llm_content = json.dumps([
            {"name": "张三", "role_type": "主角"},
            {"role_type": "配角"},
            {"name": "", "role_type": "配角"},
            {"name": "李四", "role_type": "反派"},
        ], ensure_ascii=False)
        result = ApiCharacterGenerateFromOutlineView._parse_candidates(llm_content, [])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], '张三')
        self.assertEqual(result[1]['name'], '李四')

    def test_parse_strips_whitespace_from_name(self):
        """去除名称两端空白"""
        llm_content = json.dumps([
            {"name": "  张三  ", "role_type": "主角"},
        ], ensure_ascii=False)
        result = ApiCharacterGenerateFromOutlineView._parse_candidates(llm_content, [])
        self.assertEqual(result[0]['name'], '张三')

    def test_parse_non_dict_items_skipped(self):
        """非字典项被跳过"""
        llm_content = json.dumps([
            "not a dict",
            123,
            {"name": "张三", "role_type": "主角"},
        ], ensure_ascii=False)
        result = ApiCharacterGenerateFromOutlineView._parse_candidates(llm_content, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], '张三')


# ============ _post_process_optimize 静态方法测试 ============

class PostProcessOptimizeStaticMethodTest(TestCase):
    """ApiCharacterOptimizeView._post_process_optimize 静态方法测试"""

    def test_extract_valid_json_array(self):
        """从 LLM 输出中提取有效 JSON 数组"""
        llm_content = '以下是优化建议：\n' + json.dumps([
            {"name": "张三", "type": "modify", "params": [{"param": "身份", "new": "剑神"}]},
        ], ensure_ascii=False)
        result = ApiCharacterOptimizeView._post_process_optimize(llm_content)
        parsed = json.loads(result)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['name'], '张三')

    def test_extract_from_markdown(self):
        """从 markdown 代码块中提取"""
        llm_content = '''优化结果：

```json
[
    {"name": "李四", "type": "add", "params": []}
]
```'''
        result = ApiCharacterOptimizeView._post_process_optimize(llm_content)
        parsed = json.loads(result)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['name'], '李四')

    def test_no_json_array_returns_empty(self):
        """没有 JSON 数组时返回空数组"""
        result = ApiCharacterOptimizeView._post_process_optimize('纯文本内容，没有JSON')
        parsed = json.loads(result)
        self.assertEqual(parsed, [])

    def test_invalid_json_returns_empty(self):
        """JSON 解析失败时返回空数组"""
        result = ApiCharacterOptimizeView._post_process_optimize('[invalid json]')
        parsed = json.loads(result)
        self.assertEqual(parsed, [])

    def test_non_list_json_returns_empty(self):
        """非数组 JSON 返回空数组"""
        result = ApiCharacterOptimizeView._post_process_optimize('{"key": "value"}')
        parsed = json.loads(result)
        self.assertEqual(parsed, [])

    def test_empty_array(self):
        """空数组正常返回"""
        result = ApiCharacterOptimizeView._post_process_optimize('[]')
        parsed = json.loads(result)
        self.assertEqual(parsed, [])

    def test_nested_json_array(self):
        """嵌套复杂 JSON 数组"""
        data = [
            {"name": "张三", "type": "modify", "params": [
                {"param": "身份", "origin": "剑仙", "new": "剑神"},
                {"param": "关系", "origin": "李四是我的朋友", "new": "李四是我的师父"},
            ]},
        ]
        result = ApiCharacterOptimizeView._post_process_optimize(json.dumps(data, ensure_ascii=False))
        parsed = json.loads(result)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['params'][0]['new'], '剑神')


# ============ _sanitize_field_value 静态方法测试 ============

class SanitizeFieldValueStaticMethodTest(TestCase):
    """ApiCharacterOptimizeSaveView._sanitize_field_value 静态方法测试"""

    def test_age_integer(self):
        """年龄为整数直接返回"""
        result = ApiCharacterOptimizeSaveView._sanitize_field_value(None, 'age', 25)
        self.assertEqual(result, 25)

    def test_age_string_number(self):
        """年龄为数字字符串提取数字"""
        result = ApiCharacterOptimizeSaveView._sanitize_field_value(None, 'age', '30')
        self.assertEqual(result, 30)

    def test_age_string_with_text(self):
        """年龄为包含数字的字符串提取第一个数字"""
        result = ApiCharacterOptimizeSaveView._sanitize_field_value(None, 'age', '约25岁')
        self.assertEqual(result, 25)

    def test_age_empty_string(self):
        """年龄为空字符串返回 None"""
        result = ApiCharacterOptimizeSaveView._sanitize_field_value(None, 'age', '')
        self.assertIsNone(result)

    def test_age_none(self):
        """年龄为 None 返回 None"""
        result = ApiCharacterOptimizeSaveView._sanitize_field_value(None, 'age', None)
        self.assertIsNone(result)

    def test_age_non_numeric_string(self):
        """年龄为非数字字符串返回 None"""
        result = ApiCharacterOptimizeSaveView._sanitize_field_value(None, 'age', '未知')
        self.assertIsNone(result)

    def test_non_age_field_passthrough(self):
        """非 age 字段直接返回原值"""
        result = ApiCharacterOptimizeSaveView._sanitize_field_value(None, 'gender', '男')
        self.assertEqual(result, '男')

    def test_non_age_field_list(self):
        """非 age 字段列表直接返回"""
        data = [{'targetName': '李四', 'relationshipType': '朋友'}]
        result = ApiCharacterOptimizeSaveView._sanitize_field_value(None, 'relationships', data)
        self.assertEqual(result, data)

    def test_age_float_value(self):
        """年龄为浮点数转为整数"""
        result = ApiCharacterOptimizeSaveView._sanitize_field_value(None, 'age', 25.7)
        self.assertEqual(result, 25)


# ============ BaseCharacterAPIView 辅助方法测试 ============

class BaseCharacterHelperMethodsTest(TestCase):
    """BaseCharacterAPIView 辅助方法测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.view = BaseCharacterAPIView()

    def test_validate_field_length_short_string(self):
        """短字符串不截断"""
        result = self.view._validate_field_length('content', '短文本')
        self.assertEqual(result, '短文本')

    def test_validate_field_length_long_string_truncated(self):
        """超长字符串被截断到 2000 字符"""
        long_text = 'a' * 3000
        result = self.view._validate_field_length('content', long_text)
        self.assertEqual(len(result), 2000)

    def test_validate_field_length_long_string_adds_warning(self):
        """超长字符串截断时添加警告"""
        warnings = []
        long_text = 'a' * 3000
        self.view._validate_field_length('content', long_text, warnings)
        self.assertEqual(len(warnings), 1)
        self.assertIn('超长', warnings[0])

    def test_validate_field_length_list_normal(self):
        """正常长度列表直接返回"""
        data = [{'targetName': '李四', 'relationshipType': '朋友'}]
        result = self.view._validate_field_length('relationships', data)
        self.assertEqual(result, data)

    def test_validate_field_length_list_too_long(self):
        """超长 JSON 列表被清空"""
        huge_list = [{'targetName': f'角色{i}', 'relationshipType': '朋友', 'description': 'x' * 50}
                     for i in range(100)]
        warnings = []
        result = self.view._validate_field_length('relationships', huge_list, warnings)
        self.assertEqual(result, [])
        self.assertEqual(len(warnings), 1)
        self.assertIn('JSON超长', warnings[0])

    def test_validate_field_length_exact_boundary(self):
        """刚好 2000 字符的字符串不截断"""
        exact_text = 'a' * 2000
        result = self.view._validate_field_length('content', exact_text)
        self.assertEqual(len(result), 2000)

    def test_get_worldview_str_with_worldview(self):
        """有世界观时返回世界观内容"""
        self.view.get_worldview_context = lambda project: '这是一个完整的修仙世界观'
        result = self.view._get_worldview_str(self.project)
        self.assertEqual(result, '这是一个完整的修仙世界观')

    def test_get_worldview_str_without_worldview(self):
        """无世界观时返回默认文本"""
        self.view.get_worldview_context = lambda project: None
        result = self.view._get_worldview_str(self.project)
        self.assertEqual(result, '暂无世界观设定')

    def test_get_worldview_str_with_placeholder(self):
        """世界观包含'暂无'时返回默认文本"""
        self.view.get_worldview_context = lambda project: '（暂无世界观设定）'
        result = self.view._get_worldview_str(self.project)
        self.assertEqual(result, '暂无世界观设定')

    def test_format_character_data_single(self):
        """格式化单个角色"""
        result = self.view._format_character_data([self.character])
        self.assertIn('角色：张三', result)
        self.assertIn('定位：主角', result)
        self.assertIn('性别：男', result)
        self.assertIn('身份：剑仙', result)

    def test_format_character_data_multiple(self):
        """格式化多个角色"""
        char2 = Character.objects.create(
            project=self.project, name='李四', role_type='配角', gender='女',
            age=20, faction='反派', identity='刺客',
        )
        result = self.view._format_character_data([self.character, char2])
        self.assertIn('角色：张三', result)
        self.assertIn('角色：李四', result)
        self.assertIn('势力：正派', result)
        self.assertIn('势力：反派', result)

    def test_format_character_data_with_relationships(self):
        """格式化带关系的角色"""
        self.character.relationships = [
            {'targetName': '李四', 'relationshipType': '朋友', 'description': '青梅竹马'},
        ]
        self.character.save()
        result = self.view._format_character_data([self.character])
        self.assertIn('关系', result)
        self.assertIn('李四是我的朋友', result)
        self.assertIn('青梅竹马', result)

    def test_format_character_data_with_string_relationships(self):
        """格式化字符串关系"""
        self.character.relationships = '李四是我的朋友'
        self.character.save()
        result = self.view._format_character_data([self.character])
        self.assertIn('关系', result)

    def test_format_character_data_empty_content(self):
        """无 content 时不出现在输出中"""
        self.character.content = ''
        self.character.save()
        result = self.view._format_character_data([self.character])
        self.assertNotIn('内容', result)


# ============ 关系同步方法测试 ============

class CharacterRelationshipMethodsTest(TestCase):
    """角色关系同步方法测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()
        self.view = BaseCharacterAPIView()

        self.char_b = Character.objects.create(
            project=self.project, name='李四', role_type='配角', gender='女',
        )
        self.char_c = Character.objects.create(
            project=self.project, name='王五', role_type='反派', gender='男',
        )

    def test_create_reverse_relationships_basic(self):
        """创建反向关系 - 基本场景"""
        relationships = [{
            'targetName': '李四',
            'relationshipType': '朋友',
            'description': '青梅竹马',
            'createReverse': True,
        }]
        self.view._create_reverse_relationships(self.project, self.character, relationships)

        self.char_b.refresh_from_db()
        self.assertEqual(len(self.char_b.relationships), 1)
        self.assertEqual(self.char_b.relationships[0]['targetName'], '张三')
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '朋友')

    def test_create_reverse_relationships_parent_child(self):
        """创建反向关系 - 父母/子女互转"""
        relationships = [{
            'targetName': '李四',
            'relationshipType': '父母',
            'createReverse': True,
        }]
        self.view._create_reverse_relationships(self.project, self.character, relationships)

        self.char_b.refresh_from_db()
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '子女')

    def test_create_reverse_relationships_skip_without_flag(self):
        """createReverse=False 时不创建反向关系"""
        relationships = [{
            'targetName': '李四',
            'relationshipType': '朋友',
            'createReverse': False,
        }]
        self.view._create_reverse_relationships(self.project, self.character, relationships)

        self.char_b.refresh_from_db()
        self.assertEqual(len(self.char_b.relationships), 0)

    def test_create_reverse_relationships_target_not_found(self):
        """目标角色不存在时跳过"""
        relationships = [{
            'targetName': '不存在的角色',
            'relationshipType': '朋友',
            'createReverse': True,
        }]
        self.view._create_reverse_relationships(self.project, self.character, relationships)

    def test_create_reverse_relationships_update_existing(self):
        """已有反向关系时更新类型"""
        self.char_b.relationships = [{
            'targetName': '张三',
            'relationshipType': '敌人',
            'createReverse': False,
        }]
        self.char_b.save()

        relationships = [{
            'targetName': '李四',
            'relationshipType': '朋友',
            'createReverse': True,
        }]
        self.view._create_reverse_relationships(self.project, self.character, relationships)

        self.char_b.refresh_from_db()
        self.assertEqual(len(self.char_b.relationships), 1)
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '朋友')

    def test_create_reverse_relationships_no_change_same_type(self):
        """已有反向关系且类型相同，不修改"""
        self.char_b.relationships = [{
            'targetName': '张三',
            'relationshipType': '朋友',
            'createReverse': False,
        }]
        self.char_b.save()

        relationships = [{
            'targetName': '李四',
            'relationshipType': '朋友',
            'createReverse': True,
        }]
        self.view._create_reverse_relationships(self.project, self.character, relationships)

        self.char_b.refresh_from_db()
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '朋友')

    def test_create_reverse_relationships_multiple_targets(self):
        """批量创建多个反向关系"""
        relationships = [
            {'targetName': '李四', 'relationshipType': '朋友', 'createReverse': True},
            {'targetName': '王五', 'relationshipType': '敌人', 'createReverse': True},
        ]
        self.view._create_reverse_relationships(self.project, self.character, relationships)

        self.char_b.refresh_from_db()
        self.char_c.refresh_from_db()
        self.assertEqual(len(self.char_b.relationships), 1)
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '朋友')
        self.assertEqual(len(self.char_c.relationships), 1)
        self.assertEqual(self.char_c.relationships[0]['relationshipType'], '敌人')

    def test_sync_reverse_relationships_add_new(self):
        """同步：新增关系创建反向"""
        old_rels = []
        new_rels = [{'targetName': '李四', 'relationshipType': '朋友', 'createReverse': True}]
        self.view._sync_reverse_relationships(self.project, self.character, old_rels, new_rels)

        self.char_b.refresh_from_db()
        self.assertEqual(len(self.char_b.relationships), 1)
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '朋友')

    def test_sync_reverse_relationships_remove_old(self):
        """同步：删除关系清理反向"""
        self.char_b.relationships = [{
            'targetName': '张三', 'relationshipType': '朋友', 'createReverse': False,
        }]
        self.char_b.save()

        old_rels = [{'targetName': '李四', 'relationshipType': '朋友'}]
        new_rels = []
        self.view._sync_reverse_relationships(self.project, self.character, old_rels, new_rels)

        self.char_b.refresh_from_db()
        self.assertEqual(len(self.char_b.relationships), 0)

    def test_sync_reverse_relationships_change_type(self):
        """同步：类型变更更新反向"""
        self.char_b.relationships = [{
            'targetName': '张三', 'relationshipType': '朋友', 'createReverse': False,
        }]
        self.char_b.save()

        old_rels = [{'targetName': '李四', 'relationshipType': '朋友'}]
        new_rels = [{'targetName': '李四', 'relationshipType': '敌人'}]
        self.view._sync_reverse_relationships(self.project, self.character, old_rels, new_rels)

        self.char_b.refresh_from_db()
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '敌人')

    def test_sync_reverse_relationships_no_targets(self):
        """空目标集合时不操作"""
        old_rels = []
        new_rels = []
        self.view._sync_reverse_relationships(self.project, self.character, old_rels, new_rels)

    def test_sync_reverse_relationships_complex_diff(self):
        """同步：复杂差异（同时有新增、删除、变更）"""
        self.char_b.relationships = [{
            'targetName': '张三', 'relationshipType': '朋友', 'createReverse': False,
        }]
        self.char_b.save()
        self.char_c.relationships = [{
            'targetName': '张三', 'relationshipType': '敌人', 'createReverse': False,
        }]
        self.char_c.save()

        old_rels = [
            {'targetName': '李四', 'relationshipType': '朋友'},
            {'targetName': '王五', 'relationshipType': '敌人'},
        ]
        new_rels = [
            {'targetName': '李四', 'relationshipType': '敌人'},
        ]
        self.view._sync_reverse_relationships(self.project, self.character, old_rels, new_rels)

        self.char_b.refresh_from_db()
        self.char_c.refresh_from_db()
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '敌人')
        self.assertEqual(len(self.char_c.relationships), 0)

    def test_update_reverse_for_single_change_same_target_type_changed(self):
        """单条变更：同一目标，类型变了"""
        self.char_b.relationships = [{
            'targetName': '张三', 'relationshipType': '朋友', 'createReverse': False,
        }]
        self.char_b.save()

        origin = {'targetName': '李四', 'relationshipType': '朋友'}
        new = {'targetName': '李四', 'relationshipType': '敌人'}
        self.view._update_reverse_for_single_change(self.project, self.character, origin, new)

        self.char_b.refresh_from_db()
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '敌人')

    def test_update_reverse_for_single_change_delete_relation(self):
        """单条变更：关系被删除"""
        self.char_b.relationships = [{
            'targetName': '张三', 'relationshipType': '朋友', 'createReverse': False,
        }]
        self.char_b.save()

        origin = {'targetName': '李四', 'relationshipType': '朋友'}
        new = {'targetName': None}
        self.view._update_reverse_for_single_change(self.project, self.character, origin, new)

        self.char_b.refresh_from_db()
        self.assertEqual(len(self.char_b.relationships), 0)

    def test_update_reverse_for_single_change_add_new(self):
        """单条变更：新增关系"""
        origin = {}
        new = {'targetName': '李四', 'relationshipType': '师父'}
        self.view._update_reverse_for_single_change(self.project, self.character, origin, new)

        self.char_b.refresh_from_db()
        self.assertEqual(len(self.char_b.relationships), 1)
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '徒弟')

    def test_update_reverse_for_single_change_string_input(self):
        """单条变更：字符串格式输入"""
        self.char_b.relationships = [{
            'targetName': '张三', 'relationshipType': '朋友', 'createReverse': False,
        }]
        self.char_b.save()

        origin = '李四是我的朋友'
        new = '李四是我的师父'
        self.view._update_reverse_for_single_change(self.project, self.character, origin, new)

        self.char_b.refresh_from_db()
        self.assertEqual(self.char_b.relationships[0]['relationshipType'], '徒弟')

    def test_apply_relationship_change_dict_with_origin(self):
        """增量更新：dict→dict，按 targetName 匹配替换"""
        self.character.relationships = [
            {'targetName': '李四', 'relationshipType': '朋友', 'description': '旧描述'},
        ]

        origin = {'targetName': '李四'}
        new_value = {'targetName': '李四', 'relationshipType': '敌人', 'description': '新描述'}
        self.view._apply_relationship_change(self.character, origin, new_value)

        self.assertEqual(len(self.character.relationships), 1)
        self.assertEqual(self.character.relationships[0]['relationshipType'], '敌人')
        self.assertEqual(self.character.relationships[0]['description'], '新描述')

    def test_apply_relationship_change_dict_without_origin(self):
        """增量更新：无 origin 时追加"""
        self.character.relationships = []
        new_value = {'targetName': '李四', 'relationshipType': '朋友'}
        self.view._apply_relationship_change(self.character, None, new_value)

        self.assertEqual(len(self.character.relationships), 1)
        self.assertEqual(self.character.relationships[0]['targetName'], '李四')

    def test_apply_relationship_change_dict_origin_not_found(self):
        """增量更新：origin 目标不存在时追加"""
        self.character.relationships = [
            {'targetName': '王五', 'relationshipType': '敌人'},
        ]
        origin = {'targetName': '不存在的角色'}
        new_value = {'targetName': '李四', 'relationshipType': '朋友'}
        self.view._apply_relationship_change(self.character, origin, new_value)

        self.assertEqual(len(self.character.relationships), 2)

    def test_apply_relationship_change_list(self):
        """增量更新：list→list 直接替换"""
        self.character.relationships = [
            {'targetName': '李四', 'relationshipType': '朋友'},
        ]
        new_value = [
            {'targetName': '王五', 'relationshipType': '敌人'},
            {'targetName': '赵六', 'relationshipType': '师父'},
        ]
        self.view._apply_relationship_change(self.character, None, new_value)

        self.assertEqual(len(self.character.relationships), 2)
        self.assertEqual(self.character.relationships[0]['relationshipType'], '敌人')
        self.assertEqual(self.character.relationships[1]['relationshipType'], '师父')

    def test_apply_relationship_change_string_new(self):
        """增量更新：字符串格式新增"""
        self.character.relationships = []
        self.view._apply_relationship_change(self.character, None, '李四是我的朋友')

        self.assertEqual(len(self.character.relationships), 1)
        self.assertEqual(self.character.relationships[0]['targetName'], '李四')
        self.assertEqual(self.character.relationships[0]['relationshipType'], '朋友')

    def test_apply_relationship_change_string_with_origin(self):
        """增量更新：字符串格式替换"""
        self.character.relationships = [
            {'targetName': '李四', 'relationshipType': '朋友'},
        ]
        self.view._apply_relationship_change(self.character, '李四是我的朋友', '李四是我的敌人')

        self.assertEqual(len(self.character.relationships), 1)
        self.assertEqual(self.character.relationships[0]['relationshipType'], '敌人')

    def test_apply_relationship_change_string_invalid(self):
        """增量更新：无效字符串不修改"""
        self.character.relationships = [
            {'targetName': '李四', 'relationshipType': '朋友'},
        ]
        self.view._apply_relationship_change(self.character, None, '无法解析的关系')
        self.assertEqual(len(self.character.relationships), 1)

    def test_parse_relationship_string_basic(self):
        """解析关系字符串 - 基本格式"""
        result = BaseCharacterAPIView._parse_relationship_string('刘禅是我的父母')
        self.assertEqual(result['targetName'], '刘禅')
        self.assertEqual(result['relationshipType'], '父母')
        self.assertEqual(result['description'], '')
        self.assertTrue(result['createReverse'])

    def test_parse_relationship_string_with_description(self):
        """解析关系字符串 - 带描述"""
        result = BaseCharacterAPIView._parse_relationship_string('刘禅是我的父母 - 严厉但深爱')
        self.assertEqual(result['targetName'], '刘禅')
        self.assertEqual(result['relationshipType'], '父母')
        self.assertEqual(result['description'], '严厉但深爱')

    def test_parse_relationship_string_old_format(self):
        """解析关系字符串 - 旧格式（类型-目标-描述）"""
        result = BaseCharacterAPIView._parse_relationship_string('朋友-李四-青梅竹马')
        self.assertEqual(result['targetName'], '李四')
        self.assertEqual(result['relationshipType'], '朋友')
        self.assertEqual(result['description'], '青梅竹马')

    def test_parse_relationship_string_old_format_no_desc(self):
        """解析关系字符串 - 旧格式无描述"""
        result = BaseCharacterAPIView._parse_relationship_string('敌人-王五')
        self.assertEqual(result['targetName'], '王五')
        self.assertEqual(result['relationshipType'], '敌人')

    def test_parse_relationship_string_empty(self):
        """解析空字符串返回 None"""
        self.assertIsNone(BaseCharacterAPIView._parse_relationship_string(''))
        self.assertIsNone(BaseCharacterAPIView._parse_relationship_string(None))


# ============ _batch_sync_characters_to_graph 测试 ============

class BatchSyncCharactersToGraphTest(TestCase):
    """_batch_sync_characters_to_graph 函数测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()

    def test_sync_with_valid_ids(self):
        """有有效 ID 时不报错"""
        from apps.characters.views import _batch_sync_characters_to_graph
        _batch_sync_characters_to_graph(self.project, [{'id': self.character.id}])

    def test_sync_with_empty_list(self):
        """空列表不报错"""
        from apps.characters.views import _batch_sync_characters_to_graph
        _batch_sync_characters_to_graph(self.project, [])

    def test_sync_with_no_id(self):
        """没有 id 的项跳过"""
        from apps.characters.views import _batch_sync_characters_to_graph
        _batch_sync_characters_to_graph(self.project, [{'name': 'test'}])

    def test_sync_with_none_id(self):
        """id 为 None 的项跳过"""
        from apps.characters.views import _batch_sync_characters_to_graph
        _batch_sync_characters_to_graph(self.project, [{'id': None}])


# ============ _parse_candidate_list 测试 ============

class ParseCandidateListFunctionTest(TestCase):
    """new_views._parse_candidate_list 函数测试"""

    def test_parse_dict_with_characters_key(self):
        """解析包含 characters 键的 JSON 对象"""
        from apps.characters.new_views import _parse_candidate_list
        llm_content = json.dumps({
            "characters": [
                {"name": "张三", "role_type": "主角"},
                {"name": "李四", "role_type": "配角"},
            ]
        }, ensure_ascii=False)
        result = _parse_candidate_list(llm_content, [])
        self.assertEqual(len(result), 2)
        self.assertTrue(result[0]['is_new'])
        self.assertTrue(result[1]['is_new'])

    def test_parse_with_existing_names(self):
        """标记已有角色"""
        from apps.characters.new_views import _parse_candidate_list
        llm_content = json.dumps({
            "characters": [
                {"name": "张三", "role_type": "主角"},
                {"name": "王五", "role_type": "配角"},
            ]
        }, ensure_ascii=False)
        result = _parse_candidate_list(llm_content, ['张三'])
        self.assertEqual(len(result), 2)
        self.assertFalse(result[0]['is_new'])
        self.assertTrue(result[1]['is_new'])

    def test_parse_invalid_content(self):
        """无效内容返回空列表"""
        from apps.characters.new_views import _parse_candidate_list
        result = _parse_candidate_list('这不是 JSON', [])
        self.assertEqual(result, [])

    def test_parse_dict_with_candidates_key(self):
        """对象中包含 candidates 键"""
        from apps.characters.new_views import _parse_candidate_list
        llm_content = json.dumps({
            "candidates": [
                {"name": "张三", "role_type": "主角"},
            ]
        }, ensure_ascii=False)
        result = _parse_candidate_list(llm_content, [])
        self.assertEqual(len(result), 1)

    def test_parse_dict_with_roles_key(self):
        """对象中包含 roles 键"""
        from apps.characters.new_views import _parse_candidate_list
        llm_content = json.dumps({
            "roles": [
                {"name": "张三", "role_type": "主角"},
            ]
        }, ensure_ascii=False)
        result = _parse_candidate_list(llm_content, [])
        self.assertEqual(len(result), 1)

    def test_parse_dict_without_array_key_returns_empty(self):
        """不含 characters/candidates/roles 键的对象返回空"""
        from apps.characters.new_views import _parse_candidate_list
        llm_content = json.dumps({"other_key": "value"})
        result = _parse_candidate_list(llm_content, [])
        self.assertEqual(result, [])

    def test_parse_non_list_non_dict_returns_empty(self):
        """非列表非字典结果返回空"""
        from apps.characters.new_views import _parse_candidate_list
        result = _parse_candidate_list('"just a string"', [])
        self.assertEqual(result, [])

    def test_parse_skip_items_without_name(self):
        """跳过没有 name 的项"""
        from apps.characters.new_views import _parse_candidate_list
        llm_content = json.dumps({
            "characters": [
                {"name": "张三", "role_type": "主角"},
                {"role_type": "配角"},
                {"name": ""},
            ]
        }, ensure_ascii=False)
        result = _parse_candidate_list(llm_content, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], '张三')

    def test_parse_strips_whitespace(self):
        """去除名称空白"""
        from apps.characters.new_views import _parse_candidate_list
        llm_content = json.dumps({
            "characters": [
                {"name": "  张三  ", "role_type": "主角"},
            ]
        }, ensure_ascii=False)
        result = _parse_candidate_list(llm_content, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], '张三')

    def test_parse_empty_characters_list(self):
        """空 characters 列表返回空结果"""
        from apps.characters.new_views import _parse_candidate_list
        llm_content = json.dumps({"characters": []})
        result = _parse_candidate_list(llm_content, [])
        self.assertEqual(result, [])

    def test_parse_characters_with_non_dict_items(self):
        """characters 中非字典项被跳过"""
        from apps.characters.new_views import _parse_candidate_list
        llm_content = json.dumps({
            "characters": [
                "string", 123, None, {"name": "张三"},
            ]
        }, ensure_ascii=False)
        result = _parse_candidate_list(llm_content, [])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], '张三')
