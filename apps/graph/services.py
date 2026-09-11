"""
图谱服务层 —— 负责从 Character 模型同步数据到 GraphNode/GraphEdge
"""
from loguru import logger
from django.db import transaction, models as db_models

from apps.characters.models import Character
from apps.characters.constants import RELATIONSHIP_REVERSE, normalize_relationship_type
from .models import GraphNode, GraphEdge


class GraphService:
    """图谱数据同步和查询服务"""

    # ------------------------------------------------------------------ #
    #  同步单个角色
    # ------------------------------------------------------------------ #
    @staticmethod
    @transaction.atomic
    def sync_character(character_id: int):
        """将单个角色同步到图谱（节点 + 关系边 + 势力节点 + 反向边）"""
        try:
            char = Character.objects.get(pk=character_id)
        except Character.DoesNotExist:
            logger.warning(f"graph.sync_character: 角色 {character_id} 已删除，跳过")
            return

        project = char.project

        # 1. 创建/更新角色节点
        char_node, created = GraphNode.objects.update_or_create(
            project=project,
            node_type='character',
            name=char.name,
            defaults={
                'description': char.tagline or (char.content[:200] if char.content else ''),
                'properties': {
                    'role_type': char.role_type,
                    'gender': char.gender,
                    'age': char.age,
                    'identity': char.identity,
                    'faction': char.faction or '',
                },
                'source_id': char.pk,
            },
        )

        # 2. 处理势力节点 + belongs_to 边
        if char.faction:
            faction_node, _ = GraphNode.objects.get_or_create(
                project=project,
                node_type='faction',
                name=char.faction,
                defaults={'description': ''},
            )
            GraphEdge.objects.update_or_create(
                project=project,
                source=char_node,
                target=faction_node,
                edge_type='belongs_to',
                defaults={'description': '', 'is_bidirectional': False},
            )
        else:
            # 如果角色没有势力，清理旧的 belongs_to 边
            GraphEdge.objects.filter(
                project=project, source=char_node, edge_type='belongs_to'
            ).delete()

        # 3. 同步人际关系边
        relationships = char.relationships or []
        GraphService._sync_relationship_edges(project, char_node, relationships)

    # ------------------------------------------------------------------ #
    #  同步关系边（精确对比，增删改）
    # ------------------------------------------------------------------ #
    @staticmethod
    def _sync_relationship_edges(project, char_node, relationships):
        """精确对比新旧关系，同步图谱边"""
        # 现有的关系边（排除 belongs_to）
        existing_edges = {
            e.target.name: e
            for e in GraphEdge.objects.filter(
                project=project, source=char_node
            ).exclude(edge_type='belongs_to').select_related('target')
        }

        new_targets = set()
        for rel in relationships:
            if not isinstance(rel, dict):
                continue
            target_name = rel.get('targetName', '').strip()
            if not target_name:
                continue

            rel_type = normalize_relationship_type(rel.get('relationshipType'))
            desc = rel.get('description', '')
            new_targets.add(target_name)

            # 查找目标角色节点
            target_node = GraphNode.objects.filter(
                project=project, node_type='character', name=target_name
            ).first()
            if not target_node:
                # 目标角色可能还没同步到图谱，跳过
                continue

            edge, created = GraphEdge.objects.update_or_create(
                project=project,
                source=char_node,
                target=target_node,
                defaults={
                    'edge_type': rel_type,
                    'description': desc,
                    'is_bidirectional': rel_type in RELATIONSHIP_REVERSE,
                },
            )

        # 删除不再存在的关系边
        for target_name, edge in existing_edges.items():
            if target_name not in new_targets:
                edge.delete()

    # ------------------------------------------------------------------ #
    #  删除角色节点
    # ------------------------------------------------------------------ #
    @staticmethod
    def delete_character(character_id: int):
        """删除角色对应的图谱节点（CASCADE 自动清理关联的边）"""
        GraphNode.objects.filter(
            node_type='character', source_id=character_id
        ).delete()

    # ------------------------------------------------------------------ #
    #  全量重建
    # ------------------------------------------------------------------ #
    @staticmethod
    @transaction.atomic
    def build_trajectories_for_project(project_id: int):
        """遍历 CharacterTrajectory，生成 trajectory 类型的图谱边"""
        from apps.characters.models import CharacterTrajectory

        # 清理旧的 trajectory 边
        GraphEdge.objects.filter(
            project_id=project_id, edge_type='trajectory'
        ).delete()

        trajectories = CharacterTrajectory.objects.filter(
            project_id=project_id
        ).select_related('character')

        created = 0
        for traj in trajectories:
            # 获取或创建角色节点
            char_node = GraphNode.objects.filter(
                node_type='character', source_id=traj.character_id, project_id=project_id
            ).first()
            if not char_node:
                continue

            # 创建轨迹边：角色 -> 自身（自环边，记录轨迹事件）
            details = traj.details or {}
            description_parts = [traj.title]
            if details.get('location'):
                description_parts.append(f"地点: {details['location']}")
            if details.get('key_events'):
                description_parts.append(f"事件: {', '.join(details['key_events'][:3])}")

            GraphEdge.objects.create(
                project_id=project_id,
                source=char_node,
                target=char_node,
                edge_type='trajectory',
                description='; '.join(description_parts),
                properties={
                    'trajectory_id': traj.pk,
                    'start_time': traj.start_time,
                    'end_time': traj.end_time,
                    'order': traj.order,
                },
            )
            created += 1

        logger.info(
            f"graph.build_trajectories: 项目 {project_id} 生成 {created} 条轨迹边"
        )

    @staticmethod
    @transaction.atomic
    def rebuild_project(project_id: int):
        """全量重建项目图谱"""
        # 删除旧数据
        GraphNode.objects.filter(project_id=project_id).delete()

        # 遍历所有未删除的角色
        characters = Character.objects.filter(
            project_id=project_id, is_deleted=False
        )
        for char in characters:
            GraphService.sync_character(char.pk)

        # 构建轨迹边
        GraphService.build_trajectories_for_project(project_id)

        logger.info(
            f"graph.rebuild_project: 项目 {project_id} 图谱重建完成，"
            f"共 {characters.count()} 个角色"
        )

    # ------------------------------------------------------------------ #
    #  查询：完整图谱
    # ------------------------------------------------------------------ #
    # 边缘类型显示映射（英文→中文）
    EDGE_TYPE_DISPLAY = {
        'belongs_to': '所属',
    }

    @staticmethod
    def get_graph_data(project_id, node_types=None, edge_types=None):
        """获取项目完整图谱数据（含统计）"""
        nodes_qs = GraphNode.objects.filter(project_id=project_id)
        if node_types:
            nodes_qs = nodes_qs.filter(node_type__in=node_types.split(','))

        edges_qs = GraphEdge.objects.filter(project_id=project_id)
        if edge_types:
            edges_qs = edges_qs.filter(edge_type__in=edge_types.split(','))

        # 如果有节点类型筛选，边也要跟着过滤
        if node_types:
            allowed_node_ids = set(nodes_qs.values_list('id', flat=True))
            edges_qs = edges_qs.filter(source_id__in=allowed_node_ids, target_id__in=allowed_node_ids)

        # 一次性查询
        nodes = list(nodes_qs.values('id', 'node_type', 'name', 'description', 'properties'))
        edges_raw = list(edges_qs.values('id', 'source_id', 'target_id', 'edge_type', 'description', 'is_bidirectional'))

        # 映射边缘类型显示名
        display_map = GraphService.EDGE_TYPE_DISPLAY
        for e in edges_raw:
            et = e['edge_type']
            if et in display_map:
                e['edge_type'] = display_map[et]

        # 同时计算统计（复用已查询的数据，避免额外 DB 查询）
        from collections import Counter
        nodes_by_type = Counter(n['node_type'] for n in nodes)
        edges_by_type = Counter(e['edge_type'] for e in edges_raw)
        stats = {
            'total_nodes': len(nodes),
            'total_edges': len(edges_raw),
            'nodes_by_type': dict(nodes_by_type),
            'edges_by_type': dict(edges_by_type),
        }

        return {'nodes': nodes, 'edges': list(edges_raw), 'stats': stats}

    # ------------------------------------------------------------------ #
    #  查询：角色子图
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_character_subgraph(project_id, character_name, hops=1):
        """获取指定角色的 N 跳子图"""
        # 找到起始节点
        start_node = GraphNode.objects.filter(
            project_id=project_id, node_type='character', name=character_name
        ).first()
        if not start_node:
            return {'nodes': [], 'edges': []}

        visited_nodes = {start_node.id}
        visited_edges = set()
        frontier = {start_node.id}

        for _ in range(hops):
            if not frontier:
                break

            # 查找与 frontier 相连的所有边
            from django.db.models import Q
            edges = GraphEdge.objects.filter(
                project_id=project_id
            ).filter(
                Q(source_id__in=frontier) | Q(target_id__in=frontier)
            ).select_related('source', 'target')

            new_frontier = set()
            for e in edges:
                if e.id in visited_edges:
                    continue
                visited_edges.add(e.id)

                if e.source_id not in visited_nodes:
                    new_frontier.add(e.source_id)
                    visited_nodes.add(e.source_id)
                if e.target_id not in visited_nodes:
                    new_frontier.add(e.target_id)
                    visited_nodes.add(e.target_id)

            frontier = new_frontier

        # 构建结果
        nodes = GraphNode.objects.filter(id__in=visited_nodes)
        edges = GraphEdge.objects.filter(id__in=visited_edges).select_related('source', 'target')

        display_map = GraphService.EDGE_TYPE_DISPLAY

        return {
            'nodes': [
                {
                    'id': n.id,
                    'node_type': n.node_type,
                    'name': n.name,
                    'description': n.description,
                    'properties': n.properties,
                }
                for n in nodes
            ],
            'edges': [
                {
                    'id': e.id,
                    'source_id': e.source_id,
                    'target_id': e.target_id,
                    'edge_type': display_map.get(e.edge_type, e.edge_type),
                    'description': e.description,
                    'is_bidirectional': e.is_bidirectional,
                }
                for e in edges
            ],
        }

    # ------------------------------------------------------------------ #
    #  查询：统计信息
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_stats(project_id):
        """获取图谱统计信息"""
        from django.db.models import Count

        total_nodes = GraphNode.objects.filter(project_id=project_id).count()
        total_edges = GraphEdge.objects.filter(project_id=project_id).count()

        nodes_by_type = dict(
            GraphNode.objects.filter(project_id=project_id)
            .values_list('node_type')
            .annotate(count=Count('id'))
            .values_list('node_type', 'count')
        )

        edges_by_type = dict(
            GraphEdge.objects.filter(project_id=project_id)
            .values_list('edge_type')
            .annotate(count=Count('id'))
            .values_list('edge_type', 'count')
        )

        # 映射边缘类型显示名
        display_map = GraphService.EDGE_TYPE_DISPLAY
        edges_by_type = {
            display_map.get(k, k): v for k, v in edges_by_type.items()
        }

        return {
            'total_nodes': total_nodes,
            'total_edges': total_edges,
            'nodes_by_type': nodes_by_type,
            'edges_by_type': edges_by_type,
        }

    # ------------------------------------------------------------------ #
    #  地点节点同步
    # ------------------------------------------------------------------ #
    @staticmethod
    def upsert_location(project_id, name, description=''):
        """幂等创建或更新地点节点，返回 GraphNode 实例"""
        if not name or not name.strip():
            return None
        node, created = GraphNode.objects.update_or_create(
            project_id=project_id,
            node_type='location',
            name=name.strip(),
            defaults={'description': description},
        )
        return node

    # ------------------------------------------------------------------ #
    #  时间线事件同步
    # ------------------------------------------------------------------ #
    @staticmethod
    @transaction.atomic
    def sync_timeline_event(timeline_event):
        """同步时间线事件到图谱：创建 event 节点 + occurs_at 边 + involves 边"""
        project = timeline_event.project

        # 1. 创建/更新事件节点
        event_node, _ = GraphNode.objects.update_or_create(
            project=project,
            node_type='event',
            name=timeline_event.title,
            defaults={
                'description': timeline_event.description or '',
                'properties': {
                    'event_type': timeline_event.event_type,
                    'start_year': timeline_event.start_year,
                    'start_month': timeline_event.start_month,
                    'end_year': timeline_event.end_year,
                    'end_month': timeline_event.end_month,
                    'is_time_estimated': timeline_event.is_time_estimated,
                },
                'source_id': timeline_event.pk,
            },
        )

        # 2. 创建 occurs_at 边（事件 → 地点）
        if timeline_event.location:
            location_node = GraphService.upsert_location(
                project.pk, timeline_event.location
            )
            if location_node:
                GraphEdge.objects.update_or_create(
                    project=project,
                    source=event_node,
                    target=location_node,
                    edge_type='occurs_at',
                    defaults={'description': '', 'is_bidirectional': False},
                )

        # 3. 创建 involves 边（事件 → 人物）
        characters = timeline_event.characters.all()
        for char in characters:
            char_node = GraphNode.objects.filter(
                project=project, node_type='character', source_id=char.pk
            ).first()
            if char_node:
                GraphEdge.objects.update_or_create(
                    project=project,
                    source=event_node,
                    target=char_node,
                    edge_type='involves',
                    defaults={'description': '', 'is_bidirectional': False},
                )

    @staticmethod
    def delete_timeline_event(timeline_event_id):
        """清理时间线事件对应的图谱节点和边"""
        GraphNode.objects.filter(
            node_type='event', source_id=timeline_event_id
        ).delete()

    # ------------------------------------------------------------------ #
    #  人物在场边同步
    # ------------------------------------------------------------------ #
    @staticmethod
    def sync_present_at(character, location_name, story_year=None, story_month=None):
        """同步人物在场边（properties 存故事时间）"""
        if not location_name or not character:
            return
        project = character.project
        char_node = GraphNode.objects.filter(
            project=project, node_type='character', source_id=character.pk
        ).first()
        if not char_node:
            return
        location_node = GraphService.upsert_location(project.pk, location_name)
        if not location_node:
            return
        properties = {}
        if story_year is not None:
            properties['story_year'] = story_year
        if story_month is not None:
            properties['story_month'] = story_month
        GraphEdge.objects.update_or_create(
            project=project,
            source=char_node,
            target=location_node,
            edge_type='present_at',
            defaults={
                'description': '',
                'is_bidirectional': False,
                'properties': properties,
            },
        )
