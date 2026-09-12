"""
Volume views - 卷相关视图
"""
import json
import time
from loguru import logger
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from langchain_core.prompts import ChatPromptTemplate

from apps.project.base import BaseAPIView
from apps.project.models import ProjectList
from apps.outline.models import Outline
from apps.volume.models import Volume
from apps.volume.services import VolumeService
from agent.llm import get_llm
from apps.volume.prompts import (
    VOLUME_STRUCTURE_SYSTEM_PROMPT, VOLUME_STRUCTURE_USER_PROMPT,
    VOLUME_DETAIL_SYSTEM_PROMPT, VOLUME_DETAIL_USER_PROMPT,
    VOLUME_OPTIMIZE_SYSTEM_PROMPT, VOLUME_OPTIMIZE_USER_PROMPT,
    VOLUME_SINGLE_OPTIMIZE_SYSTEM_PROMPT, VOLUME_SINGLE_OPTIMIZE_USER_PROMPT,
    VOLUME_CHAT_SYSTEM_PROMPT, VOLUME_CHAT_USER_PROMPT,
    VOLUME_QUALITY_EVAL_SYSTEM_PROMPT, VOLUME_QUALITY_EVAL_USER_PROMPT,
)


# ========== 基础视图类 ==========

class BaseVolumeAPIView(BaseAPIView):
    """卷API基础类 - 继承项目基础类"""
    pass


class ApiVolumeGenerateView(BaseVolumeAPIView):
    """单卷AI生成（用于补生成失败的卷）"""

    def post(self, request, project_id, volume_id):
        project, err = self.get_project(request, project_id)
        if err:
            return err

        volume = get_object_or_404(Volume, pk=volume_id, project=project)

        if volume.is_locked:
            return JsonResponse({'success': False, 'message': '该卷已锁定，无法修改'}, status=400)

        outline_text = volume.outline.content if volume.outline else ''
        if not outline_text:
            return JsonResponse({'success': False, 'message': '缺少大纲内容'}, status=400)

        chapter_count = volume.chapter_count or 10
        description = volume.summary or ''
        worldview_context, characters_context, timeline_context = self.get_project_context(project)

        def generate():
            MAX_RETRIES = 2
            try:
                llm = get_llm(user=request.user, scene="volume_single_generate")
                prompt = ChatPromptTemplate.from_messages([
                    ("system", VOLUME_DETAIL_SYSTEM_PROMPT),
                    ("human", VOLUME_DETAIL_USER_PROMPT),
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
                        last_chunk = None
                        usage_chunk = None
                        for chunk in chain.stream(input_vars):
                            last_chunk = chunk
                            if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                                usage_chunk = chunk
                            vol_buffer += self.get_chunk_text(chunk)
                        self.log_token_usage('volume_single_generate', result=last_chunk, usage_result=usage_chunk, user=request.user, project=project)
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
                        yield self.sse_event('progress', {'message': f'生成内容为空，正在重试({attempt}/{MAX_RETRIES})...'})

                if vol_buffer.strip():
                    volume.content = vol_buffer
                    volume.save(update_fields=['content', 'updated_at'])
                    logger.info(f"单卷生成成功: 第{volume.volume_number}卷 - {volume.title}")
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

        return self.sse_response(generate, timeout=300)


# ========== 单卷操作 ==========

class ApiVolumeLockView(BaseVolumeAPIView):
    """单卷锁定/解锁"""

    def put(self, request, project_id, volume_id):
        is_locked = self._get_param(request, 'is_locked')
        if is_locked is None:
            return JsonResponse({'success': False, 'message': '缺少is_locked参数'}, status=400)

        volume = get_object_or_404(Volume, pk=volume_id, project__user=request.user)
        volume.is_locked = str(is_locked).lower() in ('true', '1')
        volume.save(update_fields=['is_locked', 'updated_at'])

        return JsonResponse({'success': True, 'is_locked': volume.is_locked})


class ApiVolumeOptimizeView(BaseVolumeAPIView):
    """单卷AI优化"""

    def post(self, request, project_id):
        version = self._get_param(request, 'version')
        volume_number = self._get_param(request, 'volume_number')
        volume_title = self._get_param(request, 'volume_title')
        volume_summary = self._get_param(request, 'volume_summary')
        current_content = self._get_param(request, 'current_content') or ''
        user_feedback = self._get_param(request, 'user_feedback') or '请优化这一卷的大纲'

        if not volume_title and not volume_summary and not current_content:
            return JsonResponse({'success': False, 'message': '缺少卷信息'}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err

        if not version:
            return JsonResponse({'success': False, 'message': '缺少version'}, status=400)

        if VolumeService.is_version_locked(project, version):
            return JsonResponse({'success': False, 'message': '该版本已锁定，无法修改'}, status=400)

        if volume_number:
            vol = Volume.objects.filter(project=project, version=version, volume_number=volume_number).first()
            if vol and vol.is_locked:
                return JsonResponse({'success': False, 'message': '该卷已锁定，无法修改'}, status=400)

        outline_text = '（暂无大纲）'
        outline_id = Volume.objects.filter(project=project, version=version).values_list('outline_id', flat=True).first()
        if outline_id:
            outline_obj = Outline.objects.filter(pk=outline_id).first()
            if outline_obj:
                outline_text = outline_obj.content

        worldview_context, characters_context, timeline_context = self.get_project_context(project)

        llm = get_llm(user=request.user, scene="volume_single_optimize")
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
                last_chunk = None
                usage_chunk = None
                for chunk in chain.stream(input_vars):
                    last_chunk = chunk
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        usage_chunk = chunk
                    chunk_content = self.get_chunk_text(chunk)
                    full_content += chunk_content
                    yield self.sse_event('chunk', {'data': chunk_content})

                self.log_token_usage('volume_single_optimize', result=last_chunk, usage_result=usage_chunk, user=request.user, project=project)

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

        return self.sse_response(generate, timeout=300)


class ApiVolumeVersionChatView(BaseVolumeAPIView):
    """卷对话 API"""

    def post(self, request, project_id, version):
        message = self._get_param(request, 'message')
        context_messages = self._get_param(request, 'context_messages') or []
        current_volume_number = self._get_param(request, 'current_volume_number')

        if not message:
            return JsonResponse({'success': False, 'message': '缺少消息内容'}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err

        current_volumes = VolumeService.get_volumes_list(project, version)

        # 检查版本锁定
        if VolumeService.is_version_locked(project, version):
            return JsonResponse({'success': False, 'message': '该版本已锁定，无法修改'}, status=400)

        # 获取当前选中卷
        current_volume = None
        if current_volume_number:
            try:
                current_volume_number = int(current_volume_number)
            except (ValueError, TypeError):
                return JsonResponse({'success': False, 'message': 'current_volume_number格式错误'}, status=400)
            current_volume = next((v for v in current_volumes if v['volume_number'] == current_volume_number), None)

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
            context_messages = context_messages[-20:]
            for msg in context_messages:
                if isinstance(msg, dict):
                    role = '用户' if msg.get('role') == 'user' else '助手'
                    history_text += f'{role}：{msg.get("content", "")}\n'

        volumes_list = '\n'.join([f"第{v['volume_number']}卷「{v['title']}」" for v in current_volumes])
        cv_title = current_volume.get('title', '') if current_volume else ''
        cv_summary = current_volume.get('summary', '') if current_volume else ''
        cv_content = current_volume.get('content', '') if current_volume else ''
        history_section = f'历史对话：\n{history_text}\n' if history_text else ''

        outline_obj = Volume.objects.filter(project=project, version=version).values_list('outline_id', flat=True).first()
        outline = get_object_or_404(Outline, pk=outline_obj) if outline_obj else None
        worldview_context, characters_context, timeline_context = self.get_project_context(project)

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
                    "outline": outline.content if outline else '',
                    "worldview": worldview_context,
                    "characters": characters_context,
                    "timeline": timeline_context,
                    "history": history_section,
                    "message": message,
                }

                last_chunk = None
                usage_chunk = None
                for chunk in chain.stream(input_vars):
                    last_chunk = chunk
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        usage_chunk = chunk
                    chunk_content = self.get_chunk_text(chunk)
                    full_content += chunk_content
                    yield self.sse_event('chunk', {'data': chunk_content})

                self.log_token_usage('volume_chat', result=last_chunk, usage_result=usage_chunk, user=request.user, project=project)

                # 解析 JSON 输出
                parsed_data = VolumeService.parse_chat_json(full_content)
                reply = parsed_data.get('reply', '')
                patch_list = parsed_data.get('patch_list', [])
                target_volume_number = parsed_data.get('target_volume_number')

                # 应用补丁到当前卷
                updated_volumes = None
                if current_volume and patch_list:
                    vol_obj = Volume.objects.filter(project=project, version=version, volume_number=current_volume_number).first()
                    if vol_obj and not vol_obj.is_locked:
                        patch_result = VolumeService.apply_content_patches(vol_obj.content, patch_list)
                        if patch_result['edits_applied'] > 0:
                            vol_obj.content = patch_result['new_content']
                            vol_obj.save(update_fields=['content', 'updated_at'])
                    updated_volumes = VolumeService.get_volumes_list(project, version)

                # 跨卷操作：将部分 patch 应用到目标卷
                target_volume_data = None
                if target_volume_number and patch_list:
                    target_vol_obj = Volume.objects.filter(project=project, version=version, volume_number=target_volume_number).first()
                    if target_vol_obj and not target_vol_obj.is_locked:
                        # 过滤出属于目标卷的 patch（带 target_volume_number 标记）
                        target_patches = [p for p in patch_list if p.get('target_volume_number') == target_volume_number]
                        if target_patches:
                            yield self.sse_event('target_merge', {
                                'target_volume_number': target_volume_number,
                                'target_volume_title': target_vol_obj.title,
                            })
                            target_patch_result = VolumeService.apply_content_patches(target_vol_obj.content, target_patches)
                            if target_patch_result['edits_applied'] > 0:
                                target_vol_obj.content = target_patch_result['new_content']
                                target_vol_obj.save(update_fields=['content', 'updated_at'])
                                target_volume_data = {
                                    'volume_number': target_vol_obj.volume_number,
                                    'title': target_vol_obj.title,
                                    'content': target_patch_result['new_content'],
                                }
                                updated_volumes = VolumeService.get_volumes_list(project, version)

                yield self.sse_event('complete', {
                    'volumes': updated_volumes,
                    'target_volume': target_volume_data,
                })

            except Exception as e:
                logger.error(f"卷对话LLM调用失败: {e}")
                yield self.sse_event('error', {'message': 'AI处理失败，请重试'})

        return self.sse_response(generate, timeout=300)



class ApiVolumeVersionOptimizeView(BaseVolumeAPIView):
    """优化卷结构（逐卷流式生成）"""

    def post(self, request, project_id, version):
        user_feedback = self._get_param(request, 'user_feedback')
        if not user_feedback:
            return JsonResponse({'success': False, 'message': '缺少调整意见'}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err

        if VolumeService.is_version_locked(project, version):
            return JsonResponse({'success': False, 'message': '该版本已锁定，无法优化。'}, status=400)

        current_volumes = VolumeService.get_volumes_list(project, version)
        outline_id = Volume.objects.filter(project=project, version=version).values_list('outline_id', flat=True).first()
        outline = get_object_or_404(Outline, pk=outline_id) if outline_id else None

        def generate():
            new_version = None
            volume_count = 0
            total_chars = 0
            worldview_context, characters_context, timeline_context = self.get_project_context(project)

            try:
                total_volumes = len(current_volumes)
                yield self.sse_event('analysis', {
                    'total_volumes': total_volumes,
                    'volume_plan': [{'volume_number': v['volume_number'], 'chapter_count': v['chapter_count']} for v in current_volumes]
                })

                llm = get_llm(user=request.user, scene="volume_single_optimize")
                generate_prompt = ChatPromptTemplate.from_messages([
                    ("system", VOLUME_OPTIMIZE_SYSTEM_PROMPT),
                    ("human", VOLUME_OPTIMIZE_USER_PROMPT),
                ])
                generate_chain = generate_prompt | llm

                new_version = VolumeService.get_next_version(project)

                for vol_info in current_volumes:
                    vol_num = vol_info['volume_number']

                    # 已锁定卷跳过优化，直接复制到新版本
                    if vol_info.get('is_locked'):
                        VolumeService.create_volume(project, outline, new_version, vol_info)
                        volume_count += 1
                        yield self.sse_event('volume', {
                            'volume': vol_info, 'volume_count': volume_count,
                            'total_chars': total_chars, 'is_locked': True,
                        })
                        continue

                    yield self.sse_event('progress', {'message': f'正在优化第 {vol_num}/{total_volumes} 卷...'})

                    vol_buffer = ""
                    input_vars = {
                        "current_volumes": json.dumps(current_volumes, ensure_ascii=False),
                        "outline": outline.content if outline else '',
                        "user_feedback": user_feedback,
                        "worldview": worldview_context,
                        "characters": characters_context,
                        "timeline": timeline_context,
                    }

                    MAX_RETRIES = 2
                    for attempt in range(1, MAX_RETRIES + 1):
                        vol_buffer = ""
                        try:
                            last_chunk = None
                            usage_chunk = None
                            for chunk in generate_chain.stream(input_vars):
                                last_chunk = chunk
                                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                                    usage_chunk = chunk
                                vol_buffer += self.get_chunk_text(chunk)
                            self.log_token_usage('volume_optimize', result=last_chunk, usage_result=usage_chunk, user=request.user, project=project)
                        except Exception as stream_err:
                            logger.warning(f"优化第{vol_num}卷流异常(第{attempt}次): {stream_err}")
                            if attempt < MAX_RETRIES:
                                yield self.sse_event('progress', {'message': f'第 {vol_num} 卷优化异常，正在重试({attempt}/{MAX_RETRIES})...'})
                                continue
                            else:
                                break
                        if vol_buffer.strip():
                            break
                        if attempt < MAX_RETRIES:
                            yield self.sse_event('progress', {'message': f'第 {vol_num} 卷优化内容为空，正在重试({attempt}/{MAX_RETRIES})...'})

                    parsed_volumes = VolumeService.parse_volumes_from_llm_output(vol_buffer)
                    if not parsed_volumes:
                        yield self.sse_event('volume_error', {'message': f'第{vol_num}卷数据解析失败'})
                        continue

                    for vol_data in parsed_volumes:
                        volume_count += 1
                        total_chars += len(vol_buffer)
                        if 'chapter_count' not in vol_data:
                            vol_data['chapter_count'] = vol_info.get('chapter_count', 0)
                        VolumeService.create_volume(project, outline, new_version, vol_data)
                        logger.info(f"优化卷: 第{volume_count}卷 - {vol_data.get('title', '未知')}")
                        yield self.sse_event('volume', {
                            'volume': vol_data, 'volume_count': volume_count,
                            'total_chars': total_chars, 'total_volumes': total_volumes
                        })

                logger.info(f"卷优化完成，共{volume_count}卷")
                yield self.sse_event('complete', {
                    'version': new_version, 'volume_count': volume_count
                })

            except Exception as e:
                logger.error(f"优化卷失败: {e}")
                yield self.sse_event('error', {'message': '优化卷结构失败，请重试'})

        return self.sse_response(generate, timeout=600)


class ApiVolumeVersionFinalizeView(BaseVolumeAPIView):
    """锁定/解锁卷版本"""

    def post(self, request, project_id, version):
        project, err = self.get_project(request, project_id)
        if err:
            return err

        new_state = VolumeService.toggle_version_lock(project, version)
        if new_state is None:
            return JsonResponse({'success': False, 'message': '版本不存在'}, status=404)

        return JsonResponse({'success': True, 'is_locked': new_state})


class ApiVolumeVersionSaveView(BaseVolumeAPIView):
    """另存为新版本"""

    def post(self, request, project_id, version):
        """另存为新版本"""
        outline_version_id = self._get_param(request, 'outline_version_id')
        volumes_json = self._get_param(request, 'volumes') or '[]'

        volumes_data, err_msg = VolumeService.parse_volumes_json(volumes_json)
        if err_msg:
            return JsonResponse({'success': False, 'message': err_msg}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err
        outline = None
        if outline_version_id:
            outline = get_object_or_404(Outline, pk=outline_version_id, project=project)

        new_version = VolumeService.get_next_version(project)
        for vol_data in volumes_data:
            VolumeService.create_volume(project, outline, new_version, vol_data)

        return JsonResponse({'success': True, 'version': new_version})


# ========== 卷版本管理 ==========

class ApiVolumeVersionListView(BaseVolumeAPIView):
    """
    卷版本列表
    GET  - 获取版本列表
    POST - 生成新版本
    """

    def get(self, request, project_id):
        """获取项目的卷版本列表（按版本号分组）"""
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)

        version_groups = VolumeService.get_version_groups(project)

        versions_data = []
        for vg in version_groups:
            versions_data.append({
                'version': vg['version'],
                'outline_id': vg['outline_id'],
                'volume_count': vg['volume_count'],
                'created_at': vg['created_at'].strftime('%Y-%m-%d %H:%M') if vg['created_at'] else '',
            })

        return JsonResponse({'success': True, 'versions': versions_data})

    def post(self, request, project_id):
        """生成卷结构（先分析大纲→逐卷流式生成，含重试策略）"""
        outline_version_id = self._get_param(request, 'outline_version_id')
        if not outline_version_id:
            return JsonResponse({'success': False, 'message': '缺少outline_version_id'}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err
        outline = get_object_or_404(Outline, pk=outline_version_id, project=project)

        MAX_RETRIES = 2

        def generate():
            new_version = None
            volume_count = 0
            total_chars = 0

            worldview_context, characters_context, timeline_context = self.get_project_context(project)

            try:
                # ===== Phase 1：分析大纲 =====
                yield self.sse_event('progress', {'message': '正在分析大纲...'})

                llm = get_llm(user=request.user, scene="volume_structure_analyze")
                analysis_prompt = ChatPromptTemplate.from_messages([
                    ("system", VOLUME_STRUCTURE_SYSTEM_PROMPT),
                    ("human", VOLUME_STRUCTURE_USER_PROMPT),
                ])
                analysis_chain = analysis_prompt | llm

                analysis_result = analysis_chain.invoke({"outline": outline.content})
                self.log_token_usage('volume_analysis', result=analysis_result, user=request.user, project=project)
                analysis_content = self.get_chunk_text(analysis_result)

                volume_plan = VolumeService.parse_analysis_json(analysis_content)
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

                # ===== Phase 2：逐卷生成大纲 =====
                llm_detail = get_llm(user=request.user, scene="volume_detail_expand")
                generate_prompt = ChatPromptTemplate.from_messages([
                    ("system", VOLUME_DETAIL_SYSTEM_PROMPT),
                    ("human", VOLUME_DETAIL_USER_PROMPT),
                ])
                generate_chain = generate_prompt | llm_detail

                new_version = VolumeService.get_next_version(project)

                for vol_plan in volume_plan:
                    vol_num = vol_plan.get('volume_number', volume_count + 1)
                    vol_title = vol_plan.get('title', f'第{vol_num}卷')
                    chapter_count = vol_plan.get('chapter_count', 10)
                    description = vol_plan.get('description', '')

                    yield self.sse_event('progress', {'message': f'正在生成第 {vol_num}/{total_volumes} 卷「{vol_title}」...'})

                    vol_buffer = ""
                    for attempt in range(1, MAX_RETRIES + 1):
                        vol_buffer = ""
                        input_vars = {
                            "outline": outline.content,
                            "volume_number": vol_num,
                            "title": vol_title,
                            "chapter_count": chapter_count,
                            "description": description,
                            "worldview": worldview_context,
                            "characters": characters_context,
                            "timeline": timeline_context,
                        }
                        try:
                            last_chunk = None
                            usage_chunk = None
                            for chunk in generate_chain.stream(input_vars):
                                last_chunk = chunk
                                if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                                    usage_chunk = chunk
                                vol_buffer += self.get_chunk_text(chunk)
                            self.log_token_usage('volume_generate', result=last_chunk, usage_result=usage_chunk, user=request.user, project=project)
                        except Exception as stream_err:
                            logger.warning(f"第{vol_num}卷生成流异常(第{attempt}次): {stream_err}")
                            if attempt < MAX_RETRIES:
                                yield self.sse_event('progress', {'message': f'第 {vol_num} 卷生成异常，正在重试({attempt}/{MAX_RETRIES})...'})
                                continue
                            else:
                                break
                        if vol_buffer.strip():
                            break
                        if attempt < MAX_RETRIES:
                            yield self.sse_event('progress', {'message': f'第 {vol_num} 卷生成内容为空，正在重试({attempt}/{MAX_RETRIES})...'})

                    volume_count += 1
                    total_chars += len(vol_buffer) if vol_buffer else 0

                    if vol_buffer.strip():
                        VolumeService.create_volume(project, outline, new_version, {
                            'volume_number': vol_num,
                            'title': vol_title,
                            'summary': description,
                            'chapter_count': chapter_count,
                            'content': vol_buffer,
                        })

                # 完成
                logger.info(f"卷生成完成，共{volume_count}卷")

                # ===== Phase 3：结构校验 + 质量评分 =====
                yield self.sse_event('progress', {'message': '正在进行结构校验和质量评分...'})
                final_volumes = VolumeService.get_volumes_list(project, new_version)
                validation = VolumeService.validate_structure(final_volumes)
                quality = VolumeService.evaluate_quality(final_volumes, validation)

                yield self.sse_event('phase3_result', {
                    'validation': validation,
                    'quality': quality,
                    'version': new_version,
                    'volume_count': volume_count,
                })

                yield self.sse_event('complete', {
                    'version': new_version,
                    'volume_count': volume_count
                })

            except Exception as e:
                logger.error(f"生成卷失败: {e}")
                yield self.sse_event('error', {'message': '生成卷结构失败，请重试'})

        return self.sse_response(generate, timeout=900)


class ApiVolumeVersionDetailView(BaseVolumeAPIView):
    """
    单个卷版本
    GET    - 获取版本详情
    PUT    - 保存版本（覆盖当前版本的卷数据）
    DELETE - 删除版本（物理删除）
    """

    def get(self, request, project_id, version):
        """获取单个卷版本详情"""
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        volumes = VolumeService.get_volumes_list(project, version)
        if not volumes:
            return JsonResponse({'success': False, 'message': '版本不存在'}, status=404)

        outline_id = Volume.objects.filter(project=project, version=version).values_list('outline_id', flat=True).first()
        is_locked = VolumeService.is_version_locked(project, version)
        return JsonResponse({
            'success': True,
            'volumes': volumes,
            'outline_version_id': outline_id,
            'version': version,
            'is_version_locked': is_locked,
        })

    def put(self, request, project_id, version):
        """保存卷版本（覆盖当前版本的卷数据）"""
        outline_version_id = self._get_param(request, 'outline_version_id')
        volumes_json = self._get_param(request, 'volumes') or '[]'

        volumes_data, err_msg = VolumeService.parse_volumes_json(volumes_json)
        if err_msg:
            return JsonResponse({'success': False, 'message': err_msg}, status=400)

        project, err = self.get_project(request, project_id)
        if err:
            return err
        outline = None
        if outline_version_id:
            outline = get_object_or_404(Outline, pk=outline_version_id, project=project)

        success, err_msg = VolumeService.save_version_overwrite(project, outline, version, volumes_data)
        if not success:
            return JsonResponse({'success': False, 'message': err_msg}, status=400)

        return JsonResponse({'success': True, 'version': version})

    def delete(self, request, project_id, version):
        """删除卷版本（物理删除）"""
        project, err = self.get_project(request, project_id)
        if err:
            return err
        if VolumeService.is_version_locked(project, version):
            return JsonResponse({'success': False, 'message': '该版本已锁定，无法删除。'}, status=400)
        VolumeService.get_version_volumes(project, version).delete()
        return JsonResponse({'success': True})
