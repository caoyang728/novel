"""
Chapter views - 章节相关视图
"""
import json
from django.http import JsonResponse, StreamingHttpResponse
from django.views import View
from django.shortcuts import get_object_or_404
from django.db import transaction
from apps.core.models import Chapter, ChapterVersion, Volume, VolumeVersion, OutlineVersion
from apps.ai.services import LLMService

llm_service = LLMService()


class GenerateChapterSummariesView(View):
    def post(self, request):
        volume_id = request.POST.get('volume_id')
        volume = get_object_or_404(Volume, pk=volume_id, volume_version__project__user=request.user)
        
        chapters_data = llm_service.generate_chapter_summaries(
            volume.volume_version.outline_version.content,
            volume.volume_number,
            volume.title,
            volume.summary
        )
        
        latest_version = volume.chapter_versions.filter(is_deleted=False).order_by('-version_number').first()
        new_version_number = latest_version.version_number + 1 if latest_version else 1
        
        chapter_version = ChapterVersion.objects.create(
            volume=volume,
            version_number=new_version_number
        )
        
        for chap_data in chapters_data:
            Chapter.objects.create(
                chapter_version=chapter_version,
                chapter_number=chap_data['chapter_number'],
                title=chap_data['title'],
                summary=chap_data['summary']
            )
        
        return JsonResponse({
            'success': True,
            'version_id': chapter_version.pk,
            'version_number': chapter_version.version_number,
            'chapters': chapters_data
        })


class GenerateChapterSummariesStreamView(View):
    def post(self, request):
        volume_id = request.POST.get('volume_id')
        volume = get_object_or_404(Volume, pk=volume_id, volume_version__project__user=request.user)
        
        import logging
        logger = logging.getLogger(__name__)
        
        def stream():
            full_response = ""
            chunk_count = 0
            logger.info(f"开始流式生成章节，volume_id: {volume_id}")
            
            try:
                for chunk in llm_service.generate_chapter_summaries_stream(
                    volume.volume_version.outline_version.content,
                    volume.volume_number,
                    volume.title,
                    volume.summary
                ):
                    full_response += chunk
                    chunk_count += 1
                    logger.info(f"收到第 {chunk_count} 个 chunk，长度: {len(chunk)}")
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                logger.info(f"流式接收完成，总长度: {len(full_response)}")
                
                try:
                    result = json.loads(full_response)
                    chapters_data = result.get('chapters', [])
                    
                    latest_version = volume.chapter_versions.filter(is_deleted=False).order_by('-version_number').first()
                    new_version_number = latest_version.version_number + 1 if latest_version else 1
                    
                    chapter_version = ChapterVersion.objects.create(
                        volume=volume,
                        version_number=new_version_number
                    )
                    
                    for chap_data in chapters_data:
                        Chapter.objects.create(
                            chapter_version=chapter_version,
                            chapter_number=chap_data['chapter_number'],
                            title=chap_data['title'],
                            summary=chap_data['summary']
                        )
                    
                    logger.info(f"章节保存完成，共 {len(chapters_data)} 章")
                    yield f"data: {json.dumps({'type': 'complete', 'version_id': chapter_version.pk, 'version_number': chapter_version.version_number, 'chapters_count': len(chapters_data)})}\n\n"
                except json.JSONDecodeError as e:
                    logger.error(f"解析JSON失败: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': '解析响应失败'})}\n\n"
            except Exception as e:
                logger.error(f"流式生成章节失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        response = StreamingHttpResponse(stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class OptimizeChapterSummariesView(View):
    def post(self, request):
        volume_id = request.POST.get('volume_id')
        chapter_version_id = request.POST.get('chapter_version_id')
        user_feedback = request.POST.get('feedback')
        
        volume = get_object_or_404(Volume, pk=volume_id, volume_version__project__user=request.user)
        chapter_version = get_object_or_404(ChapterVersion, pk=chapter_version_id, volume=volume)
        
        current_chapters = []
        for chap in chapter_version.chapters.all():
            current_chapters.append({
                'chapter_number': chap.chapter_number,
                'title': chap.title,
                'summary': chap.summary
            })
        
        chapters_data = llm_service.optimize_chapter_summaries(
            volume.title,
            volume.summary,
            json.dumps(current_chapters),
            user_feedback
        )
        
        new_version_number = chapter_version.version_number + 1
        
        new_chapter_version = ChapterVersion.objects.create(
            volume=volume,
            version_number=new_version_number
        )
        
        for chap_data in chapters_data:
            Chapter.objects.create(
                chapter_version=new_chapter_version,
                chapter_number=chap_data['chapter_number'],
                title=chap_data['title'],
                summary=chap_data['summary']
            )
        
        return JsonResponse({
            'success': True,
            'version_id': new_chapter_version.pk,
            'version_number': new_chapter_version.version_number,
            'chapters': chapters_data
        })


class FinalizeChapterVersionView(View):
    def post(self, request):
        version_id = request.POST.get('version_id')
        chapter_version = get_object_or_404(ChapterVersion, pk=version_id, volume__volume_version__project__user=request.user)
        chapter_version.is_finalized = True
        chapter_version.save()
        return JsonResponse({'success': True})


class GenerateChapterContentView(View):
    def post(self, request):
        chapter_id = request.POST.get('chapter_id')
        reference_chapter_id = request.POST.get('reference_chapter_id')
        
        chapter = get_object_or_404(Chapter, pk=chapter_id, chapter_version__volume__volume_version__project__user=request.user)
        
        reference_content = ""
        if reference_chapter_id:
            ref_chapter = get_object_or_404(Chapter, pk=reference_chapter_id, chapter_version__volume__volume_version__project__user=request.user)
            reference_content = ref_chapter.content
        
        content = llm_service.generate_chapter_content(
            chapter.chapter_version.volume.volume_version.outline_version.content,
            chapter.chapter_version.volume.title,
            chapter.chapter_version.volume.summary,
            chapter.chapter_number,
            chapter.title,
            chapter.summary,
            reference_content
        )
        
        chapter.content = content
        chapter.save()
        
        return JsonResponse({'success': True, 'content': content})


class GenerateChapterContentStreamView(View):
    def post(self, request):
        chapter_id = request.POST.get('chapter_id')
        reference_chapter_id = request.POST.get('reference_chapter_id')
        
        chapter = get_object_or_404(Chapter, pk=chapter_id, chapter_version__volume__volume_version__project__user=request.user)
        
        reference_content = ""
        if reference_chapter_id:
            ref_chapter = get_object_or_404(Chapter, pk=reference_chapter_id, chapter_version__volume__volume_version__project__user=request.user)
            reference_content = ref_chapter.content
        
        import logging
        logger = logging.getLogger(__name__)
        
        def generate():
            full_content = ""
            logger.info(f"开始流式生成章节内容，chapter_id: {chapter_id}")
            try:
                for chunk in llm_service.generate_chapter_content_stream(
                    chapter.chapter_version.volume.volume_version.outline_version.content,
                    chapter.chapter_version.volume.title,
                    chapter.chapter_version.volume.summary,
                    chapter.chapter_number,
                    chapter.title,
                    chapter.summary,
                    reference_content
                ):
                    full_content += chunk
                    logger.debug(f"发送 chunk，长度: {len(chunk)}")
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                logger.info(f"流式内容生成完成，总长度: {len(full_content)}")
                chapter.content = full_content
                chapter.save()
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
            except Exception as e:
                logger.error(f"流式生成章节内容失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class GenerateChaptersBatchView(View):
    def post(self, request):
        chapter_version_id = request.POST.get('chapter_version_id')
        start_chapter = int(request.POST.get('start_chapter', 1))
        end_chapter = int(request.POST.get('end_chapter', 10))
        
        chapter_version = get_object_or_404(ChapterVersion, pk=chapter_version_id, volume__volume_version__project__user=request.user)
        
        chapters = list(chapter_version.chapters.all())
        chapters.sort(key=lambda x: x.chapter_number)
        
        reference_chapter = None
        results = []
        
        for chap in chapters:
            if start_chapter <= chap.chapter_number <= end_chapter:
                reference_content = reference_chapter.content if reference_chapter else ""
                
                content = llm_service.generate_chapter_content(
                    chapter_version.volume.volume_version.outline_version.content,
                    chapter_version.volume.title,
                    chapter_version.volume.summary,
                    chap.chapter_number,
                    chap.title,
                    chap.summary,
                    reference_content
                )
                
                chap.content = content
                chap.save()
                
                reference_chapter = chap
                results.append({
                    'chapter_number': chap.chapter_number,
                    'title': chap.title,
                    'content_length': len(content)
                })
        
        return JsonResponse({'success': True, 'chapters': results})


class VerifyChapterView(View):
    def post(self, request):
        chapter_id = request.POST.get('chapter_id')
        chapter = get_object_or_404(Chapter, pk=chapter_id, chapter_version__volume__volume_version__project__user=request.user)
        
        volume = chapter.chapter_version.volume
        outline = volume.volume_version.outline_version.content
        
        prev_chapter = chapter.chapter_version.chapters.filter(
            chapter_number=chapter.chapter_number - 1
        ).first()
        
        prev_content = prev_chapter.content if prev_chapter else ""
        
        verification_result = llm_service.verify_chapter_flow(
            outline,
            volume.title,
            volume.summary,
            chapter.chapter_number,
            chapter.title,
            chapter.content,
            prev_content,
            user=request.user,
            project=volume.volume_version.project
        )
        
        return JsonResponse({'success': True, 'verification': verification_result})


class SplitChapterView(View):
    def post(self, request):
        chapter_id = request.POST.get('chapter_id')
        chapter = get_object_or_404(Chapter, pk=chapter_id, chapter_version__volume__volume_version__project__user=request.user)
        
        if chapter.status == Chapter.STATUS_PUBLISHED:
            return JsonResponse({'success': False, 'message': '已发布章节不能拆分'})
        
        volume = chapter.chapter_version.volume
        outline = volume.volume_version.outline_version.content
        
        result = llm_service.split_chapter(
            outline,
            volume.title,
            volume.summary,
            chapter.chapter_number,
            chapter.title,
            chapter.content,
            user=request.user,
            project=volume.volume_version.project
        )
        
        if not result or 'split_chapters' not in result:
            return JsonResponse({'success': False, 'message': '拆分失败，请重试'})
        
        with transaction.atomic():
            chapter_version = chapter.chapter_version
            later_chapters = chapter_version.chapters.filter(
                chapter_number__gt=chapter.chapter_number
            ).order_by('-chapter_number')
            
            for chap in later_chapters:
                chap.chapter_number += 1
                chap.save()
            
            first_chap = result['split_chapters'][0]
            chapter.title = first_chap['title']
            chapter.content = first_chap['content']
            chapter.save()
            
            second_chap = result['split_chapters'][1]
            Chapter.objects.create(
                chapter_version=chapter_version,
                chapter_number=second_chap['chapter_number'],
                title=second_chap['title'],
                summary="",
                content=second_chap['content'],
                status=Chapter.STATUS_DRAFT
            )
        
        return JsonResponse({'success': True, 'message': '拆分成功'})


class ContinueChapterView(View):
    def post(self, request):
        chapter_id = request.POST.get('chapter_id')
        chapter = get_object_or_404(Chapter, pk=chapter_id, chapter_version__volume__volume_version__project__user=request.user)
        
        if chapter.status == Chapter.STATUS_PUBLISHED:
            return JsonResponse({'success': False, 'message': '已发布章节不能延续'})
        
        volume = chapter.chapter_version.volume
        outline = volume.volume_version.outline_version.content
        
        kept_length = min(len(chapter.content), 3100)
        kept_content = chapter.content[:kept_length]
        
        result = llm_service.continue_chapter(
            outline,
            volume.title,
            volume.summary,
            chapter.chapter_number,
            chapter.title,
            kept_content,
            chapter.chapter_number + 1,
            user=request.user,
            project=volume.volume_version.project
        )
        
        if not result or 'original_chapter' not in result or 'new_chapter' not in result:
            return JsonResponse({'success': False, 'message': '延续失败，请重试'})
        
        with transaction.atomic():
            chapter_version = chapter.chapter_version
            later_chapters = chapter_version.chapters.filter(
                chapter_number__gt=chapter.chapter_number
            ).order_by('-chapter_number')
            
            for chap in later_chapters:
                chap.chapter_number += 1
                chap.save()
            
            chapter.title = result['original_chapter']['title']
            chapter.content = result['original_chapter']['content']
            chapter.save()
            
            new_chap = result['new_chapter']
            Chapter.objects.create(
                chapter_version=chapter_version,
                chapter_number=new_chap['chapter_number'],
                title=new_chap['title'],
                summary="",
                content=new_chap['content'],
                status=Chapter.STATUS_DRAFT
            )
        
        return JsonResponse({'success': True, 'message': '延续成功'})


class OptimizeChapterContentView(View):
    def post(self, request):
        chapter_id = request.POST.get('chapter_id')
        chapter = get_object_or_404(Chapter, pk=chapter_id, chapter_version__volume__volume_version__project__user=request.user)
        
        if chapter.status == Chapter.STATUS_PUBLISHED:
            return JsonResponse({'success': False, 'message': '已发布章节不能优化'})
        
        volume = chapter.chapter_version.volume
        outline = volume.volume_version.outline_version.content
        
        optimized_content = llm_service.optimize_chapter_content(
            outline,
            volume.title,
            volume.summary,
            chapter.chapter_number,
            chapter.title,
            chapter.content,
            user=request.user,
            project=volume.volume_version.project
        )
        
        chapter.content = optimized_content
        chapter.save()
        
        return JsonResponse({'success': True, 'content': optimized_content})


class SaveChapterView(View):
    def post(self, request):
        chapter_id = request.POST.get('chapter_id')
        title = request.POST.get('title')
        summary = request.POST.get('summary')
        content = request.POST.get('content')
        
        chapter = get_object_or_404(Chapter, pk=chapter_id, chapter_version__volume__volume_version__project__user=request.user)
        
        if chapter.status == Chapter.STATUS_PUBLISHED:
            return JsonResponse({'success': False, 'message': '已发布章节不能修改'})
        
        chapter.title = title
        chapter.summary = summary
        chapter.content = content
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


class PublishChapterView(View):
    def post(self, request):
        chapter_id = request.POST.get('chapter_id')
        chapter = get_object_or_404(Chapter, pk=chapter_id, chapter_version__volume__volume_version__project__user=request.user)
        
        from django.utils import timezone
        
        chapter.status = Chapter.STATUS_PUBLISHED
        chapter.published_at = timezone.now()
        chapter.save()
        
        return JsonResponse({'success': True})


class ArchiveChapterView(View):
    def post(self, request):
        chapter_id = request.POST.get('chapter_id')
        chapter = get_object_or_404(Chapter, pk=chapter_id, chapter_version__volume__volume_version__project__user=request.user)
        
        chapter.status = Chapter.STATUS_ARCHIVED
        chapter.save()
        
        return JsonResponse({'success': True})


class LoadChapterVersionsView(View):
    def get(self, request, volume_version_id):
        from apps.core.models import VolumeVersion
        volume_version = get_object_or_404(VolumeVersion, pk=volume_version_id, project__user=request.user)
        
        chapter_versions = []
        all_chapters = []
        
        for volume in volume_version.volumes.all():
            for cv in volume.chapter_versions.filter(is_deleted=False).order_by('-version_number'):
                if cv.pk not in [v['id'] for v in chapter_versions]:
                    chapters = []
                    for chap in cv.chapters.all():
                        chapters.append({
                            'id': chap.pk,
                            'chapter_number': chap.chapter_number,
                            'title': chap.title,
                            'summary': chap.summary,
                            'content': chap.content,
                            'status': chap.status,
                            'word_count': chap.word_count,
                            'published_at': chap.published_at.isoformat() if chap.published_at else None,
                            'created_at': chap.created_at.isoformat(),
                            'updated_at': chap.updated_at.isoformat()
                        })
                        all_chapters.extend(chapters)
                    
                    chapter_versions.append({
                        'id': cv.pk,
                        'version_number': cv.version_number,
                        'volume_id': volume.pk,
                        'volume_title': volume.title,
                        'chapters': chapters,
                        'created_at': cv.created_at.isoformat()
                    })
        
        return JsonResponse({
            'success': True,
            'versions': chapter_versions,
            'all_chapters': all_chapters
        })


class SetCurrentChapterVersionView(View):
    def post(self, request):
        chapter_version_id = request.POST.get('chapter_version_id')
        chapter_version = get_object_or_404(ChapterVersion, pk=chapter_version_id, volume__volume_version__project__user=request.user)
        
        chapter_version.is_current = True
        chapter_version.save()
        
        ChapterVersion.objects.filter(
            volume=chapter_version.volume,
            is_current=True
        ).exclude(pk=chapter_version.pk).update(is_current=False)
        
        return JsonResponse({'success': True})


class ChatChapterWriteView(View):
    def post(self, request):
        chapter_id = request.POST.get('chapter_id')
        user_message = request.POST.get('message')
        chat_history_json = request.POST.get('history', '[]')
        
        try:
            chat_history = json.loads(chat_history_json)
        except json.JSONDecodeError:
            chat_history = []
        
        chapter = get_object_or_404(Chapter, pk=chapter_id, chapter_version__volume__volume_version__project__user=request.user)
        
        chapter_title = chapter.title or "未命名章节"
        chapter_content = chapter.content or ""
        
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history])
        
        prompt = f"""
小说大纲：{chapter.chapter_version.volume.volume_version.outline_version.content[:500]}...

卷标题：{chapter.chapter_version.volume.title}
卷摘要：{chapter.chapter_version.volume.summary[:300]}...

当前章节：
标题：{chapter_title}
内容：{chapter_content[:500]}...

历史对话：
{history_str}

用户指令：{user_message}

请根据用户指令对章节内容进行修改或续写。请严格按照JSON格式返回：
{{
  "response": "对用户的回复",
  "content": "修改后的章节内容",
  "title": "新的章节标题（如果需要修改）"
}}
"""
        
        response = llm_service._call_with_retry([
            SystemMessage(content="你是一位专业的小说创作助手，擅长根据用户指令创作和修改章节内容。请严格按照JSON格式返回。"),
            HumanMessage(content=prompt)
        ])
        
        try:
            result = json.loads(response.content)
            response_text = result.get('response', '')
            new_content = result.get('content', '')
            new_title = result.get('title', '')
            
            if new_content and new_content != chapter_content:
                chapter.content = new_content
                chapter.save()
            
            if new_title and new_title != chapter_title:
                chapter.title = new_title
                chapter.save()
            
            return JsonResponse({
                'success': True,
                'response': response_text,
                'content': chapter.content,
                'title': chapter.title
            })
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': '解析响应失败'
            })
