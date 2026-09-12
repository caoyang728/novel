"""
Volume services - 卷业务逻辑封装
"""
import json
import re
from loguru import logger
from django.db import transaction
from django.db.models import Count, Min

from apps.volume.models import Volume
from apps.volume.serializers import VolumeSerializer


class VolumeService:
    """卷业务逻辑服务"""

    @staticmethod
    def volume_to_dict(vol):
        """将 Volume 模型转换为字典"""
        return {
            'id': vol.id,
            'volume_number': vol.volume_number,
            'title': vol.title,
            'summary': vol.summary,
            'content': vol.content,
            'chapter_count': vol.chapter_count,
            'is_locked': vol.is_locked,
            'updated_at': vol.updated_at.strftime('%Y-%m-%d %H:%M') if vol.updated_at else '',
        }

    @staticmethod
    def create_volume(project, outline, version, vol_data):
        """从字典数据创建 Volume 记录"""
        serializer = VolumeSerializer(data=vol_data, context={
            'project': project,
            'outline': outline,
            'version': version,
        })
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    @staticmethod
    def get_next_version(project):
        """获取项目下一个版本号"""
        latest = Volume.objects.filter(project=project).order_by('-version').first()
        return (latest.version + 1) if latest else 1

    @staticmethod
    def get_version_volumes(project, version):
        """获取指定版本的所有卷"""
        return Volume.objects.filter(project=project, version=version).order_by('volume_number')

    @staticmethod
    def get_volumes_list(project, version):
        """获取指定版本的卷数据列表"""
        return [VolumeService.volume_to_dict(vol) for vol in VolumeService.get_version_volumes(project, version)]

    @staticmethod
    def is_version_locked(project, version):
        """检查版本是否整体锁定（所有卷都锁定）"""
        volumes = VolumeService.get_version_volumes(project, version)
        return volumes.exists() and all(v.is_locked for v in volumes)

    @staticmethod
    def get_version_groups(project):
        """按 version 分组获取版本统计"""
        return (
            Volume.objects.filter(project=project)
            .values('version')
            .annotate(
                volume_count=Count('id'),
                outline_id=Min('outline_id'),
                created_at=Min('created_at'),
            )
            .order_by('-version')
        )

    @staticmethod
    def parse_volumes_json(volumes_json):
        """解析并校验卷数据 JSON"""
        if isinstance(volumes_json, list):
            volumes_data = volumes_json
        else:
            try:
                volumes_data = json.loads(volumes_json or '[]')
            except json.JSONDecodeError:
                return None, '卷数据格式错误'
        if not volumes_data:
            return None, '卷数据为空'
        return volumes_data, None

    @staticmethod
    def parse_analysis_json(text):
        """从 LLM 输出中解析大纲分析 JSON"""
        try:
            plan_data = json.loads(text)
            return plan_data.get('volumes', [])
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    plan_data = json.loads(json_match.group())
                    return plan_data.get('volumes', [])
                except json.JSONDecodeError:
                    pass
        return []

    @staticmethod
    def parse_volumes_from_llm_output(vol_buffer):
        """从 LLM 输出中解析卷数据（支持纯 JSON 和 JSON 列表）"""
        parsed_volumes = []

        try:
            result = json.loads(vol_buffer.strip())
            if isinstance(result, list):
                parsed_volumes = result
            elif 'volumes' in result:
                parsed_volumes = result['volumes']
            else:
                parsed_volumes = [result]
        except json.JSONDecodeError:
            json_match = re.search(r'\{[\s\S]*\}', vol_buffer)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    if isinstance(result, list):
                        parsed_volumes = result
                    elif 'volumes' in result:
                        parsed_volumes = result['volumes']
                    else:
                        parsed_volumes = [result]
                except json.JSONDecodeError:
                    logger.error(f"卷JSON解析失败: {vol_buffer[:200]}")

        return parsed_volumes

    @staticmethod
    def parse_chat_json(text):
        """从 LLM 输出中提取 JSON 格式的聊天回复
        返回 {'reply': str, 'patch_list': list, 'target_volume_number': int|None}
        """
        try:
            data = json.loads(text.strip())
            return {
                'reply': data.get('reply', ''),
                'patch_list': data.get('patch_list', []),
                'target_volume_number': data.get('target_volume_number'),
            }
        except json.JSONDecodeError:
            # 降级：尝试从文本中提取 JSON
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                    return {
                        'reply': data.get('reply', ''),
                        'patch_list': data.get('patch_list', []),
                        'target_volume_number': data.get('target_volume_number'),
                    }
                except json.JSONDecodeError:
                    pass
            logger.warning(f"卷对话JSON解析失败: {text[:200]}")
            return {'reply': text, 'patch_list': [], 'target_volume_number': None}

    @staticmethod
    def apply_content_patches(original_content, patch_list):
        """将 patch_list（old_snippet/new_snippet）应用到内容，返回结果 dict

        Args:
            original_content: 原始 Markdown 内容
            patch_list: 补丁列表，每项包含 old_snippet/new_snippet

        Returns:
            {'new_content': str, 'edits_applied': int, 'edits_total': int, 'edits_summary': list}
        """
        if not patch_list:
            return {
                'new_content': original_content,
                'edits_applied': 0,
                'edits_total': 0,
                'edits_summary': [],
            }

        result_text = original_content
        applied_count = 0
        edits_summary = []

        for patch in patch_list:
            old_snippet = patch.get('old_snippet', '')
            new_snippet = patch.get('new_snippet', '')

            if not old_snippet:
                # 新增内容（文档为空或末尾追加）
                if not result_text.strip():
                    result_text = new_snippet
                else:
                    result_text = result_text.rstrip('\n') + '\n\n' + new_snippet
                applied_count += 1
                edits_summary.append({'type': 'add', 'preview': new_snippet[:80]})
                continue

            count = result_text.count(old_snippet)
            if count == 0:
                logger.warning(f"[VOLUME] Patch未匹配: old_snippet={old_snippet[:60]}...")
                edits_summary.append({'type': 'failed', 'preview': old_snippet[:60]})
                continue
            if count > 1:
                logger.warning(f"[VOLUME] Patch多处匹配({count}次): old_snippet={old_snippet[:60]}...")
                edits_summary.append({'type': 'ambiguous', 'preview': old_snippet[:60]})
                continue

            result_text = result_text.replace(old_snippet, new_snippet, 1)
            applied_count += 1
            edits_summary.append({'type': 'replace', 'preview': old_snippet[:60]})

        return {
            'new_content': result_text,
            'edits_applied': applied_count,
            'edits_total': len(patch_list),
            'edits_summary': edits_summary,
        }

    @staticmethod
    def validate_structure(volumes):
        """
        Phase 3 结构校验
        返回 {'valid': bool, 'errors': list, 'warnings': list}
        """
        errors = []
        warnings = []

        if not volumes:
            errors.append('卷列表为空')
            return {'valid': False, 'errors': errors, 'warnings': warnings}

        # 检查必填字段
        for vol in volumes:
            vol_num = vol.get('volume_number', '?')
            if not vol.get('title'):
                errors.append(f'第{vol_num}卷缺少标题')
            if not vol.get('chapter_count') or vol.get('chapter_count', 0) <= 0:
                errors.append(f'第{vol_num}卷章节数无效')
            if not vol.get('content') and not vol.get('summary'):
                warnings.append(f'第{vol_num}卷缺少内容和摘要')

        # 卷标题格式检查（2-8汉字，无数字/章节号）
        for vol in volumes:
            title = vol.get('title', '')
            if title:
                if len(title) < 2 or len(title) > 8:
                    warnings.append(f'第{vol.get("volume_number")}卷标题长度异常：{title}（{len(title)}字）')
                if re.search(r'\d', title):
                    errors.append(f'第{vol.get("volume_number")}卷标题含数字：{title}')
                if re.search(r'[章回节]', title):
                    errors.append(f'第{vol.get("volume_number")}卷标题含"章/回/节"字：{title}')

        # 章节编号连续性检查
        sorted_volumes = sorted(volumes, key=lambda v: v.get('volume_number', 0))
        expected_start = 1
        for vol in sorted_volumes:
            vol_num = vol.get('volume_number', 0)
            chapter_count = vol.get('chapter_count', 0)
            description = vol.get('description', '') or vol.get('summary', '')

            # 从 description 中提取章节范围声明
            range_match = re.search(r'第(\d+)章.*?第(\d+)章', description)
            if range_match:
                start_ch = int(range_match.group(1))
                end_ch = int(range_match.group(2))
                if start_ch != expected_start:
                    errors.append(
                        f'第{vol_num}卷章节范围起始号不连续：'
                        f'期望第{expected_start}章，实际第{start_ch}章'
                    )
                expected_start = end_ch + 1
            elif chapter_count > 0:
                # 没有范围声明时，用 chapter_count 推算
                expected_start += chapter_count

        return {'valid': len(errors) == 0, 'errors': errors, 'warnings': warnings}

    @staticmethod
    def evaluate_quality(volumes, validation_result):
        """
        Phase 3 质量评分
        返回 {'score': int, 'dimensions': dict, 'suggestions': list}
        """
        score = 100
        dimensions = {}
        suggestions = []

        # 1. 结构完整性（40分）
        if not validation_result['valid']:
            error_penalty = min(40, len(validation_result['errors']) * 10)
            score -= error_penalty
            dimensions['structure'] = 40 - error_penalty
            suggestions.append(f'结构问题：修复 {len(validation_result["errors"])} 个错误')
        else:
            dimensions['structure'] = 40

        # 2. 内容丰富度（30分）
        empty_count = sum(1 for v in volumes if not v.get('content'))
        if empty_count > 0:
            penalty = min(30, empty_count * 10)
            score -= penalty
            dimensions['richness'] = 30 - penalty
            suggestions.append(f'内容缺失：{empty_count} 卷无大纲内容')
        else:
            # 检查内容长度
            short_count = sum(1 for v in volumes if len(v.get('content', '')) < 500)
            if short_count > 0:
                penalty = min(15, short_count * 5)
                score -= penalty
                dimensions['richness'] = 30 - penalty
                suggestions.append(f'内容偏短：{short_count} 卷大纲不足500字')
            else:
                dimensions['richness'] = 30

        # 3. 章节编号正确性（20分）
        if validation_result['errors']:
            chapter_errors = [e for e in validation_result['errors'] if '章节' in e or '编号' in e]
            if chapter_errors:
                penalty = min(20, len(chapter_errors) * 10)
                score -= penalty
                dimensions['chapter_numbering'] = 20 - penalty
                suggestions.append(f'章节编号：修复 {len(chapter_errors)} 个编号问题')
            else:
                dimensions['chapter_numbering'] = 20
        else:
            dimensions['chapter_numbering'] = 20

        # 4. 格式规范性（10分）
        format_issues = []
        for v in volumes:
            if v.get('title') and (len(v['title']) < 2 or len(v['title']) > 8):
                format_issues.append(f'第{v["volume_number"]}卷标题长度异常')
            if v.get('title') and re.search(r'\d', v['title']):
                format_issues.append(f'第{v["volume_number"]}卷标题含数字')
        if format_issues:
            penalty = min(10, len(format_issues) * 3)
            score -= penalty
            dimensions['format'] = 10 - penalty
            suggestions.append(f'格式问题：{len(format_issues)} 个')
        else:
            dimensions['format'] = 10

        return {
            'score': max(0, score),
            'dimensions': dimensions,
            'suggestions': suggestions,
        }

    @staticmethod
    def save_version_overwrite(project, outline, version, volumes_data):
        """覆盖保存卷版本（删除未锁定卷，插入新数据，保留锁定卷）"""
        if VolumeService.is_version_locked(project, version):
            return False, '该版本已锁定，无法修改。请使用"另存新版"。'

        locked_volumes = {
            vol.volume_number: vol
            for vol in VolumeService.get_version_volumes(project, version).filter(is_locked=True)
        }

        # 检查锁定卷是否被删除
        if locked_volumes:
            submitted_numbers = {v.get('volume_number') for v in volumes_data if v.get('volume_number')}
            missing_locked = set(locked_volumes.keys()) - submitted_numbers
            if missing_locked:
                locked_titles = [locked_volumes[n].title for n in sorted(missing_locked)]
                return False, f'已锁定的卷不可删除：{", ".join(locked_titles)}'

        with transaction.atomic():
            VolumeService.get_version_volumes(project, version).exclude(is_locked=True).delete()
            for vol_data in volumes_data:
                vol_number = vol_data.get('volume_number')
                if vol_number and vol_number in locked_volumes:
                    locked_vol = locked_volumes[vol_number]
                    vol_data = {
                        'volume_number': locked_vol.volume_number, 'title': locked_vol.title,
                        'summary': locked_vol.summary, 'content': locked_vol.content,
                        'chapter_count': locked_vol.chapter_count, 'is_locked': True,
                    }
                VolumeService.create_volume(project, outline, version, vol_data)

        return True, None

    @staticmethod
    def toggle_version_lock(project, version):
        """切换版本锁定状态：全部锁定→全部解锁，否则→全部锁定"""
        volumes = VolumeService.get_version_volumes(project, version)
        if not volumes.exists():
            return None
        all_locked = all(v.is_locked for v in volumes)
        new_state = not all_locked
        volumes.update(is_locked=new_state)
        return new_state
