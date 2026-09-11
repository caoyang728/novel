"""
characters 序列化器 & 常量测试

运行命令:
    python manage.py test apps.characters.tests.test_serializers --keepdb -v2
"""
from django.test import TestCase
from django.contrib.auth.models import User

from apps.project.models import ProjectList as Project
from apps.characters.models import Character
from apps.characters.tests.conftest import _create_test_data


class CharacterConstantsTest(TestCase):
    """constants.py 工具函数测试"""

    def test_get_reverse_type(self):
        """反向关系映射"""
        from apps.characters.constants import get_reverse_type
        self.assertEqual(get_reverse_type('父母'), '子女')
        self.assertEqual(get_reverse_type('子女'), '父母')
        self.assertEqual(get_reverse_type('师父'), '徒弟')
        self.assertEqual(get_reverse_type('徒弟'), '师父')
        self.assertEqual(get_reverse_type('君主'), '臣子')
        self.assertEqual(get_reverse_type('臣子'), '君主')

    def test_get_reverse_type_unknown(self):
        """未知关系类型返回原值"""
        from apps.characters.constants import get_reverse_type
        self.assertEqual(get_reverse_type('朋友'), '朋友')
        self.assertEqual(get_reverse_type('其他'), '其他')

    def test_normalize_relationship_type_cn(self):
        """中文关系类型在白名单中直接返回"""
        from apps.characters.constants import normalize_relationship_type
        self.assertEqual(normalize_relationship_type('朋友'), '朋友')
        self.assertEqual(normalize_relationship_type('恋人'), '恋人')
        self.assertEqual(normalize_relationship_type('敌人'), '敌人')

    def test_normalize_relationship_type_en(self):
        """英文关系类型翻译为中文"""
        from apps.characters.constants import normalize_relationship_type
        self.assertEqual(normalize_relationship_type('friend'), '朋友')
        self.assertEqual(normalize_relationship_type('lover'), '恋人')
        self.assertEqual(normalize_relationship_type('enemy'), '敌人')
        self.assertEqual(normalize_relationship_type('parent'), '父母')
        self.assertEqual(normalize_relationship_type('child'), '子女')

    def test_normalize_relationship_type_unknown(self):
        """未知类型归一化为 '其他'"""
        from apps.characters.constants import normalize_relationship_type
        self.assertEqual(normalize_relationship_type('未知类型'), '其他')
        self.assertEqual(normalize_relationship_type(''), '其他')
        self.assertEqual(normalize_relationship_type(None), '其他')

    def test_valid_relationship_types_count(self):
        """白名单包含17种关系类型"""
        from apps.characters.constants import VALID_RELATIONSHIP_TYPES
        self.assertEqual(len(VALID_RELATIONSHIP_TYPES), 17)


class CharacterSerializerTest(TestCase):
    """序列化器测试"""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.project = Project.objects.create(
            user=self.user, title='测试项目', genre='xuanhuan', description='测试',
        )

    def test_sanitize_character_name_normal(self):
        """正常名称不变"""
        from apps.characters.serializers import sanitize_character_name
        self.assertEqual(sanitize_character_name('张三'), '张三')

    def test_sanitize_character_name_html_tags(self):
        """去除 HTML 标签"""
        from apps.characters.serializers import sanitize_character_name
        result = sanitize_character_name('<script>alert(1)</script>张三')
        self.assertNotIn('<script>', result)
        self.assertIn('张三', result)

    def test_sanitize_character_name_dangerous_chars(self):
        """去除危险字符"""
        from apps.characters.serializers import sanitize_character_name
        result = sanitize_character_name('张三<>"\'&')
        self.assertNotIn('<', result)
        self.assertNotIn('>', result)

    def test_sanitize_character_name_empty(self):
        """空名称返回空"""
        from apps.characters.serializers import sanitize_character_name
        self.assertEqual(sanitize_character_name(''), '')
        self.assertIsNone(sanitize_character_name(None))

    def test_sanitize_character_name_max_length(self):
        """名称长度限制100"""
        from apps.characters.serializers import sanitize_character_name
        long_name = '名字' * 60  # 120 字符
        result = sanitize_character_name(long_name)
        self.assertLessEqual(len(result), 100)

    def test_create_serializer_valid(self):
        """创建序列化器验证通过"""
        from apps.characters.serializers import CharacterCreateSerializer
        serializer = CharacterCreateSerializer(
            data={'name': '新角色', 'role_type': '主角'},
            context={'project': self.project},
        )
        self.assertTrue(serializer.is_valid())

    def test_create_serializer_duplicate_name(self):
        """创建时重名返回错误"""
        from apps.characters.serializers import CharacterCreateSerializer
        Character.objects.create(project=self.project, name='已有角色')
        serializer = CharacterCreateSerializer(
            data={'name': '已有角色'},
            context={'project': self.project},
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('name', serializer.errors)

    def test_update_serializer_valid(self):
        """更新序列化器验证通过"""
        from apps.characters.serializers import CharacterUpdateSerializer
        char = Character.objects.create(project=self.project, name='张三')
        serializer = CharacterUpdateSerializer(
            instance=char,
            data={'name': '张三', 'role_type': '反派'},
            context={'project': self.project},
        )
        self.assertTrue(serializer.is_valid())

    def test_update_serializer_same_name(self):
        """更新时保持自身名称不冲突"""
        from apps.characters.serializers import CharacterUpdateSerializer
        char = Character.objects.create(project=self.project, name='张三')
        serializer = CharacterUpdateSerializer(
            instance=char,
            data={'name': '张三'},
            context={'project': self.project},
        )
        self.assertTrue(serializer.is_valid())

    def test_create_serializer_age_empty(self):
        """age 空字符串转为 None"""
        from apps.characters.serializers import CharacterCreateSerializer
        serializer = CharacterCreateSerializer(
            data={'name': '新角色', 'age': ''},
            context={'project': self.project},
        )
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data.get('age'))

    def test_polish_serializer_valid(self):
        """润色序列化器验证"""
        from apps.characters.serializers import CharacterPolishSerializer
        serializer = CharacterPolishSerializer(data={'name': '张三'})
        self.assertTrue(serializer.is_valid())

    def test_polish_serializer_empty_name(self):
        """润色序列化器名称不能为空"""
        from apps.characters.serializers import CharacterPolishSerializer
        serializer = CharacterPolishSerializer(data={'name': ''})
        self.assertFalse(serializer.is_valid())

    def test_trajectory_create_serializer(self):
        """轨迹创建序列化器验证"""
        from apps.characters.serializers import CharacterTrajectoryCreateSerializer
        serializer = CharacterTrajectoryCreateSerializer(data={
            'title': '初入江湖',
            'start_time': '第一章',
            'end_time': '第五章',
            'order': 1,
        })
        self.assertTrue(serializer.is_valid())

    def test_trajectory_create_serializer_empty_title(self):
        """轨迹标题不能为空"""
        from apps.characters.serializers import CharacterTrajectoryCreateSerializer
        serializer = CharacterTrajectoryCreateSerializer(data={'title': ''})
        self.assertFalse(serializer.is_valid())

    def test_validate_relationships_empty_target(self):
        """关系目标名不能为空"""
        from apps.characters.serializers import CharacterCreateSerializer
        serializer = CharacterCreateSerializer(
            data={'name': '新角色', 'relationships': [{'targetName': '', 'relationshipType': '朋友'}]},
            context={'project': self.project},
        )
        self.assertFalse(serializer.is_valid())

    def test_validate_relationships_normalizes_type(self):
        """关系类型归一化"""
        from apps.characters.serializers import CharacterCreateSerializer
        serializer = CharacterCreateSerializer(
            data={'name': '新角色', 'relationships': [{'targetName': '李四', 'relationshipType': 'friend'}]},
            context={'project': self.project},
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['relationships'][0]['relationshipType'], '朋友')
