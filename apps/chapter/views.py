import json
from loguru import logger
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

from apps.project.base import BaseAPIView
from apps.chapter.models import ChapterList
from apps.volume.models import Volume
from apps.characters.models import Character
from agent.llm import get_llm, call_llm_with_retry, log_token_usage
from utils.constants import (
    MAX_CONTENT_LENGTH, MAX_TITLE_LENGTH, MAX_SUMMARY_LENGTH,
    PREV_CHAPTER_TAIL_LENGTH, MAX_CHAT_MESSAGE_LENGTH, MAX_CHAT_HISTORY_LENGTH,
    BATCH_SIZE, BATCH_PREV_CHAPTERS_COUNT, BATCH_NEXT_CHAPTERS_COUNT,
    PREV_BATCH_SUMMARY_TAIL_LENGTH, MAX_VERIFY_FIX_LOOPS,
    SCORING_PASS_THRESHOLD, MAX_REWRITE_LOOPS,
    CHAPTER_TAIL_CONTEXT_LENGTH,
    REDIS_KEY_CORNERSTONE_CTX, REDIS_KEY_VOLUME_LOCK,
)
from utils.helpers import safe_parse_json
from apps.characters.prompts import CHARACTER_OUTPUT_SCHEMA
from apps.timeline.prompts import TIMELINE_EVENT_OUTPUT_SCHEMA
from apps.chapter.prompts import (
    CHAPTER_OUTLINE_SYSTEM_PROMPT,
    CHAPTER_OUTLINE_USER_PROMPT,
    CHAPTER_CONTENT_GEN_SYSTEM_PROMPT,
    CHAPTER_CONTENT_GEN_USER_PROMPT,
    CHAPTER_CONTENT_SYSTEM_PROMPT,
    CHAPTER_CONTENT_USER_PROMPT,
    CHAPTER_VERIFY_SYSTEM_PROMPT,
    CHAPTER_VERIFY_USER_PROMPT,
    CHAPTER_VERIFY_FIX_SYSTEM_PROMPT,
    CHAPTER_VERIFY_FIX_USER_PROMPT,
    CHAPTER_SPLIT_SYSTEM_PROMPT,
    CHAPTER_SPLIT_USER_PROMPT,
    CHAPTER_SPLIT_BY_PLOT_USER_PROMPT,
    CHAPTER_CHAT_WRITE_SYSTEM_PROMPT,
    CHAPTER_CHAT_WRITE_USER_PROMPT,
    CHAPTER_BATCH_CONTENT_SYSTEM_PROMPT,
    CHAPTER_BATCH_CONTENT_USER_PROMPT,
    CHAPTER_SINGLE_CONTENT_USER_PROMPT,
    CHAPTER_SCORING_SYSTEM_PROMPT,
    CHAPTER_SCORING_USER_PROMPT,
    CHARACTER_STATE_EXTRACT_SYSTEM_PROMPT,
    CHARACTER_STATE_EXTRACT_USER_PROMPT,
    CHAPTER_OUTLINE_ADJUST_SYSTEM_PROMPT,
    CHAPTER_OUTLINE_ADJUST_USER_PROMPT,
    READER_REVIEW_SYSTEM_PROMPT,
    READER_REVIEW_USER_PROMPT,
    CHAPTER_BATCH_CHECK_SYSTEM_PROMPT,
    CHAPTER_BATCH_CHECK_USER_PROMPT,
    CHAPTER_BATCH_FIX_SYSTEM_PROMPT,
    CHAPTER_BATCH_FIX_USER_PROMPT,
)


# ========== 基础视图类 ==========

class BaseChapterAPIView(BaseAPIView):
    """章节API基础类 - 继承项目基础类，添加章节相关工具方法"""

    def get_chapter(self, request, chapter_id=None):
        """获取章节对象，验证权限"""
        if chapter_id is None:
            chapter_id = request.data.get('chapter_id')
        if not chapter_id:
            return None, JsonResponse({'success': False, 'message': '缺少chapter_id'}, status=400)
        try:
            chapter = ChapterList.objects.select_related('volume', 'volume__project').get(
                pk=chapter_id, volume__project__user=request.user
            )
            return chapter, None
        except ChapterList.DoesNotExist:
            return None, JsonResponse({'success': False, 'message': '章节不存在'}, status=404)

    def get_adjacent_context(self, chapter):
        """获取章节的上下文（上一章末尾、下一章概述）"""
        volume = chapter.volume
        prev_chapter_tail = ""
        next_chapter_summary = ""

        prev_chapter = ChapterList.objects.filter(
            volume=volume,
            chapter_number=chapter.chapter_number - 1,
            state=ChapterList.STATE_NORMAL
        ).first()
        if prev_chapter and prev_chapter.content:
            prev_chapter_tail = f"【上一章末尾】\n{prev_chapter.content[-PREV_CHAPTER_TAIL_LENGTH:]}"

        next_chapter = ChapterList.objects.filter(
            volume=volume,
            chapter_number=chapter.chapter_number + 1,
            state=ChapterList.STATE_NORMAL
        ).first()
        if next_chapter and next_chapter.summary:
            next_chapter_summary = f"【下一章概述】\n第{next_chapter.chapter_number}章 {next_chapter.title}：{next_chapter.summary}"

        return prev_chapter_tail, next_chapter_summary

    def get_enhanced_adjacent_context(self, volume, chapter_number, title=None, prev_count=None, next_count=None):
        """
        增强版上下文获取：取前N章摘要+后M章概述（批次生成用）
        返回 (prev_chapters_context, next_chapters_context)
        """
        prev_count = prev_count or BATCH_PREV_CHAPTERS_COUNT
        next_count = next_count or BATCH_NEXT_CHAPTERS_COUNT

        # 前N章摘要（已完成的章节，从数据库读取原文摘要）
        prev_chapters_context = ""
        if title:
            prev_chapters_context = f"当前章节标题：{title}\n"
        prev_chapters = ChapterList.objects.filter(
            volume=volume,
            chapter_number__lt=chapter_number,
            state=ChapterList.STATE_NORMAL,
            status__in=[ChapterList.STATUS_DRAFT, ChapterList.STATUS_PUBLISHED],
        ).order_by('-chapter_number')[:prev_count]

        prev_list = sorted(prev_chapters, key=lambda c: c.chapter_number)
        if prev_list:
            parts = []
            for pc in prev_list:
                summary_text = pc.content[-CHAPTER_TAIL_CONTEXT_LENGTH:] if pc.content else (pc.summary or "")
                parts.append(f"第{pc.chapter_number}章 {pc.title}\n{summary_text}")
            prev_chapters_context = "\n---\n".join(parts)

        # 后M章概述
        next_chapters_context = ""
        next_chapters = ChapterList.objects.filter(
            volume=volume,
            chapter_number__gt=chapter_number,
            state=ChapterList.STATE_NORMAL,
            summary__isnull=False,
        ).exclude(summary="").order_by('chapter_number')[:next_count]
        if next_chapters:
            parts = []
            for nc in next_chapters:
                parts.append(f"第{nc.chapter_number}章 {nc.title}：{nc.summary}")
            next_chapters_context = "\n".join(parts)

        return prev_chapters_context, next_chapters_context

    def get_previous_batch_context(self, volume, last_chapter_number, batch_size=None):
        """获取上一批次章节摘要（用于批次间衔接）"""
        batch_size = batch_size or BATCH_SIZE
        prev_chapters = ChapterList.objects.filter(
            volume=volume,
            chapter_number__lte=last_chapter_number,
            chapter_number__gt=last_chapter_number - batch_size,
            state=ChapterList.STATE_NORMAL,
            status__in=[ChapterList.STATUS_DRAFT, ChapterList.STATUS_PUBLISHED],
        ).order_by('chapter_number')

        if not prev_chapters:
            return ""

        parts = []
        for pc in prev_chapters:
            content = pc.content or ""
            summary_text = content[-PREV_BATCH_SUMMARY_TAIL_LENGTH:] if len(content) > PREV_BATCH_SUMMARY_TAIL_LENGTH else content
            parts.append(f"第{pc.chapter_number}章 {pc.title}：{summary_text}")
        return "\n---\n".join(parts)

    def get_cornerstone_context(self, project, volume):
        """
        获取基石上下文（世界观 + 角色静态属性 + 卷大纲），带 Redis 缓存
        System Prompt 命中 LLM 厂商缓存后能省 30-50% Token
        """
        cache_key = f"{REDIS_KEY_CORNERSTONE_CTX}:{project.pk}:{volume.pk}"
        cached = cache.get(cache_key)
        if cached:
            return cached["worldview"], cached["characters"], cached["volume_outline"]

        worldview, characters, _extra = self.get_knowledge_context(project)
        volume_outline = volume.content or volume.summary or ""

        cornerstone = {
            "worldview": worldview,
            "characters": characters,
            "volume_outline": volume_outline,
        }
        # 缓存 24 小时（或直到卷大纲被修改时失效）
        cache.set(cache_key, cornerstone, timeout=86400)
        return worldview, characters, volume_outline

    def get_character_dynamic_states_context(self, project):
        """获取所有角色的动态状态上下文（用于 User Prompt 注入）"""
        characters = Character.objects.filter(project=project, is_deleted=False)
        parts = []
        for ch in characters:
            states = ch.dynamic_states or {}
            if states:
                state_lines = [f"- {k}: {v}" for k, v in states.items() if v]
                if state_lines:
                    parts.append(f"{ch.name}：\n" + "\n".join(state_lines))
        if parts:
            return "\n\n".join(parts)
        return ""

    def get_timeline_context(self, project):
        """获取时间线结构化文本（用于 User Prompt 注入），展示与当前章节相关的历史事件"""
        from apps.timeline.models import TimelineEvent
        events = TimelineEvent.objects.filter(
            project=project, is_active=True
        ).order_by('start_year', 'start_month')[:30]  # 限制数量避免 token 过长
        if not events:
            return ""
        lines = []
        for ev in events:
            era = ev.era_unit or ""
            time_str = f"{era}{ev.start_year}年" if ev.start_year is not None else "未知时间"
            if ev.end_year and ev.end_year != ev.start_year:
                time_str += f" - {era}{ev.end_year}年"
            loc = f" @{ev.location}" if ev.location else ""
            chars = "、".join(c.name for c in ev.characters.all())
            char_str = f"（{chars}）" if chars else ""
            lines.append(f"- [{time_str}] {ev.title}{char_str}{loc}")
        return "\n".join(lines)

    def get_location_context(self, project, chapter=None):
        """获取地点状态上下文：相关地点的最近事件"""
        from apps.timeline.models import TimelineEvent
        # 收集所有出现过的地点
        locations = set(
            TimelineEvent.objects.filter(
                project=project, is_active=True, location__isnull=False
            ).values_list('location', flat=True).distinct()[:20]
        )
        if not locations:
            return ""
        parts = []
        for loc in sorted(locations):
            recent_events = TimelineEvent.objects.filter(
                project=project, is_active=True, location=loc
            ).order_by('-start_year', '-start_month')[:3]
            if recent_events:
                ev_lines = []
                for ev in recent_events:
                    era = ev.era_unit or ""
                    time_str = f"{era}{ev.start_year}年" if ev.start_year is not None else ""
                    ev_lines.append(f"  - {ev.title}（{time_str}）")
                parts.append(f"{loc}：\n" + "\n".join(ev_lines))
        if parts:
            return "\n".join(parts)
        return ""

    def get_character_trajectories_context(self, project):
        """获取角色轨迹文本（用于 User Prompt 注入），展示角色在各章节中的变化"""
        from apps.characters.models import CharacterTrajectory
        trajectories = CharacterTrajectory.objects.filter(
            project=project
        ).select_related('character').order_by(
            'character__name', 'order', 'created_at'
        )
        if not trajectories:
            return ""
        # 按角色分组
        by_character = {}
        for t in trajectories:
            char_name = t.character.name if t.character else "未知"
            if char_name not in by_character:
                by_character[char_name] = []
            by_character[char_name].append(t)
        parts = []
        for char_name, trajs in by_character.items():
            lines = [f"{char_name}："]
            for t in trajs[:10]:  # 每个角色最多 10 条
                time_label = f"（{t.start_time}）" if t.start_time else ""
                location = f" @{t.details.get('location', '')}" if t.details.get('location') else ""
                desc = t.title or ""
                lines.append(f"  {time_label}{location}：{desc}")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)

    def get_relationship_subgraph_context(self, project):
        """获取角色关系子图上下文（结构化 N-hop），用于章节生成"""
        from apps.graph.models import GraphNode, GraphEdge
        characters = Character.objects.filter(project=project, is_deleted=False)
        if not characters.exists():
            return ""
        try:
            char_nodes = GraphNode.objects.filter(
                project_id=project.pk, node_type='character'
            ).values_list('id', 'name')
            if not char_nodes:
                return ""
            char_id_map = {nid: nname for nid, nname in char_nodes}
            char_ids = set(char_id_map.keys())
            edges = GraphEdge.objects.filter(
                project_id=project.pk,
                source_id__in=char_ids
            ).exclude(
                edge_type__in=('located_in', 'occurs_at')
            )[:30]
            if not edges:
                return ""
            lines = []
            for e in edges:
                src = char_id_map.get(e.source_id, f"#{e.source_id}")
                tgt = char_id_map.get(e.target_id, f"#{e.target_id}")
                desc = f"（{e.description}）" if e.description else ""
                lines.append(f"- {src} —[{e.edge_type}]→ {tgt}{desc}")
            return "\n".join(lines)
        except Exception:
            return ""

    def extract_and_update_character_states(self, project, chapter_content, user, chapter=None):
        """从章节内容中进行合并提取：状态更新 + 新角色发现 + 剧情事件 + 故事时间

        Args:
            project: 项目实例
            chapter_content: 章节正文内容
            user: 当前用户
            chapter: ChapterList 实例（可选，用于创建轨迹记录和事件关联）
        """
        try:
            characters = list(Character.objects.filter(project=project, is_deleted=False))
            if not characters:
                return

            # 构建角色列表（含当前状态）
            char_parts = []
            for ch in characters:
                states_str = json.dumps(ch.dynamic_states or {}, ensure_ascii=False)
                char_parts.append(f"- {ch.name}（{ch.role_type}）：当前状态={states_str}")
            characters_with_states = "\n".join(char_parts)

            llm = get_llm(user=user, scene="character_state_extract")
            prompt = ChatPromptTemplate.from_messages([
                ("system", CHARACTER_STATE_EXTRACT_SYSTEM_PROMPT),
                ("human", CHARACTER_STATE_EXTRACT_USER_PROMPT),
            ])
            chain = prompt | llm
            result = call_llm_with_retry(
                chain,
                input_vars={
                    "character_output_schema": CHARACTER_OUTPUT_SCHEMA,
                    "timeline_event_output_schema": TIMELINE_EVENT_OUTPUT_SCHEMA,
                    "characters_with_states": characters_with_states,
                    "chapter_content": chapter_content[-8000:],
                },
                user=user,
                scene="character_state_extract",
                project=project,
                task_type="character_state_extract",
            )

            text = result.content if hasattr(result, 'content') else str(result)
            parsed = safe_parse_json(text)

            # 降级处理：如果返回格式异常，退化为仅做状态提取
            if not parsed or not isinstance(parsed, dict):
                logger.warning(f"合并提取返回格式异常，尝试降级为旧格式解析: {text[:200]}")
                self._fallback_state_only_extract(parsed, characters, text, project)
                return

            # 1. 处理角色状态更新
            state_updates = parsed.get('state_updates') or []
            if isinstance(state_updates, list):
                self._process_state_updates(state_updates, characters, project)

            # 2. 处理新角色发现
            new_characters = parsed.get('new_characters') or []
            if isinstance(new_characters, list) and new_characters:
                self._process_new_characters(new_characters, project, chapter)
                # 刷新角色列表，确保新创建的角色能被后续步骤引用
                characters = list(Character.objects.filter(project=project, is_deleted=False))

            # 3. 处理剧情事件
            timeline_events = parsed.get('timeline_events') or []
            if isinstance(timeline_events, list) and timeline_events:
                self._process_timeline_events(timeline_events, project, chapter, characters)

            # 4. 更新故事时间
            current_story_time = parsed.get('current_story_time')
            if current_story_time and chapter:
                self._update_chapter_story_time(chapter, current_story_time)

            # 5. 创建角色轨迹记录
            if chapter and isinstance(state_updates, list):
                self._create_character_trajectories(state_updates, project, chapter, characters, current_story_time)

            logger.info("章节定稿合并提取完成")

        except Exception as e:
            logger.warning(f"角色状态提取失败（非致命）: {e}")

    def _fallback_state_only_extract(self, parsed, characters, text, project):
        """降级处理：仅做角色状态更新（兼容旧格式）"""
        try:
            # 尝试将 parsed 作为旧格式列表处理
            state_list = parsed if isinstance(parsed, list) else None
            if not state_list:
                # 尝试从 text 中解析旧格式 JSON 数组
                import re as _re
                array_match = _re.search(r'\[[\s\S]*\]', text)
                if array_match:
                    state_list = safe_parse_json(array_match.group(0))

            if not state_list or not isinstance(state_list, list):
                logger.warning("降级提取也无法解析状态数据")
                return

            self._process_state_updates(
                [{'character_name': item.get('character_name'), 'updates': item.get('updates', {})}
                 for item in state_list if isinstance(item, dict)],
                characters, project
            )
        except Exception as e:
            logger.warning(f"降级状态提取也失败: {e}")

    def _process_state_updates(self, state_updates, characters, project):
        """处理角色状态更新（覆盖写入 dynamic_states）"""
        char_map = {ch.name: ch for ch in characters}
        updated = 0
        for update_item in state_updates:
            name = (update_item.get("character_name") or "").strip()
            updates = update_item.get("updates", {})
            if not name or not updates:
                continue
            character = char_map.get(name)
            if not character:
                continue
            current_states = character.dynamic_states or {}
            current_states.update(updates)
            character.dynamic_states = current_states
            character.save(update_fields=['dynamic_states'])
            updated += 1
        if updated:
            logger.info(f"角色动态状态更新完成，更新 {updated}/{len(characters)} 个角色")

    def _process_new_characters(self, new_characters, project, chapter=None):
        """处理新发现的角色（自动创建 Character 记录）"""
        from apps.characters.models import Character as CharacterModel

        existing_names = set(
            CharacterModel.objects.filter(project=project, is_deleted=False).values_list('name', flat=True)
        )
        created_count = 0
        for char_data in new_characters:
            if not isinstance(char_data, dict):
                continue
            name = (char_data.get('name') or '').strip()
            if not name or name in existing_names:
                continue
            try:
                char = CharacterModel(
                    project=project,
                    name=name,
                    role_type=char_data.get('role_type', '配角'),
                    gender=char_data.get('gender', '未知'),
                    source='chapter_discover',
                )
                # 设置可选字段
                for field in ['age', 'identity', 'faction', 'personality', 'appearance',
                              'backstory', 'motivation', 'strengths', 'flaws', 'abilities',
                              'weaknesses', 'secrets', 'dark_history', 'development']:
                    val = char_data.get(field)
                    if val is not None:
                        setattr(char, field, val)
                char.save()
                existing_names.add(name)
                created_count += 1
                logger.info(f"章节发现新角色：{name}")
            except Exception as e:
                logger.warning(f"创建新角色「{name}」失败: {e}")
        if created_count:
            logger.info(f"章节定稿发现并创建 {created_count} 个新角色")

    def _process_timeline_events(self, timeline_events, project, chapter, characters):
        """处理剧情事件（创建 TimelineEvent 记录）"""
        from apps.timeline.models import TimelineEvent

        char_map = {ch.name: ch for ch in characters}
        created_count = 0
        for event_data in timeline_events:
            if not isinstance(event_data, dict):
                continue
            title = (event_data.get('title') or '').strip()
            if not title:
                continue
            try:
                event = TimelineEvent(
                    project=project,
                    title=title,
                    description=event_data.get('description', ''),
                    era_unit=event_data.get('era_unit', ''),
                    start_year=event_data.get('start_year', 0),
                    start_month=event_data.get('start_month', 0),
                    end_year=event_data.get('end_year', 0),
                    end_month=event_data.get('end_month', 0),
                    location=event_data.get('location', ''),
                    event_type=event_data.get('event_type', 'main'),
                    is_time_estimated=event_data.get('is_time_estimated', False),
                    chapter=chapter,
                )
                event.save()
                # 关联涉及人物
                char_names = event_data.get('characters') or []
                if isinstance(char_names, list):
                    related_chars = [char_map[n] for n in char_names if n in char_map]
                    if related_chars:
                        event.characters.set(related_chars)
                created_count += 1
            except Exception as e:
                logger.warning(f"创建时间线事件「{title}」失败: {e}")
        if created_count:
            logger.info(f"章节定稿提取并创建 {created_count} 个时间线事件")

    def _create_character_trajectories(self, state_updates, project, chapter, characters, story_time=None):
        """为涉及的角色创建轨迹记录"""
        from apps.characters.models import CharacterTrajectory

        char_map = {ch.name: ch for ch in characters}
        story_year = story_time.get('year') if isinstance(story_time, dict) else None
        story_month = story_time.get('month') if isinstance(story_time, dict) else None

        # 构建时间字符串
        time_str = ''
        if story_year is not None:
            time_str = f"开元{story_year}年"
            if story_month:
                time_str += f"{story_month}月"

        # 获取章节编号用于排序
        chapter_number = getattr(chapter, 'chapter_number', 0) or 0

        trajectories = []
        for update_item in state_updates:
            name = (update_item.get('character_name') or '').strip()
            updates = update_item.get('updates', {})
            if not name:
                continue
            character = char_map.get(name)
            if not character:
                continue

            # 生成轨迹摘要
            summary_parts = []
            if updates.get('current_location'):
                summary_parts.append(f"所在地：{updates['current_location']}")
            if updates.get('emotional_state'):
                summary_parts.append(f"情绪：{updates['emotional_state']}")
            if updates.get('key_events'):
                summary_parts.append(f"事件：{', '.join(updates['key_events'])}")
            summary = '；'.join(summary_parts)

            # 将所有状态字段存入 details JSONField
            details = {
                'location': updates.get('current_location', ''),
                'power_level': updates.get('power_level', ''),
                'faction': updates.get('faction', ''),
                'identity': updates.get('identity', ''),
                'emotional_state': updates.get('emotional_state', ''),
                'physical_state': updates.get('physical_state', ''),
                'relationship_changes': updates.get('relationship_changes', {}),
                'ability_progress': updates.get('ability_progress', ''),
                'key_events': updates.get('key_events', []),
                'summary': summary,
                'raw_data': updates,
            }

            trajectory = CharacterTrajectory(
                character=character,
                project=project,
                source='chapter',
                title=f"第{chapter_number}章状态更新" if chapter_number else '状态更新',
                start_time=time_str,
                end_time=time_str,
                chapter_ids=[chapter.id] if hasattr(chapter, 'id') and chapter.id else [],
                order=chapter_number,
                details=details,
            )
            trajectories.append(trajectory)

        if trajectories:
            CharacterTrajectory.objects.bulk_create(trajectories)
            logger.info(f"创建 {len(trajectories)} 条角色轨迹记录")

    def _update_chapter_story_time(self, chapter, story_time):
        """更新章节的故事时间（存储在 chapter 的 extra_info 或直接记录）"""
        if not isinstance(story_time, dict):
            return
        year = story_time.get('year')
        month = story_time.get('month')
        if year is not None:
            # 将故事时间存储到章节的 content metadata 中（如果有）
            # 这里使用 chapter 的 update_fields 来存储
            try:
                # 检查是否有 story_year/story_month 字段
                if hasattr(chapter, 'story_year'):
                    chapter.story_year = year
                    chapter.story_month = month or 0
                    chapter.save(update_fields=['story_year', 'story_month'])
            except Exception:
                pass

    def adjust_subsequent_outlines(self, volume, completed_chapters, user, project):
        """完成批次后微调后续章节概述"""
        try:
            pending_chapters = ChapterList.objects.filter(
                volume=volume,
                state=ChapterList.STATE_NORMAL,
                status=ChapterList.STATUS_SUMMARY,
            ).order_by('chapter_number')

            if not pending_chapters.exists():
                return

            completed_summaries = "\n".join([
                f"第{ch.chapter_number}章 {ch.title}：{ch.content[-CHAPTER_TAIL_CONTEXT_LENGTH:] if ch.content else ch.summary}"
                for ch in completed_chapters[:3]
            ])
            pending_summaries = "\n".join([
                f"第{ch.chapter_number}章 {ch.title}：{ch.summary}"
                for ch in pending_chapters[:10]
            ])

            llm = get_llm(user=user, scene="chapter_outline_adjust")
            prompt = ChatPromptTemplate.from_messages([
                ("system", CHAPTER_OUTLINE_ADJUST_SYSTEM_PROMPT),
                ("human", CHAPTER_OUTLINE_ADJUST_USER_PROMPT),
            ])
            chain = prompt | llm
            result = call_llm_with_retry(
                chain,
                input_vars={
                    "volume_title": volume.title,
                    "volume_summary": volume.summary or "",
                    "completed_summaries": completed_summaries,
                    "pending_summaries": pending_summaries,
                },
                user=user,
                scene="chapter_outline_adjust",
                project=project,
                task_type="chapter_outline_adjust",
            )

            text = result.content if hasattr(result, 'content') else str(result)
            adjusted = safe_parse_json(text)
            if not adjusted or not isinstance(adjusted, dict):
                return

            adjusted_list = adjusted.get("adjusted_chapters", [])
            for item in adjusted_list:
                ch_num = item.get("chapter_number")
                new_summary = item.get("adjusted_summary")
                if ch_num and new_summary:
                    chapter = pending_chapters.filter(chapter_number=ch_num).first()
                    if chapter:
                        chapter.summary = new_summary
                        chapter.save(update_fields=['summary'])
        except Exception as e:
            logger.warning(f"概述微调失败（非致命）: {e}")

    def validate_chapter_id(self, request):
        """校验 chapter_id 参数（仅校验参数存在性，不查询数据库）"""
        chapter_id = request.data.get('chapter_id')
        if not chapter_id:
            return None, JsonResponse({'success': False, 'message': '缺少chapter_id'}, status=400)
        return chapter_id, None

    def _get_vector_retrieval_context(self, project, query_text):
        """J4: 向量语义检索历史相关片段"""
        try:
            from apps.knowledge.retriever import KnowledgeRetriever
            from apps.outline.models import Outline

            retriever = KnowledgeRetriever()
            current_outline = Outline.objects.filter(
                project=project, is_current=True, is_deleted=False
            ).first()
            results = retriever.search_project_with_scores(
                project_id=str(project.pk),
                query=query_text,
                top_k=5,
                threshold=0.55,
                outline_version_id=current_outline.pk if current_outline else None,
            )
            if results:
                parts = []
                for doc_type, score, content in results[:5]:
                    parts.append(f"[{doc_type}] {content}")
                return "\n---\n".join(parts)
        except Exception as e:
            logger.warning(f"向量检索失败（非致命）: {e}")
        return ""


class ApiChapterGenerateView(BaseChapterAPIView):
    """两阶段章节生成：阶段1生成标题+概述，阶段2批次生成正文 + 自动反思修复 + 评分"""

    def post(self, request, project_id):

        volume_id = request.data.get('volume_id')
        if not volume_id:
            return JsonResponse({'success': False, 'message': '缺少volume_id'}, status=400)
        volume = get_object_or_404(
            Volume.objects.select_related('project'),
            pk=volume_id,
            project__user=request.user
        )
        project = volume.project

        # 检查是否已有章节
        existing_chapters = list(ChapterList.objects.filter(volume=volume).order_by('chapter_number'))
        skip_outline = False
        outline_gap_info = None  # { "existing_chapters_text": "第1章...", "missing_range": "第5-10章" }
        if existing_chapters:
            chapters_with_content = sum(
                1 for ch in existing_chapters
                if ch.status in (ChapterList.STATUS_DRAFT, ChapterList.STATUS_PUBLISHED, ChapterList.STATUS_ARCHIVED)
                and ch.content
            )
            if chapters_with_content == len(existing_chapters):
                return JsonResponse({'success': False, 'message': f'该卷已有{len(existing_chapters)}个章节（含已生成内容），请先删除后再重新生成'}, status=400)

            # 检测概述缺口：volume.chapter_count 已知时判断是否有章节缺失
            if volume.chapter_count and volume.chapter_count > 0:
                max_num = max(ch.chapter_number for ch in existing_chapters)
                existing_nums = {ch.chapter_number for ch in existing_chapters}
                all_nums = set(range(1, volume.chapter_count + 1))
                missing_nums = sorted(all_nums - existing_nums)
                # 同时检查 LLM 输出是否超过 chapter_count（部分生成但未完整）
                extra_nums = sorted(existing_nums - all_nums)
                if missing_nums or (max_num < volume.chapter_count) or extra_nums:
                    # 有缺口：让 Phase 1 补全
                    skip_outline = False
                    recent_chapters = existing_chapters[-3:]  # 最后3章
                    existing_text = "\n".join([
                        f"第{ch.chapter_number}章 {ch.title}：{ch.summary or '(无概述)'}"
                        for ch in existing_chapters
                    ])
                    recent_text = "\n".join([
                        f"第{ch.chapter_number}章 {ch.title}：{ch.summary or '(无概述)'}"
                        for ch in recent_chapters
                    ]) if recent_chapters else "(暂无)"
                    missing_range = f"{min(missing_nums or [volume.chapter_count])}-{volume.chapter_count}章" if missing_nums else f"第{max_num + 1}-{volume.chapter_count}章"
                    # 清理多余章节（超过 chapter_count 的）
                    if extra_nums:
                        ChapterList.objects.filter(
                            volume=volume,
                            chapter_number__in=extra_nums
                        ).delete()
                        existing_chapters = [ch for ch in existing_chapters if ch.chapter_number not in extra_nums]
                    outline_gap_info = {
                        "existing_chapters_text": existing_text,
                        "recent_chapters_text": recent_text,
                        "missing_range": missing_range,
                        "existing_count": len(existing_chapters),
                        "target_count": volume.chapter_count,
                    }
                else:
                    # 无缺口 → 所有概述完整，跳过 Phase 1
                    skip_outline = True
            else:
                # volume.chapter_count 未设置，无法判断完整性，直接跳过 Phase 1
                skip_outline = True

        def stream():
            nonlocal skip_outline, existing_chapters, outline_gap_info
            try:
                # 章节数量规划
                if volume.chapter_count:
                    chapter_count_section = f"预估章节数：{volume.chapter_count}章"
                    chapter_count_requirement = "请严格按照预估章节数生成章节，"
                    chapter_count_rule = f"章节数量必须为{volume.chapter_count}章，不能多也不能少"
                    total_chapters = volume.chapter_count
                else:
                    chapter_count_section = ""
                    chapter_count_requirement = "请根据卷大纲合理规划章节数量，"
                    chapter_count_rule = "根据卷大纲的情节走向和节奏，合理确定章节数量"
                    total_chapters = None

                if not skip_outline:
                    # ========== 阶段1：生成标题+概述 ==========
                    yield self.sse_event('progress', {'message': '思考中...', 'phase': 'outline'})

                    llm = get_llm(user=request.user, scene="chapter_batch_generate")

                    outline_input_vars = {
                        "volume_outline": volume.content or volume.summary or "",
                        "volume_number": volume.volume_number,
                        "volume_title": volume.title,
                        "volume_summary": volume.summary or "",
                        "chapter_count_section": chapter_count_section,
                        "chapter_count_requirement": chapter_count_requirement,
                        "chapter_count_rule": chapter_count_rule,
                        "existing_chapters_info": "",
                        "gap_instruction": "",
                    }
                    # 补全模式：告诉 LLM 已有哪些章节，只生成缺失的
                    if outline_gap_info:
                        outline_input_vars["existing_chapters_info"] = (
                            f"【已有章节概述（直接复用，不要重新生成）】\n"
                            f"已生成 {outline_gap_info['existing_count']}/{outline_gap_info['target_count']} 章：\n"
                            f"{outline_gap_info['recent_chapters_text']}\n"
                            f"(以上为最后3章概述，更多已有章节不再列出)\n"
                        )
                        outline_input_vars["gap_instruction"] = (
                            f"【补全要求】\n"
                            f"你只需要生成缺失章节的概述，范围：{outline_gap_info['missing_range']}。\n"
                            f"已有章节的概述请原样保留勿动，chapter_number 严格按缺失范围输出。\n"
                        )
                    outline_prompt = ChatPromptTemplate.from_messages([
                        ("system", CHAPTER_OUTLINE_SYSTEM_PROMPT),
                        ("human", CHAPTER_OUTLINE_USER_PROMPT),
                    ])
                    outline_chain = outline_prompt | llm

                    yield self.sse_event('progress', {'message': '拆分卷内容中...', 'phase': 'outline'})

                    # 流式接收阶段1，按分隔符切割
                    buffer = ""
                    in_content = False
                    outline_chapters = []
                    chapter_number_counter = 0
                    last_outline_chunk = None

                    for chunk in outline_chain.stream(outline_input_vars):
                        last_outline_chunk = chunk
                        chunk_content = self.get_chunk_text(chunk)
                        buffer += chunk_content

                        while True:
                            if not in_content:
                                start_idx = buffer.find('════CONTENT_START════')
                                if start_idx == -1:
                                    break
                                in_content = True
                                buffer = buffer[start_idx + len('════CONTENT_START════'):]
                            else:
                                end_idx = buffer.find('════CONTENT_END════')
                                if end_idx == -1:
                                    break
                                current_json = buffer[:end_idx].strip()
                                buffer = buffer[end_idx + len('════CONTENT_END════'):]

                                chapter_number_counter += 1
                                chap_data = safe_parse_json(current_json)
                                if chap_data:
                                    chap_number = chap_data.get('chapter_number', chapter_number_counter)
                                    chap_title = chap_data.get('title', f'第{chap_number}章')
                                    chap_summary = chap_data.get('summary', '')

                                    ChapterList.objects.update_or_create(
                                        volume=volume,
                                        chapter_number=chap_number,
                                        defaults={
                                            'title': chap_title,
                                            'summary': chap_summary,
                                            'status': ChapterList.STATUS_SUMMARY,
                                            'word_count': 0,
                                        },
                                    )

                                    outline_chapters.append({
                                        'chapter_number': chap_number,
                                        'title': chap_title,
                                        'summary': chap_summary,
                                    })

                                    yield self.sse_event('outline', {
                                        'chapter': {
                                            'chapter_number': chap_number,
                                            'title': chap_title,
                                            'summary': chap_summary,
                                        },
                                        'current': len(outline_chapters),
                                        'total': total_chapters or 0,
                                    })
                                else:
                                    chap_number = chapter_number_counter
                                    chap_title = f'第{chap_number}章'
                                    ChapterList.objects.create(
                                        volume=volume,
                                        chapter_number=chap_number,
                                        title=chap_title,
                                        summary='',
                                        status=ChapterList.STATUS_SUMMARY,
                                        word_count=0,
                                    )
                                    outline_chapters.append({
                                        'chapter_number': chap_number,
                                        'title': chap_title,
                                        'summary': '',
                                    })
                                    logger.warning(f"阶段1：第{chap_number}章JSON解析失败，创建空占位章节")

                                    yield self.sse_event('outline', {
                                        'chapter': {
                                            'chapter_number': chap_number,
                                            'title': chap_title,
                                            'summary': '',
                                        },
                                        'current': len(outline_chapters),
                                        'total': total_chapters or 0,
                                    })

                                in_content = False

                    if not outline_chapters:
                        yield self.sse_event('error', {'message': '未生成任何章节概述'})
                        return

                    self.log_token_usage('chapter_outline', result=last_outline_chunk, user=request.user, project=project)

                    if not total_chapters:
                        total_chapters = len(outline_chapters)
                else:
                    # 跳过阶段1，使用已有的概述数据
                    outline_chapters = [
                        {'chapter_number': ch.chapter_number, 'title': ch.title, 'summary': ch.summary or ''}
                        for ch in existing_chapters
                    ]
                    if not total_chapters:
                        total_chapters = len(outline_chapters)
                    yield self.sse_event('progress', {'message': f'已有{len(outline_chapters)}章概述，直接开始正文生成...', 'phase': 'content'})

                # ========== 阶段2：批次生成正文（优化版） ==========
                yield self.sse_event('progress', {'message': '准备批次生成...', 'phase': 'content'})

                # 获取基石上下文（缓存命中则跳过 LLM 查询，System Prompt 命中厂商缓存）
                worldview, characters, volume_outline = self.get_cornerstone_context(project, volume)

                # 跳过已有正文的章节（内容非空）
                existing_chapter_numbers = set(
                    ChapterList.objects.filter(
                        volume=volume,
                        chapter_number__in=[ch['chapter_number'] for ch in outline_chapters],
                        status__in=(ChapterList.STATUS_DRAFT, ChapterList.STATUS_PUBLISHED, ChapterList.STATUS_ARCHIVED),
                    ).exclude(content='').values_list('chapter_number', flat=True)
                )
                if existing_chapter_numbers:
                    skipped = []
                    filtered = []
                    for ch in outline_chapters:
                        if ch['chapter_number'] in existing_chapter_numbers:
                            skipped.append(ch['chapter_number'])
                        else:
                            filtered.append(ch)
                    if skipped:
                        yield self.sse_event('progress', {
                            'message': f'跳过已有正文的章节: 第{",".join(str(n) for n in sorted(skipped))}章',
                            'phase': 'content',
                        })
                    outline_chapters = filtered
                    if not outline_chapters:
                        yield self.sse_event('progress', {
                            'message': '所有章节已有正文，跳过正文生成',
                            'phase': 'content',
                        })
                        yield self.sse_event('complete', {
                            'volume_id': volume.pk,
                            'version': volume.version,
                            'chapters_count': 0,
                        })
                        return

                # 分为批次（按连续性断开：章节号不连续则新起一批）
                total_chapters = len(outline_chapters)
                batch_size = BATCH_SIZE
                all_batches = []
                current_batch = []
                for ch in outline_chapters:
                    # 检测连续性：当前章节号不是上一章的下一章，断开批次
                    if current_batch and ch['chapter_number'] != current_batch[-1]['chapter_number'] + 1:
                        all_batches.append(current_batch)
                        current_batch = []
                    current_batch.append(ch)
                    if len(current_batch) >= batch_size:
                        all_batches.append(current_batch)
                        current_batch = []
                if current_batch:
                    all_batches.append(current_batch)

                total_batches = len(all_batches)
                completed_chapter_numbers = []

                for batch_idx, batch_chapters in enumerate(all_batches):
                    first_chap_num = batch_chapters[0]['chapter_number']
                    last_chap_num = batch_chapters[-1]['chapter_number']

                    yield self.sse_event('progress', {
                        'message': f'正在生成第{first_chap_num}-{last_chap_num}章（第{batch_idx + 1}/{total_batches}批）',
                        'phase': 'content',
                        'current': len(completed_chapter_numbers) + len(batch_chapters),
                        'total': total_chapters,
                    })

                    # --- 组装动态上下文（User Prompt 部分） ---
                    # J1: 本批次章节概述
                    batch_chapters_text = "\n".join([
                        f"第{ch['chapter_number']}章 {ch['title']}：{ch['summary']}"
                        for ch in batch_chapters
                    ])

                    # J2: 前N章上下文 + 后M章概述
                    prev_chapters_context, next_chapters_context = self.get_enhanced_adjacent_context(
                        volume, first_chap_num
                    )

                    # J3: 角色动态状态
                    character_dynamic_states = self.get_character_dynamic_states_context(project)

                    # J3.5: 时间线 + 地点上下文
                    timeline_context = self.get_timeline_context(project)
                    location_context = self.get_location_context(project)

                    # J3.6: 角色轨迹 + 关系子图上下文
                    character_trajectories = self.get_character_trajectories_context(project)
                    relationship_subgraph = self.get_relationship_subgraph_context(project)

                    # J4: 向量语义检索
                    search_query = batch_chapters[0]['summary'] or batch_chapters[0]['title']
                    retriever_context = self._get_vector_retrieval_context(project, search_query)

                    # J5: 上一批次摘要
                    prev_batch_context = ""
                    if batch_idx > 0:
                        prev_batch_context = self.get_previous_batch_context(volume, first_chap_num - 1)

                    # --- 构建 LLM 请求 ---
                    # System = 基石上下文（可命中厂商缓存）
                    system_text = CHAPTER_BATCH_CONTENT_SYSTEM_PROMPT.format(
                        worldview=worldview,
                        characters=characters,
                        volume_outline=volume_outline,
                        min_words_per_chapter=project.min_words_per_chapter,
                    )

                    # User = 动态上下文（每次变化）
                    user_text = CHAPTER_BATCH_CONTENT_USER_PROMPT.format(
                        volume_number=volume.volume_number,
                        volume_title=volume.title,
                        volume_summary=volume.summary or "",
                        batch_chapters=batch_chapters_text,
                        prev_batch_context=prev_batch_context,
                        prev_chapters_context=prev_chapters_context,
                        next_chapters_context=next_chapters_context,
                        character_dynamic_states=character_dynamic_states,
                        character_trajectories=character_trajectories,
                        relationship_subgraph=relationship_subgraph,
                        timeline_context=timeline_context,
                        location_context=location_context,
                        relevant_history=retriever_context,
                    )

                    # 直接使用消息列表拼接，避免 f-string 中 {} 冲突
                    messages = [
                        SystemMessage(content=system_text),
                        HumanMessage(content=user_text),
                    ]

                    # --- 生成初稿 ---
                    batch_content = self._generate_batch_content(
                        messages, batch_chapters, user=request.user, project=project
                    )
                    if not batch_content:
                        yield self.sse_event('error', {'message': f'第{first_chap_num}-{last_chap_num}章批次生成失败'})
                        continue

                    # --- 自动反思修复闭环（最多2次） ---
                    batch_content = self._auto_verify_fix_loop(
                        volume, batch_content, batch_chapters,
                        max_loops=MAX_VERIFY_FIX_LOOPS,
                        user=request.user, project=project,
                    )

                    # --- 多维度评分 ---
                    scored_chapters = self._score_batch_chapters(
                        volume, batch_content, batch_chapters,
                        user=request.user, project=project,
                        min_words=project.min_words_per_chapter,
                    )

                    # --- 评分不达标 → 定向重写（最多1次） ---
                    batch_content = self._auto_rewrite_loop(
                        volume, batch_content, batch_chapters, scored_chapters,
                        max_loops=MAX_REWRITE_LOOPS,
                        user=request.user, project=project,
                        system_text=system_text,
                    )

                    # --- 保存定稿 ---
                    for chap_idx, (chap_data, chap_info) in enumerate(zip(batch_content, batch_chapters)):
                        content = chap_data.get('content', '')
                        word_count = len(content)

                        chapter_obj = ChapterList.objects.filter(
                            volume=volume,
                            chapter_number=chap_info['chapter_number']
                        ).first()
                        if chapter_obj:
                            chapter_obj.content = content
                            chapter_obj.word_count = word_count
                            chapter_obj.status = ChapterList.STATUS_DRAFT
                            chapter_obj.save()

                            completed_chapter_numbers.append(chap_info['chapter_number'])

                            yield self.sse_event('chapter', {
                                'chapter': {
                                    'chapter_number': chap_info['chapter_number'],
                                    'title': chap_info['title'],
                                    'content': content,
                                    'word_count': word_count,
                                    'status': 'draft',
                                },
                                'current': len(completed_chapter_numbers),
                                'total': total_chapters,
                            })

                    # --- 定稿后：角色状态提取 ---
                    try:
                        total_batch_content = "\n\n".join([
                            ch.get('content', '') for ch in batch_content
                        ])
                        self.extract_and_update_character_states(project, total_batch_content, request.user)
                    except Exception as e:
                        logger.warning(f"角色状态提取失败（非致命）: {e}")

                    # --- 定稿后：概述微调 ---
                    try:
                        batch_chapter_numbers = [ch['chapter_number'] for ch in batch_chapters]
                        completed_objs = list(ChapterList.objects.filter(
                            volume=volume,
                            chapter_number__in=batch_chapter_numbers,
                            status=ChapterList.STATUS_DRAFT,
                        ))
                        self.adjust_subsequent_outlines(volume, completed_objs, request.user, project)
                    except Exception as e:
                        logger.warning(f"概述微调失败（非致命）: {e}")

                # 完成
                yield self.sse_event('complete', {
                    'volume_id': volume.pk,
                    'version': volume.version,
                    'chapters_count': total_chapters,
                })

            except Exception as e:
                logger.error(f"流式生成章节失败: {e}")
                yield self.sse_event('error', {'message': '章节生成失败，请稍后重试'})

        return self.sse_response(stream)


# ========== 批量章节校验与修复 ==========

class ApiChapterBatchCheckView(BaseChapterAPIView):
    """批量章节校验：每批10章核心，前后各扩展3章上下文"""

    BATCH_SIZE = 10   # 每批核心校验章节数
    OVERLAP = 3       # 前后扩展上下文章节数

    def post(self, request, project_id):
        volume_id = request.data.get('volume_id')
        start_chapter = request.data.get('start_chapter')
        end_chapter = request.data.get('end_chapter')

        if not volume_id:
            return JsonResponse({'success': False, 'message': '缺少 volume_id'}, status=400)
        if not start_chapter or not end_chapter:
            return JsonResponse({'success': False, 'message': '缺少起始/结束章节号'}, status=400)

        try:
            start_chapter = int(start_chapter)
            end_chapter = int(end_chapter)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'message': '章节号格式错误'}, status=400)

        if start_chapter > end_chapter:
            return JsonResponse({'success': False, 'message': '起始章节不能大于结束章节'}, status=400)

        try:
            volume = Volume.objects.get(id=volume_id, project_id=project_id)
        except Volume.DoesNotExist:
            return JsonResponse({'success': False, 'message': '卷不存在'}, status=404)

        # 获取卷中所有有效章节
        all_chapters = list(ChapterList.objects.filter(
            volume=volume,
            state__in=[ChapterList.STATE_NORMAL, ChapterList.STATE_LOCKED],
        ).order_by('chapter_number'))

        if not all_chapters:
            return JsonResponse({'success': False, 'message': '该卷下没有可用章节'}, status=400)

        min_ch = all_chapters[0].chapter_number
        max_ch = all_chapters[-1].chapter_number

        # 扩展前后各3章作为上下文
        context_start = max(min_ch, start_chapter - self.OVERLAP)
        context_end = min(max_ch, end_chapter + self.OVERLAP)

        # 筛选范围内的章节
        review_chapters = [ch for ch in all_chapters
                           if context_start <= ch.chapter_number <= context_end]

        # 按内容划分：前3章（只读上下文）、核心10章（主要校验）、后3章（可修改上下文）
        context_before = [ch for ch in review_chapters if ch.chapter_number < start_chapter]
        main_chapters = [ch for ch in review_chapters
                         if start_chapter <= ch.chapter_number <= end_chapter]
        context_after = [ch for ch in review_chapters if ch.chapter_number > end_chapter]

        # 构建章节文本
        def build_chapter_text(ch):
            content = ch.content or ''
            return f"=== 第{ch.chapter_number}章 {ch.title or ''} ===\n字数: {len(content)}\n{content[:5000]}"

        chapters_text_parts = [build_chapter_text(ch) for ch in review_chapters]
        chapters_text = "\n\n".join(chapters_text_parts)

        def stream():
            try:
                messages = [
                    SystemMessage(content=CHAPTER_BATCH_CHECK_SYSTEM_PROMPT),
                    HumanMessage(content=CHAPTER_BATCH_CHECK_USER_PROMPT.format(
                        volume_title=volume.title,
                        volume_summary=volume.summary or '',
                        context_before_count=len(context_before),
                        context_before_start=context_start if context_before else 0,
                        context_before_end=start_chapter - 1 if context_before else 0,
                        main_count=len(main_chapters),
                        main_start=start_chapter,
                        main_end=end_chapter,
                        context_after_count=len(context_after),
                        context_after_start=end_chapter + 1 if context_after else 0,
                        context_after_end=context_end if context_after else 0,
                        chapters_text=chapters_text,
                    )),
                ]

                result = call_llm_with_retry(
                    messages,
                    user=request.user, scene="chapter_scoring",
                    project=volume.project, task_type="batch_chapter_check",
                )
                text = result.content if hasattr(result, 'content') else str(result)
                check_data = safe_parse_json(text)

                if not check_data or not isinstance(check_data, dict):
                    yield self.sse_event('error', {'message': '校验结果解析失败'})
                    return

                yield self.sse_event('check_result', {
                    'data': check_data,
                    'context_range': [context_start, context_end],
                    'main_range': [start_chapter, end_chapter],
                })

                yield self.sse_event('complete', {'message': '校验完成'})

            except Exception as e:
                logger.error(f"批量章节校验失败: {e}")
                yield self.sse_event('error', {'message': f'校验失败: {str(e)}'})

        return self.sse_response(stream)


class ApiChapterBatchFixView(BaseChapterAPIView):
    """批量章节修复：根据校验问题列表修复章节"""

    def post(self, request, project_id):
        volume_id = request.data.get('volume_id')
        issues = request.data.get('issues', [])

        if not volume_id:
            return JsonResponse({'success': False, 'message': '缺少 volume_id'}, status=400)
        if not issues:
            return JsonResponse({'success': False, 'message': '没有需要修复的问题'}, status=400)

        try:
            volume = Volume.objects.get(id=volume_id, project_id=project_id)
        except Volume.DoesNotExist:
            return JsonResponse({'success': False, 'message': '卷不存在'}, status=404)

        # 收集涉及的所有章节号
        chapter_numbers = set()
        for issue in issues:
            cn = issue.get('chapter_number')
            if cn:
                chapter_numbers.add(int(cn))
        # 也收集跨章节问题的章节号
        for issue in issues:
            chs = issue.get('chapters', [])
            for cn in chs:
                chapter_numbers.add(int(cn))

        if not chapter_numbers:
            return JsonResponse({'success': False, 'message': '无法确定需要修复的章节'}, status=400)

        # 获取相关章节
        chapters = list(ChapterList.objects.filter(
            volume=volume,
            chapter_number__in=chapter_numbers,
            state__in=[ChapterList.STATE_NORMAL, ChapterList.STATE_LOCKED],
        ).order_by('chapter_number'))

        chapter_map = {ch.chapter_number: ch for ch in chapters}

        # 构建上下文：获取所有涉及章节前后各1章作为参考
        all_context_numbers = set(chapter_numbers)
        for cn in chapter_numbers:
            all_context_numbers.add(cn - 1)
            all_context_numbers.add(cn + 1)
        all_context_numbers = {n for n in all_context_numbers
                                if min(chapter_numbers) - 3 <= n <= max(chapter_numbers) + 3}

        context_chapters = list(ChapterList.objects.filter(
            volume=volume,
            chapter_number__in=all_context_numbers,
            state__in=[ChapterList.STATE_NORMAL, ChapterList.STATE_LOCKED],
        ).order_by('chapter_number'))

        def build_chapter_text(ch):
            content = ch.content or ''
            return f"=== 第{ch.chapter_number}章 {ch.title or ''} ===\n{content[:5000]}"

        chapters_text = "\n\n".join([build_chapter_text(ch) for ch in context_chapters])

        # 构建问题文本
        issues_text_parts = []
        for i, issue in enumerate(issues):
            cn = issue.get('chapter_number', '?')
            t = issue.get('type', '?')
            desc = issue.get('description', '')
            suggestion = issue.get('suggestion', '')
            user_comment = issue.get('user_comment', '')
            text = f"问题{i + 1}[第{cn}章][{t}]: {desc}"
            if suggestion:
                text += f"\n  建议: {suggestion}"
            if user_comment:
                text += f"\n  用户意见: {user_comment}"
            issues_text_parts.append(text)
        issues_text = "\n\n".join(issues_text_parts)

        # 记录原内容用于对比
        original_chapters = {}
        for ch in chapters:
            original_chapters[ch.chapter_number] = {
                'id': ch.pk,
                'title': ch.title,
                'content': ch.content,
                'word_count': ch.word_count,
            }

        def stream():
            try:
                messages = [
                    SystemMessage(content=CHAPTER_BATCH_FIX_SYSTEM_PROMPT),
                    HumanMessage(content=CHAPTER_BATCH_FIX_USER_PROMPT.format(
                        volume_title=volume.title,
                        volume_summary=volume.summary or '',
                        chapters_text=chapters_text,
                        issues_text=issues_text,
                    )),
                ]

                result = call_llm_with_retry(
                    messages,
                    user=request.user, scene="chapter_scoring",
                    project=volume.project, task_type="batch_chapter_fix",
                )
                text = result.content if hasattr(result, 'content') else str(result)
                fix_data = safe_parse_json(text)

                if not fix_data or not isinstance(fix_data, (list, dict)):
                    yield self.sse_event('error', {'message': '修复结果解析失败'})
                    return

                # 统一转为列表
                fixed_chapters = fix_data if isinstance(fix_data, list) else fix_data.get('chapters', [fix_data])

                # 构建对比数据
                compare_data = []
                for fc in fixed_chapters:
                    cn = fc.get('chapter_number')
                    if cn is None:
                        continue
                    orig = original_chapters.get(cn, {})
                    compare_data.append({
                        'chapter_number': cn,
                        'chapter_id': orig.get('id'),
                        'original_title': orig.get('title', ''),
                        'original_content': orig.get('content', ''),
                        'modified_title': fc.get('title', orig.get('title', '')),
                        'modified_content': fc.get('content', ''),
                    })

                yield self.sse_event('fix_complete', {
                    'fixed_count': len(compare_data),
                    'compare_data': compare_data,
                })

                yield self.sse_event('complete', {'message': f'修复完成，共{len(compare_data)}章'})

            except Exception as e:
                logger.error(f"批量章节修复失败: {e}")
                yield self.sse_event('error', {'message': f'修复失败: {str(e)}'})

        return self.sse_response(stream)

    # --- 内部辅助方法 ---

    def _generate_batch_content(self, messages, batch_chapters, user=None, project=None):
        """调用 LLM 生成批次章节正文，解析分隔符格式
        重试策略（按时间/Token费用排序）：
          1. safe_parse_json 解析 CONTENT_START/END 块
          2. 正则提取 content 字段
          3. LLM 修复格式
          4. LLM 重新生成（兜底）
        """
        import re as regex_module

        text = None

        # --- 第1次尝试 ---
        try:
            result = call_llm_with_retry(
                messages,
                user=user, scene="chapter_batch_content",
                project=project, task_type="chapter_batch_content",
            )
            text = result.content if hasattr(result, 'content') else str(result)
        except Exception as e:
            logger.error(f"批次 LLM 调用失败: {e}")
            return None

        def parse_with_json_blocks(raw_text):
            """策略1: 解析 CONTENT_START/END 分隔的 JSON"""
            chapters = []
            in_block = False
            block_content = ""
            for line in raw_text.split('\n'):
                if '════CONTENT_START════' in line:
                    in_block = True
                    block_content = ""
                elif '════CONTENT_END════' in line:
                    if in_block:
                        chap_data = safe_parse_json(block_content.strip())
                        if chap_data:
                            chapters.append(chap_data)
                    in_block = False
                    block_content = ""
                elif in_block:
                    block_content += line + "\n"
            return chapters

        def parse_with_regex(raw_text):
            """策略2: 正则提取 - 在 CONTENT_START/END 块中用正则捞 content 和 chapter_number"""
            chapters = []
            # 找到所有 CONTENT_START/END 块
            blocks = regex_module.findall(
                r'════CONTENT_START════\s*\n(.*?)\n\s*════CONTENT_END════',
                raw_text, regex_module.DOTALL
            )
            for block in blocks:
                # 尝试提取 chapter_number
                num_match = regex_module.search(r'"chapter_number"\s*:\s*(\d+)', block)
                cn = int(num_match.group(1)) if num_match else None
                # 尝试提取 content 字段: "content": "..."  （处理多行内容）
                content_match = regex_module.search(r'"content"\s*:\s*"((?:\\.|[^"\\])*)"', block, regex_module.DOTALL)
                content = ""
                if content_match:
                    content = content_match.group(1)
                    # 还原转义
                    content = content.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
                if content or cn:
                    chapters.append({'chapter_number': cn, 'content': content})
            return chapters

        def ask_llm_to_fix_format(raw_text):
            """策略3: 让 LLM 修复格式，返回修复后的文本"""
            fix_messages = [
                SystemMessage(content=(
                    "你是一个JSON格式修复助手。下面是一段包含章节内容的文本，其中使用了 ════CONTENT_START/END════ 标记包裹每章JSON，"
                    "但JSON格式可能不完整或有错误（如未转义的引号、截断的内容、多余的空白等）。\n"
                    "请修复JSON格式，确保每个 CONTENT_START/END 块内的JSON都是有效且完整的。"
                    "只输出修复后的文本，不要添加任何额外说明。"
                )),
                HumanMessage(content=raw_text),
            ]
            try:
                fix_result = call_llm_with_retry(
                    fix_messages,
                    user=user, scene="chapter_batch_content",
                    project=project, task_type="chapter_batch_fix",
                )
                return fix_result.content if hasattr(fix_result, 'content') else str(fix_result)
            except Exception as e:
                logger.warning(f"LLM 格式修复失败: {e}")
                return None

        def ask_llm_to_regenerate():
            """策略4: LLM 重新生成（兜底）"""
            try:
                retry_result = call_llm_with_retry(
                    messages,
                    user=user, scene="chapter_batch_content",
                    project=project, task_type="chapter_batch_content",
                )
                return retry_result.content if hasattr(retry_result, 'content') else str(retry_result)
            except Exception as e:
                logger.error(f"LLM 重新生成失败: {e}")
                return None

        def build_result(chapters):
            """将解析出的章节列表与 batch_chapters 对齐"""
            if not chapters:
                return None
            result_chapters = []
            for i, ch_info in enumerate(batch_chapters):
                found = None
                for ch in chapters:
                    if ch.get('chapter_number') == ch_info['chapter_number']:
                        found = ch
                        break
                if found:
                    result_chapters.append(found)
                else:
                    if i < len(chapters):
                        chapters[i]['chapter_number'] = ch_info['chapter_number']
                        result_chapters.append(chapters[i])
                    else:
                        logger.warning(f"批次正文缺少第{ch_info['chapter_number']}章")
                        result_chapters.append({
                            'chapter_number': ch_info['chapter_number'],
                            'content': '',
                        })
            return result_chapters

        # --- 策略1: JSON 块解析 ---
        chapters = parse_with_json_blocks(text)
        if chapters:
            return build_result(chapters)

        logger.warning(f"批次正文 JSON 解析失败，原始文本前500字符: {text[:500]}")

        # --- 策略2: 正则提取 ---
        logger.info("尝试正则提取...")
        chapters = parse_with_regex(text)
        if chapters:
            logger.info(f"正则提取成功，解析出 {len(chapters)} 章")
            return build_result(chapters)

        # --- 策略3: LLM 修复格式 ---
        logger.info("尝试 LLM 修复格式...")
        fixed_text = ask_llm_to_fix_format(text)
        if fixed_text:
            chapters = parse_with_json_blocks(fixed_text)
            if chapters:
                logger.info(f"LLM 修复后 JSON 解析成功，解析出 {len(chapters)} 章")
                return build_result(chapters)
            chapters = parse_with_regex(fixed_text)
            if chapters:
                logger.info(f"LLM 修复后正则提取成功，解析出 {len(chapters)} 章")
                return build_result(chapters)

        # --- 策略4: LLM 重新生成（兜底） ---
        logger.warning("所有解析策略失败，尝试 LLM 重新生成...")
        new_text = ask_llm_to_regenerate()
        if not new_text:
            logger.error("LLM 重新生成失败，批次生成彻底失败")
            return None

        chapters = parse_with_json_blocks(new_text)
        if not chapters:
            chapters = parse_with_regex(new_text)
        if chapters:
            return build_result(chapters)

        logger.error(f"批次正文所有策略均失败，最终文本前500字符: {new_text[:500]}")
        return None

    def _auto_verify_fix_loop(self, volume, batch_content, batch_chapters, max_loops=2, user=None, project=None):
        """自动反思修复闭环：校验 → 修复 → 再校验，最多 N 次"""
        for loop_idx in range(max_loops):
            has_issues = False
            for chap_idx, (chap_data, chap_info) in enumerate(zip(batch_content, batch_chapters)):
                content = chap_data.get('content', '')
                if not content:
                    continue

                # 获取上一章内容（批次内前一篇或已完成的前一章）
                prev_content = ""
                if chap_idx > 0:
                    prev_content = batch_content[chap_idx - 1].get('content', '')
                else:
                    prev_obj = ChapterList.objects.filter(
                        volume=volume,
                        chapter_number=chap_info['chapter_number'] - 1,
                        status=ChapterList.STATUS_DRAFT,
                    ).first()
                    if prev_obj:
                        prev_content = prev_obj.content or ""

                # 调用校验
                try:
                    issues = self._verify_single_chapter(
                        volume, chap_info['chapter_number'], chap_info['title'],
                        content, prev_content, user=user, project=project,
                    )
                except Exception as e:
                    logger.warning(f"校验第{chap_info['chapter_number']}章失败: {e}")
                    continue

                if issues and not any(issue.get('type') == 'pass' for issue in issues):
                    has_issues = True
                    # 构建修复请求
                    issues_text = "\n".join([
                        f"- [{issue.get('type', 'unknown')}] {issue.get('description', '')}"
                        for issue in issues
                    ])

                    try:
                        fixed_content = self._fix_single_chapter(
                            volume, chap_info['chapter_number'], chap_info['title'],
                            content, issues_text, user=user, project=project,
                        )
                        if fixed_content:
                            batch_content[chap_idx]['content'] = fixed_content
                            logger.info(f"第{chap_info['chapter_number']}章修复完成 (第{loop_idx + 1}轮)")
                    except Exception as e:
                        logger.warning(f"修复第{chap_info['chapter_number']}章失败: {e}")

            if not has_issues:
                logger.info(f"自动校验通过（第{loop_idx + 1}轮），无需修复")
                break

        return batch_content

    def _verify_single_chapter(self, volume, chapter_number, chapter_title, chapter_content, prev_content="", user=None, project=None):
        """调用校验 LLM 发现章节问题，返回问题列表"""
        input_vars = {
            "volume_outline": volume.content or volume.summary or "",
            "volume_title": volume.title,
            "volume_summary": volume.summary or "",
            "prev_chapter_content": prev_content,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "chapter_content": chapter_content,
        }

        llm = get_llm(user=user, scene="chapter_verify")
        prompt = ChatPromptTemplate.from_messages([
            ("system", CHAPTER_VERIFY_SYSTEM_PROMPT),
            ("human", CHAPTER_VERIFY_USER_PROMPT),
        ])
        chain = prompt | llm
        result = call_llm_with_retry(
            chain, input_vars=input_vars,
            user=user, scene="chapter_verify",
            project=project, task_type="chapter_verify",
        )

        text = result.content if hasattr(result, 'content') else str(result)
        return self._parse_verify_issues(text)

    def _parse_verify_issues(self, text):
        """从校验结果中解析问题列表（══ITEM_START/END════ 格式）"""
        issues = []
        in_item = False
        item_content = ""
        for line in text.split('\n'):
            if '════ITEM_START════' in line:
                in_item = True
                item_content = ""
            elif '════ITEM_END════' in line:
                if in_item:
                    issue = safe_parse_json(item_content.strip())
                    if issue:
                        issues.append(issue)
                in_item = False
                item_content = ""
            elif in_item:
                item_content += line + "\n"
        return issues

    def _fix_single_chapter(self, volume, chapter_number, chapter_title, chapter_content, issues_text, user=None, project=None):
        """调用修复 LLM 修复章节问题"""
        input_vars = {
            "volume_title": volume.title,
            "volume_summary": volume.summary or "",
            "volume_outline": volume.content or volume.summary or "",
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "chapter_content": chapter_content,
            "issues_text": issues_text,
        }

        llm = get_llm(user=user, scene="chapter_verify")
        prompt = ChatPromptTemplate.from_messages([
            ("system", CHAPTER_VERIFY_FIX_SYSTEM_PROMPT),
            ("human", CHAPTER_VERIFY_FIX_USER_PROMPT),
        ])
        chain = prompt | llm
        result = call_llm_with_retry(
            chain, input_vars=input_vars,
            user=user, scene="chapter_verify",
            project=project, task_type="chapter_verify_fix",
        )

        return result.content if hasattr(result, 'content') else str(result)

    def _score_batch_chapters(self, volume, batch_content, batch_chapters, user=None, project=None, min_words=3000):
        """对批次中每章进行5维度评分（字数不足仅做字数审阅，不评分）"""
        scored = {}
        for chap_data, chap_info in zip(batch_content, batch_chapters):
            content = chap_data.get('content', '')
            if not content:
                scored[chap_info['chapter_number']] = {"average": 100, "low_dimensions": []}
                continue

            # 字数检查：不足则不评分，直接触发重写扩展
            content_len = len(content)
            if content_len < min_words:
                scored[chap_info['chapter_number']] = {
                    "average": 0,
                    "low_dimensions": ["word_count"],
                    "suggestions": {
                        "word_count": f"当前章节字数仅{content_len}字，目标至少{min_words}字，大幅扩展情节描写、对话和场景细节"
                    },
                }
                continue

            try:
                # 获取前后文用于评分
                prev_idx = next((i for i, c in enumerate(batch_chapters) if c['chapter_number'] == chap_info['chapter_number'] - 1), -1)
                prev_tail = batch_content[prev_idx].get('content', '')[-CHAPTER_TAIL_CONTEXT_LENGTH:] if prev_idx >= 0 else ""
                if not prev_tail:
                    prev_obj = ChapterList.objects.filter(
                        volume=volume, chapter_number=chap_info['chapter_number'] - 1,
                        status=ChapterList.STATUS_DRAFT,
                    ).first()
                    if prev_obj:
                        prev_tail = (prev_obj.content or "")[-CHAPTER_TAIL_CONTEXT_LENGTH:]

                next_idx = next((i for i, c in enumerate(batch_chapters) if c['chapter_number'] == chap_info['chapter_number'] + 1), -1)
                next_summary = batch_chapters[next_idx].get('summary', '') if next_idx >= 0 else ""

                # 获取相关角色信息
                project_obj = volume.project
                characters = Character.objects.filter(project=project_obj, is_deleted=False)
                related_characters = "\n".join([
                    f"- {ch.name}: {ch.tagline or (ch.content[:100] if ch.content else '')}"
                    for ch in characters[:5]
                ]) if characters.exists() else ""

                input_vars = {
                    "volume_title": volume.title,
                    "volume_summary": volume.summary or "",
                    "chapter_number": chap_info['chapter_number'],
                    "chapter_title": chap_info['title'],
                    "chapter_content": content,
                    "prev_chapter_tail": prev_tail,
                    "next_chapter_summary": next_summary,
                    "related_characters": related_characters,
                }

                llm = get_llm(user=user, scene="chapter_scoring")
                prompt = ChatPromptTemplate.from_messages([
                    ("system", CHAPTER_SCORING_SYSTEM_PROMPT),
                    ("human", CHAPTER_SCORING_USER_PROMPT),
                ])
                chain = prompt | llm
                result = call_llm_with_retry(
                    chain, input_vars=input_vars,
                    user=user, scene="chapter_scoring",
                    project=project, task_type="chapter_scoring",
                )

                text = result.content if hasattr(result, 'content') else str(result)
                score_data = safe_parse_json(text)
                if score_data and isinstance(score_data, dict):
                    avg = float(score_data.get("average", 0)) * 5  # 0-20 转为 0-100
                    scored[chap_info['chapter_number']] = {
                        "scores": score_data.get("scores", {}),
                        "average": min(100, avg),
                        "low_dimensions": score_data.get("low_dimensions", []),
                        "suggestions": score_data.get("suggestions", {}),
                    }
                else:
                    scored[chap_info['chapter_number']] = {"average": 80, "low_dimensions": []}

            except Exception as e:
                logger.warning(f"评分第{chap_info['chapter_number']}章失败（非致命）: {e}")
                scored[chap_info['chapter_number']] = {"average": 80, "low_dimensions": []}

        return scored

    def _auto_rewrite_loop(self, volume, batch_content, batch_chapters, scored_chapters, max_loops=1, user=None, project=None, system_text=""):
        """自动重写低分章节（最多1次）"""
        for loop_idx in range(max_loops):
            needs_rewrite = False
            for chap_idx, chap_info in enumerate(batch_chapters):
                score_info = scored_chapters.get(chap_info['chapter_number'], {})
                avg_score = score_info.get("average", 80)

                if avg_score < SCORING_PASS_THRESHOLD:
                    needs_rewrite = True
                    low_dims = score_info.get("low_dimensions", [])
                    suggestions = score_info.get("suggestions", {})

                    # 构建定向重写提示
                    rewrite_hints = []
                    word_count_hint = None
                    for dim in low_dims:
                        if dim == "word_count":
                            # 字数不足：优先给出具体的字数目标
                            suggestion = suggestions.get(dim, "")
                            word_count_hint = f"请扩展本章节内容，{suggestion}"
                            continue
                        suggestion = suggestions.get(dim, "")
                        if suggestion:
                            rewrite_hints.append(f"- {dim}: {suggestion}")

                    if word_count_hint:
                        rewrite_hints.insert(0, word_count_hint)

                    if not rewrite_hints:
                        rewrite_hints.append("整体质量需要提升")

                    rewrite_prompt = f"请重新创作第{chap_info['chapter_number']}章，重点改进以下方面：\n" + "\n".join(rewrite_hints)

                    try:
                        messages = [
                            SystemMessage(content=system_text),
                            HumanMessage(content=rewrite_prompt),
                        ]
                        result = call_llm_with_retry(
                            messages,
                            user=user, scene="chapter_batch_content",
                            project=project, task_type="chapter_batch_content",
                        )
                        new_text = result.content if hasattr(result, 'content') else str(result)

                        # 解析新内容
                        in_block = False
                        block_content = ""
                        for line in new_text.split('\n'):
                            if '════CONTENT_START════' in line:
                                in_block = True
                                block_content = ""
                            elif '════CONTENT_END════' in line:
                                if in_block:
                                    chap_data = safe_parse_json(block_content.strip())
                                    if chap_data and chap_data.get('content'):
                                        batch_content[chap_idx]['content'] = chap_data['content']
                                        logger.info(f"第{chap_info['chapter_number']}章重写完成 (第{loop_idx + 1}轮)")
                                in_block = False
                                block_content = ""
                            elif in_block:
                                block_content += line + "\n"
                    except Exception as e:
                        logger.warning(f"重写第{chap_info['chapter_number']}章失败: {e}")

            if not needs_rewrite:
                logger.info(f"评分全部达标，跳过重写")
                break

        return batch_content


def _extract_single_content(raw_text, chapter_number):
    """从 LLM 流式输出中提取单章正文
    支持两种格式：
    1. ════CONTENT_START/END════ 包裹的 JSON（批量格式）
    2. 纯文本正文
    """
    import re as _re

    # 尝试提取 CONTENT_START/END 块
    pattern = r'════CONTENT_START════\s*\n(.*?)\n\s*════CONTENT_END════'
    blocks = _re.findall(pattern, raw_text, _re.DOTALL)
    for block in blocks:
        # 尝试 JSON 解析
        chap_data = safe_parse_json(block.strip())
        if chap_data and isinstance(chap_data, dict):
            content = chap_data.get('content', '')
            if content:
                return content
        # 正则兜底提取 content 字段
        content_match = _re.search(r'"content"\s*:\s*"((?:\\.|[^"\\])*)"', block, _re.DOTALL)
        if content_match:
            content = content_match.group(1)
            content = content.replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"')
            if content:
                return content

    # 纯文本：直接返回（去掉可能的尾部JSON标记行）
    cleaned = _re.sub(r'\s*════CONTENT_(START|END)════', '', raw_text)
    # 去掉可能残留在开头的 JSON 结构标记
    cleaned = _re.sub(r'^\s*\{\s*"chapter_number"\s*:\s*\d+\s*,\s*"content"\s*:\s*"', '', cleaned)
    # 去掉末尾的 "
    cleaned = _re.sub(r'"\s*\}\s*$', '', cleaned)
    return cleaned.strip()


class ApiChapterContentView(BaseChapterAPIView):
    def post(self, request, project_id):
        chapter_id = request.data.get('chapter_id')
        if not chapter_id:
            return JsonResponse({'success': False, 'message': '缺少chapter_id'}, status=400)
        reference_chapter_id = request.data.get('reference_chapter_id')

        chapter = get_object_or_404(
            ChapterList.objects.select_related('volume', 'volume__project'),
            pk=chapter_id, volume__project__user=request.user
        )

        # 内容长度校验
        if chapter.content and len(chapter.content) >= MAX_CONTENT_LENGTH:
            return JsonResponse({'success': False, 'message': f'章节内容已达上限{MAX_CONTENT_LENGTH}字'}, status=400)

        project = chapter.volume.project
        volume = chapter.volume

        # 获取基石上下文（与批量生成一致）
        worldview, characters, volume_outline = self.get_cornerstone_context(project, volume)

        # 获取上下文（前N章 + 后M章概述）
        prev_chapters_context, next_chapters_context = self.get_enhanced_adjacent_context(
            volume, chapter.chapter_number
        )

        # 角色动态状态
        character_dynamic_states = self.get_character_dynamic_states_context(project)

        # 时间线 + 地点上下文
        timeline_context = self.get_timeline_context(project)
        location_context = self.get_location_context(project)

        # 角色轨迹 + 关系子图上下文
        character_trajectories = self.get_character_trajectories_context(project)
        relationship_subgraph = self.get_relationship_subgraph_context(project)

        # 向量语义检索
        search_query = chapter.summary or chapter.title
        retriever_context = self._get_vector_retrieval_context(project, search_query)

        # 上一章完整内容（reference）
        reference_context = ""
        if reference_chapter_id:
            ref_chapter = get_object_or_404(ChapterList, pk=reference_chapter_id, volume__project__user=request.user)
            reference_context = ref_chapter.content or ""
        elif chapter.chapter_number > 1:
            prev_chapter = ChapterList.objects.filter(
                volume=volume,
                chapter_number=chapter.chapter_number - 1,
                status=ChapterList.STATUS_DRAFT,
            ).first()
            if prev_chapter and prev_chapter.content:
                reference_context = prev_chapter.content

        # 构建单章 batch 格式
        batch_chapters_text = f"第{chapter.chapter_number}章 {chapter.title}：{chapter.summary or ''}"

        prev_batch_context = ""
        if reference_context:
            prev_batch_context = f"{reference_context[-3000:]}\n"

        # 构建与批量生成一致的 prompt
        system_text = CHAPTER_BATCH_CONTENT_SYSTEM_PROMPT.format(
            worldview=worldview,
            characters=characters,
            volume_outline=volume_outline,
            min_words_per_chapter=project.min_words_per_chapter,
        )

        user_text = CHAPTER_SINGLE_CONTENT_USER_PROMPT.format(
            chapter_number=chapter.chapter_number,
            volume_number=volume.volume_number,
            volume_title=volume.title,
            volume_summary=volume.summary or "",
            batch_chapters=batch_chapters_text,
            prev_batch_context=prev_batch_context,
            prev_chapters_context=prev_chapters_context,
            next_chapters_context=next_chapters_context,
            character_dynamic_states=character_dynamic_states,
            character_trajectories=character_trajectories,
            relationship_subgraph=relationship_subgraph,
            timeline_context=timeline_context,
            location_context=location_context,
            relevant_history=retriever_context,
        )

        # 额外上下文（写作参考等）
        worldview_ctx, characters_ctx, extra_context = self.get_knowledge_context_for_chapter(project, chapter)
        if extra_context:
            user_text += f"\n\n【额外写作参考】\n{extra_context}"

        def generate():
            full_response = ""
            try:
                llm = get_llm(user=request.user, scene="chapter_batch_content")
                logger.info(f"单章生成 max_tokens={llm.max_tokens}, model={llm.model_name}")
                messages = [
                    SystemMessage(content=system_text),
                    HumanMessage(content=user_text),
                ]

                for chunk_text in call_llm_with_retry(
                    messages,
                    user=request.user, scene="chapter_batch_content",
                    project=project, task_type='chapter_content',
                    stream=True,
                ):
                    if chunk_text:
                        full_response += chunk_text
                        yield self.sse_event('chunk', {'content': chunk_text})

                # 单章 prompt 直接输出纯文本，无需 JSON 解析
                content = full_response.strip()
                if not content:
                    yield self.sse_event('error', {'message': '生成的章节内容为空'})
                    return

                word_count = len(content)
                chapter.content = content
                chapter.word_count = word_count
                chapter.status = ChapterList.STATUS_DRAFT
                chapter.save()
                yield self.sse_event('complete', {'word_count': word_count})

                # 角色状态提取（合并提取：状态更新 + 新角色 + 事件 + 轨迹）
                try:
                    self.extract_and_update_character_states(project, content, request.user, chapter=chapter)
                except Exception as e:
                    logger.warning(f"单章角色状态提取失败（非致命）: {e}")

            except Exception as e:
                logger.error(f"流式生成章节内容失败: {e}")
                yield self.sse_event('error', {'message': '章节内容生成失败，请稍后重试'})

        return self.sse_response(generate)



class ApiChapterVerifyView(BaseChapterAPIView):
    def _verify_chapter_flow(self, volume_outline, volume_title, volume_summary, chapter_number, chapter_title, chapter_content, prev_chapter_content="", user=None, project=None, stream=False):
        input_vars = {
            "volume_outline": volume_outline,
            "volume_title": volume_title,
            "volume_summary": volume_summary,
            "prev_chapter_content": prev_chapter_content,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "chapter_content": chapter_content,
        }

        llm = get_llm(user=user, scene="chapter_verify")
        prompt = ChatPromptTemplate.from_messages([
            ("system", CHAPTER_VERIFY_SYSTEM_PROMPT),
            ("human", CHAPTER_VERIFY_USER_PROMPT),
        ])
        chain = prompt | llm

        if stream:
            return call_llm_with_retry(chain, input_vars=input_vars, user=user, scene="chapter_verify", project=project, task_type='chapter_verify', stream=True)
        else:
            response = call_llm_with_retry(chain, input_vars=input_vars, user=user, scene="chapter_verify", project=project, task_type='chapter_verify')
            return response

    def post(self, request, project_id):
        chapter, err = self.get_chapter(request)
        if err:
            return err

        volume = chapter.volume
        volume_outline = volume.content or volume.summary

        prev_chapter = ChapterList.objects.filter(
            volume=volume,
            chapter_number=chapter.chapter_number - 1,
            state=ChapterList.STATE_NORMAL
        ).first()

        prev_content = prev_chapter.content if prev_chapter else ""

        result_generator = self._verify_chapter_flow(
            volume_outline,
            volume.title,
            volume.summary,
            chapter.chapter_number,
            chapter.title,
            chapter.content,
            prev_content,
            user=request.user,
            project=volume.project,
            stream=True
        )

        def generate():
            full_verification = ""
            try:
                for chunk in result_generator:
                    if chunk:
                        full_verification += chunk
                        yield self.sse_event('chunk', {'content': chunk})

                yield self.sse_event('complete', {'verification': full_verification})

            except Exception as e:
                logger.error(f"流式校验章节失败: {e}")
                yield self.sse_event('error', {'message': str(e)})

        return self.sse_response(generate)


class ApiChapterVerifyFixView(BaseChapterAPIView):
    """章节校验修复 - 根据选中的校验问题+用户意见，流式生成修复后的内容"""

    def post(self, request, project_id):
        chapter, err = self.get_chapter(request)
        if err:
            return err

        volume = chapter.volume
        volume_outline = volume.content or volume.summary

        issues_text = request.data.get('issues_text', '')
        if not issues_text:
            return JsonResponse({'success': False, 'message': '缺少校验问题信息'}, status=400)

        input_vars = {
            "volume_title": volume.title,
            "volume_summary": volume.summary,
            "volume_outline": volume_outline,
            "chapter_number": chapter.chapter_number,
            "chapter_title": chapter.title,
            "chapter_content": chapter.content or '',
            "issues_text": issues_text,
        }

        llm = get_llm(user=request.user, scene="chapter_verify")
        prompt = ChatPromptTemplate.from_messages([
            ("system", CHAPTER_VERIFY_FIX_SYSTEM_PROMPT),
            ("human", CHAPTER_VERIFY_FIX_USER_PROMPT),
        ])
        chain = prompt | llm

        result_generator = call_llm_with_retry(
            chain, input_vars=input_vars,
            user=request.user, scene="chapter_verify",
            project=volume.project,
            task_type='chapter_verify_fix', stream=True
        )

        def generate():
            full_content = ""
            try:
                for chunk in result_generator:
                    if chunk:
                        full_content += chunk
                        yield self.sse_event('chunk', {'content': chunk})

                yield self.sse_event('complete', {'content': full_content})
            except Exception as e:
                logger.error(f"流式修复章节失败: {e}")
                yield self.sse_event('error', {'message': str(e)})

        return self.sse_response(generate)


class ApiChapterSplitView(BaseChapterAPIView):
    """章节拆分 - 流式响应，返回拆分对比数据，不自动保存"""

    def post(self, request, project_id):
        chapter, err = self.get_chapter(request)
        if err:
            return err

        if chapter.status == ChapterList.STATUS_PUBLISHED:
            return JsonResponse({'success': False, 'message': '已发布章节不能拆分'})

        split_mode = request.data.get('split_mode', 'word_count')

        volume = chapter.volume
        volume_outline = volume.content or volume.summary
        original_content = chapter.content or ""
        original_title = chapter.title or ""

        input_vars = {
            "volume_outline": volume_outline,
            "volume_title": volume.title,
            "volume_summary": volume.summary,
            "chapter_number": chapter.chapter_number,
            "chapter_title": chapter.title,
            "chapter_content": chapter.content,
            "next_chapter_number": chapter.chapter_number + 1,
        }

        llm = get_llm(user=request.user, scene="chapter_split")

        if split_mode == 'plot':
            prompt = ChatPromptTemplate.from_messages([
                ("system", CHAPTER_SPLIT_SYSTEM_PROMPT),
                ("human", CHAPTER_SPLIT_BY_PLOT_USER_PROMPT),
            ])
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", CHAPTER_SPLIT_SYSTEM_PROMPT),
                ("human", CHAPTER_SPLIT_USER_PROMPT),
            ])
        chain = prompt | llm

        def generate():
            buffer = ""
            in_content = False
            content_acc = ""  # 累积完整 JSON，不受 TAIL_RESERVE 影响
            split_chapters = []
            CONTENT_START = "════CONTENT_START════"
            CONTENT_END = "════CONTENT_END════"
            # 保留结尾字符防止分片切除标记前缀
            TAIL_RESERVE = max(len(CONTENT_START), len(CONTENT_END)) - 1

            try:
                last_chunk = None
                usage_chunk = None
                full_content = ''
                for chunk in chain.stream(input_vars):
                    last_chunk = chunk
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        usage_chunk = chunk
                    chunk_content = self.get_chunk_text(chunk)
                    full_content += chunk_content
                    buffer += chunk_content

                    while True:
                        if not in_content:
                            idx = buffer.find(CONTENT_START)
                            if idx == -1:
                                # Skip pre-start garbage but reserve tail
                                if len(buffer) > TAIL_RESERVE:
                                    buffer = buffer[-TAIL_RESERVE:]
                                break
                            in_content = True
                            content_acc = ""
                            buffer = buffer[idx + len(CONTENT_START):]
                            break  # 等下一个 LLM chunk，让内容流式发送
                        else:
                            idx = buffer.find(CONTENT_END)
                            if idx == -1:
                                # 流式发送安全部分（保留结尾防止分片）
                                safe_len = len(buffer) - TAIL_RESERVE
                                if safe_len > 0:
                                    safe_part = buffer[:safe_len]
                                    content_acc += safe_part
                                    yield self.sse_event('chunk', {'content': safe_part})
                                    buffer = buffer[safe_len:]
                                break
                            # 找到结束标记 — 尾部剩余也要计入 content_acc
                            content_acc += buffer[:idx]
                            buffer = buffer[idx + len(CONTENT_END):]
                            in_content = False

                            chap_data = safe_parse_json(content_acc.strip())
                            if chap_data:
                                split_chapters.append(chap_data)
                                yield self.sse_event('split_chapter', chap_data)
                            else:
                                logger.warning(f"拆分JSON解析失败: {content_acc[:200]}")

                # Flush remaining buffer
                if in_content and buffer:
                    yield self.sse_event('chunk', {'content': buffer})

                if len(split_chapters) < 2:
                    yield self.sse_event('error', {'message': '拆分结果不完整，请重试'})
                    return

                yield self.sse_event('complete', {
                    'original': {
                        'chapter_id': chapter.pk,
                        'chapter_number': chapter.chapter_number,
                        'title': original_title,
                        'content': original_content,
                    },
                    'split_chapters': split_chapters,
                })

                # 记录 token 使用量
                self.log_token_usage('chapter_split', result=last_chunk, usage_result=usage_chunk, user=request.user, project=volume.project)
            except Exception as e:
                logger.error(f"流式拆分章节失败: {e}")
                yield self.sse_event('error', {'message': str(e)})

        return self.sse_response(generate)


class ApiChapterSaveView(BaseChapterAPIView):
    def post(self, request, project_id):
        chapter_id = request.data.get('chapter_id')

        # 新建章节模式（拆分产生的新章节）
        if not chapter_id or chapter_id == 0:
            volume_id = request.data.get('volume_id')
            chapter_number = request.data.get('chapter_number')
            title = request.data.get('title')
            content = request.data.get('content')

            if not volume_id:
                return JsonResponse({'success': False, 'message': '新建章节缺少volume_id'}, status=400)
            if not title or not title.strip():
                return JsonResponse({'success': False, 'message': '标题不能为空'}, status=400)
            if not chapter_number:
                return JsonResponse({'success': False, 'message': '缺少chapter_number'}, status=400)

            volume = get_object_or_404(
                Volume.objects.select_related('project'),
                pk=volume_id,
                project__user=request.user
            )

            # 后续章节序号后移
            later_chapters = ChapterList.objects.filter(
                volume=volume,
                chapter_number__gte=chapter_number
            ).order_by('-chapter_number')
            for chap in later_chapters:
                chap.chapter_number += 1
                chap.save()

            chapter = ChapterList.objects.create(
                volume=volume,
                chapter_number=chapter_number,
                title=title.strip(),
                summary="",
                content=content or "",
                word_count=len(content) if content else 0,
                status=ChapterList.STATUS_DRAFT,
            )

            return JsonResponse({
                'success': True,
                'chapter': {
                    'id': chapter.pk,
                    'title': chapter.title,
                    'content': chapter.content,
                    'word_count': chapter.word_count,
                    'chapter_number': chapter.chapter_number,
                    'updated_at': chapter.updated_at.isoformat()
                }
            })

        # 现有章节更新模式
        chapter, err = self.get_chapter(request)
        if err:
            return err

        title = request.data.get('title')
        summary = request.data.get('summary')
        content = request.data.get('content')

        if chapter.status == ChapterList.STATUS_PUBLISHED:
            return JsonResponse({'success': False, 'message': '已发布章节不能修改'})

        if chapter.state == ChapterList.STATE_LOCKED:
            return JsonResponse({'success': False, 'message': '章节已锁定，无法修改'})

        if chapter.state == ChapterList.STATE_DELETED:
            return JsonResponse({'success': False, 'message': '章节已删除，无法修改'})

        # 字段长度校验
        if title is not None:
            if not title.strip():
                return JsonResponse({'success': False, 'message': '标题不能为空'}, status=400)
            if len(title) > MAX_TITLE_LENGTH:
                return JsonResponse({'success': False, 'message': f'标题长度不能超过{MAX_TITLE_LENGTH}字'}, status=400)
            chapter.title = title
        if summary is not None:
            if len(summary) > MAX_SUMMARY_LENGTH:
                return JsonResponse({'success': False, 'message': f'摘要长度不能超过{MAX_SUMMARY_LENGTH}字'}, status=400)
            chapter.summary = summary
        if content is not None:
            if len(content) > MAX_CONTENT_LENGTH:
                return JsonResponse({'success': False, 'message': f'内容长度不能超过{MAX_CONTENT_LENGTH}字'}, status=400)
            chapter.content = content
            chapter.word_count = len(content) if content else 0
            # 内容为空时回退到"已生成概述"状态，前端展示"生成正文"按钮
            if not content or not content.strip():
                chapter.status = ChapterList.STATUS_SUMMARY

        chapter.save()

        return JsonResponse({
            'success': True,
            'chapter': {
                'id': chapter.pk,
                'title': chapter.title,
                'summary': chapter.summary,
                'content': chapter.content,
                'word_count': chapter.word_count,
                'status': chapter.status,
                'updated_at': chapter.updated_at.isoformat()
            }
        })


class ApiChapterStatusView(BaseChapterAPIView):
    """章节状态操作：发布、归档、锁定/解锁、软删除、恢复"""
    VALID_ACTIONS = {'publish', 'archive', 'lock', 'unlock', 'soft_delete', 'restore'}

    def post(self, request, project_id):
        chapter, err = self.get_chapter(request)
        if err:
            return err
        action = request.data.get('action')
        if not action:
            return JsonResponse({'success': False, 'message': '缺少action参数'}, status=400)
        if action not in self.VALID_ACTIONS:
            return JsonResponse({'success': False, 'message': f'无效的操作: {action}'}, status=400)

        if action == 'publish':
            if not chapter.content:
                return JsonResponse({'success': False, 'message': '章节无内容，无法发布'})
            if chapter.state != ChapterList.STATE_LOCKED:
                return JsonResponse({'success': False, 'message': '请先锁定章节再发布'})
            chapter.status = ChapterList.STATUS_PUBLISHED
            chapter.published_at = timezone.now()
            chapter.save()
            return JsonResponse({'success': True, 'state': chapter.state, 'status': chapter.status})

        elif action == 'archive':
            chapter.status = ChapterList.STATUS_ARCHIVED
            chapter.save()
            return JsonResponse({'success': True, 'state': chapter.state, 'status': chapter.status})

        elif action == 'lock':
            if chapter.state == ChapterList.STATE_DELETED:
                return JsonResponse({'success': False, 'message': '已删除章节无法锁定'})
            if chapter.state == ChapterList.STATE_LOCKED:
                return JsonResponse({'success': False, 'message': '章节已锁定'})
            chapter.state = ChapterList.STATE_LOCKED
            chapter.save()
            return JsonResponse({'success': True, 'state': chapter.state})

        elif action == 'unlock':
            if chapter.state != ChapterList.STATE_LOCKED:
                return JsonResponse({'success': False, 'message': '章节未锁定'})
            chapter.state = ChapterList.STATE_NORMAL
            chapter.save()
            return JsonResponse({'success': True, 'state': chapter.state})

        elif action == 'soft_delete':
            if chapter.state == ChapterList.STATE_LOCKED:
                return JsonResponse({'success': False, 'message': '章节已锁定，无法删除'})
            if chapter.state == ChapterList.STATE_DELETED:
                return JsonResponse({'success': False, 'message': '章节已删除'})
            chapter.state = ChapterList.STATE_DELETED
            chapter.save()
            return JsonResponse({'success': True, 'state': chapter.state})

        elif action == 'restore':
            if chapter.state != ChapterList.STATE_DELETED:
                return JsonResponse({'success': False, 'message': '该章节未被删除，无需恢复'})
            chapter.state = ChapterList.STATE_NORMAL
            chapter.save()
            return JsonResponse({'success': True, 'state': chapter.state, 'status': chapter.status})


class ApiChapterLoadView(BaseChapterAPIView):
    """按卷加载章节列表（不含正文内容，减少传输量）"""
    def get(self, request, project_id, volume_id):

        volume = get_object_or_404(Volume, pk=volume_id, project__user=request.user)

        chapters = []
        for chap in volume.chapter_list.all().order_by('chapter_number'):
            chapters.append({
                'id': chap.pk,
                'chapter_number': chap.chapter_number,
                'title': chap.title,
                'status': chap.status,
                'state': chap.state,
                'word_count': chap.word_count,
                'updated_at': chap.updated_at.isoformat(),
            })

        return JsonResponse({
            'success': True,
            'chapters': chapters,
        })


class ApiChapterDetailView(BaseChapterAPIView):
    """获取单个章节详细信息（含正文）"""
    def get(self, request, project_id, chapter_id):
        chapter, err = self.get_chapter(request, chapter_id)
        if err:
            return err

        return JsonResponse({
            'success': True,
            'chapter': {
                'id': chapter.pk,
                'chapter_number': chapter.chapter_number,
                'title': chapter.title,
                'summary': chapter.summary,
                'content': chapter.content,
                'status': chapter.status,
                'state': chapter.state,
                'word_count': chapter.word_count,
                'updated_at': chapter.updated_at.isoformat(),
            }
        })


class ApiChapterChatView(BaseChapterAPIView):
    """章节对话写作 - 流式响应，返回修改前后对比，不再自动保存"""

    def _build_chat_context(self, chapter, current_title=None, current_content=None, current_summary=None):
        """构建对话上下文，支持前端传入的当前内容覆盖数据库"""
        volume = chapter.volume
        volume_outline = volume.content or volume.summary or ""

        chapter_title = current_title or chapter.title or "未命名章节"
        chapter_content = current_content or chapter.content or ""
        chapter_summary = current_summary or chapter.summary or ""

        prev_chapter_tail, next_chapter_summary = self.get_adjacent_context(chapter)

        return chapter_title, chapter_content, chapter_summary, volume, volume_outline, prev_chapter_tail, next_chapter_summary

    def post(self, request, project_id):
        chapter, err = self.get_chapter(request)
        if err:
            return err

        if chapter.status == ChapterList.STATUS_PUBLISHED:
            return JsonResponse({'success': False, 'message': '已发布章节不能对话修改'})

        user_message = request.data.get('message')
        if not user_message:
            return JsonResponse({'success': False, 'message': '缺少message参数'}, status=400)
        if len(user_message) > MAX_CHAT_MESSAGE_LENGTH:
            return JsonResponse({'success': False, 'message': f'消息长度不能超过{MAX_CHAT_MESSAGE_LENGTH}字'}, status=400)

        chat_history_raw = request.data.get('history', [])

        # 校验聊天历史格式
        try:
            chat_history = chat_history_raw if isinstance(chat_history_raw, list) else json.loads(chat_history_raw)
            if not isinstance(chat_history, list):
                chat_history = []
            # 过滤无效条目，确保每条都有 role 和 content
            chat_history = [
                msg for msg in chat_history
                if isinstance(msg, dict) and 'role' in msg and 'content' in msg
            ]
        except (json.JSONDecodeError, TypeError):
            chat_history = []

        # 限制聊天历史长度，只保留最近的消息
        if len(chat_history) > MAX_CHAT_HISTORY_LENGTH:
            chat_history = chat_history[-MAX_CHAT_HISTORY_LENGTH:]

        # 获取前端传入的当前内容（弹窗模式下使用修改后的内容继续对话）
        current_title = request.data.get('current_title')
        current_content = request.data.get('current_content')
        current_summary = request.data.get('current_summary')

        chapter_title, chapter_content, chapter_summary, volume, volume_outline, prev_chapter_tail, next_chapter_summary = \
            self._build_chat_context(chapter, current_title, current_content, current_summary)

        # 记录原始数据（用于对比展示）
        original_title = chapter.title or "未命名章节"
        original_content = chapter.content or ""

        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])

        input_vars = {
            "volume_title": volume.title,
            "volume_summary": volume.summary,
            "volume_outline": volume_outline,
            "chapter_number": chapter.chapter_number,
            "chapter_title": chapter_title,
            "chapter_summary": chapter_summary,
            "chapter_content": chapter_content,
            "prev_chapter_tail": prev_chapter_tail,
            "next_chapter_summary": next_chapter_summary,
            "history": history_str,
            "user_message": user_message,
        }

        llm = get_llm(user=request.user, scene="default")
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", CHAPTER_CHAT_WRITE_SYSTEM_PROMPT),
            ("human", CHAPTER_CHAT_WRITE_USER_PROMPT),
        ])
        chain = chat_prompt | llm

        def generate():
            full_response = ""
            try:
                last_chunk = None
                usage_chunk = None
                for chunk in chain.stream(input_vars):
                    last_chunk = chunk
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        usage_chunk = chunk
                    chunk_content = self.get_chunk_text(chunk)
                    full_response += chunk_content
                    yield self.sse_event('chunk', {'content': chunk_content})

                # 记录 token 使用量
                self.log_token_usage('chapter_chat', result=last_chunk, usage_result=usage_chunk, user=request.user, project=chapter.volume.project)

                # 尝试解析 JSON 响应（支持纯JSON或包裹在文本/markdown中）
                try:
                    result = safe_parse_json(full_response)
                    if not result or not isinstance(result, dict):
                        raise ValueError("JSON解析结果非法")

                    response_text = result.get('response', '')
                    new_content = result.get('content', '')
                    new_title = result.get('title', '')

                    # 不再自动保存到数据库
                    final_content = new_content if new_content else chapter_content
                    final_title = new_title if new_title else chapter_title

                    yield self.sse_event('complete', {
                        'response': response_text,
                        'content': final_content,
                        'title': final_title,
                        'original_content': original_content,
                        'original_title': original_title,
                        'chapter_id': chapter.pk,
                        'chapter_number': chapter.chapter_number,
                    })
                except (json.JSONDecodeError, TypeError):
                    # LLM 返回非 JSON，直接作为文本响应
                    yield self.sse_event('complete', {
                        'response': full_response,
                        'content': chapter_content,
                        'title': chapter_title,
                        'original_content': original_content,
                        'original_title': original_title,
                        'chapter_id': chapter.pk,
                        'chapter_number': chapter.chapter_number,
                    })
            except Exception as e:
                logger.error(f"流式对话写作失败: {e}")
                yield self.sse_event('error', {'message': 'AI对话写作失败，请稍后重试'})

        return self.sse_response(generate)


class ApiChapterHardDeleteView(BaseChapterAPIView):
    """永久删除章节（需确认标题）"""
    def post(self, request, project_id):
        chapter, err = self.get_chapter(request)
        if err:
            return err

        confirm_title = request.data.get('confirm_title')
        if not confirm_title:
            return JsonResponse({'success': False, 'message': '缺少confirm_title参数'}, status=400)

        if confirm_title != chapter.title:
            return JsonResponse({'success': False, 'message': '确认标题不匹配'}, status=400)

        chapter.delete()

        return JsonResponse({'success': True})


class ApiChapterReorderView(BaseChapterAPIView):
    """重新排列卷内章节序号"""
    def post(self, request, project_id):
        volume_id = request.data.get('volume_id')
        if not volume_id:
            return JsonResponse({'success': False, 'message': '缺少volume_id'}, status=400)

        volume = get_object_or_404(
            Volume,
            pk=volume_id,
            project__user=request.user
        )

        chapters = ChapterList.objects.filter(
            volume=volume,
            state__in=[ChapterList.STATE_NORMAL, ChapterList.STATE_LOCKED]
        ).order_by('chapter_number')

        with transaction.atomic():
            # 先将所有 chapter_number 设为负值，避免 unique_together 冲突
            for idx, chap in enumerate(chapters):
                chap.chapter_number = -(idx + 1)
                chap.save()

            # 再按顺序设置正确的 chapter_number
            for idx, chap in enumerate(chapters):
                chap.chapter_number = idx + 1
                chap.save()

        return JsonResponse({'success': True, 'chapters_count': chapters.count()})


class ApiReaderReviewView(BaseChapterAPIView):
    """读者模式审阅：每10章一批，重叠3章，以读者视角评估"""

    BATCH_SIZE = 10   # 每批审阅章节数
    OVERLAP = 3       # 重叠章节数

    def post(self, request, project_id):
        volume_id = request.data.get('volume_id')
        if not volume_id:
            return JsonResponse({'success': False, 'message': '缺少 volume_id'}, status=400)

        try:
            volume = Volume.objects.get(id=volume_id, project_id=project_id)
        except Volume.DoesNotExist:
            return JsonResponse({'success': False, 'message': '卷不存在'}, status=404)

        project = volume.project

        # 获取所有有内容的章节
        chapters = list(ChapterList.objects.filter(
            volume=volume,
            state__in=[ChapterList.STATE_NORMAL, ChapterList.STATE_LOCKED],
            status__in=(ChapterList.STATUS_DRAFT, ChapterList.STATUS_PUBLISHED, ChapterList.STATUS_ARCHIVED),
        ).exclude(content='').order_by('chapter_number'))

        if len(chapters) < 2:
            return JsonResponse({'success': False, 'message': '可审阅的章节不足（至少需要2章）'}, status=400)

        total = len(chapters)

        def stream():
            all_reviews = []
            batch_idx = 0
            start = 0

            while start < total:
                # 本批次实际审阅范围
                batch_end = min(start + self.BATCH_SIZE, total)
                batch_chapters = chapters[start:batch_end]

                # 重叠章节：下一批次的 OVERLAP 章在本批次中也审阅
                overlap_start = max(0, start - self.OVERLAP)
                overlap_before = chapters[overlap_start:start] if start > 0 else []

                overlap_count = len(overlap_before)
                review_chapters = overlap_before + batch_chapters

                batch_idx += 1
                total_batches = (total + self.BATCH_SIZE - self.OVERLAP - 1) // (self.BATCH_SIZE - self.OVERLAP)

                yield self.sse_event('progress', {
                    'current': batch_idx,
                    'total': max(total_batches, 1),
                    'chapters': f'第{review_chapters[0].chapter_number}-{review_chapters[-1].chapter_number}章',
                    'message': f'正在审阅第{batch_idx}批...',
                })

                # 构建章节文本
                chapters_text_parts = []
                for ch in review_chapters:
                    chapters_text_parts.append(
                        f"=== 第{ch.chapter_number}章 {ch.title or ''} ===\n{ch.content[:4000]}"
                    )
                chapters_text = "\n\n".join(chapters_text_parts)

                try:
                    messages = [
                        SystemMessage(content=READER_REVIEW_SYSTEM_PROMPT),
                        HumanMessage(content=READER_REVIEW_USER_PROMPT.format(
                            volume_title=volume.title,
                            volume_summary=volume.summary or '',
                            total_chapters=len(review_chapters),
                            overlap_count=overlap_count,
                            chapters_text=chapters_text,
                        )),
                    ]
                    result = call_llm_with_retry(
                        messages,
                        user=request.user, scene="chapter_scoring",
                        project=project, task_type="reader_review",
                    )
                    text = result.content if hasattr(result, 'content') else str(result)
                    review_data = safe_parse_json(text)

                    if review_data and isinstance(review_data, dict):
                        review_data['batch'] = batch_idx
                        review_data['chapter_range'] = [
                            review_chapters[0].chapter_number,
                            review_chapters[-1].chapter_number
                        ]
                        all_reviews.append(review_data)

                        yield self.sse_event('review', {
                            'batch': batch_idx,
                            'review': review_data,
                        })
                    else:
                        logger.warning(f"第{batch_idx}批审阅解析失败")
                        yield self.sse_event('review', {
                            'batch': batch_idx,
                            'error': '审阅结果解析失败',
                        })

                except Exception as e:
                    logger.error(f"第{batch_idx}批审阅失败: {e}")
                    yield self.sse_event('review', {
                        'batch': batch_idx,
                        'error': str(e),
                    })

                # 下一批从 (start + BATCH_SIZE - OVERLAP) 开始
                start = start + self.BATCH_SIZE - self.OVERLAP
                if start < 0:
                    start = 0

            yield self.sse_event('complete', {
                'total_batches': len(all_reviews),
                'all_reviews': all_reviews,
            })

        return self.sse_response(stream)
