import json
import re
from django.db import transaction
from loguru import logger
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
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
from apps.characters.constants import (
    RELATIONSHIP_REVERSE,
    VALID_RELATIONSHIP_TYPES,
    get_reverse_type,
    normalize_relationship_type,
)
from apps.characters.prompts import (
    CHARACTER_GENERATE_SYSTEM_PROMPT,
    CHARACTER_GENERATE_USER_PROMPT,
    CHARACTER_POLISH_SYSTEM_PROMPT,
    CHARACTER_POLISH_USER_PROMPT,
    CHARACTER_CHECK_SYSTEM_PROMPT,
    CHARACTER_CHECK_USER_PROMPT,
    CHARACTER_OPTIMIZE_SYSTEM_PROMPT,
    CHARACTER_OPTIMIZE_USER_PROMPT,
)


class BaseCharacterAPIView(APIView):
    """角色API基础类 - 封装鉴权和项目查询"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get_project(self, request, pk):
        """获取项目，如果不存在则抛出404异常"""
        return get_object_or_404(ProjectList, pk=pk, user=request.user)

    def _get_worldview_str(self, project):
        """获取项目世界观描述字符串"""
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
        return worldview_str

    def _format_character_data(self, characters):
        """将角色列表格式化为 LLM 输入字符串"""
        characters_data_parts = []
        for c in characters:
            parts = [f"角色：{c.name}"]
            parts.append(f"  定位：{c.role_type}")
            parts.append(f"  性别：{c.gender}")
            if c.age:
                parts.append(f"  年龄：{c.age}")
            if c.identity:
                parts.append(f"  身份：{c.identity}")
            if c.personality:
                parts.append(f"  性格：{c.personality}")
            if c.appearance:
                parts.append(f"  外貌：{c.appearance}")
            if c.faction:
                parts.append(f"  势力：{c.faction}")
            if c.backstory:
                parts.append(f"  背景：{c.backstory}")
            if c.motivation:
                parts.append(f"  动机：{c.motivation}")
            if c.strengths:
                parts.append(f"  优点：{c.strengths}")
            if c.flaws:
                parts.append(f"  缺点：{c.flaws}")
            if c.obsession:
                parts.append(f"  执念：{c.obsession}")
            if c.abilities:
                parts.append(f"  能力：{c.abilities}")
            if c.taboos:
                parts.append(f"  禁忌：{c.taboos}")
            if c.secrets:
                parts.append(f"  秘密：{c.secrets}")
            if c.dark_history:
                parts.append(f"  黑历史：{c.dark_history}")
            if c.development:
                parts.append(f"  成长轨迹：{c.development}")
            if c.weaknesses:
                parts.append(f"  弱点：{c.weaknesses}")
            if c.relationships:
                rels = c.relationships
                if isinstance(rels, list):
                    rel_strs = []
                    for r in rels:
                        if isinstance(r, dict):
                            r_type = normalize_relationship_type(r.get('relationshipType'))
                            r_target = r.get('targetName', '?')
                            r_desc = r.get('description', '')
                            # 明确标注：关系类型以本人为基准
                            rel_strs.append(f"{r_target}是我的{r_type}{' - ' + r_desc if r_desc else ''}")
                        else:
                            rel_strs.append(str(r))
                    parts.append(f"  关系（以本人为基准，描述对方相对于本人的角色）：{'; '.join(rel_strs)}")
                elif isinstance(rels, str):
                    parts.append(f"  关系（以本人为基准）：{rels}")
            if c.experiences:
                exps = c.experiences
                if isinstance(exps, list) and exps:
                    exp_strs = [f"{e.get('chapter', '?')}: {e.get('event', '?')}" for e in exps if isinstance(e, dict)]
                    parts.append(f"  经历：{'; '.join(exp_strs)}")
            characters_data_parts.append('\n'.join(parts))
        return '\n\n'.join(characters_data_parts)

    def _create_reverse_relationships(self, project, character, relationships):
        """创建反向关系"""
        # 批量查询所有目标角色，避免 N+1
        target_names = [
            rel.get('targetName') for rel in relationships
            if isinstance(rel, dict) and rel.get('createReverse') and rel.get('targetName')
        ]
        target_chars_map = {}
        if target_names:
            for char in Character.objects.filter(
                project=project, name__in=target_names, is_deleted=False
            ):
                target_chars_map[char.name] = char

        for rel in relationships:
            if not isinstance(rel, dict):
                continue
            if not rel.get('createReverse') or not rel.get('targetName'):
                continue

            target_name = rel.get('targetName')
            target_char = target_chars_map.get(target_name)

            if not target_char:
                continue

            rel_type = normalize_relationship_type(rel.get('relationshipType'))
            reverse_type = get_reverse_type(rel_type)

            target_rels = target_char.relationships or []

            # 检查是否已存在指向该角色的同向或反向关系（避免重复创建）
            existing_rel = next(
                (r for r in target_rels if isinstance(r, dict)
                 and r.get('targetName') == character.name),
                None
            )

            if existing_rel:
                # 已有关系，检查类型是否需要更新为正确的反向类型
                existing_type = existing_rel.get('relationshipType', '其他')
                if existing_type != reverse_type:
                    # 类型不匹配时更新为正确的反向类型
                    existing_rel['relationshipType'] = reverse_type
                    existing_rel['createReverse'] = False
                    target_char.relationships = target_rels
                    target_char.save()
                continue

            target_rels.append({
                'targetName': character.name,
                'relationshipType': reverse_type,
                'description': rel.get('description', ''),
                'createReverse': False
            })
            target_char.relationships = target_rels
            target_char.save()

    def _stream_llm_response(self, system_prompt, user_prompt, prompt_vars, user, scene, error_msg='操作失败，请重试', post_process=None):
        """通用 LLM 流式调用，返回 StreamingHttpResponse

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词模板
            prompt_vars: 提示词变量
            user: 当前用户
            scene: LLM 场景标识
            error_msg: 错误提示信息
            post_process: 可选后处理函数，接收 full_content，返回最终 data 值
        """
        def generate():
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", system_prompt),
                    ("user", user_prompt),
                ])
                llm = get_llm(user=user, scene=scene)
                chain = prompt | llm

                stream_response = chain.stream(prompt_vars)

                full_content = ""
                for chunk in stream_response:
                    chunk_content = chunk.content if hasattr(chunk, 'content') else str(chunk)
                    full_content += chunk_content

                if post_process:
                    data_value = post_process(full_content)
                else:
                    data_value = full_content

                yield f"data: {json.dumps({'type': 'complete', 'data': data_value}, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"LLM流式调用异常(scene={scene}): {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg}, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    def _sync_reverse_relationships(self, project, character, old_relationships, new_relationships):
        """精确对比新旧关系差异，同步更新反向关系

        对比逻辑：
        1. 被删除的关系（旧有新无）→ 清理目标角色的反向关系
        2. 新增的关系（新有旧无）→ 在目标角色创建反向关系
        3. 类型变更的关系（同目标，类型不同）→ 更新目标角色的反向类型
        """
        # 构建索引：targetName → 关系对象
        old_map = {}
        for rel in old_relationships:
            if isinstance(rel, dict) and rel.get('targetName'):
                old_map[rel['targetName']] = rel

        new_map = {}
        for rel in new_relationships:
            if isinstance(rel, dict) and rel.get('targetName'):
                new_map[rel['targetName']] = rel

        old_targets = set(old_map.keys())
        new_targets = set(new_map.keys())
        all_target_names = old_targets | new_targets

        # 批量查询所有涉及的目标角色，避免 N+1
        target_chars_map = {}
        if all_target_names:
            for char in Character.objects.filter(
                project=project, name__in=all_target_names, is_deleted=False
            ):
                target_chars_map[char.name] = char

        # 1. 被删除的关系 → 清理反向
        for target_name in (old_targets - new_targets):
            target_char = target_chars_map.get(target_name)
            if target_char:
                target_rels = list(target_char.relationships or [])
                updated_rels = [
                    r for r in target_rels
                    if not (isinstance(r, dict) and r.get('targetName') == character.name)
                ]
                if len(updated_rels) != len(target_rels):
                    target_char.relationships = updated_rels
                    target_char.save()

        # 2. 新增的关系 → 创建反向
        for target_name in (new_targets - old_targets):
            new_rel = new_map[target_name]
            new_type = new_rel.get('relationshipType', '其他')
            reverse_type = get_reverse_type(new_type)
            target_char = target_chars_map.get(target_name)
            if target_char:
                target_rels = list(target_char.relationships or [])
                existing = next(
                    (r for r in target_rels if isinstance(r, dict) and r.get('targetName') == character.name),
                    None
                )
                if existing:
                    existing['relationshipType'] = reverse_type
                    existing['createReverse'] = False
                else:
                    target_rels.append({
                        'targetName': character.name,
                        'relationshipType': reverse_type,
                        'description': new_rel.get('description', ''),
                        'createReverse': False
                    })
                target_char.relationships = target_rels
                target_char.save()

        # 3. 类型变更的关系 → 更新反向类型
        for target_name in (old_targets & new_targets):
            old_type = old_map[target_name].get('relationshipType', '其他')
            new_type = new_map[target_name].get('relationshipType', '其他')
            if old_type != new_type:
                reverse_type = get_reverse_type(new_type)
                target_char = target_chars_map.get(target_name)
                if target_char:
                    target_rels = list(target_char.relationships or [])
                    for r in target_rels:
                        if isinstance(r, dict) and r.get('targetName') == character.name:
                            r['relationshipType'] = reverse_type
                            r['createReverse'] = False
                            break
                    target_char.relationships = target_rels
                    target_char.save()

    def _update_reverse_for_single_change(self, project, character, origin_rel, new_rel):
        """基于单条关系变更，精确更新目标角色的反向关系

        处理场景：
        1. origin 有 targetName, new 也有 targetName（同一目标，类型变了）→ 更新反向类型
        2. origin 有 targetName, new 无或 targetName 不同（关系被删除/替换）→ 清理旧反向
        3. origin 无, new 有 targetName（新增关系）→ 创建反向
        """
        origin_target = None
        origin_type = None
        new_target = None
        new_type = None

        # 解析 origin
        if isinstance(origin_rel, dict):
            origin_target = origin_rel.get('targetName')
            origin_type = origin_rel.get('relationshipType')
        elif isinstance(origin_rel, str):
            parsed = self._parse_relationship_string(origin_rel)
            if parsed:
                origin_target = parsed.get('targetName')
                origin_type = parsed.get('relationshipType')

        # 解析 new
        if isinstance(new_rel, dict):
            new_target = new_rel.get('targetName')
            new_type = new_rel.get('relationshipType')
        elif isinstance(new_rel, str):
            parsed = self._parse_relationship_string(new_rel)
            if parsed:
                new_target = parsed.get('targetName')
                new_type = parsed.get('relationshipType')

        # 场景1: 同一目标，类型变了 → 更新反向关系的类型
        if origin_target and new_target and origin_target == new_target:
            if origin_type != new_type and new_type:
                target_char = Character.objects.filter(
                    project=project, name=new_target, is_deleted=False
                ).first()
                if target_char:
                    reverse_type = get_reverse_type(new_type)
                    target_rels = list(target_char.relationships or [])
                    for r in target_rels:
                        if isinstance(r, dict) and r.get('targetName') == character.name:
                            r['relationshipType'] = reverse_type
                            r['createReverse'] = False
                            break
                    target_char.relationships = target_rels
                    target_char.save()
            return

        # 场景2: 目标变了或关系被删除 → 清理旧目标的反向关系
        if origin_target and origin_target != new_target:
            target_char = Character.objects.filter(
                project=project, name=origin_target, is_deleted=False
            ).first()
            if target_char:
                target_rels = list(target_char.relationships or [])
                updated_rels = [
                    r for r in target_rels
                    if not (isinstance(r, dict) and r.get('targetName') == character.name)
                ]
                if len(updated_rels) != len(target_rels):
                    target_char.relationships = updated_rels
                    target_char.save()

        # 场景3: 新增关系 → 在目标角色创建反向关系
        if new_target and new_target != origin_target:
            target_char = Character.objects.filter(
                project=project, name=new_target, is_deleted=False
            ).first()
            if target_char:
                reverse_type = get_reverse_type(new_type or '其他')
                target_rels = list(target_char.relationships or [])

                # 检查是否已有指向当前角色的关系
                existing = next(
                    (r for r in target_rels if isinstance(r, dict) and r.get('targetName') == character.name),
                    None
                )
                if existing:
                    # 已有关系，更新类型
                    existing['relationshipType'] = reverse_type
                    existing['createReverse'] = False
                else:
                    # 新增反向关系
                    desc = new_rel.get('description', '') if isinstance(new_rel, dict) else ''
                    target_rels.append({
                        'targetName': character.name,
                        'relationshipType': reverse_type,
                        'description': desc,
                        'createReverse': False
                    })
                target_char.relationships = target_rels
                target_char.save()

    def _apply_relationship_change(self, character, origin, new_value):
        """增量更新 relationships 字段：只修改指定的那条关系记录

        支持的输入格式：
        1. origin/new 都是 dict（推荐）：精确匹配并替换单条关系
        2. origin/new 都是 list：直接替换整个关系数组
        3. origin/new 是字符串：解析后按 targetName 匹配替换
        """
        current_rels = list(character.relationships or [])

        # 格式1: dict → dict，精确替换单条关系
        if isinstance(new_value, dict):
            new_rel = new_value
            # 归一化关系类型
            new_rel['relationshipType'] = normalize_relationship_type(new_rel.get('relationshipType'))
            # 确保有 createReverse 标记
            new_rel.setdefault('createReverse', True)

            if isinstance(origin, dict) and origin.get('targetName'):
                # 按 targetName 找到旧关系，替换
                target_name = origin['targetName']
                found = False
                for i, r in enumerate(current_rels):
                    if isinstance(r, dict) and r.get('targetName') == target_name:
                        current_rels[i] = new_rel
                        found = True
                        break
                if not found:
                    current_rels.append(new_rel)
            else:
                # 没有 origin 或 origin 无 targetName，追加
                current_rels.append(new_rel)

            character.relationships = current_rels
            return

        # 格式2: list → list，直接替换整个关系数组（逐条归一化）
        if isinstance(new_value, list):
            for r in new_value:
                if isinstance(r, dict):
                    r['relationshipType'] = normalize_relationship_type(r.get('relationshipType'))
            character.relationships = new_value
            return

        # 格式3: 字符串，解析后按 targetName 匹配替换
        if isinstance(new_value, str):
            new_rel = self._parse_relationship_string(new_value)
            if not new_rel:
                logger.warning(f"优化保存: 无法解析关系字符串 '{new_value}'，跳过")
                return

            origin_rel = self._parse_relationship_string(origin) if isinstance(origin, str) else None

            if origin_rel:
                target_name = origin_rel.get('targetName')
                found = False
                for i, r in enumerate(current_rels):
                    if isinstance(r, dict) and r.get('targetName') == target_name:
                        current_rels[i] = new_rel
                        found = True
                        break
                if not found:
                    current_rels.append(new_rel)
            else:
                current_rels.append(new_rel)

            character.relationships = current_rels

    @staticmethod
    def _parse_relationship_string(rel_str):
        """将格式化后的关系字符串解析为关系对象
        支持格式：
        - "刘禅是我的父母"
        - "刘禅是我的父母 - 严厉但深爱"
        - "父母-刘禅-严厉但深爱"（旧格式兼容）
        """
        if not rel_str or not isinstance(rel_str, str):
            return None

        rel_str = rel_str.strip()

        # 格式1: "XXX是我的YYY" 或 "XXX是我的YYY - 描述"
        match = re.match(r'(.+?)是我的(.+?)(?:\s*-\s*(.+))?$', rel_str)
        if match:
            return {
                'targetName': match.group(1).strip(),
                'relationshipType': normalize_relationship_type(match.group(2).strip()),
                'description': match.group(3).strip() if match.group(3) else '',
                'createReverse': True
            }

        # 格式2: "类型-目标名-描述"（旧格式兼容）
        parts = rel_str.split('-', 2)
        if len(parts) >= 2:
            return {
                'targetName': parts[1].strip(),
                'relationshipType': normalize_relationship_type(parts[0].strip()),
                'description': parts[2].strip() if len(parts) > 2 else '',
                'createReverse': True
            }

        return None


class ApiCharacterListView(BaseCharacterAPIView):
    """人物列表API"""

    def get(self, request, pk):
        """获取角色列表（包含已删除角色）"""
        project = self.get_project(request, pk)
        characters = project.characters.all().order_by('is_deleted', 'role_type', 'name')
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
            # 检查是否为重复名称错误
            name_errors = serializer.errors.get('name', [])
            is_duplicate = any(getattr(e, 'code', '') == 'DUPLICATE_NAME' or 'DUPLICATE_NAME' in str(e) for e in name_errors)

            error_messages = []
            for field, errors in serializer.errors.items():
                for err in errors:
                    err_str = str(err)
                    if err_str == 'DUPLICATE_NAME':
                        error_messages.append('该角色名称已存在')
                    elif field != 'non_field_errors':
                        error_messages.append(f"{field}: {err_str}")
                    else:
                        error_messages.append(err_str)

            return Response({
                'success': False,
                'error': '; '.join(error_messages) if error_messages else '参数校验失败',
                'error_type': 'duplicate' if is_duplicate else 'validation'
            }, status=status.HTTP_400_BAD_REQUEST)

        character = serializer.save(project=project)
        
        relationships = serializer.validated_data.get('relationships')
        if relationships and isinstance(relationships, list):
            self._create_reverse_relationships(project, character, relationships)

        return Response({
            'success': True,
            'character': {
                'id': character.id,
                'name': character.name,
                'role_type': character.role_type,
                'gender': character.gender
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
        character = get_object_or_404(Character, pk=character_id, project=project)

        # 支持恢复已删除角色
        action = request.data.get('action')
        if action == 'restore':
            try:
                character.is_deleted = False
                character.save()
            except Exception:
                # 同名角色已存在时，唯一约束冲突
                return Response(
                    {'success': False, 'error': f'已存在同名角色"{character.name}"，无法恢复'},
                    status=400
                )
            return Response({'success': True})

        if character.is_deleted:
            return Response({'success': False, 'error': '已删除的角色不能编辑，请先恢复'}, status=400)

        serializer = CharacterUpdateSerializer(
            instance=character,
            data=request.data,
            context={'project': project}
        )
        
        if not serializer.is_valid():
            # 检查是否为重复名称错误
            name_errors = serializer.errors.get('name', [])
            is_duplicate = any(getattr(e, 'code', '') == 'DUPLICATE_NAME' or 'DUPLICATE_NAME' in str(e) for e in name_errors)

            error_messages = []
            for field, errors in serializer.errors.items():
                for err in errors:
                    err_str = str(err)
                    if err_str == 'DUPLICATE_NAME':
                        error_messages.append('该角色名称已存在')
                    elif field != 'non_field_errors':
                        error_messages.append(f"{field}: {err_str}")
                    else:
                        error_messages.append(err_str)

            return Response({
                'success': False,
                'error': '; '.join(error_messages) if error_messages else '参数校验失败',
                'error_type': 'duplicate' if is_duplicate else 'validation'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 保存旧关系用于清理
        old_relationships = list(character.relationships or []) if character.relationships else []

        character = serializer.save()

        relationships = request.data.get('relationships', [])
        if relationships:
            # 精确对比新旧关系差异，更新反向关系
            new_relationships = character.relationships or []
            self._sync_reverse_relationships(project, character, old_relationships, new_relationships)

        return Response({'success': True})

    def delete(self, request, pk, character_id):
        """删除角色（软删除）"""
        project = self.get_project(request, pk)
        character = get_object_or_404(Character, pk=character_id, project=project, is_deleted=False)
        character.is_deleted = True
        character.save()
        return Response({'success': True})


class ApiCharacterGenerateView(BaseCharacterAPIView):
    """AI生成角色预览（单个或批量）"""

    def post(self, request, pk):
        requirement = request.data.get('requirement', '').strip()
        is_batch = request.data.get('is_batch', False)

        if not requirement:
            return Response({'success': False, 'error': '请输入角色描述'}, status=400)

        if len(requirement) > 2000:
            return Response({'success': False, 'error': '角色描述不能超过2000字'}, status=400)

        project = self.get_project(request, pk)

        existing_chars = project.characters.filter(is_deleted=False).order_by('name')
        existing_str = '\n'.join([f"- {c.name}({c.role_type})" for c in existing_chars[:10]]) or '暂无已有角色'

        worldview_str = self._get_worldview_str(project)

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

        return self._stream_llm_response(
            CHARACTER_GENERATE_SYSTEM_PROMPT,
            CHARACTER_GENERATE_USER_PROMPT,
            prompt_vars,
            request.user,
            scene="character_design",
            error_msg='角色生成失败，请重试',
        )


class ApiCharacterPolishView(BaseCharacterAPIView):
    """AI角色润色API - 流式返回"""

    def post(self, request, pk):
        project = self.get_project(request, pk)

        serializer = CharacterPolishSerializer(data=request.data)
        if not serializer.is_valid():
            error_messages = []
            for field, errors in serializer.errors.items():
                for err in errors:
                    error_messages.append(f"{field}: {str(err)}" if field != 'non_field_errors' else str(err))

            return Response({
                'success': False,
                'error': '; '.join(error_messages) if error_messages else '参数校验失败',
            }, status=status.HTTP_400_BAD_REQUEST)

        character_data = serializer.validated_data
        character_json = json.dumps(character_data, ensure_ascii=False)

        return self._stream_llm_response(
            CHARACTER_POLISH_SYSTEM_PROMPT,
            CHARACTER_POLISH_USER_PROMPT,
            {"character_data": character_json},
            request.user,
            scene="character_polish",
            error_msg='角色润色失败，请重试',
        )


class ApiCharacterCheckView(BaseCharacterAPIView):
    """AI角色检测API - 检查所有角色的设定问题"""

    def post(self, request, pk):
        project = self.get_project(request, pk)
        characters = project.characters.filter(is_deleted=False).order_by('role_type', 'name')

        if not characters.exists():
            return Response({'success': False, 'error': '暂无角色可检测'}, status=400)

        # 构建角色数据字符串
        characters_data = self._format_character_data(characters)

        # 获取世界观
        worldview_str = self._get_worldview_str(project)

        return self._stream_llm_response(
            CHARACTER_CHECK_SYSTEM_PROMPT,
            CHARACTER_CHECK_USER_PROMPT,
            {"worldview": worldview_str, "characters_data": characters_data},
            request.user,
            scene="character_check",
            error_msg='角色检测失败，请重试',
        )


class ApiCharacterOptimizeView(BaseCharacterAPIView):
    """AI角色优化API - 根据检测结果和用户指示优化角色"""

    @staticmethod
    def _post_process_optimize(full_content):
        """优化接口后处理：从 LLM 输出提取 JSON 数组并二次编码"""
        array_match = re.search(r'\[[\s\S]*\]', full_content)
        if array_match:
            try:
                parsed = json.loads(array_match.group(0))
                return json.dumps(parsed, ensure_ascii=False)
            except json.JSONDecodeError:
                pass
        return json.dumps(full_content, ensure_ascii=False)

    def post(self, request, pk):
        project = self.get_project(request, pk)

        issues = request.data.get('issues', [])
        if not issues:
            return Response({'success': False, 'error': '请提供需要优化的问题列表'}, status=400)

        # 构建角色数据
        char_names = set()
        for issue in issues:
            for name in issue.get('characters', []):
                char_names.add(name)

        characters = project.characters.filter(is_deleted=False, name__in=char_names).order_by('role_type', 'name')
        if not characters.exists():
            return Response({'success': False, 'error': '未找到相关角色'}, status=400)

        characters_data = self._format_character_data(characters)

        # 构建问题+指示
        issues_parts = []
        for i, issue in enumerate(issues):
            part = f"问题{i + 1}：\n"
            part += f"  类型：{issue.get('type', '')}\n"
            part += f"  涉及角色：{', '.join(issue.get('characters', []))}\n"
            part += f"  问题描述：{issue.get('description', '')}\n"
            part += f"  用户指示：{issue.get('instruction', '请自动优化')}"
            issues_parts.append(part)

        issues_with_instructions = '\n\n'.join(issues_parts)
        worldview_str = self._get_worldview_str(project)

        return self._stream_llm_response(
            CHARACTER_OPTIMIZE_SYSTEM_PROMPT,
            CHARACTER_OPTIMIZE_USER_PROMPT,
            {
                "worldview": worldview_str,
                "characters_data": characters_data,
                "issues_with_instructions": issues_with_instructions,
            },
            request.user,
            scene="character_optimize",
            error_msg='角色优化失败，请重试',
            post_process=self._post_process_optimize,
        )


class ApiCharacterOptimizeSaveView(BaseCharacterAPIView):
    """AI角色优化保存API - 批量保存用户选择的优化结果"""

    # 中文字段名 → 模型字段名映射
    FIELD_NAME_MAP = {
        '姓名': 'name', '名称': 'name',
        '性别': 'gender',
        '定位': 'role_type', '角色类型': 'role_type',
        '年龄': 'age',
        '身份': 'identity', '身份/称号': 'identity',
        '性格': 'personality', '性格特点': 'personality',
        '外貌': 'appearance', '外貌特征': 'appearance',
        '势力': 'faction', '势力/阵营': 'faction',
        '背景': 'backstory', '背景故事': 'backstory',
        '动机': 'motivation', '核心动机': 'motivation',
        '标签': 'tagline', '签名': 'tagline',
        '优点': 'strengths', '优点/特长': 'strengths',
        '缺点': 'flaws', '弱点': 'weaknesses', '弱点/代价': 'weaknesses',
        '执念': 'obsession', '执念/软肋': 'obsession',
        '能力': 'abilities',
        '禁忌': 'taboos',
        '秘密': 'secrets',
        '黑历史': 'dark_history', '过往黑历史': 'dark_history',
        '成长': 'development', '成长轨迹': 'development',
        '关系': 'relationships', '人际关系': 'relationships',
        '经历': 'experiences',
    }

    # 允许 setattr 设置的字段白名单（防止设置 is_deleted、project、name 等敏感字段）
    # name 不允许通过优化修改，因为后续用 name 做查找
    ALLOWED_FIELDS = set(FIELD_NAME_MAP.values()) - {'name'}

    # 文本字段最大长度限制
    MAX_TEXT_FIELD_LENGTH = 2000

    def post(self, request, pk):
        project = self.get_project(request, pk)
        items = request.data.get('optimizations', [])
        if not items:
            return Response({'success': False, 'error': '请提供优化项'}, status=400)

        saved_count = 0
        errors = []

        with transaction.atomic():
            for item in items:
                name = item.get('name', '').strip()
                op_type = item.get('type', 'modify')
                params = item.get('params', [])

                if not name:
                    errors.append(f"缺少角色名称，已跳过")
                    continue

                if op_type == 'delete':
                    count = Character.objects.filter(project=project, name=name, is_deleted=False).update(is_deleted=True)
                    if count:
                        saved_count += 1
                    continue

                if op_type == 'add':
                    # 校验名称唯一性
                    if Character.objects.filter(project=project, name=name, is_deleted=False).exists():
                        errors.append(f"角色 '{name}' 已存在，已跳过")
                        continue

                    character = Character(project=project, name=name)
                    for p in params:
                        field = self.FIELD_NAME_MAP.get(p.get('param', ''), p.get('param', ''))
                        if field not in self.ALLOWED_FIELDS:
                            logger.warning(f"优化保存: 字段 '{field}' 不在白名单中，已跳过")
                            continue
                        val = self._sanitize_field_value(character, field, p.get('new'))
                        if val is not None:
                            val = self._validate_field_length(field, val, errors)
                            try:
                                setattr(character, field, val)
                            except Exception:
                                pass
                    character.save()
                    saved_count += 1
                    continue

                # modify
                character = Character.objects.filter(project=project, name=name, is_deleted=False).first()
                if not character:
                    logger.warning(f"优化保存: 未找到角色 '{name}'")
                    continue

                # 先保存旧关系，用于后续清理反向关系
                old_relationships = list(character.relationships or []) if character.relationships else []

                # 收集所有关系变更（origin, new 对），用于精确更新反向关系
                relationship_changes = []

                has_relationships = False
                for p in params:
                    field = self.FIELD_NAME_MAP.get(p.get('param', ''), p.get('param', ''))
                    if field not in self.ALLOWED_FIELDS:
                        logger.warning(f"优化保存: 字段 '{field}' 不在白名单中，已跳过")
                        continue
                    if field == 'relationships':
                        has_relationships = True
                        # relationships 字段走增量更新，不走 setattr
                        self._apply_relationship_change(character, p.get('origin'), p.get('new'))
                        relationship_changes.append((p.get('origin'), p.get('new')))
                        continue
                    val = self._sanitize_field_value(character, field, p.get('new'))
                    if val is not None:
                        val = self._validate_field_length(field, val, errors)
                        try:
                            setattr(character, field, val)
                        except Exception as e:
                            logger.warning(f"优化保存: 设置 {name}.{field}={val!r} 失败: {e}")

                character.save()
                saved_count += 1

                if has_relationships:
                    # 基于单条关系变更，精确更新反向关系
                    for origin_rel, new_rel in relationship_changes:
                        self._update_reverse_for_single_change(project, character, origin_rel, new_rel)

        result = {'success': True, 'saved_count': saved_count}
        if errors:
            result['warnings'] = errors
        return Response(result)

    @staticmethod
    def _sanitize_field_value(instance, field_name, value):
        """对字段值做类型安全转换，返回处理后的值；返回 None 表示跳过该字段"""
        # age 必须是数字或 None
        if field_name == 'age':
            if value is None or value == '':
                return None
            try:
                # 尝试从字符串中提取数字
                if isinstance(value, str):
                    nums = re.findall(r'\d+', value)
                    if nums:
                        return int(nums[0])
                    return None
                return int(value)
            except (ValueError, TypeError):
                logger.warning(f"年龄值 '{value}' 无法解析为数字，已忽略")
                return None
        return value

    def _validate_field_length(self, field_name, value, warnings=None):
        """校验文本字段长度，超长则截断"""
        if isinstance(value, str) and len(value) > self.MAX_TEXT_FIELD_LENGTH:
            msg = f"字段 '{field_name}' 值超长({len(value)}字符)，已截断至{self.MAX_TEXT_FIELD_LENGTH}字符"
            logger.warning(f"优化保存: {msg}")
            if warnings is not None:
                warnings.append(msg)
            return value[:self.MAX_TEXT_FIELD_LENGTH]
        if isinstance(value, list):
            # JSON 字段（relationships/experiences）序列化后检查总长度
            serialized = json.dumps(value, ensure_ascii=False)
            if len(serialized) > self.MAX_TEXT_FIELD_LENGTH:
                msg = f"字段 '{field_name}' JSON超长({len(serialized)}字符)，已清空"
                logger.warning(f"优化保存: {msg}")
                if warnings is not None:
                    warnings.append(msg)
                return []
        return value


