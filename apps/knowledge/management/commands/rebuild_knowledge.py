"""
Django Management Command: 重建知识库索引（pgvector 后端）

用法:
    python manage.py rebuild_knowledge --project-id=<id>        # 默认异步: 提交 Celery 任务后立即返回
    python manage.py rebuild_knowledge --project-id=<id> --sync # 同步: 当前进程阻塞跑完
    python manage.py rebuild_knowledge --all                    # 所有项目, 默认异步
    python manage.py rebuild_knowledge --all --sync
"""
from django.core.management.base import BaseCommand
from apps.project.models import ProjectList
from apps.knowledge.indexer import KnowledgeIndexer
from apps.knowledge import tasks


class Command(BaseCommand):
    help = '重建项目的 PostgreSQL pgvector 知识库索引'

    def add_arguments(self, parser):
        parser.add_argument(
            '--project-id',
            type=str,
            help='指定项目 ID',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='重建所有未删除项目的索引',
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='同步执行(默认提交到 Celery 队列后立即返回), 适用于 worker 未启动或迁移校验',
        )

    def handle(self, *args, **options):
        project_id = options.get('project_id')
        rebuild_all = options.get('all')
        sync = options.get('sync')

        if not project_id and not rebuild_all:
            self.stderr.write(self.style.ERROR('请指定 --project-id 或 --all'))
            return

        if rebuild_all:
            projects = ProjectList.objects.filter(is_deleted=False).only('pk', 'title')
        else:
            try:
                projects = [ProjectList.objects.get(pk=project_id)]
            except ProjectList.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'项目不存在: {project_id}'))
                return

        self.stdout.write(
            self.style.WARNING(
                f'执行模式: {"同步(当前进程)" if sync else "异步(Celery 队列)"}; 项目数: {len(projects)}'
            )
        )

        if sync:
            indexer = KnowledgeIndexer()
            for project in projects:
                try:
                    count = indexer.rebuild_project(project.pk)
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✔ [{project.pk}] {project.title}: 索引 {count} 条'))
                except Exception as e:  # noqa: BLE001
                    self.stderr.write(self.style.ERROR(
                        f'  ✘ [{project.pk}] {project.title}: {e}'))
        else:
            for project in projects:
                task = tasks.rebuild_project_task.delay(project.pk)
                self.stdout.write(self.style.SUCCESS(
                    f'  → [{project.pk}] {project.title}: task_id={task.id}'
                ))
            self.stdout.write(self.style.WARNING(
                '任务已提交。查看状态: celery -A novel_agent inspect active | grep rebuild_project'
            ))
