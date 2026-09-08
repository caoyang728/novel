# Generated manually for worldview field restructuring

from django.db import migrations, models


def migrate_worldview_data(apps, schema_editor):
    """迁移现有数据到新结构：
    1. 将 calendar.festivals 移动到 culture.custom.festivals（如果后者为空）
    2. 将 society.martial 重命名为 society.jianghu
    3. 将 special.rules 重命名为 special.transmigration_rules
    4. 初始化新字段的默认值
    """
    WorldView = apps.get_model('worldview', 'WorldView')
    
    for wv in WorldView.objects.all():
        changed = False
        
        # 1. 迁移 calendar.festivals -> culture.custom.festivals
        foundation = wv.foundation or {}
        calendar = foundation.get('calendar', {})
        festivals_value = calendar.pop('festivals', None)
        if festivals_value:
            foundation['calendar'] = calendar
            wv.foundation = foundation
            
            culture = wv.culture or {}
            custom = culture.get('custom', {})
            if not custom.get('festivals'):
                custom['festivals'] = festivals_value
                culture['custom'] = custom
                wv.culture = culture
            changed = True
        
        # 2. 重命名 society.martial -> society.jianghu
        society = wv.society or {}
        if 'martial' in society:
            martial_data = society.pop('martial')
            if 'jianghu' not in society:
                society['jianghu'] = martial_data
            wv.society = society
            changed = True
        
        # 3. 重命名 special.rules -> special.transmigration_rules
        special = wv.special or {}
        if 'rules' in special:
            rules_value = special.pop('rules')
            if 'transmigration_rules' not in special:
                special['transmigration_rules'] = rules_value
            wv.special = special
            changed = True
        
        # 4. 初始化新字段默认值
        if not wv.military:
            wv.military = {
                "forces": {"army_structure": "", "elite_units": ""},
                "weapons": {"types": "", "legendary": ""},
                "warfare": {"rules": "", "history": ""},
                "defense": {"fortifications": "", "strategic_points": ""}
            }
            changed = True
        
        if not wv.technology:
            wv.technology = {
                "level": "",
                "key_tech": "",
                "communication": "",
                "transport": "",
                "ethics": ""
            }
            changed = True
        
        if wv.factions is None:
            wv.factions = []
            changed = True
        
        if wv.locations is None:
            wv.locations = []
            changed = True
        
        if wv.relations is None:
            wv.relations = []
            changed = True
        
        if changed:
            wv.save()


def reverse_migrate_worldview_data(apps, schema_editor):
    """反向迁移：将数据恢复到旧结构"""
    WorldView = apps.get_model('worldview', 'WorldView')
    
    for wv in WorldView.objects.all():
        changed = False
        
        # 1. 将 culture.custom.festivals 移回 calendar.festivals
        culture = wv.culture or {}
        custom = culture.get('custom', {})
        festivals_value = custom.get('festivals', '')
        if festivals_value:
            foundation = wv.foundation or {}
            calendar = foundation.get('calendar', {})
            calendar['festivals'] = festivals_value
            foundation['calendar'] = calendar
            wv.foundation = foundation
            changed = True
        
        # 2. 重命名 jianghu -> martial
        society = wv.society or {}
        if 'jianghu' in society:
            jianghu_data = society.pop('jianghu')
            society['martial'] = jianghu_data
            wv.society = society
            changed = True
        
        # 3. 重命名 transmigration_rules -> rules
        special = wv.special or {}
        if 'transmigration_rules' in special:
            rules_value = special.pop('transmigration_rules')
            special['rules'] = rules_value
            wv.special = special
            changed = True
        
        if changed:
            wv.save()


class Migration(migrations.Migration):

    dependencies = [
        ('worldview', '0001_initial'),
    ]

    operations = [
        # 添加新字段
        migrations.AddField(
            model_name='worldview',
            name='military',
            field=models.JSONField(blank=True, default=dict, help_text='{"forces":{"army_structure":"","elite_units":""},"weapons":{"types":"","legendary":""},"warfare":{"rules":"","history":""},"defense":{"fortifications":"","strategic_points":""}}', verbose_name='军事体系'),
        ),
        migrations.AddField(
            model_name='worldview',
            name='technology',
            field=models.JSONField(blank=True, default=dict, help_text='{"level":"","key_tech":"","communication":"","transport":"","ethics":""}', verbose_name='科技体系'),
        ),
        migrations.AddField(
            model_name='worldview',
            name='factions',
            field=models.JSONField(blank=True, default=list, verbose_name='阵营列表'),
        ),
        migrations.AddField(
            model_name='worldview',
            name='locations',
            field=models.JSONField(blank=True, default=list, verbose_name='地点列表'),
        ),
        migrations.AddField(
            model_name='worldview',
            name='relations',
            field=models.JSONField(blank=True, default=list, verbose_name='关系列表'),
        ),
        # 更新现有字段的 help_text（反映结构变更）
        migrations.AlterField(
            model_name='worldview',
            name='foundation',
            field=models.JSONField(blank=True, default=dict, help_text='{"geography":{"continent_distribution":"","special_terrain":""},"calendar":{"era":"","days_per_year":"","seasons":""},"rules":{"natural_laws":"","boundaries":"","axioms":[]},"balance":""}', verbose_name='世界基础'),
        ),
        migrations.AlterField(
            model_name='worldview',
            name='society',
            field=models.JSONField(blank=True, default=dict, help_text='{"court":{"political_system":"","bureaucracy":""},"sect":{"levels":"","relationships":""},"jianghu":{"factions":"","alliances":""},"external":"","strata":{"social_classes":"","mobility":""},"currency":{"types":"","rules":""},"resource":""}', verbose_name='社会结构'),
        ),
        migrations.AlterField(
            model_name='worldview',
            name='special',
            field=models.JSONField(blank=True, default=dict, help_text='{"taboo":"","secret":"","fate":{"fortune_rules":"","destiny_types":""},"reincarnation":{"soul_rules":"","mechanics":""},"transmigration":"","system":"","transmigration_rules":""}', verbose_name='特殊规则'),
        ),
        # 数据迁移
        migrations.RunPython(migrate_worldview_data, reverse_migrate_worldview_data),
    ]
