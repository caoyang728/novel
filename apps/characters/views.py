# Characters app - 角色管理视图
import json
import time
from loguru import logger
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.views import APIView
from django.http import JsonResponse, StreamingHttpResponse
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate

from apps.project.models import ProjectList
from apps.characters.models import Character
from apps.ai.llm import get_llm
from apps.ai.prompts import CHARACTER_STREAM_PROMPT
from apps.characters.prompts import (
    CHARACTER_BATCH_STREAM_PROMPT,
    CHARACTER_POLISH_V2_PROMPT,
)


def _call_with_retry(messages, stream=False, timeout=None, user=None, scene="default"):
    from django.conf import settings
    
    max_retries = settings.LLM_RETRY
    retry_interval = settings.LLM_RETRY_INTERVAL

    llm = get_llm(user=user, scene=scene, timeout=timeout)

    prompt_messages = []
    for msg in messages:
        if isinstance(msg, dict):
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            prompt_messages.append((role, content))
        else:
            if hasattr(msg, 'content'):
                if hasattr(msg, 'role'):
                    prompt_messages.append((msg.role, msg.content))
                elif isinstance(msg, SystemMessage):
                    prompt_messages.append(('system', msg.content))
                elif isinstance(msg, HumanMessage):
                    prompt_messages.append(('user', msg.content))
    
    prompt = ChatPromptTemplate.from_messages(prompt_messages)
    chain = prompt | llm

    for retry_count in range(max_retries):
        try:
            if stream:
                def gen():
                    for chunk in chain.stream({}):
                        if hasattr(chunk, 'content'):
                            yield chunk.content
                        else:
                            yield str(chunk)
                    return gen()
            else:
                result = chain.invoke({})
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


def generate_character_stream(background, existing_characters, requirement='', count=1, user=None, project=None):
    prompt = CHARACTER_STREAM_PROMPT.format(
        count=count,
        background=background or '未提供具体背景信息',
        existing_characters=existing_characters or '暂无已有角色',
        user_requirement=requirement or '请根据背景创建合适的角色'
    )

    messages = [
        SystemMessage(content="你是一位专业的角色设计大师。必须严格按照指定的分隔符格式输出每个字段，不要任何其他文字。"),
        HumanMessage(content=prompt)
    ]

    try:
        stream_response = _call_with_retry(messages, stream=True, user=user, scene="character_design")
        
        full_content = ""
        for content_chunk in stream_response:
            if content_chunk:
                full_content += content_chunk
                yield {"type": "chunk", "data": content_chunk}

        yield {"type": "complete", "data": full_content}

    except Exception as e:
        logger.error(f"流式角色生成异常: {e}")
        yield {"type": "error", "message": str(e)}


def generate_batch_character_stream(background, existing_characters, requirement='', user=None, project=None):
    prompt = CHARACTER_BATCH_STREAM_PROMPT.format(
        background=background or '未提供具体背景信息',
        existing_characters=existing_characters or '暂无已有角色',
        user_requirement=requirement or '请根据背景创建合适的角色'
    )

    messages = [
        SystemMessage(content="你是一位专业的角色设计大师。必须严格按照指定的分隔符格式输出每个完整角色，不要任何其他文字。"),
        HumanMessage(content=prompt)
    ]

    try:
        stream_response = _call_with_retry(messages, stream=True, user=user, scene="character_design")
        
        full_content = ""
        for content_chunk in stream_response:
            if content_chunk:
                full_content += content_chunk
                yield {"type": "chunk", "data": content_chunk}
        
        yield {"type": "complete", "data": full_content}
    except Exception as e:
        logger.error(f"批量流式角色生成异常: {e}")
        yield {"type": "error", "message": str(e)}


def polish_character_stream(character_data_str, user=None, project=None):
    prompt = CHARACTER_POLISH_V2_PROMPT.format(
        character_data=character_data_str
    )

    messages = [
        SystemMessage(content="你是一位专业的小说角色编辑。必须返回完整的JSON对象，不要其他文字说明。"),
        HumanMessage(content=prompt)
    ]

    try:
        stream_response = _call_with_retry(messages, stream=True, user=user, scene="character_design")
        
        full_content = ""
        for content_chunk in stream_response:
            if content_chunk:
                full_content += content_chunk
                yield {"type": "chunk", "data": content_chunk}

        yield {"type": "complete", "data": full_content}
    except Exception as e:
        logger.error(f"流式角色润色异常: {e}")
        yield {"type": "error", "message": str(e)}


RELATIONSHIP_REVERSE = {
    'friend': 'friend',
    'lover': 'lover',
    'spouse': 'spouse',
    'parent': 'child',
    'child': 'parent',
    'sibling': 'sibling',
    'master': 'apprentice',
    'apprentice': 'master',
    'enemy': 'enemy',
    'rival': 'rival',
    'mentor': 'protégé',
    'protégé': 'mentor',
    'ally': 'ally',
    'family': 'family',
    'other': 'other',
}


class ApiCharacterListView(APIView):
    """人物列表API"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            characters = project.characters.filter(is_deleted=False).order_by('role_type', 'name')
            data = [{
                'id': c.id,
                'name': c.name,
                'role_type': c.role_type,
                'role_type_display': c.get_role_type_display(),
                'faction': c.faction,
                'tagline': c.tagline,
            } for c in characters]
            return JsonResponse({'success': True, 'characters': data})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    def post(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            data = request.data
            name = data.get('name', '').strip()

            if not name:
                return JsonResponse({'success': False, 'error': '角色名称不能为空'}, status=400)

            if Character.objects.filter(project=project, name=name, is_deleted=False).exists():
                return JsonResponse({'success': False, 'error': '该角色名称已存在'}, status=400)

            character = Character.objects.create(
                project=project,
                name=name,
                role_type=data.get('role_type', 'supporting'),
                gender=data.get('gender', 'unknown'),
                appearance=data.get('appearance', ''),
                personality=data.get('personality', ''),
                backstory=data.get('backstory', ''),
                motivation=data.get('motivation', ''),
                tagline=data.get('tagline', ''),
                faction=data.get('faction', ''),
                extra=data.get('extra', {})
            )

            extra = data.get('extra', {})
            relationships = data.get('relationships', extra.get('relationships', ''))
            if relationships:
                self._create_relationships_from_string(project, character, relationships)

            return JsonResponse({
                'success': True,
                'character': {
                    'id': character.id,
                    'name': character.name,
                    'role_type': character.role_type,
                    'role_type_display': character.get_role_type_display(),
                    'gender': character.gender,
                    'gender_display': character.get_gender_display()
                }
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)


class ApiCharacterDetailView(APIView):
    """人物详情API"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, character_id):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            character = get_object_or_404(Character, pk=character_id, project=project, is_deleted=False)
            data = {
                'id': character.id,
                'name': character.name,
                'role_type': character.role_type,
                'role_type_display': character.get_role_type_display(),
                'gender': character.gender,
                'gender_display': character.get_gender_display(),
                'appearance': character.appearance,
                'personality': character.personality,
                'backstory': character.backstory,
                'motivation': character.motivation,
                'tagline': character.tagline,
                'faction': character.faction,
                'extra': character.extra or {},
            }
            return JsonResponse({'success': True, 'character': data})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    def put(self, request, pk, character_id):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            character = get_object_or_404(Character, pk=character_id, project=project, is_deleted=False)
            data = request.data
            name = data.get('name', '').strip()

            if not name:
                return JsonResponse({'success': False, 'error': '角色名称不能为空'}, status=400)

            if Character.objects.filter(project=project, name=name, is_deleted=False).exclude(pk=character_id).exists():
                return JsonResponse({'success': False, 'error': '该角色名称已存在'}, status=400)

            character.name = name
            character.role_type = data.get('role_type', character.role_type)
            character.gender = data.get('gender', character.gender)
            character.appearance = data.get('appearance', character.appearance)
            character.personality = data.get('personality', character.personality)
            character.backstory = data.get('backstory', character.backstory)
            character.motivation = data.get('motivation', character.motivation)
            character.tagline = data.get('tagline', character.tagline)
            character.faction = data.get('faction', character.faction)
            character.extra = data.get('extra', character.extra)
            character.save()

            extra = data.get('extra', {})
            relationships = extra.get('relationships', [])
            if relationships:
                self._create_reverse_relationships(project, character, relationships)

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    def delete(self, request, pk, character_id):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            character = get_object_or_404(Character, pk=character_id, project=project, is_deleted=False)
            character.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    def _create_reverse_relationships(self, project, character, relationships):
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


class ApiCharacterGenerateView(APIView):
    """AI流式生成角色预览（单个或批量）"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        requirement = request.data.get('requirement', '')
        count = int(request.data.get('count', 1))
        is_batch = request.data.get('is_batch', False)

        project = None
        if pk:
            try:
                project = ProjectList.objects.get(pk=pk, user=request.user)
            except ProjectList.DoesNotExist:
                pass

        existing_str = ''
        if project:
            existing_chars = project.characters.filter(is_deleted=False).order_by('name')
            existing_str = '\n'.join([f"- {c.name}({c.get_role_type_display()}): {c.personality or '暂无'}" for c in existing_chars[:10]])

        worldview_data = ''
        if project:
            wvs = project.worldviews.filter(is_deleted=False)[:5]
            if wvs:
                worldview_data = '\n'.join([f"世界观: {w.content[:200]}" for w in wvs])

        background_parts = []
        if project and project.description:
            background_parts.append(f"简介: {project.description}")
        if worldview_data:
            background_parts.append(f"世界观:\n{worldview_data}")

        background = '\n'.join(background_parts) or '未提供具体背景'

        def generate():
            if is_batch:
                yield "data: {\"type\": \"start\", \"data\": \"开始批量生成角色...\"}\n\n"
                for result in generate_batch_character_stream(
                    background=background,
                    existing_characters=existing_str,
                    requirement=requirement,
                    user=request.user,
                    project=project
                ):
                    yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
            else:
                yield "data: {\"type\": \"start\", \"data\": \"开始生成角色...\"}\n\n"
                for result in generate_character_stream(
                    background=background,
                    existing_characters=existing_str,
                    requirement=requirement,
                    count=count,
                    user=request.user,
                    project=project
                ):
                    yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response


class ApiCharacterPolishView(APIView):
    """AI角色润色API - 流式返回"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            project = get_object_or_404(ProjectList, pk=pk, user=request.user)
            data = request.data

            character_data = {
                'name': data.get('name', ''),
                'gender': data.get('gender', ''),
                'role': data.get('role', ''),
                'age': data.get('age', ''),
                'identity': data.get('identity', ''),
                'personality': data.get('personality', ''),
                'strengths': data.get('strengths', ''),
                'flaws': data.get('flaws', ''),
                'obsession': data.get('obsession', ''),
                'motivation': data.get('motivation', ''),
                'appearance': data.get('appearance', ''),
                'faction': data.get('faction', ''),
                'relationships': data.get('relationships', ''),
                'abilities': data.get('abilities', ''),
                'taboos': data.get('taboos', ''),
                'dark_history': data.get('dark_history', ''),
                'secrets': data.get('secrets', ''),
                'backstory': data.get('backstory', ''),
                'development': data.get('development', ''),
                'weaknesses': data.get('weaknesses', ''),
                'tags': data.get('tags', '')
            }

            try:
                def generate():
                    for chunk in polish_character_stream(
                        json.dumps(character_data, ensure_ascii=False),
                        user=request.user,
                        project=project
                    ):
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"

                response = StreamingHttpResponse(generate(), content_type='text/event-stream')
                response['Cache-Control'] = 'no-cache'
                response['X-Accel-Buffering'] = 'no'
                return response

            except Exception as e:
                logger.error(f"AI润色失败: {e}")
                return JsonResponse({
                    'success': False,
                    'error': 'AI润色失败，请稍后重试'
                })
        except Exception as e:
            logger.error(f"角色润色异常: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
