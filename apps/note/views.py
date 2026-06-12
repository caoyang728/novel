from django.shortcuts import get_object_or_404
from django.http import StreamingHttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import serializers
from rest_framework.serializers import ModelSerializer

from apps.note.models import Note
from apps.project.models import ProjectList
from agent.llm import get_llm, call_llm_with_retry
from apps.note.prompts import NOTE_POLISH_SYSTEM_PROMPT, NOTE_POLISH_USER_PROMPT
from apps.project.base import BaseAPIView
import json
import pytz
from loguru import logger


class NoteSerializer(ModelSerializer):
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = Note
        fields = ['id', 'title', 'content', 'status', 'status_display', 'created_at', 'updated_at']
    
    def get_status_display(self, instance):
        return instance.get_status_display()
    
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        beijing_tz = pytz.timezone('Asia/Shanghai')
        
        if instance.created_at:
            created_at_utc = instance.created_at.replace(tzinfo=pytz.utc)
            created_at_beijing = created_at_utc.astimezone(beijing_tz)
            representation['created_at'] = created_at_beijing.strftime('%Y-%m-%d %H:%M')
        
        if instance.updated_at:
            updated_at_utc = instance.updated_at.replace(tzinfo=pytz.utc)
            updated_at_beijing = updated_at_utc.astimezone(beijing_tz)
            representation['updated_at'] = updated_at_beijing.strftime('%Y-%m-%d %H:%M')
        
        return representation


class NotesAPIView(BaseAPIView):

    def get(self, request, project_id):
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        search_query = request.query_params.get('search', '')
        
        notes = Note.objects.filter(project=project, user=request.user)
        
        if search_query:
            notes = notes.filter(content__icontains=search_query) | notes.filter(title__icontains=search_query)
        
        notes = notes.order_by('-created_at')
        
        serializer = NoteSerializer(notes, many=True)
        data = []
        for item in serializer.data:
            data.append({
                **item,
                'content': item['content'][:100] + '...' if len(item['content']) > 100 else item['content']
            })
        
        return Response({'success': True, 'data': data})
    
    def post(self, request, project_id):
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        
        content = request.data.get('content', '')
        if not content.strip():
            return Response({'success': False, 'error': '内容不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        
        title = request.data.get('title', '').strip()
        
        note = Note.objects.create(
            user=request.user,
            project=project,
            content=content,
            title=title
        )
        
        serializer = NoteSerializer(note)
        return Response({
            'success': True,
            'note': serializer.data
        })


class NoteDetailAPIView(BaseAPIView):

    def get(self, request, project_id, note_id):
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        note = get_object_or_404(Note, pk=note_id, project=project, user=request.user)
        
        serializer = NoteSerializer(note)
        return Response({
            'success': True,
            'note': serializer.data
        })
    
    def put(self, request, project_id, note_id):
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        note = get_object_or_404(Note, pk=note_id, project=project, user=request.user)
        
        content = request.data.get('content')
        title = request.data.get('title')
        note_status = request.data.get('status')
        
        if content is not None:
            note.content = content
        if title is not None:
            note.title = title
        if note_status is not None:
            note.status = note_status
        
        note.save()
        
        serializer = NoteSerializer(note)
        return Response({
            'success': True,
            'note': serializer.data
        })
    
    def delete(self, request, project_id, note_id):
        project = get_object_or_404(ProjectList, pk=project_id, user=request.user)
        note = get_object_or_404(Note, pk=note_id, project=project, user=request.user)
        
        note.delete()
        
        return Response({'success': True})


class NoteAIPolishAPIView(BaseAPIView):

    def post(self, request, project_id):
        try:
            project = get_object_or_404(ProjectList, pk=project_id, user=request.user)

            content = request.data.get('content', '')
            if not content.strip():
                return Response({'success': False, 'error': '内容不能为空'}, status=status.HTTP_400_BAD_REQUEST)
            
            title = request.data.get('title', '').strip()
            title_section = f'原标题：{title}\n' if title else ''
            
            def generate():
                yield f"data: {json.dumps({'type': 'start', 'content': '开始AI整理...'}, ensure_ascii=False)}\n\n"
                
                try:
                    user_prompt = NOTE_POLISH_USER_PROMPT.format(content=content, title_section=title_section)
                    
                    messages = [
                        {'role': 'system', 'content': NOTE_POLISH_SYSTEM_PROMPT},
                        {'role': 'user', 'content': user_prompt}
                    ]
                    
                    stream_response = call_llm_with_retry(messages, stream=True, user=request.user, scene="default")
                    
                    for chunk in stream_response:
                        chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                        
                        yield f"data: {json.dumps({'type': 'chunk', 'content': chunk_content}, ensure_ascii=False)}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'complete'}, ensure_ascii=False)}\n\n"
                    
                except Exception as e:
                    logger.error(f"流式整理失败: {e}")
                    yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
            
            response = StreamingHttpResponse(generate(), content_type='text/event-stream')
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response
            
        except Exception as e:
            return Response({'success': False, 'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
