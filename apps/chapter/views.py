import json
from loguru import logger
from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone

from langchain_core.prompts import ChatPromptTemplate

from apps.project.base import BaseAPIView
from apps.chapter.models import ChapterList
from apps.volume.models import VolumeList
from apps.ai.llm import get_llm, call_llm_with_retry, log_token_usage
from utils.constants import MAX_CONTENT_LENGTH, MAX_TITLE_LENGTH, MAX_SUMMARY_LENGTH, PREV_CHAPTER_TAIL_LENGTH, MAX_CHAT_MESSAGE_LENGTH, MAX_CHAT_HISTORY_LENGTH
from utils.helpers import safe_parse_json
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
            chapter = ChapterList.objects.select_related('volume', 'volume__volume_version', 'volume__volume_version__project').get(
                pk=chapter_id, volume__volume_version__project__user=request.user
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

    def validate_chapter_id(self, request):
        """校验 chapter_id 参数（仅校验参数存在性，不查询数据库）"""
        chapter_id = request.data.get('chapter_id')
        if not chapter_id:
            return None, JsonResponse({'success': False, 'message': '缺少chapter_id'}, status=400)
        return chapter_id, None


class ApiChapterGenerateView(BaseChapterAPIView):
    """两阶段章节生成：阶段1生成标题+概述，阶段2逐章生成正文"""

    def post(self, request):

        volume_id = request.data.get('volume_id')
        if not volume_id:
            return JsonResponse({'success': False, 'message': '缺少volume_id'}, status=400)
        volume = get_object_or_404(
            VolumeList.objects.select_related('volume_version__project'),
            pk=volume_id,
            volume_version__project__user=request.user
        )
        project = volume.volume_version.project

        # 检查是否已有章节，避免重复生成
        existing_count = ChapterList.objects.filter(volume=volume).count()
        if existing_count > 0:
            return JsonResponse({'success': False, 'message': f'该卷已有{existing_count}个章节，请先删除后再生成'}, status=400)

        def stream():
            try:
                # 章节数量规划
                if volume.chapter_count:
                    chapter_count_section = f"预估章节数：{volume.chapter_count}章"
                    chapter_count_requirement = f"请严格按照预估章节数生成章节，"
                    chapter_count_rule = f"章节数量必须为{volume.chapter_count}章，不能多也不能少"
                    total_chapters = volume.chapter_count
                else:
                    chapter_count_section = ""
                    chapter_count_requirement = "请根据卷大纲合理规划章节数量，"
                    chapter_count_rule = "根据卷大纲的情节走向和节奏，合理确定章节数量"
                    total_chapters = None

                # ========== 阶段1：生成标题+概述 ==========
                yield self.sse_event('progress', {'message': '思考中...', 'phase': 'outline'})

                llm = get_llm(user=request.user, scene="chapter_generate")

                outline_input_vars = {
                    "volume_outline": volume.content or volume.summary or "",
                    "volume_number": volume.volume_number,
                    "volume_title": volume.title,
                    "volume_summary": volume.summary or "",
                    "chapter_count_section": chapter_count_section,
                    "chapter_count_requirement": chapter_count_requirement,
                    "chapter_count_rule": chapter_count_rule,
                }
                outline_prompt = ChatPromptTemplate.from_messages([
                    ("system", CHAPTER_OUTLINE_SYSTEM_PROMPT),
                    ("human", CHAPTER_OUTLINE_USER_PROMPT),
                ])
                outline_chain = outline_prompt | llm

                yield self.sse_event('progress', {'message': '拆分卷内容中...', 'phase': 'outline'})

                # 流式接收阶段1，按分隔符切割
                buffer = ""
                in_content = False
                outline_chapters = []  # 存储阶段1结果
                chapter_number_counter = 0  # 章节计数器，确保连续

                for chunk in outline_chain.stream(outline_input_vars):
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

                                # 保存到数据库，状态为 summary
                                ChapterList.objects.create(
                                    volume=volume,
                                    chapter_number=chap_number,
                                    title=chap_title,
                                    summary=chap_summary,
                                    status=ChapterList.STATUS_SUMMARY,
                                    word_count=0,
                                )

                                outline_chapters.append({
                                    'chapter_number': chap_number,
                                    'title': chap_title,
                                    'summary': chap_summary,
                                })

                                # 推送概述到前端
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
                                # JSON解析失败，仍然创建空章节占位
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

                # 更新总数（如果之前未知）
                if not total_chapters:
                    total_chapters = len(outline_chapters)

                # ========== 阶段2：逐章生成正文 ==========
                yield self.sse_event('progress', {'message': '生成中...', 'phase': 'content'})

                worldview = self.get_worldview_context(project)
                characters = self.get_characters_context(project)
                volume_outline = volume.content or volume.summary or ""

                for i, chap_info in enumerate(outline_chapters):
                    chap_number = chap_info['chapter_number']
                    chap_title = chap_info['title']
                    chap_summary = chap_info['summary']

                    # 上一章内容
                    if i > 0:
                        prev_chap = outline_chapters[i - 1]
                        prev_chapter_tail = f"【上一章末尾】\n{prev_chap.get('last_content', '')[-PREV_CHAPTER_TAIL_LENGTH:]}"
                    else:
                        prev_chapter_tail = ""

                    # 下一章概述
                    if i < len(outline_chapters) - 1:
                        next_chap = outline_chapters[i + 1]
                        next_chapter_summary = f"【下一章概述】\n第{next_chap['chapter_number']}章 {next_chap['title']}：{next_chap['summary']}"
                    else:
                        next_chapter_summary = ""

                    yield self.sse_event('progress', {
                        'message': f'正在生成第{chap_number}章: {chap_title}',
                        'phase': 'content',
                        'current': i + 1,
                        'total': total_chapters,
                    })

                    content_input_vars = {
                        "worldview": worldview,
                        "characters": characters,
                        "volume_title": volume.title,
                        "volume_summary": volume.summary or "",
                        "volume_outline": volume_outline,
                        "chapter_number": chap_number,
                        "chapter_title": chap_title,
                        "chapter_summary": chap_summary,
                        "prev_chapter_tail": prev_chapter_tail,
                        "next_chapter_summary": next_chapter_summary,
                    }
                    content_prompt = ChatPromptTemplate.from_messages([
                        ("system", CHAPTER_CONTENT_GEN_SYSTEM_PROMPT),
                        ("human", CHAPTER_CONTENT_GEN_USER_PROMPT),
                    ])
                    content_chain = content_prompt | llm

                    try:
                        # 流式生成正文
                        full_content = ""
                        for chunk in content_chain.stream(content_input_vars):
                            chunk_content = self.get_chunk_text(chunk)
                            full_content += chunk_content

                        word_count = len(full_content) if full_content else 0

                        # 更新数据库
                        chapter_obj = ChapterList.objects.filter(
                            volume=volume,
                            chapter_number=chap_number
                        ).first()
                        if chapter_obj:
                            chapter_obj.content = full_content
                            chapter_obj.word_count = word_count
                            chapter_obj.status = ChapterList.STATUS_DRAFT
                            chapter_obj.save()

                        # 记录内容用于下章衔接
                        chap_info['last_content'] = full_content

                        # 推送到前端
                        yield self.sse_event('chapter', {
                            'chapter': {
                                'chapter_number': chap_number,
                                'title': chap_title,
                                'content': full_content,
                                'word_count': word_count,
                                'status': 'draft',
                            },
                            'current': i + 1,
                            'total': total_chapters,
                        })

                    except Exception as e:
                        logger.error(f"生成第{chap_number}章内容失败: {e}")
                        # 标记为生成失败，但保留章节记录
                        chapter_obj = ChapterList.objects.filter(
                            volume=volume,
                            chapter_number=chap_number
                        ).first()
                        if chapter_obj:
                            chapter_obj.status = ChapterList.STATUS_FAILED
                            chapter_obj.save()

                        yield self.sse_event('chapter_failed', {
                            'chapter_number': chap_number,
                            'title': chap_title,
                            'message': str(e),
                        })

                # 完成
                yield self.sse_event('complete', {
                    'volume_id': volume.pk,
                    'volume_version_id': volume.volume_version.pk,
                    'chapters_count': len(outline_chapters),
                })

            except Exception as e:
                logger.error(f"流式生成章节失败: {e}")
                yield self.sse_event('error', {'message': '章节生成失败，请稍后重试'})

        return self.sse_response(stream)


class ApiChapterContentView(BaseChapterAPIView):
    def _generate_chapter_content_stream(self, volume_outline, volume_title, volume_summary, chapter_number, chapter_title, chapter_summary, reference_content=None, user=None, project=None, worldview="", characters=""):
        reference_context = ""
        if reference_content:
            reference_context = f"上一章节的内容（作为写作参考，保持风格和情节连续性）:\n{reference_content}\n\n"

        llm = get_llm(user=user, scene="content_generate")

        input_vars = {
            "volume_outline": volume_outline,
            "volume_title": volume_title,
            "volume_summary": volume_summary,
            "chapter_number": chapter_number,
            "chapter_title": chapter_title,
            "chapter_summary": chapter_summary,
            "reference_context": reference_context,
            "worldview": worldview,
            "characters": characters,
        }

        prompt = ChatPromptTemplate.from_messages([
            ("system", CHAPTER_CONTENT_SYSTEM_PROMPT),
            ("human", CHAPTER_CONTENT_USER_PROMPT),
        ])
        chain = prompt | llm

        for chunk in call_llm_with_retry(chain, input_vars=input_vars, stream=True, user=user, scene="content_generate", project=project):
            if chunk:
                yield chunk

    def post(self, request):
        chapter_id = request.data.get('chapter_id')
        if not chapter_id:
            return JsonResponse({'success': False, 'message': '缺少chapter_id'}, status=400)
        reference_chapter_id = request.data.get('reference_chapter_id')

        chapter = get_object_or_404(
            ChapterList.objects.select_related('volume', 'volume__volume_version', 'volume__volume_version__project'),
            pk=chapter_id, volume__volume_version__project__user=request.user
        )

        # 内容长度校验
        if chapter.content and len(chapter.content) >= MAX_CONTENT_LENGTH:
            return JsonResponse({'success': False, 'message': f'章节内容已达上限{MAX_CONTENT_LENGTH}字'}, status=400)

        reference_content = ""
        if reference_chapter_id:
            ref_chapter = get_object_or_404(ChapterList, pk=reference_chapter_id, volume__volume_version__project__user=request.user)
            reference_content = ref_chapter.content

        project = chapter.volume.volume_version.project
        worldview = self.get_worldview_context(project)
        characters = self.get_characters_context(project)

        def generate():
            full_content = ""
            # logger.info(f"开始流式生成章节内容，chapter_id: {chapter_id}")
            try:
                volume = chapter.volume
                for chunk in self._generate_chapter_content_stream(
                    volume.content or volume.summary,
                    volume.title,
                    volume.summary,
                    chapter.chapter_number,
                    chapter.title,
                    chapter.summary,
                    reference_content,
                    user=request.user,
                    project=project,
                    worldview=worldview,
                    characters=characters,
                ):
                    full_content += chunk
                    yield self.sse_event('chunk', {'content': chunk})

                # logger.info(f"流式内容生成完成，总长度: {len(full_content)}")
                word_count = len(full_content) if full_content else 0
                chapter.content = full_content
                chapter.word_count = word_count
                chapter.status = ChapterList.STATUS_DRAFT
                chapter.save()
                yield self.sse_event('complete', {'word_count': word_count})
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

        llm = get_llm(user=user, scene="default")
        prompt = ChatPromptTemplate.from_messages([
            ("system", CHAPTER_VERIFY_SYSTEM_PROMPT),
            ("human", CHAPTER_VERIFY_USER_PROMPT),
        ])
        chain = prompt | llm

        if stream:
            return call_llm_with_retry(chain, input_vars=input_vars, user=user, scene="default", project=project, task_type='content', stream=True)
        else:
            response = call_llm_with_retry(chain, input_vars=input_vars, user=user, scene="default", project=project, task_type='content')
            return response

    def post(self, request):
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
            project=volume.volume_version.project,
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

    def post(self, request):
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

        llm = get_llm(user=request.user, scene="default")
        prompt = ChatPromptTemplate.from_messages([
            ("system", CHAPTER_VERIFY_FIX_SYSTEM_PROMPT),
            ("human", CHAPTER_VERIFY_FIX_USER_PROMPT),
        ])
        chain = prompt | llm

        result_generator = call_llm_with_retry(
            chain, input_vars=input_vars,
            user=request.user, scene="default",
            project=volume.volume_version.project,
            task_type='content', stream=True
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

    def post(self, request):
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

        llm = get_llm(user=request.user, scene="chapter_generate")

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
            CONTENT_START = "══CONTENT_START════"
            CONTENT_END = "════CONTENT_END════"
            # 保留结尾字符防止分片切除标记前缀
            TAIL_RESERVE = max(len(CONTENT_START), len(CONTENT_END)) - 1

            try:
                for chunk in chain.stream(input_vars):
                    chunk_content = self.get_chunk_text(chunk)
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
            except Exception as e:
                logger.error(f"流式拆分章节失败: {e}")
                yield self.sse_event('error', {'message': str(e)})

        return self.sse_response(generate)


class ApiChapterSaveView(BaseChapterAPIView):
    def post(self, request):
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
                VolumeList.objects.select_related('volume_version__project'),
                pk=volume_id,
                volume_version__project__user=request.user
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
        chapter.save()

        return JsonResponse({
            'success': True,
            'chapter': {
                'id': chapter.pk,
                'title': chapter.title,
                'summary': chapter.summary,
                'content': chapter.content,
                'word_count': chapter.word_count,
                'updated_at': chapter.updated_at.isoformat()
            }
        })


class ApiChapterStatusView(BaseChapterAPIView):
    """章节状态操作：发布、归档、锁定/解锁、软删除、恢复"""
    VALID_ACTIONS = {'publish', 'archive', 'lock', 'unlock', 'soft_delete', 'restore'}

    def post(self, request):
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
    def get(self, request, volume_id):

        volume = get_object_or_404(VolumeList, pk=volume_id, volume_version__project__user=request.user)

        chapters = []
        for chap in volume.chapter_list.all().order_by('chapter_number'):
            chapters.append({
                'id': chap.pk,
                'chapter_number': chap.chapter_number,
                'title': chap.title,
                'summary': chap.summary,
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
    def get(self, request, chapter_id):
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

    def post(self, request):
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

        llm = get_llm(user=request.user, scene="content_generate")
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", CHAPTER_CHAT_WRITE_SYSTEM_PROMPT),
            ("human", CHAPTER_CHAT_WRITE_USER_PROMPT),
        ])
        chain = chat_prompt | llm

        def generate():
            full_response = ""
            try:
                for chunk in chain.stream(input_vars):
                    chunk_content = self.get_chunk_text(chunk)
                    full_response += chunk_content
                    yield self.sse_event('chunk', {'content': chunk_content})

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
    def post(self, request):
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
    def post(self, request):
        volume_id = request.data.get('volume_id')
        if not volume_id:
            return JsonResponse({'success': False, 'message': '缺少volume_id'}, status=400)

        volume = get_object_or_404(
            VolumeList,
            pk=volume_id,
            volume_version__project__user=request.user
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
