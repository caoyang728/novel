"""重建知识图谱

Usage:
    python manage.py rebuild_graph              # 重建所有项目
    python manage.py rebuild_graph --project-id=1  # 重建指定项目
"""
from django.core.management.base import BaseCommand
from apps.project.models import ProjectList
from apps.graph.services import GraphService


class Command(BaseCommand):
    help = '重建知识图谱（从 Character 模型同步到 GraphNode/GraphEdge）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id', type=int, help='指定项目 ID，不指定则重建所有项目'
        )

    def handle(self, *args, **options):
        project_id = options.get('project_id')
        if project_id:
            projects = ProjectList.objects.filter(pk=project_id)
            if not projects.exists():
                self.stderr.write(f'项目 {project_id} 不存在')
                return
        else:
            projects = ProjectList.objects.all()

        for project in projects:
            self.stdout.write(f'重建项目 [{project.pk}] {project.title} 的图谱...')
            GraphService.rebuild_project(project.pk)
            self.stdout.write(self.style.SUCCESS(f'  完成'))

        self.stdout.write(self.style.SUCCESS('全部完成'))
