"""
Volume views - 卷相关视图
"""
import json
import re
import time
from loguru import logger
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from langchain_core.prompts import ChatPromptTemplate

from apps.project.models import ProjectList
from apps.outline.models import OutlineVersion
from apps.volume.models import VolumeVersion, VolumeList
from apps.volume.serializers import VolumeListSerializer
from apps.characters.models import Character
from apps.worldview.models import WorldView
from apps.timeline.models import TimelineEvent
from apps.ai.llm import get_llm
from apps.volume.prompts import (
    VOLUME_ANALYSIS_SYSTEM_PROMPT, VOLUME_ANALYSIS_USER_PROMPT,
    VOLUME_GENERATION_SYSTEM_PROMPT, VOLUME_GENERATION_USER_PROMPT,
    VOLUME_OPTIMIZE_SYSTEM_PROMPT, VOLUME_OPTIMIZE_USER_PROMPT,
    VOLUME_SINGLE_OPTIMIZE_SYSTEM_PROMPT, VOLUME_SINGLE_OPTIMIZE_USER_PROMPT,
    VOLUME_CHAT_SYSTEM_PROMPT, VOLUME_CHAT_USER_PROMPT,
    VOLUME_CHAT_MERGE_SYSTEM_PROMPT, VOLUME_CHAT_MERGE_USER_PROMPT,
)

VOLUME_START_MARKER = '════VOLUME_START════'
CHAPTER_START_MARKER = '════CHAPTER_START════'
from apps.user.models import TokenUsageLog
from novel_agent.authentication import JWTAuthentication


# ========== 基础视图类 ==========

class BaseVolumeAPIView(APIView):
    """卷API基础类 - 封装鉴权、项目查询、上下文格式化和通用工具方法"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    # ---------- 通用工具方法 ----------

    @staticmethod
    def get_chunk_text(chunk):
        """从 LangChain 的 stream chunk 中提取纯文本内容"""
        if hasattr(chunk, 'content'):
            content = chunk.content
            if isinstance(content, list):
                return ''.join(block.get('text', str(block)) if isinstance(block, dict) else str(block) for block in content)
            elif isinstance(content, str):
                return content
            else:
                return str(content)
        return str(chunk)

    @staticmethod
    def volume_to_dict(vol):
        """将 VolumeList 模型转换为字典"""
        return {
            'id': vol.id,
            'volume_number': vol.volume_number,
            'title': vol.title,
            'summary': vol.summary,
            'content': vol.content,
            'chapter_count': vol.chapter_count,
            'chapters': vol.chapters,
            'is_locked': vol.is_locked,
            'updated_at': vol.updated_at.strftime('%Y-%m-%d %H:%M') if vol.updated_at else '',
        }

    @staticmethod
    def create_volume(volume_version, vol_data):
        """从字典数据创建 VolumeList 记录"""
        serializer = VolumeListSerializer(data=vol_data, context={'volume_version': volume_version})
        serializer.is_valid(raise_exception=True)
        return serializer.save()

    @staticmethod
    def create_new_version(project, outline_version):
        """创建新的卷版本"""
        latest_version = project.volume_versions.order_by('-version_number').first()
        new_version_number = latest_version.version_number + 1 if latest_version else 1
        return VolumeVersion.objects.create(
            project=project,
            outline_version=outline_version,
            version_number=new_version_number
        )

    @staticmethod
    def sse_event(event_type, data=None, **kwargs):
        """格式化 SSE 事件"""
        payload = {'type': event_type}
        if data:
            payload.update(data)
        payload.update(kwargs)
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @staticmethod
    def sse_response(generator_func):
        """创建 SSE StreamingHttpResponse"""
        response = StreamingHttpResponse(generator_func(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

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
        """从 LLM 输出中解析卷数据（支持标记格式和纯 JSON）"""
        parsed_volumes = []
        # 先尝试 VOLUME_START/CHAPTER_START 标记格式
        temp_buffer = vol_buffer
        while True:
            start_idx = temp_buffer.find(VOLUME_START_MARKER)
            if start_idx == -1:
                break
            end_idx = temp_buffer.find(CHAPTER_START_MARKER, start_idx + len(VOLUME_START_MARKER))
            if end_idx == -1:
                break
            json_start = start_idx + len(VOLUME_START_MARKER)
            volume_str = temp_buffer[json_start:end_idx].strip()
            temp_buffer = temp_buffer[end_idx + len(CHAPTER_START_MARKER):]
            try:
                parsed_volumes.append(json.loads(volume_str))
            except json.JSONDecodeError:
                logger.error(f"优化卷解析失败: {volume_str[:200]}")

        # 如果没有标记格式，尝试直接解析 JSON
        if not parsed_volumes:
            try:
                result = json.loads(vol_buffer.strip())
                if 'volumes' in result:
                    parsed_volumes = result['volumes']
                else:
                    parsed_volumes = [result]
            except json.JSONDecodeError:
                json_match = re.search(r'\{[\s\S]*\}', vol_buffer)
                if json_match:
                    try:
                        result = json.loads(json_match.group())
                        if 'volumes' in result:
                            parsed_volumes = result['volumes']
                        else:
                            parsed_volumes = [result]
                    except json.JSONDecodeError:
                        logger.error(f"优化卷JSON解析失败: {vol_buffer[:200]}")

        return parsed_volumes

    # ---------- 请求与查询方法 ----------

    def call_llm_with_retry(self, chain, input_vars, stream=False, user=None, project=None):
        """LCEL模式调用LLM，支持重试"""
        from django.conf import settings

        max_retries = settings.LLM_RETRY
        retry_interval = settings.LLM_RETRY_INTERVAL

        for retry_count in range(max_retries):
            try:
                if stream:
                    def gen():
                        for chunk in chain.stream(input_vars):
                            yield self.get_chunk_text(chunk)
                    return gen()
                else:
                    result = chain.invoke(input_vars)
                    # 记录 token 使用
                    if user and hasattr(result, 'usage_metadata') and result.usage_metadata:
                        try:
                            TokenUsageLog.objects.create(
                                user=user,
                                project=project,
                                model_name='',
                                prompt_tokens=result.usage_metadata.get('input_tokens', 0),
                                completion_tokens=result.usage_metadata.get('output_tokens', 0),
                                total_tokens=result.usage_metadata.get('total_tokens', 0),
                            )
                        except Exception as e:
                            logger.error(f"记录Token使用失败: {e}")
                    if hasattr(result, 'content'):
                        return result.content
                    return str(result)
            except Exception as e:
                error_msg = str(e)
                logger.error(f"LLM调用失败: {error_msg}, 重试 {retry_count + 1}/{max_retries}")
                if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                    retry_interval *= 2
                if retry_count < max_retries - 1:
                    time.sleep(retry_interval)

        raise Exception(f"LLM调用失败，已重试 {max_retries} 次")

    def get_project(self, request, pk=None):
        """获取项目，如果不存在则抛出404异常"""
        project_id = pk or self._get_param(request, 'project_id')
        if not project_id:
            return None, JsonResponse({'success': False, 'message': '缺少project_id'}, status=400)
        try:
            project = ProjectList.objects.get(pk=project_id, user=request.user)
            return project, None
        except ProjectList.DoesNotExist:
            return None, JsonResponse({'success': False, 'message': '项目不存在'}, status=404)

    def _get_param(self, request, key):
        """统一从 request.data 或 request.POST 获取参数"""
        if hasattr(request, 'data') and isinstance(request.data, dict):
            return request.data.get(key)
        return request.POST.get(key) if hasattr(request, 'POST') else None

    def get_volume_version(self, version_id, project=None):
        """获取卷版本，支持按项目过滤"""
        if project:
            return get_object_or_404(VolumeVersion, pk=version_id, project=project)
        return get_object_or_404(VolumeVersion, pk=version_id, project__user=self.request.user)

    def get_volumes_list(self, volume_version):
        """获取卷版本的卷数据列表"""
        return [self.volume_to_dict(vol) for vol in volume_version.volumes.all()]

    def format_worldview_context(self, project):
        """格式化项目世界观设定为文本"""
        try:
            worldview = WorldView.objects.filter(project=project).first()
            if not worldview:
                return '（暂无世界观设定）'

            parts = []
            # 基础设定
            setting = worldview.setting or {}
            identity = setting.get('identity', {})
            if isinstance(identity, dict):
                world_name = identity.get('name', '') or identity.get('world_name', '')
                genre = identity.get('genre', '')
                if world_name:
                    parts.append(f'世界名称：{world_name}')
                if genre:
                    parts.append(f'题材类型：{genre}')
            elif identity:
                parts.append(f'世界身份：{identity}')

            position = setting.get('position', {})
            if isinstance(position, dict):
                tone = position.get('tone', '')
                if tone:
                    parts.append(f'整体调性：{tone}')
            elif position:
                parts.append(f'世界定位：{position}')

            overview = setting.get('overview', '')
            if overview:
                parts.append(f'世界简介：{overview}')
            conflict = setting.get('conflict', '')
            if conflict:
                parts.append(f'核心冲突：{conflict}')

            # 世界基础
            foundation = worldview.foundation or {}
            geography = foundation.get('geography', {})
            if isinstance(geography, dict):
                geo_content = geography.get('continents', '') or geography.get('continent_distribution', '') or geography.get('terrain', '')
                if geo_content:
                    parts.append(f'地理：{geo_content}')
            elif geography:
                parts.append(f'地理：{geography}')

            calendar = foundation.get('calendar', {})
            if isinstance(calendar, dict):
                era = calendar.get('era', '')
                if era:
                    parts.append(f'纪元：{era}')

            rules = foundation.get('rules', {})
            if isinstance(rules, dict):
                axioms = rules.get('axioms', [])
                if axioms:
                    rules_text = '；'.join([r.get('name', str(r)) if isinstance(r, dict) else str(r) for r in axioms[:5]])
                    parts.append(f'核心规则：{rules_text}')
            elif rules:
                parts.append(f'核心规则：{rules}')

            # 力量体系
            power = worldview.power or {}
            energy = power.get('energy', {})
            if isinstance(energy, dict):
                energy_type = energy.get('type', '') or energy.get('types', '')
                if energy_type:
                    parts.append(f'力量类型：{energy_type}')
            level = power.get('level', '')
            if level:
                parts.append(f'等级体系：{level}')

            # 社会结构
            society = worldview.society or {}
            sect = society.get('sect', {})
            if isinstance(sect, dict):
                sect_content = sect.get('hierarchy', '') or sect.get('levels', '') or sect.get('description', '')
                if sect_content:
                    parts.append(f'宗门/势力：{sect_content}')
            court = society.get('court', {})
            if isinstance(court, dict):
                court_content = court.get('system', '') or court.get('political_system', '') or court.get('description', '')
                if court_content:
                    parts.append(f'政体：{court_content}')

            # 历史
            history = worldview.history or {}
            for key, label in [('ancient', '远古历史'), ('modern', '近代历史'), ('crisis', '重大危机'), ('destiny', '命运走向')]:
                val = history.get(key, '')
                if val:
                    parts.append(f'{label}：{val}')

            # 特殊规则
            special = worldview.special or {}
            for key, label in [('taboo', '禁忌'), ('secret', '秘密'), ('fate', '命运规则'), ('reincarnation', '转世机制')]:
                val = special.get(key, '')
                if isinstance(val, dict):
                    val = val.get('description', '') or val.get('type', '')
                if val:
                    parts.append(f'{label}：{val}')

            if not parts:
                return '（暂无世界观设定）'
            return '\n'.join(parts)
        except Exception as e:
            logger.error(f"格式化世界观上下文失败: {e}")
            return '（暂无世界观设定）'

    def format_characters_context(self, project):
        """格式化项目人物清单为文本"""
        try:
            characters = Character.objects.filter(project=project, is_deleted=False)
            if not characters.exists():
                return '（暂无人物设定）'

            parts = []
            for char in characters:
                char_info = f'【{char.name}】'
                details = []
                if char.role_type:
                    details.append(f'角色：{char.role_type}')
                if char.gender and char.gender != '未知':
                    details.append(f'性别：{char.gender}')
                if char.age:
                    details.append(f'年龄：{char.age}')
                if char.identity:
                    details.append(f'身份：{char.identity}')
                if char.faction:
                    details.append(f'阵营：{char.faction}')
                if char.personality:
                    details.append(f'性格：{char.personality}')
                if char.backstory:
                    details.append(f'背景：{char.backstory}')
                if char.motivation:
                    details.append(f'动机：{char.motivation}')
                if char.abilities:
                    details.append(f'能力：{char.abilities}')
                if char.development:
                    details.append(f'成长：{char.development}')
                if char.relationships:
                    rel_list = []
                    for rel in char.relationships:
                        if isinstance(rel, dict):
                            target = rel.get('targetName', '')
                            rel_type = rel.get('relationshipType', '')
                            if target and rel_type:
                                rel_list.append(f'{target}({rel_type})')
                    if rel_list:
                        details.append(f'关系：{", ".join(rel_list)}')
                if details:
                    char_info += ' ' + '；'.join(details)
                parts.append(char_info)

            return '\n'.join(parts)
        except Exception as e:
            logger.error(f"格式化人物上下文失败: {e}")
            return '（暂无人物设定）'

    def format_timeline_context(self, project):
        """格式化项目时间线为文本"""
        try:
            events = TimelineEvent.objects.filter(project=project, is_active=True).order_by('start_year', 'start_month', 'end_year', 'end_month')
            if not events.exists():
                return '（暂无时间线）'

            parts = []
            for event in events:
                time_range = event.format_time_range()
                event_text = f'【{event.title}】{time_range}'
                if event.description:
                    event_text += f'：{event.description}'
                parts.append(event_text)

            return '\n'.join(parts)
        except Exception as e:
            logger.error(f"格式化时间线上下文失败: {e}")
            return '（暂无时间线）'

    def get_project_context(self, project):
        """获取项目的世界观、人物、时间线上下文"""
        worldview_context = self.format_worldview_context(project)
        characters_context = self.format_characters_context(project)
        timeline_context = self.format_timeline_context(project)
        return worldview_context, characters_context, timeline_context


# ========== 卷版本管理 ==========

class VolumeVersionListView(BaseVolumeAPIView):
    """
    卷版本列表
    GET  - 获取版本列表
    POST - 生成新版本
    """

    def get(self, request):
        """获取项目的卷版本列表"""
        project_id = request.query_params.get('project_id') or request.GET.get('project_id')
        if not project_id:
            return JsonResponse({'success': False, 'message': '缺少project_id'}, status=400)
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        versions = project.volume_versions.filter(is_deleted=False).order_by('-created_at')

        versions_data = []
        for v in versions:
            versions_data.append({
                'id': v.id,
                'version_number': v.version_number,
                'is_finalized': v.is_finalized,
                'created_at': v.created_at.strftime('%Y-%m-%d %H:%M'),
                'outline_version_number': v.outline_version.version_number,
                'volume_count': v.volumes.count()
            })

        return JsonResponse({'success': True, 'versions': versions_data})

    def post(self, request):
        """生成卷结构（先分析大纲→逐卷流式生成，含重试策略）"""
        project_id = self._get_param(request, 'project_id')
        outline_version_id = self._get_param(request, 'outline_version_id')

        if not outline_version_id:
            return JsonResponse({'success': False, 'message': '缺少outline_version_id'}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project=project)

        MAX_RETRIES = 2

        def generate():
            volume_version = None
            volume_count = 0
            total_chars = 0

            # 获取项目上下文（世界观、人物、时间线）
            worldview_context, characters_context, timeline_context = self.get_project_context(project)

            try:
                # ===== 第一阶段：分析大纲，提取卷结构规划 =====
                yield self.sse_event('progress', {'message': '正在分析大纲...'})

                llm = get_llm(user=request.user, scene="volume_generate")
                analysis_prompt = ChatPromptTemplate.from_messages([
                    ("system", VOLUME_ANALYSIS_SYSTEM_PROMPT),
                    ("human", VOLUME_ANALYSIS_USER_PROMPT),
                ])
                analysis_chain = analysis_prompt | llm

                analysis_result = analysis_chain.invoke({"outline": outline_version.content})
                analysis_content = self.get_chunk_text(analysis_result)

                # 解析分析结果
                volume_plan = self.parse_analysis_json(analysis_content)

                if not volume_plan:
                    yield self.sse_event('error', {'message': '无法从大纲中解析出卷结构规划'})
                    return

                total_volumes = len(volume_plan)
                total_chapters = sum(v.get('chapter_count', 0) for v in volume_plan)
                logger.info(f"大纲分析完成: 共{total_volumes}卷, 总计{total_chapters}章")
                yield self.sse_event('analysis', {
                    'total_volumes': total_volumes,
                    'total_chapters': total_chapters,
                    'volume_plan': volume_plan
                })

                # ===== 第二阶段：逐卷生成大纲（含重试） =====
                generate_prompt = ChatPromptTemplate.from_messages([
                    ("system", VOLUME_GENERATION_SYSTEM_PROMPT),
                    ("human", VOLUME_GENERATION_USER_PROMPT),
                ])
                generate_chain = generate_prompt | llm

                for vol_plan in volume_plan:
                    vol_num = vol_plan.get('volume_number', volume_count + 1)
                    vol_title = vol_plan.get('title', f'第{vol_num}卷')
                    chapter_count = vol_plan.get('chapter_count', 10)
                    description = vol_plan.get('description', '')

                    yield self.sse_event('progress', {'message': f'正在生成第 {vol_num}/{total_volumes} 卷「{vol_title}」...'})

                    # 带重试的生成
                    vol_buffer = ""
                    for attempt in range(1, MAX_RETRIES + 1):
                        vol_buffer = ""
                        input_vars = {
                            "outline": outline_version.content,
                            "volume_number": vol_num,
                            "title": vol_title,
                            "chapter_count": chapter_count,
                            "description": description,
                            "worldview": worldview_context,
                            "characters": characters_context,
                            "timeline": timeline_context,
                        }

                        try:
                            for chunk in generate_chain.stream(input_vars):
                                chunk_content = self.get_chunk_text(chunk)
                                vol_buffer += chunk_content
                        except Exception as stream_err:
                            logger.warning(f"第{vol_num}卷生成流异常(第{attempt}次): {stream_err}")
                            if attempt < MAX_RETRIES:
                                yield self.sse_event('progress', {'message': f'第 {vol_num} 卷生成异常，正在重试({attempt}/{MAX_RETRIES})...'})
                                continue
                            else:
                                break

                        if vol_buffer.strip():
                            break  # 成功

                        if attempt < MAX_RETRIES:
                            logger.warning(f"第{vol_num}卷生成内容为空(第{attempt}次)")
                            yield self.sse_event('progress', {'message': f'第 {vol_num} 卷生成内容为空，正在重试({attempt}/{MAX_RETRIES})...'})
                        else:
                            logger.error(f"第{vol_num}卷重试{MAX_RETRIES}次后仍失败")

                    # 无论成功与否，都创建卷记录
                    volume_count += 1
                    total_chars += len(vol_buffer) if vol_buffer else 0

                    # 确保版本已创建（首卷生成失败时也需要版本记录）
                    if volume_version is None:
                        volume_version = self.create_new_version(project, outline_version)

                    if vol_buffer.strip():
                        # 生成成功
                        self.create_volume(volume_version, {
                            'volume_number': vol_num,
                            'title': vol_title,
                            'summary': description,
                            'chapter_count': chapter_count,
                            'content': vol_buffer,
                            'chapters': []
                        })
                        logger.info(f"生成卷: 第{volume_count}卷 - {vol_title}, 内容长度: {len(vol_buffer)}")

                        yield self.sse_event('volume', {
                            'volume': {'volume_number': vol_num, 'title': vol_title, 'content': vol_buffer},
                            'volume_count': volume_count,
                            'total_chars': total_chars,
                            'total_volumes': total_volumes
                        })
                    else:
                        # 生成失败，创建占位卷
                        failed_vol = self.create_volume(volume_version, {
                            'volume_number': vol_num,
                            'title': vol_title,
                            'summary': description,
                            'chapter_count': chapter_count,
                            'content': '',
                            'chapters': []
                        })
                        logger.warning(f"第{vol_num}卷生成失败，已创建占位卷")

                        yield self.sse_event('volume_failed', {
                            'volume_id': failed_vol.pk,
                            'volume_number': vol_num,
                            'volume_count': volume_count,
                            'total_volumes': total_volumes,
                            'message': f'「{vol_title}」生成失败，已创建占位'
                        })

                # 完成
                if volume_version is None:
                    yield self.sse_event('error', {'message': '未生成任何卷'})
                    return

                logger.info(f"卷生成完成，共{volume_count}卷")
                yield self.sse_event('complete', {
                    'version_id': volume_version.pk,
                    'version_number': volume_version.version_number,
                    'volume_count': volume_count
                })

            except Exception as e:
                logger.error(f"生成卷失败: {e}")
                yield self.sse_event('error', {'message': '生成卷结构失败，请重试'})

        return self.sse_response(generate)


class VolumeVersionDetailView(BaseVolumeAPIView):
    """
    单个卷版本
    GET    - 获取版本详情
    PUT    - 保存版本（覆盖当前版本的卷数据）
    DELETE - 删除版本（物理删除）
    """

    def get(self, request, version_id):
        """获取单个卷版本详情"""
        volume_version = self.get_volume_version(version_id)

        return JsonResponse({
            'success': True,
            'volumes': self.get_volumes_list(volume_version),
            'outline_version_id': volume_version.outline_version.pk,
            'is_finalized': volume_version.is_finalized
        })

    def put(self, request, version_id):
        """保存卷版本（覆盖当前版本的卷数据）"""
        project_id = self._get_param(request, 'project_id')
        outline_version_id = self._get_param(request, 'outline_version_id')
        volumes_json = self._get_param(request, 'volumes') or '[]'

        if not outline_version_id:
            return JsonResponse({'success': False, 'message': '缺少outline_version_id'}, status=400)

        volumes_data, err_msg = self.parse_volumes_json(volumes_json)
        if err_msg:
            return JsonResponse({'success': False, 'message': err_msg}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project=project)

        volume_version = get_object_or_404(VolumeVersion, pk=version_id, project=project)
        if volume_version.is_finalized:
            return JsonResponse({
                'success': False,
                'message': '该版本已锁定，无法修改。请使用"另存新版"。'
            }, status=400)

        # 校验已锁定卷：已锁定卷不能被删除或修改
        locked_volumes = {vol.volume_number: vol for vol in volume_version.volumes.filter(is_locked=True)}
        if locked_volumes:
            submitted_numbers = {v.get('volume_number') for v in volumes_data if v.get('volume_number')}
            missing_locked = set(locked_volumes.keys()) - submitted_numbers
            if missing_locked:
                locked_titles = [locked_volumes[n].title for n in sorted(missing_locked)]
                return JsonResponse({
                    'success': False,
                    'message': f'已锁定的卷不可删除：{", ".join(locked_titles)}'
                }, status=400)

        from django.db import transaction

        with transaction.atomic():
            volume_version.volumes.all().delete()
            volume_version.outline_version = outline_version
            volume_version.save(update_fields=['outline_version'])

            for vol_data in volumes_data:
                # 已锁定卷保留原数据
                vol_number = vol_data.get('volume_number')
                if vol_number and vol_number in locked_volumes:
                    locked_vol = locked_volumes[vol_number]
                    vol_data = {
                        'volume_number': locked_vol.volume_number,
                        'title': locked_vol.title,
                        'summary': locked_vol.summary,
                        'content': locked_vol.content,
                        'chapter_count': locked_vol.chapter_count,
                        'chapters': locked_vol.chapters,
                        'is_locked': True,
                    }
                self.create_volume(volume_version, vol_data)

        return JsonResponse({
            'success': True,
            'version_id': volume_version.pk,
            'version_number': volume_version.version_number
        })

    def delete(self, request, version_id):
        """删除卷版本（物理删除）"""
        volume_version = self.get_volume_version(version_id)

        if volume_version.is_finalized:
            return JsonResponse({
                'success': False,
                'message': '该版本已锁定，无法删除。请先解锁后再删除。'
            }, status=400)

        # 物理删除：先删关联的卷，再删版本
        volume_version.volumes.all().delete()
        volume_version.delete()

        return JsonResponse({'success': True})


class VolumeVersionSaveView(BaseVolumeAPIView):
    """另存为新版本"""

    def post(self, request, version_id):
        """另存为新版本（基于当前版本数据创建新版本）"""
        project_id = self._get_param(request, 'project_id')
        outline_version_id = self._get_param(request, 'outline_version_id')
        volumes_json = self._get_param(request, 'volumes') or '[]'

        if not outline_version_id:
            return JsonResponse({'success': False, 'message': '缺少outline_version_id'}, status=400)

        volumes_data, err_msg = self.parse_volumes_json(volumes_json)
        if err_msg:
            return JsonResponse({'success': False, 'message': err_msg}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err
        outline_version = get_object_or_404(OutlineVersion, pk=outline_version_id, project=project)

        # 获取源版本
        source_version = get_object_or_404(VolumeVersion, pk=version_id, project=project)

        # 创建新版本
        new_version = self.create_new_version(project, outline_version)

        for vol_data in volumes_data:
            self.create_volume(new_version, vol_data)

        return JsonResponse({
            'success': True,
            'version_id': new_version.pk,
            'version_number': new_version.version_number
        })


class VolumeVersionFinalizeView(BaseVolumeAPIView):
    """锁定/解锁卷版本"""

    def post(self, request, version_id):
        volume_version = self.get_volume_version(version_id)

        volume_version.is_finalized = not volume_version.is_finalized
        volume_version.save()

        return JsonResponse({'success': True, 'is_finalized': volume_version.is_finalized})


class VolumeVersionOptimizeView(BaseVolumeAPIView):
    """优化卷结构（逐卷流式生成）"""

    def post(self, request, version_id):
        project_id = self._get_param(request, 'project_id')
        user_feedback = self._get_param(request, 'user_feedback')

        if not user_feedback:
            return JsonResponse({'success': False, 'message': '缺少调整意见'}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err
        volume_version = self.get_volume_version(version_id, project=project)

        if volume_version.is_finalized:
            return JsonResponse({'success': False, 'message': '该版本已锁定，无法优化。请使用"另存新版"。'}, status=400)

        current_volumes = self.get_volumes_list(volume_version)

        def generate():
            new_volume_version = None
            volume_count = 0
            total_chars = 0

            # 获取项目上下文（世界观、人物、时间线）
            worldview_context, characters_context, timeline_context = self.get_project_context(project)

            try:
                total_volumes = len(current_volumes)
                yield self.sse_event('analysis', {
                    'total_volumes': total_volumes,
                    'volume_plan': [{'volume_number': v['volume_number'], 'chapter_count': v['chapter_count']} for v in current_volumes]
                })

                llm = get_llm(user=request.user, scene="volume_optimize")
                generate_prompt = ChatPromptTemplate.from_messages([
                    ("system", VOLUME_OPTIMIZE_SYSTEM_PROMPT),
                    ("human", VOLUME_OPTIMIZE_USER_PROMPT),
                ])
                generate_chain = generate_prompt | llm

                for vol_info in current_volumes:
                    vol_num = vol_info['volume_number']

                    # 已锁定卷跳过优化，直接复制到新版本
                    if vol_info.get('is_locked'):
                        if new_volume_version is None:
                            new_volume_version = self.create_new_version(project, volume_version.outline_version)
                        self.create_volume(new_volume_version, vol_info)
                        volume_count += 1
                        yield self.sse_event('volume', {
                            'volume': vol_info,
                            'volume_count': volume_count,
                            'total_chars': total_chars,
                            'is_locked': True,
                        })
                        continue

                    yield self.sse_event('progress', {'message': f'正在优化第 {vol_num}/{total_volumes} 卷...'})

                    # 收集单卷的完整输出
                    vol_buffer = ""
                    input_vars = {
                        "current_volumes": json.dumps(current_volumes, ensure_ascii=False),
                        "outline": volume_version.outline_version.content,
                        "user_feedback": user_feedback,
                        "worldview": worldview_context,
                        "characters": characters_context,
                        "timeline": timeline_context,
                    }

                    for chunk in generate_chain.stream(input_vars):
                        chunk_content = self.get_chunk_text(chunk)
                        vol_buffer += chunk_content

                    # 解析 LLM 输出
                    parsed_volumes = self.parse_volumes_from_llm_output(vol_buffer)

                    if not parsed_volumes:
                        yield self.sse_event('volume_error', {'message': f'第{vol_num}卷数据解析失败'})
                        continue

                    for vol_data in parsed_volumes:
                        volume_count += 1
                        total_chars += len(vol_buffer)

                        if new_volume_version is None:
                            new_volume_version = self.create_new_version(project, volume_version.outline_version)

                        # 合并 chapter_count：优先用 LLM 输出，回退到原卷数据
                        if 'chapter_count' not in vol_data:
                            vol_data['chapter_count'] = vol_info.get('chapter_count', 0)

                        self.create_volume(new_volume_version, vol_data)

                        logger.info(f"优化卷: 第{volume_count}卷 - {vol_data.get('title', '未知')}, 内容长度: {len(vol_data.get('content', ''))}")

                        yield self.sse_event('volume', {
                            'volume': vol_data,
                            'volume_count': volume_count,
                            'total_chars': total_chars,
                            'total_volumes': total_volumes
                        })

                if new_volume_version is None:
                    yield self.sse_event('error', {'message': '未生成任何卷'})
                    return

                logger.info(f"卷优化完成，共{volume_count}卷")
                yield self.sse_event('complete', {
                    'version_id': new_volume_version.pk,
                    'version_number': new_volume_version.version_number,
                    'volume_count': volume_count
                })

            except Exception as e:
                logger.error(f"优化卷失败: {e}")
                yield self.sse_event('error', {'message': '优化卷结构失败，请重试'})

        return self.sse_response(generate)


class VolumeVersionChatView(BaseVolumeAPIView):
    """卷对话 API - 使用 LLM 进行卷结构优化对话，支持跨卷操作"""

    def post(self, request, version_id):
        message = self._get_param(request, 'message')
        context_messages = self._get_param(request, 'context_messages') or []
        current_volume_number = self._get_param(request, 'current_volume_number')

        if not message:
            return JsonResponse({'success': False, 'message': '缺少消息内容'}, status=400)

        volume_version = self.get_volume_version(version_id)

        if volume_version.is_finalized:
            return JsonResponse({'success': False, 'message': '该版本已锁定，无法修改'}, status=400)

        # 获取当前卷数据
        current_volumes = self.get_volumes_list(volume_version)

        # 获取当前选中卷信息
        current_volume = None
        if current_volume_number:
            try:
                current_volume_number = int(current_volume_number)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'current_volume_number格式错误'}, status=400)
            current_volume = next((v for v in current_volumes if v['volume_number'] == current_volume_number), None)

        # 校验当前卷锁定状态
        if current_volume and current_volume.get('is_locked'):
            return JsonResponse({'success': False, 'message': '该卷已锁定，无法修改'}, status=400)

        # 构建历史对话
        history_text = ''
        if context_messages:
            if isinstance(context_messages, str):
                try:
                    context_messages = json.loads(context_messages)
                except json.JSONDecodeError:
                    context_messages = []
            if not isinstance(context_messages, list):
                context_messages = []
            # 限制历史消息数量，防止上下文过长
            context_messages = context_messages[-20:]
            for msg in context_messages:
                if isinstance(msg, dict):
                    role = '用户' if msg.get('role') == 'user' else '助手'
                    history_text += f'{role}：{msg.get("content", "")}\n'

        # 构建卷列表摘要（供 LLM 了解所有卷）
        volumes_list = '\n'.join([
            f"第{v['volume_number']}卷「{v['title']}」"
            for v in current_volumes
        ])

        # 当前卷信息
        cv_title = current_volume.get('title', '') if current_volume else ''
        cv_summary = current_volume.get('summary', '') if current_volume else ''
        cv_content = current_volume.get('content', '') if current_volume else ''

        history_section = f'历史对话：\n{history_text}\n' if history_text else ''

        # 获取项目上下文（世界观、人物、时间线）
        worldview_context, characters_context, timeline_context = self.get_project_context(volume_version.project)

        def generate():
            full_content = ""
            try:
                llm = get_llm(user=request.user, scene="volume_chat")
                prompt = ChatPromptTemplate.from_messages([
                    ("system", VOLUME_CHAT_SYSTEM_PROMPT),
                    ("human", VOLUME_CHAT_USER_PROMPT),
                ])
                chain = prompt | llm

                input_vars = {
                    "current_volume_number": current_volume_number or 0,
                    "current_volume_title": cv_title,
                    "current_volume_summary": cv_summary,
                    "current_content": cv_content or '（暂无卷大纲）',
                    "volumes_list": volumes_list,
                    "outline": volume_version.outline_version.content,
                    "worldview": worldview_context,
                    "characters": characters_context,
                    "timeline": timeline_context,
                    "history": history_section,
                    "message": message,
                }

                # 流式推送原始 LLM 输出，前端自行解析分隔符
                for chunk in chain.stream(input_vars):
                    chunk_content = self.get_chunk_text(chunk)
                    full_content += chunk_content
                    yield self.sse_event('chunk', {'data': chunk_content})

                # 解析分隔符提取 content / question / target
                parsed_content, parsed_question, target_info = self._parse_chat_output(full_content)

                # 更新当前卷
                updated_volumes = None
                if current_volume and parsed_content:
                    vol_obj = volume_version.volumes.filter(volume_number=current_volume_number).first()
                    if vol_obj and not vol_obj.is_locked:
                        vol_obj.content = parsed_content
                        vol_obj.save(update_fields=['content', 'updated_at'])
                    updated_volumes = self.get_volumes_list(volume_version)

                # 跨卷操作：合并到目标卷
                target_volume_data = None
                if target_info:
                    target_volume_number = target_info.get('target_volume_number')
                    target_addition = target_info.get('target_addition')
                    if target_volume_number and target_addition:
                        target_vol_obj = volume_version.volumes.filter(volume_number=target_volume_number).first()
                        if target_vol_obj and not target_vol_obj.is_locked:
                            yield self.sse_event('target_merge', {
                                'target_volume_number': target_volume_number,
                                'target_volume_title': target_vol_obj.title,
                            })

                            merge_content = self._merge_target_volume(
                                request.user, volume_version, target_vol_obj, target_addition
                            )
                            if merge_content:
                                target_vol_obj.content = merge_content
                                target_vol_obj.save(update_fields=['content', 'updated_at'])
                                target_volume_data = {
                                    'volume_number': target_vol_obj.volume_number,
                                    'title': target_vol_obj.title,
                                    'content': merge_content,
                                }
                                updated_volumes = self.get_volumes_list(volume_version)

                yield self.sse_event('complete', {
                    'volumes': updated_volumes,
                    'target_volume': target_volume_data,
                })

            except Exception as e:
                logger.error(f"卷对话LLM调用失败: {e}")
                yield self.sse_event('error', {'message': 'AI处理失败，请重试'})

        return self.sse_response(generate)

    @staticmethod
    def _parse_chat_output(text):
        """从 LLM 输出中解析分隔符，提取 content / question / target"""
        content = ''
        question = ''
        target_info = None

        # 提取 content
        content_match = re.search(
            r'════CONTENT_START════\s*([\s\S]*?)\s*════CONTENT_END════', text
        )
        if content_match:
            content = content_match.group(1).strip()

        # 提取 question
        question_match = re.search(
            r'════QUESTION_START════\s*([\s\S]*?)\s*════QUESTION_END════', text
        )
        if question_match:
            question = question_match.group(1).strip()

        # 提取 target（跨卷操作）
        target_match = re.search(
            r'════TARGET_START════\s*([\s\S]*?)\s*════TARGET_END════', text
        )
        if target_match:
            try:
                target_info = json.loads(target_match.group(1).strip())
            except json.JSONDecodeError:
                logger.error(f"跨卷目标JSON解析失败: {target_match.group(1)[:200]}")

        return content, question, target_info

    def _merge_target_volume(self, user, volume_version, target_vol, target_addition):
        """调用合并 LLM 将新内容合并到目标卷"""
        try:
            llm = get_llm(user=user, scene="volume_chat")
            prompt = ChatPromptTemplate.from_messages([
                ("system", VOLUME_CHAT_MERGE_SYSTEM_PROMPT),
                ("human", VOLUME_CHAT_MERGE_USER_PROMPT),
            ])
            chain = prompt | llm

            # 获取项目上下文（世界观、人物、时间线）
            worldview_context, characters_context, timeline_context = self.get_project_context(volume_version.project)

            input_vars = {
                "target_volume_number": target_vol.volume_number,
                "target_volume_title": target_vol.title,
                "target_volume_summary": target_vol.summary or '',
                "target_content": target_vol.content or '（暂无卷大纲）',
                "target_addition": target_addition,
                "outline": volume_version.outline_version.content,
                "worldview": worldview_context,
                "characters": characters_context,
                "timeline": timeline_context,
            }

            full_content = ""
            last_chunk = None
            for chunk in chain.stream(input_vars):
                chunk_content = self.get_chunk_text(chunk)
                full_content += chunk_content
                last_chunk = chunk

            # 从最后一个 chunk 提取 token 使用信息
            if user and last_chunk and hasattr(last_chunk, 'usage_metadata') and last_chunk.usage_metadata:
                try:
                    TokenUsageLog.objects.create(
                        user=user,
                        project=volume_version.project,
                        model_name='',
                        prompt_tokens=last_chunk.usage_metadata.get('input_tokens', 0),
                        completion_tokens=last_chunk.usage_metadata.get('output_tokens', 0),
                        total_tokens=last_chunk.usage_metadata.get('total_tokens', 0),
                    )
                except Exception as e:
                    logger.error(f"记录Token使用失败: {e}")

            return full_content.strip()
        except Exception as e:
            logger.error(f"合并目标卷LLM调用失败: {e}")
            return None


# ========== 单卷操作 ==========

class VolumeLockView(BaseVolumeAPIView):
    """单卷锁定/解锁"""

    def put(self, request, volume_id):
        is_locked = self._get_param(request, 'is_locked')

        if is_locked is None:
            return JsonResponse({
                'success': False,
                'message': '缺少is_locked参数'
            }, status=400)

        volume = get_object_or_404(VolumeList, pk=volume_id, volume_version__project__user=request.user)

        if volume.volume_version.is_finalized:
            return JsonResponse({
                'success': False,
                'message': '该版本已整体锁定，无法操作单卷锁定'
            }, status=400)

        volume.is_locked = str(is_locked).lower() in ('true', '1')
        volume.save(update_fields=['is_locked', 'updated_at'])

        return JsonResponse({'success': True, 'is_locked': volume.is_locked})


class VolumeOptimizeView(BaseVolumeAPIView):
    """单卷AI优化"""

    def post(self, request):
        project_id = self._get_param(request, 'project_id')
        version_id = self._get_param(request, 'version_id')
        volume_number = self._get_param(request, 'volume_number')
        volume_title = self._get_param(request, 'volume_title')
        volume_summary = self._get_param(request, 'volume_summary')
        current_content = self._get_param(request, 'current_content') or ''
        user_feedback = self._get_param(request, 'user_feedback') or '请优化这一卷的大纲，以扩展和丰富章节内容为主'

        if not volume_title and not volume_summary and not current_content:
            return JsonResponse({'success': False, 'message': '缺少卷信息'}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err

        # 校验版本锁定（version_id 必填）
        if not version_id:
            return JsonResponse({'success': False, 'message': '缺少version_id'}, status=400)
        volume_version = get_object_or_404(VolumeVersion, pk=version_id, project=project)
        if volume_version.is_finalized:
            return JsonResponse({'success': False, 'message': '该版本已锁定，无法修改'}, status=400)
        # 校验单卷锁定
        if volume_number:
            vol = volume_version.volumes.filter(volume_number=volume_number).first()
            if vol and vol.is_locked:
                return JsonResponse({'success': False, 'message': '该卷已锁定，无法修改'}, status=400)

        # 获取大纲
        outline_text = '（暂无大纲）'
        latest_outline = project.outline_versions.filter(is_deleted=False).order_by('-version_number').first()
        if latest_outline:
            outline_text = latest_outline.content

        # 获取项目上下文（世界观、人物、时间线）
        worldview_context, characters_context, timeline_context = self.get_project_context(project)

        llm = get_llm(user=request.user, scene="volume_optimize")
        prompt = ChatPromptTemplate.from_messages([
            ("system", VOLUME_SINGLE_OPTIMIZE_SYSTEM_PROMPT),
            ("human", VOLUME_SINGLE_OPTIMIZE_USER_PROMPT),
        ])
        chain = prompt | llm

        input_vars = {
            "volume_number": volume_number or 0,
            "volume_title": volume_title or '',
            "volume_summary": volume_summary or '',
            "current_content": current_content or '（暂无卷大纲）',
            "outline": outline_text,
            "worldview": worldview_context,
            "characters": characters_context,
            "timeline": timeline_context,
            "user_feedback": user_feedback,
        }

        def generate():
            full_content = ""
            try:
                for chunk in chain.stream(input_vars):
                    chunk_content = self.get_chunk_text(chunk)
                    full_content += chunk_content
                    yield self.sse_event('chunk', {'data': chunk_content})

                volume_data = {
                    'volume_number': volume_number,
                    'title': volume_title,
                    'summary': volume_summary,
                    'content': full_content,
                }

                yield self.sse_event('complete', {'volume': volume_data})

            except Exception as e:
                logger.error(f"单卷优化LLM调用失败: {e}")
                yield self.sse_event('error', {'message': 'AI优化失败，请重试'})

        return self.sse_response(generate)


class VolumeGenerateView(BaseVolumeAPIView):
    """单卷AI生成（用于补生成失败的卷）"""

    def post(self, request, volume_id):
        project_id = self._get_param(request, 'project_id')

        project, err = self.get_project(request, project_id)
        if err:
            return err

        volume = get_object_or_404(VolumeList, pk=volume_id, volume_version__project=project)
        volume_version = volume.volume_version

        if volume_version.is_finalized:
            return JsonResponse({'success': False, 'message': '该版本已锁定，无法修改'}, status=400)
        if volume.is_locked:
            return JsonResponse({'success': False, 'message': '该卷已锁定，无法修改'}, status=400)

        # 获取大纲
        outline_text = ''
        if volume_version.outline_version:
            outline_text = volume_version.outline_version.content

        if not outline_text:
            return JsonResponse({'success': False, 'message': '缺少大纲内容'}, status=400)

        # 从数据库获取 chapter_count
        chapter_count = volume.chapter_count or 10

        description = volume.summary or ''

        # 获取项目上下文（世界观、人物、时间线）
        worldview_context, characters_context, timeline_context = self.get_project_context(project)

        def generate():
            MAX_RETRIES = 2

            try:
                llm = get_llm(user=request.user, scene="volume_generate")
                prompt = ChatPromptTemplate.from_messages([
                    ("system", VOLUME_GENERATION_SYSTEM_PROMPT),
                    ("human", VOLUME_GENERATION_USER_PROMPT),
                ])
                chain = prompt | llm

                input_vars = {
                    "outline": outline_text,
                    "volume_number": volume.volume_number,
                    "title": volume.title,
                    "chapter_count": chapter_count,
                    "description": description,
                    "worldview": worldview_context,
                    "characters": characters_context,
                    "timeline": timeline_context,
                }

                vol_buffer = ""
                for attempt in range(1, MAX_RETRIES + 1):
                    vol_buffer = ""

                    yield self.sse_event('progress', {'message': f'正在生成「{volume.title}」卷大纲...'})

                    try:
                        for chunk in chain.stream(input_vars):
                            chunk_content = self.get_chunk_text(chunk)
                            vol_buffer += chunk_content
                    except Exception as stream_err:
                        logger.warning(f"单卷生成流异常(第{attempt}次): {stream_err}")
                        if attempt < MAX_RETRIES:
                            yield self.sse_event('progress', {'message': f'生成异常，正在重试({attempt}/{MAX_RETRIES})...'})
                            continue
                        else:
                            break

                    if vol_buffer.strip():
                        break

                    if attempt < MAX_RETRIES:
                        logger.warning(f"单卷生成内容为空(第{attempt}次)")
                        yield self.sse_event('progress', {'message': f'生成内容为空，正在重试({attempt}/{MAX_RETRIES})...'})

                if vol_buffer.strip():
                    # 更新卷记录 - 存储原始 Markdown 文本
                    volume.content = vol_buffer
                    volume.chapters = []
                    volume.save(update_fields=['content', 'chapters', 'updated_at'])
                    logger.info(f"单卷生成成功: 第{volume.volume_number}卷 - {volume.title}, 内容长度: {len(vol_buffer)}")

                    yield self.sse_event('complete', {
                        'volume': {
                            'volume_number': volume.volume_number,
                            'title': volume.title,
                            'summary': volume.summary,
                            'content': vol_buffer,
                        }
                    })
                else:
                    yield self.sse_event('error', {'message': f'「{volume.title}」生成失败，请重试'})

            except Exception as e:
                logger.error(f"单卷生成失败: {e}")
                yield self.sse_event('error', {'message': '单卷生成失败，请重试'})

        return self.sse_response(generate)
