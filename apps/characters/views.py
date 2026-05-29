import json
import time
from loguru import logger
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.conf import settings
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from langchain_core.prompts import ChatPromptTemplate

from apps.project.models import ProjectList
from apps.characters.models import Character
from apps.characters.serializers import (
    CharacterListSerializer,
    CharacterDetailSerializer,
    CharacterCreateSerializer,
    CharacterUpdateSerializer,
    CharacterPolishSerializer,
)
from apps.ai.llm import get_llm
from apps.characters.prompts import (
    CHARACTER_GENERATE_SYSTEM_PROMPT,
    CHARACTER_GENERATE_USER_PROMPT,
    CHARACTER_POLISH_SYSTEM_PROMPT,
    CHARACTER_POLISH_USER_PROMPT,
)

RELATIONSHIP_REVERSE = {
    'friend': 'friend',
    'enemy': 'enemy',
    'family': 'family',
    'lover': 'lover',
    'master': 'disciple',
    'disciple': 'master',
    'partner': 'partner',
    'rival': 'rival',
    'other': 'other'
}


class BaseCharacterAPIView(APIView):
    """角色API基础类 - 封装鉴权和项目查询"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_project(self, request, pk):
        """获取项目，如果不存在则抛出404异常"""
        return get_object_or_404(ProjectList, pk=pk, user=request.user)

    def _create_reverse_relationships(self, project, character, relationships):
        """创建反向关系"""
        for rel in relationships:
            if not rel.get('createReverse') or not rel.get('targetName'):
                continue

            target_name = rel.get('targetName')
            target_char = Character.objects.filter(
                project=project, 
                name=target_name, 
                is_deleted=False
            ).first()
            
            if not target_char:
                continue

            rel_type = rel.get('relationshipType', 'other')
            reverse_type = RELATIONSHIP_REVERSE.get(rel_type, 'other')

            target_extra = target_char.extra or {}
            target_rels = target_extra.get('relationships', [])
            
            rel_exists = any(
                r.get('targetName') == character.name 
                for r in target_rels if isinstance(r, dict)
            )
            
            if not rel_exists:
                target_rels.append({
                    'targetName': character.name,
                    'relationshipType': reverse_type,
                    'description': rel.get('description', ''),
                    'createReverse': False
                })
                target_extra['relationships'] = target_rels
                target_char.extra = target_extra
                target_char.save()

    def _create_relationships_from_string(self, project, character, relationships_str):
        """从字符串解析并创建关系"""
        if not relationships_str or not isinstance(relationships_str, str):
            return

        relationships = []
        for rel_str in relationships_str.split(','):
            rel_str = rel_str.strip()
            if not rel_str:
                continue

            parts = rel_str.split('-')
            if len(parts) >= 2:
                rel_type = parts[0].strip()
                target_name = parts[1].strip() if len(parts) > 1 else ''
                description = parts[2].strip() if len(parts) > 2 else ''

                target_char = Character.objects.filter(
                    project=project,
                    name=target_name,
                    is_deleted=False
                ).first()

                if target_char:
                    relationships.append({
                        'targetName': target_name,
                        'relationshipType': rel_type,
                        'description': description,
                        'createReverse': True
                    })

        if relationships:
            extra = character.extra or {}
            extra['relationships'] = relationships
            character.extra = extra
            character.save()

            self._create_reverse_relationships(project, character, relationships)


class ApiCharacterListView(BaseCharacterAPIView):
    """人物列表API"""

    def get(self, request, pk):
        """获取角色列表"""
        project = self.get_project(request, pk)
        characters = project.characters.filter(is_deleted=False).order_by('role_type', 'name')
        serializer = CharacterListSerializer(characters, many=True)
        return Response({'success': True, 'characters': serializer.data})

    def post(self, request, pk):
        """创建角色"""
        project = self.get_project(request, pk)
        
        serializer = CharacterCreateSerializer(
            data=request.data,
            context={'project': project}
        )
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        character = serializer.save(project=project)
        
        relationships = serializer.validated_data.get('relationships')
        if relationships:
            self._create_relationships_from_string(project, character, relationships)

        return Response({
            'success': True,
            'character': {
                'id': character.id,
                'name': character.name,
                'role_type': character.role_type,
                'role_type_display': character.get_role_type_display(),
                'gender': character.gender,
                'gender_display': character.get_gender_display()
            }
        }, status=status.HTTP_201_CREATED)


class ApiCharacterDetailView(BaseCharacterAPIView):
    """人物详情API"""

    def get(self, request, pk, character_id):
        """获取角色详情"""
        project = self.get_project(request, pk)
        character = get_object_or_404(Character, pk=character_id, project=project, is_deleted=False)
        serializer = CharacterDetailSerializer(character)
        return Response({'success': True, 'character': serializer.data})

    def put(self, request, pk, character_id):
        """更新角色"""
        project = self.get_project(request, pk)
        character = get_object_or_404(Character, pk=character_id, project=project, is_deleted=False)
        
        serializer = CharacterUpdateSerializer(
            instance=character,
            data=request.data,
            context={'project': project}
        )
        
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        character = serializer.save()
        
        extra = request.data.get('extra', {})
        relationships = extra.get('relationships', [])
        if relationships:
            self._create_reverse_relationships(project, character, relationships)

        return Response({'success': True})

    def delete(self, request, pk, character_id):
        """删除角色"""
        project = self.get_project(request, pk)
        character = get_object_or_404(Character, pk=character_id, project=project, is_deleted=False)
        character.delete()
        return Response({'success': True})


class ApiCharacterGenerateView(BaseCharacterAPIView):
    """AI生成角色预览（单个或批量）"""

    def _generate_stream(self, system_prompt, user_prompt_template, prompt_vars, user):
        from django.conf import settings
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt_template)
        ])

        llm = get_llm(user=user, scene="character_design")
        chain = prompt | llm

        max_retries = settings.LLM_RETRY
        retry_interval = settings.LLM_RETRY_INTERVAL

        for retry_count in range(max_retries):
            try:
                stream_response = chain.stream(prompt_vars)

                full_content = ""
                for chunk in stream_response:
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                return {"type": "complete", "data": full_content}
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"角色生成异常: {error_msg}, 重试 {retry_count + 1}/{max_retries}")
                if retry_count < max_retries - 1:
                    if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                        retry_interval *= 2
                    time.sleep(retry_interval)

        return {"type": "error", "message": f"LLM调用失败，已重试 {max_retries} 次"}

    def post(self, request, pk):
        requirement = request.data.get('requirement', '').strip()
        is_batch = request.data.get('is_batch', False)

        if not requirement:
            return Response({'success': False, 'error': '请输入角色描述'}, status=400)

        project = self.get_project(request, pk)

        existing_str = ''
        existing_chars = project.characters.filter(is_deleted=False).order_by('name')
        existing_str = '\n'.join([f"- {c.name}({c.get_role_type_display()})" for c in existing_chars[:10]]) or '暂无已有角色'

        worldview_str = '暂无世界观设定'
        wv = project.worldviews.first()
        if wv:
            worldview_parts = []
            if wv.setting:
                foundation = wv.setting.get('foundation', {})
                if foundation.get('world_name'):
                    worldview_parts.append(f"世界名称: {foundation['world_name']}")
                if foundation.get('genre'):
                    worldview_parts.append(f"题材类型: {foundation['genre']}")
            if wv.power:
                worldview_parts.append(f"力量体系: {json.dumps(wv.power, ensure_ascii=False)[:500]}")
            if wv.society:
                worldview_parts.append(f"社会结构: {json.dumps(wv.society, ensure_ascii=False)[:500]}")
            if worldview_parts:
                worldview_str = '\n'.join(worldview_parts)

        def generate():
            try:
                if is_batch:
                    count_str = "合适数量的"
                    extra_requirements = "请确保：\n1. 角色要契合用户描述的主题\n2. 角色之间有有趣的关系网络\n3. 能够推动故事发展"
                else:
                    count_str = "1个"
                    extra_requirements = "请生成一个符合用户描述的角色。"
                
                prompt_vars = {
                    "count": count_str,
                    "requirement": requirement,
                    "worldview": worldview_str,
                    "existing_characters": existing_str,
                    "extra_requirements": extra_requirements
                }
                result = self._generate_stream(
                    CHARACTER_GENERATE_SYSTEM_PROMPT,
                    CHARACTER_GENERATE_USER_PROMPT,
                    prompt_vars,
                    request.user
                )
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"角色生成失败: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiCharacterPolishView(BaseCharacterAPIView):
    """AI角色润色API - 流式返回"""

    def post(self, request, pk):
        project = self.get_project(request, pk)

        serializer = CharacterPolishSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'error': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        character_data = serializer.validated_data
        character_json = json.dumps(character_data, ensure_ascii=False)

        def generate():
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", CHARACTER_POLISH_SYSTEM_PROMPT),
                    ("user", CHARACTER_POLISH_USER_PROMPT),
                ])

                llm = get_llm(user=request.user, scene="character_polish")
                chain = prompt | llm

                stream_response = chain.stream({
                    "character_data": character_json
                })

                full_content = ""
                for chunk in stream_response:
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                yield f"data: {json.dumps({'type': 'complete', 'data': full_content}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"流式角色润色异常: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

