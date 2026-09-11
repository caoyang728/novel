from django.shortcuts import get_object_or_404
from django.db import transaction
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.response import Response
from apps.project.base import BaseAPIView
from apps.project.models import ProjectList
from apps.worldview.utils import get_worldview_context
from agent.llm import get_llm
from loguru import logger
from .models import TimelineEvent
from .serializers import (
    TimelineEventSerializer,
    TimelineEventCreateUpdateSerializer,
    TimelineSplitSerializer,
    TimelineMergeSerializer,
    TimelineCheckOptimizeSerializer,
    TimelineSingleOptimizeSerializer,
    TimelineGenerateFieldsSerializer,
)
from .prompts import (
    TIMELINE_GENERATION_PROMPT,
    TIMELINE_INCREMENTAL_PROMPT,
    TIMELINE_MERGE_PROMPT,
    SINGLE_ITEM_OPTIMIZE_PROMPT,
    TIMELINE_CHECK_PROMPT,
    TIMELINE_CHECK_OPTIMIZE_PROMPT,
    TIMELINE_GENERATE_FIELDS_PROMPT
)
from langchain_core.prompts import ChatPromptTemplate
import json
import re


def _sync_event_after_save(event):
    """事件保存后异步同步图谱和知识库索引"""
    try:
        from apps.graph.tasks import sync_timeline_event_task
        sync_timeline_event_task.delay(event.pk)
    except Exception:
        pass
    try:
        from apps.knowledge.indexer import KnowledgeIndexer
        indexer = KnowledgeIndexer()
        indexer.index_timeline_event(event)
    except Exception:
        pass


def _sync_event_after_delete(event_id, project_id):
    """事件删除后异步清理图谱和知识库索引"""
    try:
        from apps.graph.tasks import delete_timeline_event_task
        delete_timeline_event_task.delay(event_id)
    except Exception:
        pass
    try:
        from apps.knowledge.indexer import KnowledgeIndexer
        from apps.knowledge.models import KnowledgeVector
        indexer = KnowledgeIndexer()
        KnowledgeVector.objects.filter(
            project_id=project_id, id__startswith=f"{project_id}_timeline_{event_id}"
        ).delete()
    except Exception:
        pass


class BaseTimelineAPIView(BaseAPIView):

    def get_project(self, project_id):
        """获取项目并校验归属当前用户"""
        return get_object_or_404(ProjectList, pk=project_id, user=self.request.user)

    def get_worldview_summary(self, project):
        """获取世界观文档的 Markdown 内容作为上下文"""
        return get_worldview_context(project)

    def build_sse_response(self, chain, chain_params, user=None, scene="timeline_generate", project=None, task_type=None):
        if user is None:
            user = self.request.user

        llm = get_llm(user=user, scene=scene)
        full_chain = chain | llm

        def generate():
            try:
                last_chunk = None
                usage_chunk = None
                full_content = ''
                for chunk in full_chain.stream(chain_params):
                    last_chunk = chunk
                    if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
                        usage_chunk = chunk
                    content_chunk = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    if content_chunk:
                        full_content += content_chunk
                        yield f"data: {json.dumps({'type': 'chunk', 'data': content_chunk}, ensure_ascii=False)}\n\n"
                # 记录 token 使用量
                log_task = task_type or scene
                self.log_token_usage(log_task, result=last_chunk, usage_result=usage_chunk, user=user, project=project)
                yield f"data: {json.dumps({'type': 'stream_complete'}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['X-Accel-Buffering'] = 'no'
        response['Cache-Control'] = 'no-cache'
        return response

    def build_context_section(self, prev_item, next_item, prefix_label="相邻事件上下文（供参考，不要修改）"):
        """构建相邻事件上下文文本，供多个 View 复用"""
        context_lines = []
        if prev_item:
            context_lines.append(self._format_neighbor_event(prev_item, "前一个事件"))
        if next_item:
            context_lines.append(self._format_neighbor_event(next_item, "后一个事件"))

        if context_lines:
            return prefix_label + '：\n' + '\n'.join(context_lines)
        return ''

    def _format_neighbor_event(self, item, label):
        """格式化单个相邻事件信息"""
        title = item.get('title', '')
        era_unit = item.get('era_unit', '')
        start_year = item.get('start_year', 0)
        start_month = item.get('start_month', 0)
        end_year = item.get('end_year', 0)
        end_month = item.get('end_month', 0)
        desc = item.get('description', item.get('content', ''))
        time_range = TimelineEvent(
            era_unit=era_unit,
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month
        ).format_time_range()
        return f"{label}：\n标题：{title}\n时间范围：{time_range}\n描述：{desc}"


class ApiTimelineEventListView(BaseTimelineAPIView):

    def get(self, request, project_id):
        project = self.get_project(project_id)
        events = TimelineEvent.objects.filter(
            project=project
        ).order_by('start_year', 'start_month', 'end_year', 'end_month')

        data = [{
            'id': e.id,
            'title': e.title,
            'description': e.description,
            'era_unit': e.era_unit,
            'start_year': e.start_year,
            'start_month': e.start_month,
            'end_year': e.end_year,
            'end_month': e.end_month,
            'time_range': e.format_time_range(),
            'is_active': e.is_active
        } for e in events]

        worldview_content = get_worldview_context(project)
        worldview_info = None
        if worldview_content:
            overview = worldview_content[:100] + '...' if len(worldview_content) > 100 else worldview_content
            worldview_info = {
                'world_name': '',
                'genre': project.genre or '',
                'overview': overview,
            }

        return Response({
            'events': data,
            'worldview_info': worldview_info,
        })

    def post(self, request, project_id):
        serializer = TimelineEventCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': '参数校验失败',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        project = self.get_project(project_id)
        event_id = validated.get('id')

        if event_id:
            # 更新现有记录，校验事件属于该项目
            try:
                event = TimelineEvent.objects.get(id=event_id, project=project)
            except TimelineEvent.DoesNotExist:
                return Response({'success': False, 'message': '记录不存在'}, status=status.HTTP_404_NOT_FOUND)

            for field in ['title', 'description', 'era_unit', 'start_year', 'start_month', 'end_year', 'end_month', 'is_active']:
                if field in validated:
                    setattr(event, field, validated[field])
            event.save()

            # 异步同步图谱和知识库索引
            transaction.on_commit(lambda: _sync_event_after_save(event))

            return Response({
                'success': True,
                'message': '更新成功',
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'era_unit': event.era_unit,
                'start_year': event.start_year,
                'start_month': event.start_month,
                'end_year': event.end_year,
                'end_month': event.end_month,
                'time_range': event.format_time_range(),
                'is_active': event.is_active
            })
        else:
            # 创建新记录
            event = TimelineEvent.objects.create(
                project=project,
                title=validated['title'],
                description=validated.get('description', ''),
                era_unit=validated.get('era_unit', ''),
                start_year=validated.get('start_year', 0),
                start_month=validated.get('start_month', 0),
                end_year=validated.get('end_year', 0),
                end_month=validated.get('end_month', 0),
                is_active=validated.get('is_active', True)
            )

            # 异步同步图谱和知识库索引
            transaction.on_commit(lambda: _sync_event_after_save(event))

            return Response({
                'success': True,
                'message': '创建成功',
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'era_unit': event.era_unit,
                'start_year': event.start_year,
                'start_month': event.start_month,
                'end_year': event.end_year,
                'end_month': event.end_month,
                'time_range': event.format_time_range(),
                'is_active': event.is_active
            })


class ApiTimelineEventDetailView(BaseTimelineAPIView):

    def get_event(self, request, project_id, pk):
        """获取事件并校验归属"""
        project = self.get_project(project_id)
        return get_object_or_404(TimelineEvent, pk=pk, project=project)

    def get(self, request, project_id, pk):
        event = self.get_event(request, project_id, pk)
        serializer = TimelineEventSerializer(event)
        return Response(serializer.data)

    def put(self, request, project_id, pk):
        event = self.get_event(request, project_id, pk)
        serializer = TimelineEventSerializer(event, data=request.data, partial=False)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': '参数校验失败',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response({
            'success': True,
            'message': '更新成功',
            **serializer.data
        })

    def patch(self, request, project_id, pk):
        event = self.get_event(request, project_id, pk)
        serializer = TimelineEventSerializer(event, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': '参数校验失败',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response({
            'success': True,
            'message': '更新成功',
            **serializer.data
        })

    def delete(self, request, project_id, pk):
        event = self.get_event(request, project_id, pk)
        event_id = event.pk
        project_id_val = project_id
        event.delete()
        # 异步清理图谱和知识库索引
        transaction.on_commit(lambda: _sync_event_after_delete(event_id, project_id_val))
        return Response({'success': True, 'message': '删除成功'})


class ApiTimelineGenerateView(BaseTimelineAPIView):

    def post(self, request, project_id):
        project = self.get_project(project_id)

        worldview_content = get_worldview_context(project)
        if not worldview_content:
            return Response({
                'success': False,
                'error': 'no_worldview',
                'message': '尚未构建世界观，请先完善世界观设定'
            }, status=status.HTTP_400_BAD_REQUEST)

        extra_prompt = request.data.get('extra_prompt', '')

        prompt = ChatPromptTemplate.from_messages([
            ("system", TIMELINE_GENERATION_PROMPT)
        ])

        return self.build_sse_response(
            chain=prompt,
            chain_params={
                "worldview_setting": worldview_content,
                "worldview_history": '',
                "worldview_foundation": '',
                "project_title": project.title,
                "extra_prompt": extra_prompt
            },
            project=project,
            task_type='timeline_generate',
        )


class ApiTimelineChatGenerateView(BaseTimelineAPIView):

    def post(self, request, project_id):
        project = self.get_project(project_id)

        worldview_summary = self.get_worldview_summary(project)
        if not worldview_summary:
            return Response({
                'success': False,
                'error': 'no_worldview',
                'message': '尚未构建世界观，请先完善世界观设定'
            }, status=status.HTTP_400_BAD_REQUEST)

        user_input = request.data.get('user_input', '')
        last_ai_message = request.data.get('last_ai_message', '')
        current_timeline = request.data.get('current_timeline', '')

        if last_ai_message:
            prompt = ChatPromptTemplate.from_messages([
                ("system", TIMELINE_INCREMENTAL_PROMPT),
                ("ai", "{last_ai_message}"),
                ("human", "{user_input}")
            ])
        else:
            prompt = ChatPromptTemplate.from_messages([
                ("system", TIMELINE_INCREMENTAL_PROMPT),
                ("human", "{user_input}")
            ])

        chain_params = {
            "outline": worldview_summary,
            "project_title": project.title,
            "current_timeline": current_timeline or "（当前无时间线事件）",
            "user_input": user_input
        }
        if last_ai_message:
            chain_params["last_ai_message"] = last_ai_message

        return self.build_sse_response(
            chain=prompt,
            chain_params=chain_params,
            project=project,
            task_type='timeline_chat',
        )


class ApiTimelineSingleOptimizeView(BaseTimelineAPIView):

    def post(self, request, project_id):
        serializer = TimelineSingleOptimizeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': '参数校验失败',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        project = self.get_project(project_id)

        title = validated.get('title', '')
        era_unit = validated.get('era_unit', '')
        start_year = validated.get('start_year', 0)
        start_month = validated.get('start_month', 0)
        end_year = validated.get('end_year', 0)
        end_month = validated.get('end_month', 0)
        content = validated.get('content', '')
        prev_item = validated.get('prev_item')
        next_item = validated.get('next_item')

        worldview_summary = self.get_worldview_summary(project)
        if not worldview_summary:
            return Response({
                'success': False,
                'error': 'no_worldview',
                'message': '尚未构建世界观，请先完善世界观设定'
            }, status=status.HTTP_400_BAD_REQUEST)

        project_title = project.title or ''

        context_section = self.build_context_section(prev_item, next_item)
        if not context_section:
            context_section = '（无相邻事件上下文）'

        # 构造当前事件的时间范围字符串
        current_time_range = TimelineEvent(
            era_unit=era_unit,
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month
        ).format_time_range()

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的小说时间线规划师。"),
            ("user", SINGLE_ITEM_OPTIMIZE_PROMPT)
        ])

        return self.build_sse_response(
            chain=prompt,
            chain_params={
                "project_title": project_title,
                "outline": worldview_summary,
                "title": title,
                "time_range": current_time_range,
                "content": content,
                "context_section": context_section
            },
            project=project,
            task_type='timeline_single_optimize',
        )


class ApiTimelineGenerateFieldsView(BaseTimelineAPIView):
    """根据描述生成事件字段"""

    def post(self, request, project_id):
        serializer = TimelineGenerateFieldsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': '参数校验失败',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        project = self.get_project(project_id)

        description = validated.get('description', '')
        prev_item = validated.get('prev_item')
        next_item = validated.get('next_item')

        worldview_summary = self.get_worldview_summary(project)
        if not worldview_summary:
            return Response({
                'success': False,
                'error': 'no_worldview',
                'message': '尚未构建世界观，请先完善世界观设定'
            }, status=status.HTTP_400_BAD_REQUEST)

        project_title = project.title or ''

        context_section = self.build_context_section(
            prev_item, next_item,
            prefix_label="相邻事件上下文（供参考，生成的时间范围应与之逻辑连贯）"
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的小说时间线规划师。"),
            ("user", TIMELINE_GENERATE_FIELDS_PROMPT)
        ])

        return self.build_sse_response(
            chain=prompt,
            chain_params={
                "project_title": project_title,
                "outline": worldview_summary,
                "description": description,
                "context_section": context_section
            },
            scene="timeline_generate",
            project=project,
            task_type='timeline_generate_fields',
        )


class ApiTimelineMergeView(BaseTimelineAPIView):

    def post(self, request, project_id):
        serializer = TimelineMergeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': '参数校验失败',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        event_ids = serializer.validated_data['event_ids']
        project = self.get_project(project_id)

        worldview_summary = self.get_worldview_summary(project)
        if not worldview_summary:
            return Response({
                'success': False,
                'error': 'no_worldview',
                'message': '尚未构建世界观，请先完善世界观设定'
            }, status=status.HTTP_400_BAD_REQUEST)

        events = TimelineEvent.objects.filter(id__in=event_ids, project=project).order_by('start_year', 'start_month', 'end_year', 'end_month')

        if len(events) != len(event_ids):
            return Response({'success': False, 'message': '部分时间线不存在'}, status=status.HTTP_404_NOT_FOUND)

        events_text = '\n'.join([
            f"{e.format_time_range()}: {e.title}\n{e.description}"
            for e in events
        ])

        prompt = ChatPromptTemplate.from_messages([
            ("system", TIMELINE_MERGE_PROMPT)
        ])

        chain = prompt | get_llm(user=request.user, scene="timeline_merge", stream=False)
        try:
            result = chain.invoke({
                "project_title": project.title or '',
                "outline": worldview_summary,
                "events_to_merge": events_text
            })
            self.log_token_usage('timeline_merge', result=result, user=request.user, project=project)
            ai_content = result.content if hasattr(result, 'content') else str(result)

            # 改进 JSON 解析：使用非贪婪匹配，支持嵌套花括号
            json_match = re.search(r'\{.*?\}', ai_content, re.DOTALL)
            if json_match:
                try:
                    ai_data = json.loads(json_match.group())
                    title = ai_data.get('title', '')
                    description = ai_data.get('description', '')
                except json.JSONDecodeError:
                    # 非贪婪匹配失败，尝试找最外层花括号对
                    first_brace = ai_content.find('{')
                    last_brace = ai_content.rfind('}')
                    if first_brace != -1 and last_brace > first_brace:
                        try:
                            ai_data = json.loads(ai_content[first_brace:last_brace + 1])
                            title = ai_data.get('title', '')
                            description = ai_data.get('description', '')
                        except json.JSONDecodeError:
                            title = events.first().title
                            description = events.first().description
                    else:
                        title = events.first().title
                        description = events.first().description
            else:
                title = events.first().title
                description = events.first().description
        except Exception as e:
            logger.error(f"AI合并生成失败: {e}")
            title = events.first().title
            description = events.first().description

        if not title:
            title = '、'.join([e.title for e in events[:3]])
            if len(events) > 3:
                title += '等'

        first_event = events.first()
        first_event.title = title
        first_event.description = description
        first_event.start_year = events.first().start_year
        first_event.start_month = events.first().start_month
        first_event.end_year = events.last().end_year
        first_event.end_month = events.last().end_month
        first_event.save()

        events.exclude(id=first_event.id).delete()

        return Response({
            'success': True,
            'message': '合并成功',
            'event': {
                'id': first_event.id,
                'title': first_event.title,
                'description': first_event.description,
                'era_unit': first_event.era_unit,
                'start_year': first_event.start_year,
                'start_month': first_event.start_month,
                'end_year': first_event.end_year,
                'end_month': first_event.end_month,
                'time_range': first_event.format_time_range()
            }
        })


class ApiTimelineSplitView(BaseTimelineAPIView):

    def post(self, request, project_id):
        serializer = TimelineSplitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': '参数校验失败',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        event_id = validated['event_id']
        split_points = validated['split_points']
        split_era_unit = validated.get('era_unit', '')

        project = self.get_project(project_id)
        event = get_object_or_404(TimelineEvent, id=event_id, project=project)

        # split_points 格式: [{'year': 3, 'month': 6}, {'year': 5, 'month': 1}]
        # 构建时间点序列: [起始, 拆分点1, 拆分点2, ..., 结束]
        points = [
            {'year': event.start_year, 'month': event.start_month}
        ] + split_points + [
            {'year': event.end_year, 'month': event.end_month}
        ]

        new_events = []
        for i in range(len(points) - 1):
            start_pt = points[i]
            end_pt = points[i + 1]
            new_event = TimelineEvent.objects.create(
                project=project,
                title=f"{event.title}（{i + 1}）",
                description='',  # 拆分后子事件描述留空，避免所有子事件共享同一描述
                era_unit=split_era_unit or event.era_unit,
                start_year=start_pt['year'],
                start_month=start_pt['month'],
                end_year=end_pt['year'],
                end_month=end_pt['month'],
            )
            new_events.append({
                'id': new_event.id,
                'title': new_event.title,
                'era_unit': new_event.era_unit,
                'start_year': new_event.start_year,
                'start_month': new_event.start_month,
                'end_year': new_event.end_year,
                'end_month': new_event.end_month,
                'time_range': new_event.format_time_range()
            })

        event.delete()

        return Response({
            'success': True,
            'message': '拆分成功',
            'events': new_events
        })


class ApiTimelineCheckView(BaseTimelineAPIView):

    def post(self, request, project_id):
        project = self.get_project(project_id)

        worldview_summary = self.get_worldview_summary(project)
        if not worldview_summary:
            return Response({
                'success': False,
                'error': 'no_worldview',
                'message': '尚未构建世界观，请先完善世界观设定'
            }, status=status.HTTP_400_BAD_REQUEST)

        events = TimelineEvent.objects.filter(
            project=project
        ).order_by('start_year', 'start_month', 'end_year', 'end_month')

        if not events.exists():
            return Response({
                'success': False,
                'message': '当前没有时间线事件，无法进行检查'
            }, status=status.HTTP_400_BAD_REQUEST)

        current_timeline = '\n'.join([
            f"[ID:{e.id}] {e.title}（{e.format_time_range_for_llm()}）：{e.description}"
            for e in events
        ])

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的时间线审校编辑。"),
            ("user", TIMELINE_CHECK_PROMPT)
        ])

        return self.build_sse_response(
            chain=prompt,
            chain_params={
                "project_title": project.title or '',
                "outline": worldview_summary,
                "current_timeline": current_timeline
            },
            scene="timeline_check",
            project=project,
            task_type='timeline_check',
        )


class ApiTimelineCheckOptimizeView(BaseTimelineAPIView):

    def post(self, request, project_id):
        serializer = TimelineCheckOptimizeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'message': '参数校验失败',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        validated = serializer.validated_data
        events_data = validated['events']
        user_solution = validated.get('user_solution', '')

        project = self.get_project(project_id)

        worldview_summary = self.get_worldview_summary(project)
        if not worldview_summary:
            return Response({
                'success': False,
                'message': '尚未构建世界观，请先完善世界观设定'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 查找每个事件，优先用ID，其次用标题
        resolved_events = []
        for evt in events_data:
            evt_id = evt.get('id', '')
            evt_title = evt.get('title', '')
            reasons = evt.get('reasons', [])

            event_obj = None
            if evt_id:
                event_obj = TimelineEvent.objects.filter(
                    project=project, id=evt_id
                ).first()
            if not event_obj and evt_title:
                event_obj = TimelineEvent.objects.filter(
                    project=project, title=evt_title
                ).first()

            if event_obj:
                resolved_events.append({
                    'obj': event_obj,
                    'reasons': reasons
                })
            else:
                logger.warning(f'未找到事件(id={evt_id}, title={evt_title}), project_id={project_id}')

        if not resolved_events:
            return Response({
                'success': False,
                'message': '未找到任何对应的事件'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 构建 events_section 文本
        events_section_parts = []
        for i, evt_info in enumerate(resolved_events, 1):
            obj = evt_info['obj']
            reasons_text = '；'.join(evt_info['reasons']) if evt_info['reasons'] else '无'
            section = f"事件{i}：{obj.title}（{obj.format_time_range_for_llm()}）\n描述：{obj.description or ''}\n存在问题：{reasons_text}"
            events_section_parts.append(section)

        events_section = '\n\n'.join(events_section_parts)

        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一位专业的时间线修复编辑。"),
            ("user", TIMELINE_CHECK_OPTIMIZE_PROMPT)
        ])

        return self.build_sse_response(
            chain=prompt,
            chain_params={
                "project_title": project.title or '',
                "outline": worldview_summary,
                "events_section": events_section,
                "user_solution": user_solution
            },
            scene="timeline_check",
            project=project,
            task_type='timeline_check_optimize',
        )


class ApiTimelineGraphView(BaseTimelineAPIView):
    """时间线图谱聚合数据接口 — 支持全局/人物/地点三种视图"""

    def get(self, request, project_id):
        project = self.get_project(project_id)
        if not project:
            return Response({'success': False, 'message': '项目不存在'}, status=404)

        view_type = request.query_params.get('view', 'global')
        character_id = request.query_params.get('character_id')
        location_name = request.query_params.get('location_name')
        start_year = request.query_params.get('start_year')
        end_year = request.query_params.get('end_year')

        # 构建查询
        events_qs = TimelineEvent.objects.filter(
            project=project, is_active=True
        ).prefetch_related('characters')

        # 按视图类型过滤
        if view_type == 'character' and character_id:
            events_qs = events_qs.filter(characters__id=character_id)
        elif view_type == 'location' and location_name:
            events_qs = events_qs.filter(location=location_name)

        # 时间窗口过滤
        if start_year is not None:
            try:
                events_qs = events_qs.filter(start_year__gte=int(start_year))
            except (ValueError, TypeError):
                pass
        if end_year is not None:
            try:
                events_qs = events_qs.filter(start_year__lte=int(end_year))
            except (ValueError, TypeError):
                pass

        # 按故事时间排序
        events_qs = events_qs.order_by('start_year', 'start_month', 'end_year', 'end_month')

        # 序列化事件
        timeline = []
        for event in events_qs:
            chars = [
                {'id': c.id, 'name': c.name, 'role_type': c.role_type}
                for c in event.characters.all()
            ]
            timeline.append({
                'id': event.id,
                'title': event.title,
                'description': event.description,
                'start_year': event.start_year,
                'start_month': event.start_month,
                'end_year': event.end_year,
                'end_month': event.end_month,
                'event_type': event.event_type,
                'chapter_number': event.chapter.chapter_number if event.chapter else None,
                'chapter_title': event.chapter.title if event.chapter else None,
                'location': event.location,
                'is_time_estimated': event.is_time_estimated,
                'characters': chars,
            })

        # 如果是人物视图，附加角色轨迹
        trajectories = []
        if view_type == 'character' and character_id:
            from apps.characters.models import CharacterTrajectory
            from apps.chapter.models import ChapterList
            traj_qs = CharacterTrajectory.objects.filter(
                project=project, character_id=character_id
            ).select_related('character').order_by('order', 'start_time', 'created_at')

            # 批量查询章节信息
            all_chapter_ids = set()
            for t in traj_qs:
                if t.chapter_ids:
                    all_chapter_ids.update(t.chapter_ids)
            chapter_map = {}
            if all_chapter_ids:
                for ch in ChapterList.objects.filter(id__in=all_chapter_ids):
                    chapter_map[ch.id] = {
                        'chapter_number': ch.chapter_number,
                        'title': ch.title,
                    }

            for t in traj_qs:
                details = t.details or {}
                # 从 chapter_ids 获取章节信息
                chapters_info = []
                if t.chapter_ids:
                    for ch_id in t.chapter_ids[:3]:  # 最多展示 3 个章节
                        ch_info = chapter_map.get(ch_id)
                        if ch_info:
                            chapters_info.append({
                                'id': ch_id,
                                'chapter_number': ch_info['chapter_number'],
                                'title': ch_info['title'],
                            })

                trajectories.append({
                    'id': t.id,
                    'title': t.title,
                    'start_time': t.start_time,
                    'end_time': t.end_time,
                    'order': t.order,
                    'source': t.source,
                    'chapters': chapters_info,
                    'location': details.get('location', ''),
                    'power_level': details.get('power_level', ''),
                    'emotional_state': details.get('emotional_state', ''),
                    'key_events': details.get('key_events', []),
                    'description': details.get('description', ''),
                })

        # 元数据
        meta = {}
        if timeline:
            years = [e['start_year'] for e in timeline if e['start_year'] is not None]
            if years:
                meta['earliest_year'] = min(years)
                meta['latest_year'] = max(years)
        meta['total_events'] = len(timeline)
        # 获取纪元单位
        first_event = events_qs.first()
        if first_event:
            meta['era_unit'] = first_event.era_unit or ''

        return Response({
            'success': True,
            'data': {
                'timeline': timeline,
                'trajectories': trajectories,
                'meta': meta,
            }
        })


class ApiTimelineGraphStatsView(BaseTimelineAPIView):
    """时间线图谱统计视图"""

    def get(self, request, project_id):
        project = self.get_project(project_id)

        # 事件统计
        events_qs = TimelineEvent.objects.filter(project=project, is_active=True)
        total_events = events_qs.count()
        event_type_counts = {}
        for etype in ['main', 'side', 'character', 'world']:
            count = events_qs.filter(event_type=etype).count()
            if count > 0:
                event_type_counts[etype] = count

        # 时间跨度
        years = list(events_qs.values_list('start_year', flat=True).distinct())
        years = [y for y in years if y is not None]
        time_span = {
            'earliest_year': min(years) if years else None,
            'latest_year': max(years) if years else None,
        }

        # 角色统计
        from apps.characters.models import Character
        total_characters = Character.objects.filter(
            project=project, is_deleted=False
        ).count()

        # 参与事件的角色统计（使用 annotate）
        from django.db.models import Count
        top_characters = Character.objects.filter(
            project=project, is_deleted=False
        ).annotate(
            event_count=Count('timeline_events')
        ).filter(event_count__gt=0).order_by('-event_count')[:10]

        # 地点统计
        location_counts = {}
        for loc in events_qs.exclude(location='').values_list('location', flat=True):
            location_counts[loc] = location_counts.get(loc, 0) + 1
        top_locations = sorted(
            location_counts.items(), key=lambda x: -x[1]
        )[:10]

        # 轨迹统计
        from apps.characters.models import CharacterTrajectory
        total_trajectories = CharacterTrajectory.objects.filter(
            project=project
        ).count()

        return Response({
            'success': True,
            'data': {
                'total_events': total_events,
                'event_type_counts': event_type_counts,
                'time_span': time_span,
                'total_characters': total_characters,
                'total_trajectories': total_trajectories,
                'top_characters': [
                    {'id': c.id, 'name': c.name, 'role_type': c.role_type, 'event_count': c.event_count}
                    for c in top_characters
                ],
                'top_locations': [
                    {'name': loc, 'count': count}
                    for loc, count in top_locations
                ],
            }
        })
