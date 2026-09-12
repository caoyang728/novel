"""
rebuild_trajectories — 对已有章节批量补录角色轨迹记录

用法:
  docker compose exec django python manage.py rebuild_trajectories --project_id=1
  docker compose exec django python manage.py rebuild_trajectories --project_id=1 --dry-run
"""
from django.core.management.base import BaseCommand
from loguru import logger

from apps.characters.models import Character, CharacterTrajectory
from apps.chapter.models import ChapterList
from apps.timeline.models import TimelineEvent


class Command(BaseCommand):
    help = '对已有章节批量补录角色轨迹记录'

    def add_arguments(self, parser):
        parser.add_argument('--project_id', type=int, required=True, help='项目 ID')
        parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际写入')

    def handle(self, *args, **options):
        project_id = options['project_id']
        dry_run = options['dry_run']

        # 获取已完成的章节（按章节号排序）
        chapters = ChapterList.objects.filter(
            volume__project_id=project_id,
        ).exclude(
            content=''
        ).order_by('chapter_number')

        if not chapters.exists():
            self.stdout.write(f'项目 {project_id} 没有已完成的章节')
            return

        # 获取项目中的所有角色
        characters = Character.objects.filter(project_id=project_id, is_deleted=False)
        if not characters.exists():
            self.stdout.write(f'项目 {project_id} 没有角色')
            return

        char_name_map = {c.name: c for c in characters}
        created_count = 0
        skipped_count = 0

        for chapter in chapters:
            # 检查该章节是否已有轨迹记录（通过 chapter_ids 字段匹配）
            existing = CharacterTrajectory.objects.filter(
                project_id=project_id, chapter_ids__contains=chapter.id
            ).count()
            if existing > 0:
                skipped_count += 1
                continue

            # 从章节内容中简单匹配角色出现（文本匹配）
            content = chapter.content or ''
            matched_chars = []
            for char_name, char_obj in char_name_map.items():
                if char_name in content:
                    matched_chars.append(char_obj)

            if not matched_chars:
                continue

            # 从章节事件中提取故事时间
            events = TimelineEvent.objects.filter(
                project_id=project_id, chapter=chapter, is_active=True
            ).order_by('start_year')

            story_year = None
            story_month = None
            if events.exists():
                first_event = events.first()
                story_year = first_event.start_year
                story_month = first_event.start_month

            # 收集该章涉及的地点
            locations = set(events.exclude(location='').values_list('location', flat=True))

            # 构建时间字符串
            time_str = ''
            if story_year is not None:
                time_str = f"开元{story_year}年"
                if story_month:
                    time_str += f"{story_month}月"

            chapter_number = chapter.chapter_number or 0

            if dry_run:
                self.stdout.write(
                    f'  [预览] 第{chapter_number}章 "{chapter.title}": '
                    f'{len(matched_chars)}个角色, 故事时间={story_year}年{story_month}月, '
                    f'地点={locations or "无"}'
                )
            else:
                for char in matched_chars:
                    details = {
                        'location': '、'.join(locations) if locations else '',
                        'summary': f'第{chapter_number}章出场',
                    }
                    CharacterTrajectory.objects.create(
                        character=char,
                        project_id=project_id,
                        source='chapter',
                        title=f"第{chapter_number}章出场",
                        start_time=time_str,
                        end_time=time_str,
                        chapter_ids=[chapter.id],
                        order=chapter_number,
                        details=details,
                    )
                    created_count += 1

        action = '预览' if dry_run else '补录'
        self.stdout.write(
            f'完成！{action}了 {created_count} 条轨迹记录，'
            f'跳过 {skipped_count} 个已有轨迹的章节，'
            f'共处理 {chapters.count()} 个章节'
        )
