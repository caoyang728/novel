from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from apps.project.models import ProjectList
from .models import TimelineEvent, TimelineChatHistory
from apps.ai.llm import get_llm
from .prompts import (
    TIMELINE_GENERATION_PROMPT,
    TIMELINE_INCREMENTAL_PROMPT,
    TIMELINE_MERGE_PROMPT,
    TIMELINE_SPLIT_PROMPT,
    DESCRIPTION_OPTIMIZE_PROMPT
)
from langchain_core.messages import HumanMessage, SystemMessage
from django.http import StreamingHttpResponse
import json


class TimelineEventList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        events = TimelineEvent.objects.filter(
            project_id=project_id,
            is_deleted=False
        ).order_by('start_chapter', 'end_chapter')
        
        data = [{
            'id': e.id,
            'title': e.title,
            'description': e.description,
            'start_chapter': e.start_chapter,
            'end_chapter': e.end_chapter,
            'event_order': e.event_order
        } for e in events]
        
        return Response(data)

    def post(self, request, project_id):
        from rest_framework import serializers
        
        event_id = request.data.get('id')
        title = request.data.get('title', '')
        description = request.data.get('description', '')
        start_chapter = request.data.get('start_chapter', 1)
        end_chapter = request.data.get('end_chapter', 1)
        event_order = request.data.get('event_order', 0)

        if not title:
            return Response({'success': False, 'message': '标题不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        project = get_object_or_404(ProjectList, pk=project_id)

        if event_id:
            # 更新现有记录
            try:
                event = TimelineEvent.objects.get(id=event_id, project_id=project_id, is_deleted=False)
                event.title = title
                event.description = description
                event.start_chapter = start_chapter
                event.end_chapter = end_chapter
                event.event_order = event_order
                event.save()
                
                return Response({
                    'success': True,
                    'message': '更新成功',
                    'id': event.id,
                    'title': event.title,
                    'description': event.description,
                    'start_chapter': event.start_chapter,
                    'end_chapter': event.end_chapter,
                    'event_order': event.event_order
                })
            except TimelineEvent.DoesNotExist:
                return Response({'success': False, 'message': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)
        else:
            # 创建新记录
            event = TimelineEvent.objects.create(
                project=project,
                title=title,
                description=description,
                start_chapter=start_chapter,
                end_chapter=end_chapter,
                event_order=event_order
            )
            
            return Response({
                'success': True,
                'message': '创建成功',
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'start_chapter': event.start_chapter,
                'end_chapter': event.end_chapter,
                'event_order': event.event_order
            })


class TimelineEventDetail(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = TimelineEvent.objects.filter(is_deleted=False)
    lookup_field = 'pk'

    def get_serializer_class(self):
        from rest_framework import serializers
        class TimelineEventSerializer(serializers.ModelSerializer):
            class Meta:
                model = TimelineEvent
                fields = ['id', 'title', 'description', 'start_chapter', 'end_chapter', 'event_order']
                read_only_fields = ['id']
        return TimelineEventSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_deleted = True
        instance.save()
        return Response({'success': True, 'message': '删除成功'})


class TimelineChatView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, project_id):
        chats = TimelineChatHistory.objects.filter(
            project_id=project_id,
            is_deleted=False
        ).order_by('created_at')
        data = [{'id': c.id, 'role': c.role, 'content': c.content} for c in chats]
        return Response({'success': True, 'messages': data})

    def post(self, request, project_id):
        content = request.data.get('content', '')
        if not content.strip():
            return Response({'success': False, 'message': '内容不能为空'}, status=status.HTTP_400_BAD_REQUEST)

        project = get_object_or_404(ProjectList, pk=project_id)
        
        TimelineChatHistory.objects.create(
            project=project,
            role='user',
            content=content
        )

        return Response({'success': True})


class GenerateTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        from langchain_core.prompts import ChatPromptTemplate
        
        project = get_object_or_404(ProjectList, pk=project_id)
        
        outline_content = ''
        if hasattr(project, 'outline_versions'):
            latest_outline = project.outline_versions.filter(is_deleted=False).first()
            if latest_outline:
                outline_content = latest_outline.content

        estimate_chapters = request.data.get('estimate_chapters', 100)
        extra_prompt = request.data.get('extra_prompt', '')
        
        current_timeline = request.data.get('current_timeline', '')
        
        messages = request.data.get('messages', [])
        user_input = messages[-1]['content'] if messages else ''

        if current_timeline.strip():
            prompt = ChatPromptTemplate.from_messages([
                ("system", TIMELINE_INCREMENTAL_PROMPT),
                *[(msg['role'], msg['content']) for msg in messages]
            ])
            
            llm = get_llm(user=request.user, scene="timeline_generate")
            chain = prompt | llm
            
            def generate():
                for chunk in chain.stream({
                    "outline": outline_content,
                    "project_title": project.title,
                    "current_timeline": current_timeline,
                    "user_input": user_input
                }):
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    if chunk_content:
                        yield f"data: {json.dumps({'type': 'chunk', 'data': chunk_content}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'stream_complete'}, ensure_ascii=False)}\n\n"
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", TIMELINE_GENERATION_PROMPT)
            ])
            
            llm = get_llm(user=request.user, scene="timeline_generate")
            chain = prompt | llm
            
            def generate():
                for chunk in chain.stream({
                    "outline": outline_content,
                    "project_title": project.title,
                    "estimate_chapters": estimate_chapters,
                    "extra_prompt": extra_prompt
                }):
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    if chunk_content:
                        yield f"data: {json.dumps({'type': 'chunk', 'data': chunk_content}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'type': 'stream_complete'}, ensure_ascii=False)}\n\n"

        from django.http import StreamingHttpResponse
        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['X-Accel-Buffering'] = 'no'
        response['Cache-Control'] = 'no-cache'
        return response


class MergeTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        event_ids = request.data.get('event_ids', [])
        title = request.data.get('title', '')
        description = request.data.get('description', '')

        if len(event_ids) < 2:
            return Response({'success': False, 'message': '至少选择2个时间线进行合并'}, status=status.HTTP_400_BAD_REQUEST)

        if not title:
            return Response({'success': False, 'message': '请输入合并后的标题'}, status=status.HTTP_400_BAD_REQUEST)

        events = TimelineEvent.objects.filter(id__in=event_ids, project_id=project_id, is_deleted=False)
        
        if not events:
            return Response({'success': False, 'message': '未找到指定的时间线事件'}, status=status.HTTP_404_NOT_FOUND)

        start_chapter = min(e.start_chapter for e in events)
        end_chapter = max(e.end_chapter for e in events)

        merged_event = TimelineEvent.objects.create(
            project_id=project_id,
            title=title,
            description=description,
            start_chapter=start_chapter,
            end_chapter=end_chapter,
            event_order=0
        )

        events.update(is_deleted=True)

        return Response({
            'success': True,
            'message': '合并成功',
            'event': {
                'id': merged_event.id,
                'title': merged_event.title,
                'description': merged_event.description,
                'start_chapter': merged_event.start_chapter,
                'end_chapter': merged_event.end_chapter
            }
        })


class SplitTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        event_id = request.data.get('event_id')
        split_points = request.data.get('split_points', [])

        if not event_id:
            return Response({'success': False, 'message': '请指定要拆分的时间线事件'}, status=status.HTTP_400_BAD_REQUEST)

        if not split_points or len(split_points) == 0:
            return Response({'success': False, 'message': '请输入至少一个拆分点'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            split_points = sorted([int(p) for p in split_points])
        except ValueError:
            return Response({'success': False, 'message': '拆分点必须是数字'}, status=status.HTTP_400_BAD_REQUEST)

        event = get_object_or_404(TimelineEvent, id=event_id, project_id=project_id, is_deleted=False)

        if min(split_points) <= event.start_chapter or max(split_points) >= event.end_chapter:
            return Response({'success': False, 'message': '拆分点必须在时间线范围内'}, status=status.HTTP_400_BAD_REQUEST)

        points = [event.start_chapter] + split_points + [event.end_chapter]
        
        new_events = []
        for i in range(len(points) - 1):
            start = points[i]
            end = points[i + 1] if i == len(points) - 2 else points[i + 1]
            
            new_event = TimelineEvent.objects.create(
                project_id=project_id,
                title=f"{event.title} ({start}-{end}章)",
                description=event.description,
                start_chapter=start,
                end_chapter=end,
                event_order=i
            )
            new_events.append({
                'id': new_event.id,
                'title': new_event.title,
                'start_chapter': new_event.start_chapter,
                'end_chapter': new_event.end_chapter
            })

        event.is_deleted = True
        event.save()

        return Response({
            'success': True,
            'message': '拆分成功',
            'events': new_events
        })


class AiMergeTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(ProjectList, pk=project_id)
        event_ids = request.data.get('event_ids', [])

        if len(event_ids) < 2:
            return Response({'success': False, 'message': '至少选择2个时间线进行合并'}, status=status.HTTP_400_BAD_REQUEST)

        events = TimelineEvent.objects.filter(id__in=event_ids, project_id=project_id, is_deleted=False).order_by('start_chapter')

        if len(events) != len(event_ids):
            return Response({'success': False, 'message': '部分时间线不存在'}, status=status.HTTP_404_NOT_FOUND)

        events_text = '\n'.join([
            f"第{e.start_chapter}-{e.end_chapter}章: {e.title}\n{e.description}"
            for e in events
        ])

        outline_content = ''
        if hasattr(project, 'outline_versions'):
            latest_outline = project.outline_versions.filter(is_deleted=False).first()
            if latest_outline:
                outline_content = latest_outline.content
        project_title = project.title or ''

        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的小说时间线规划师。"),
            ("user", TIMELINE_MERGE_PROMPT)
        ])

        llm = get_llm(user=request.user, scene="timeline_generate")
        chain = prompt | llm

        def generate():
            try:
                for chunk in chain.stream({
                    "project_title": project_title,
                    "outline": outline_content,
                    "events_to_merge": events_text
                }):
                    content_chunk = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'data': content_chunk}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps({'type': 'stream_complete'}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['X-Accel-Buffering'] = 'no'
        response['Cache-Control'] = 'no-cache'
        return response


class AiSplitTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(ProjectList, pk=project_id)
        event_id = request.data.get('event_id')
        split_points = request.data.get('split_points', [])

        if not event_id:
            return Response({'success': False, 'message': '请指定要拆分的时间线事件'}, status=status.HTTP_400_BAD_REQUEST)

        event = get_object_or_404(TimelineEvent, id=event_id, project_id=project_id, is_deleted=False)

        outline_content = ''
        if hasattr(project, 'outline_versions'):
            latest_outline = project.outline_versions.filter(is_deleted=False).first()
            if latest_outline:
                outline_content = latest_outline.content
        project_title = project.title or ''

        split_points_text = ', '.join([str(p) for p in split_points]) if split_points else '未指定，由AI自动拆分'

        event_text = f"第{event.start_chapter}-{event.end_chapter}章: {event.title}\n{event.description}"

        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的小说时间线规划师。"),
            ("user", TIMELINE_SPLIT_PROMPT)
        ])

        llm = get_llm(user=request.user, scene="timeline_generate")
        chain = prompt | llm

        def generate():
            try:
                for chunk in chain.stream({
                    "project_title": project_title,
                    "outline": outline_content,
                    "event_to_split": event_text,
                    "split_points": split_points_text
                }):
                    content_chunk = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'data': content_chunk}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps({'type': 'stream_complete'}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['X-Accel-Buffering'] = 'no'
        response['Cache-Control'] = 'no-cache'
        return response


class OptimizeDescriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(ProjectList, pk=project_id)
        event_id = request.data.get('event_id')
        title = request.data.get('title', '')
        start_chapter = request.data.get('start_chapter', 1)
        end_chapter = request.data.get('end_chapter', 10)
        content = request.data.get('content', '')

        if not event_id:
            return Response({'success': False, 'message': '请指定要优化的时间线事件'}, status=status.HTTP_400_BAD_REQUEST)

        outline_content = ''
        if hasattr(project, 'outline_versions'):
            latest_outline = project.outline_versions.filter(is_deleted=False).first()
            if latest_outline:
                outline_content = latest_outline.content
        project_title = project.title or ''

        from langchain_core.prompts import ChatPromptTemplate

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的小说编辑。"),
            ("user", DESCRIPTION_OPTIMIZE_PROMPT)
        ])

        llm = get_llm(user=request.user, scene="timeline_generate")
        chain = prompt | llm

        def generate():
            try:
                for chunk in chain.stream({
                    "project_title": project_title,
                    "outline": outline_content,
                    "title": title,
                    "start_chapter": start_chapter,
                    "end_chapter": end_chapter,
                    "content": content
                }):
                    content_chunk = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    yield f"data: {json.dumps({'type': 'chunk', 'data': content_chunk}, ensure_ascii=False)}\n\n"

                yield f"data: {json.dumps({'type': 'stream_complete'}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['X-Accel-Buffering'] = 'no'
        response['Cache-Control'] = 'no-cache'
        return response
