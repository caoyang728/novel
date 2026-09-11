"""
characters 模型测试

运行命令:
    python manage.py test apps.characters.tests.test_models --keepdb -v2
"""
from django.test import TestCase
from django.db import IntegrityError

from apps.characters.models import Character, CharacterTrajectory
from apps.characters.tests.conftest import _create_test_data


class CharacterModelTest(TestCase):
    """Character 模型测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()

    def test_create_character(self):
        """创建角色并验证所有字段"""
        char = self.character
        self.assertEqual(char.project, self.project)
        self.assertEqual(char.name, '张三')
        self.assertEqual(char.role_type, '主角')
        self.assertEqual(char.gender, '男')
        self.assertEqual(char.age, 25)
        self.assertEqual(char.faction, '正派')
        self.assertEqual(char.identity, '剑仙')
        self.assertEqual(char.tagline, '一剑破万法')
        self.assertEqual(char.source, 'manual')
        self.assertFalse(char.is_deleted)
        self.assertIsNotNone(char.created_at)
        self.assertIsNotNone(char.updated_at)

    def test_character_source_choices(self):
        """验证 source 字段的 choices"""
        valid_sources = ['manual', 'ai_generate', 'outline_extract', 'volume_extract', 'chapter_discover']
        for source in valid_sources:
            char = Character.objects.create(
                project=self.project,
                name=f'角色_{source}',
                source=source,
            )
            self.assertEqual(char.source, source)

    def test_character_unique_name_per_project(self):
        """同项目下重名应报 IntegrityError"""
        with self.assertRaises(IntegrityError):
            Character.objects.create(
                project=self.project,
                name='张三',
            )

    def test_character_content_field(self):
        """验证 content Markdown 字段存储和读取"""
        markdown_content = """## 外貌

身高八尺，面容俊朗。

## 背景

出身名门，自幼修剑。

### 能力
- 御剑飞行
- 剑气纵横
"""
        self.character.content = markdown_content
        self.character.save()

        refreshed = Character.objects.get(pk=self.character.pk)
        self.assertEqual(refreshed.content, markdown_content)
        self.assertIn('## 外貌', refreshed.content)
        self.assertIn('- 御剑飞行', refreshed.content)


class CharacterTrajectoryModelTest(TestCase):
    """CharacterTrajectory 模型测试"""

    def setUp(self):
        self.user, self.project, self.character = _create_test_data()

    def test_create_trajectory(self):
        """创建轨迹并验证字段"""
        trajectory = CharacterTrajectory.objects.create(
            character=self.character,
            project=self.project,
            title='初入江湖',
            start_time='第一章',
            end_time='第五章',
            chapter_ids=[1, 2, 3],
            order=1,
            details={
                'location': '青云镇',
                'power_level': '筑基期',
            },
        )
        self.assertEqual(trajectory.character, self.character)
        self.assertEqual(trajectory.project, self.project)
        self.assertEqual(trajectory.title, '初入江湖')
        self.assertEqual(trajectory.start_time, '第一章')
        self.assertEqual(trajectory.end_time, '第五章')
        self.assertEqual(trajectory.chapter_ids, [1, 2, 3])
        self.assertEqual(trajectory.order, 1)

    def test_trajectory_str(self):
        """验证 __str__ 返回 f'{character.name} - {title}'"""
        trajectory = CharacterTrajectory.objects.create(
            character=self.character,
            project=self.project,
            title='踏入修仙界',
        )
        self.assertEqual(str(trajectory), '张三 - 踏入修仙界')

    def test_trajectory_details_json(self):
        """验证 details JSON 字段存储 location、power_level 等"""
        details = {
            'description': '在青云镇拜入仙门',
            'location': '青云镇',
            'emotional_state': '兴奋',
            'power_level': '筑基期',
            'key_events': ['拜师', '获得法宝'],
            'tags': ['成长', '转折'],
        }
        trajectory = CharacterTrajectory.objects.create(
            character=self.character,
            project=self.project,
            title='拜师入门',
            details=details,
        )

        refreshed = CharacterTrajectory.objects.get(pk=trajectory.pk)
        self.assertEqual(refreshed.details['location'], '青云镇')
        self.assertEqual(refreshed.details['power_level'], '筑基期')
        self.assertEqual(refreshed.details['emotional_state'], '兴奋')
        self.assertEqual(refreshed.details['key_events'], ['拜师', '获得法宝'])
        self.assertEqual(refreshed.details['tags'], ['成长', '转折'])

    def test_trajectory_cascade_delete(self):
        """删除角色时轨迹级联删除"""
        CharacterTrajectory.objects.create(
            character=self.character,
            project=self.project,
            title='轨迹1',
        )
        CharacterTrajectory.objects.create(
            character=self.character,
            project=self.project,
            title='轨迹2',
        )
        char_id = self.character.id
        self.assertEqual(CharacterTrajectory.objects.filter(character_id=char_id).count(), 2)

        self.character.delete()
        self.assertEqual(CharacterTrajectory.objects.filter(character_id=char_id).count(), 0)
