"""
Django Management Command: 重建知识库索引

用法:
    python manage.py rebuild_knowledge --project-id=<id>
    python manage.py rebuild_knowledge --all
"""
from django.core.management.base import BaseCommand
from apps.project.models import ProjectList
from apps.knowledge.indexer import KnowledgeIndexer
from loguru import logger


class Command(BaseCommand):
    help = '重建项目的 Milvus 知识库索引'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=str,
            help='指定项目 ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='重建所有项目的索引',
        )

    def handle(self, *args, **options):
        project_id = options.get('project_id')
        rebuild_all = options.get('all')

        if not project_id and not rebuild_all:
            self.stderr.write(self.style.ERROR('请指定 --project-id 或 --all'))
            return

        indexer = KnowledgeIndexer()

        if rebuild_all:
            projects = ProjectList.objects.all()
            self.stdout.write(f'开始重建 {projects.count()} 个项目的知识库...')
            for project in projects:
                try:
                    count = indexer.rebuild_project(project.pk)
                    self.stdout.write(self.style.SUCCESS(f'  [{project.pk}] {project.title}: {count} 条'))
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'  [{project.pk}] {project.title}: 失败 - {e}'))
        else:
            try:
                project = ProjectList.objects.get(pk=project_id)
                count = indexer.rebuild_project(project_id)
                self.stdout.write(self.style.SUCCESS(f'项目 [{project.pk}] {project.title}: 重建完成, 共 {count} 条'))
            except ProjectList.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'项目不存在: {project_id}'))
                return
