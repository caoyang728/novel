"""
worldview 接口测试

运行命令:
    python manage.py test apps.worldview.tests --keepdb
    python manage.py test apps.worldview.tests.WorldviewLayerSaveTest --keepdb
    python manage.py test apps.worldview.tests.WorldviewSerializerTest --keepdb
"""
import json
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.project.models import ProjectList as Project
from apps.worldview.models import WorldView
from apps.worldview.serializers import clean_worldview_layer, clean_worldview_data
from apps.worldview.views import ApiWorldviewLayerView


def _create_test_data():
    """创建测试所需的 user、project、worldview"""
    user = User.objects.create_user(username='testuser', password='testpass123')
    project = Project.objects.create(
        user=user,
        name='测试项目',
        novel_type='玄幻',
        description='测试用项目'
    )
    worldview = WorldView.objects.create(
        project=project,
        setting={
            'identity': {'world_name': '测试世界', 'genre': '玄幻'},
            'position': {'identity': '东方玄幻', 'tone': '热血'},
            'overview': '一个测试世界',
            'conflict': '正邪之争',
        },
        foundation={
            'geography': {'continent_distribution': '三块大陆', 'special_terrain': '无尽深渊'},
            'calendar': {'era': '星历', 'days_per_year': '360', 'seasons': '四季', 'festivals': '创世节'},
            'rules': {'natural_laws': '灵气循环', 'boundaries': '世界壁垒', 'axioms': ['公理一', '公理二']},
            'balance': '天道平衡',
        },
        history={'ancient': '混沌初开', 'modern': '三国鼎立', 'crisis': '', 'destiny': '', 'future': ''},
    )
    return user, project, worldview


@override_settings(
    MILVUS_ALIAS='default',
)
class WorldviewSerializerTest(TestCase):
    """测试序列化器：校验、清洗"""

    def test_clean_foundation_strips_unknown_keys(self):
        """未知字段应被剥离"""
        dirty = {
            'geography': {'continent_distribution': '亚洲', 'special_terrain': '喜马拉雅', 'garbage': '垃圾'},
            'calendar': {'era': '公元', 'days_per_year': '365', 'seasons': '四季', 'festivals': ''},
            'rules': {'natural_laws': '', 'boundaries': '', 'axioms': ['公理A', '公理B']},
            'balance': '',
        }
        cleaned = clean_worldview_layer('foundation', dirty)
        self.assertNotIn('garbage', cleaned.get('geography', {}))
        self.assertIn('continent_distribution', cleaned.get('geography', {}))

    def test_clean_foundation_fills_defaults(self):
        """缺失的子结构应填充默认值"""
        dirty = {'geography': {'continent_distribution': '仅一块大陆'}}
        cleaned = clean_worldview_layer('foundation', dirty)
        self.assertIn('calendar', cleaned)
        self.assertIn('rules', cleaned)
        self.assertEqual(cleaned['calendar']['era'], '')
        self.assertEqual(cleaned['balance'], '')

    def test_clean_history_drops_unknown_keys(self):
        """history 层多余字段应被剥离"""
        dirty = {
            'ancient': '远古时代',
            'modern': '近代',
            'crisis': '',
            'destiny': '',
            'future': '',
            'extra_field': '多余数据',
        }
        cleaned = clean_worldview_layer('history', dirty)
        self.assertNotIn('extra_field', cleaned)
        self.assertEqual(cleaned['ancient'], '远古时代')

    def test_axioms_list_preserved(self):
        """核心公理 list 类型应正确保留"""
        dirty = {
            'rules': {'natural_laws': '', 'boundaries': '', 'axioms': ['公理1', '公理2', '公理3']},
        }
        cleaned = clean_worldview_layer('foundation', dirty)
        self.assertEqual(cleaned['rules']['axioms'], ['公理1', '公理2', '公理3'])

    def test_axioms_empty_list(self):
        """核心公理为空数组时应保留为 []"""
        dirty = {
            'rules': {'natural_laws': '', 'boundaries': '', 'axioms': []},
        }
        cleaned = clean_worldview_layer('foundation', dirty)
        self.assertEqual(cleaned['rules']['axioms'], [])

    def test_deep_merge_preserves_list(self):
        """验证 _deep_merge 对 list 字段是追加而非覆盖"""
        from apps.worldview.views import _deep_merge
        base = {'rules': {'axioms': ['已有的公理1', '已有的公理2']}}
        incoming = {'rules': {'axioms': ['新增公理']}}
        _deep_merge(base, incoming)
        # 追加，不覆盖已有项
        self.assertEqual(len(base['rules']['axioms']), 3)
        self.assertIn('已有的公理1', base['rules']['axioms'])
        self.assertIn('已有的公理2', base['rules']['axioms'])
        self.assertIn('新增公理', base['rules']['axioms'])

    def test_clean_worldview_data_all_layers(self):
        """全层清洗应覆盖所有 8 层"""
        worldview = WorldView(project_id=1)
        data = clean_worldview_data(vars(worldview))
        expected_layers = ['setting', 'foundation', 'power', 'races', 'society', 'culture', 'history', 'special']
        for layer in expected_layers:
            self.assertIn(layer, data, f'Missing layer: {layer}')

    def test_class_renamed_to_strata(self):
        """society 层 class 字段已重命名为 strata"""
        dirty = {
            'strata': {'social_classes': '贵族、平民', 'mobility': ''},
            'external': '',
            'resource': '',
        }
        cleaned = clean_worldview_layer('society', dirty)
        self.assertIn('strata', cleaned)
        self.assertNotIn('class', cleaned)
        self.assertIn('social_classes', cleaned.get('strata', {}))


@override_settings(
    MILVUS_ALIAS='default',
)
class WorldviewLayerSaveTest(TestCase):
    """测试 PUT /layer/<layer>/ — 分层保存 + serializer 校验"""

    def setUp(self):
        self.user, self.project, self.worldview = _create_test_data()
        self.factory = APIRequestFactory()

    def _put_layer(self, layer, body):
        """Helper: PUT /api/projects/<pid>/worldviews/<wid>/layer/<layer>/"""
        view = ApiWorldviewLayerView.as_view()
        request = self.factory.put(
            f'/api/projects/{self.project.id}/worldviews/{self.worldview.id}/layer/{layer}/',
            data=body,
            content_type='application/json',
        )
        force_authenticate(request, user=self.user)
        return view(request, project_id=self.project.id, pk=self.worldview.id, layer=layer)

    def test_put_foundation_overwrites_and_cleans(self):
        """保存 foundation 层应覆盖写入 + 清洗多余字段"""
        body = {
            'continent': '新大陆分布',
            'terrain': '新特殊地形',
            'era': '新纪年',
            'days': '',
            'seasons': '',
            'festivals': '',
            'laws': '',
            'boundary': '',
            'axioms': '公理A\n公理B\n公理C',
            'balance': '新平衡',
        }
        response = self._put_layer('foundation', body)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data.get('success'))

        # 验证 DB 已更新
        wv = WorldView.objects.get(pk=self.worldview.id)
        self.assertEqual(wv.foundation['geography']['continent_distribution'], '新大陆分布')
        self.assertEqual(wv.foundation['geography']['special_terrain'], '新特殊地形')
        self.assertEqual(wv.foundation['calendar']['era'], '新纪年')
        self.assertEqual(wv.foundation['balance'], '新平衡')

    def test_put_foundation_axioms_split(self):
        """axioms 字符串应按换行拆分为数组"""
        body = {
            'continent': '', 'terrain': '', 'era': '', 'days': '', 'seasons': '', 'festivals': '',
            'laws': '', 'boundary': '', 'balance': '',
            'axioms': '第一法则\n第二法则\n第三法则',
        }
        response = self._put_layer('foundation', body)
        self.assertEqual(response.status_code, 200)
        wv = WorldView.objects.get(pk=self.worldview.id)
        self.assertEqual(wv.foundation['rules']['axioms'], ['第一法则', '第二法则', '第三法则'])

    def test_put_history_overwrites_completely(self):
        """保存 history 层应完整覆盖，旧字段不留痕"""
        # 先确认初始值
        wv = WorldView.objects.get(pk=self.worldview.id)
        self.assertEqual(wv.history['ancient'], '混沌初开')

        body = {
            'ancient': '混沌初开（修订版）',
            'modern': '',
            'crisis': '',
            'destiny': '',
            'future': '',
        }
        response = self._put_layer('history', body)
        self.assertEqual(response.status_code, 200)
        wv.refresh_from_db()
        self.assertEqual(wv.history['ancient'], '混沌初开（修订版）')
        self.assertEqual(wv.history['modern'], '')

    def test_put_drops_extra_keys(self):
        """保存时多余字段应被 serializer 剥离"""
        body = {
            'ancient': '远古',
            'modern': '',
            'crisis': '',
            'destiny': '',
            'future': '',
            'garbage_field': '垃圾数据',
        }
        response = self._put_layer('history', body)
        self.assertEqual(response.status_code, 200)
        wv = WorldView.objects.get(pk=self.worldview.id)
        self.assertNotIn('garbage_field', wv.history)
