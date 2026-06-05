"""
临时脚本：将 Character.extra 中的数据迁移到新字段

用法: python manage.py migrate_extra_fields
      python manage.py migrate_extra_fields --dry-run  # 只预览不动库

字段映射:
  extra.age          → age
  extra.identity     → identity
  extra.relationships → relationships
  extra.experiences  → experiences
  extra.development  → development
  extra.strengths    → strengths
  extra.flaws        → flaws
  extra.obsession    → obsession
  extra.taboos       → taboos
  extra.abilities    → abilities
  extra.secrets      → secrets
  extra.dark_history → dark_history
  extra.weaknesses   → weaknesses
  extra.motivation   → motivation（仅当 motivation 字段为空时覆盖）
"""

from django.core.management.base import BaseCommand
from apps.characters.models import Character
from loguru import logger


FIELD_MAP = {
    'age': str,
    'identity': str,
    'development': str,
    'strengths': str,
    'flaws': str,
    'obsession': str,
    'taboos': str,
    'abilities': str,
    'secrets': str,
    'dark_history': str,
    'weaknesses': str,
}

JSON_FIELDS = {'relationships', 'experiences'}


class Command(BaseCommand):
    help = '将 Character.extra 中的数据迁移到新字段'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅预览需要迁移的数据，不实际写入',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        characters = Character.objects.filter(is_deleted=False).order_by('id')
        total = characters.count()
        migrated = 0
        skipped = 0

        logger.info(f"共找到 {total} 个角色 (dry_run={dry_run})")

        for c in characters:
            extra = c.extra
            if not extra or not isinstance(extra, dict):
                skipped += 1
                continue

            changed = False
            updates = {}

            # 普通文本字段
            for field, cast in FIELD_MAP.items():
                val = extra.get(field)
                if val and cast(getattr(c, field, '') or '') != cast(val):
                    if cast == str and isinstance(val, (int, float)):
                        val = str(val)
                    updates[field] = val
                    if not dry_run:
                        setattr(c, field, val)
                    changed = True

            # motivation（仅当 motivation 字段为空时）
            extra_motivation = extra.get('motivation')
            if extra_motivation and not c.motivation:
                updates['motivation'] = str(extra_motivation)
                if not dry_run:
                    c.motivation = str(extra_motivation)
                changed = True

            # JSON 字段
            for field in JSON_FIELDS:
                val = extra.get(field)
                if val and isinstance(val, list) and len(val) > 0:
                    current = getattr(c, field, []) or []
                    if current != val:
                        updates[field] = val
                        if not dry_run:
                            setattr(c, field, val)
                        changed = True

            if changed:
                migrated += 1
                logger.info(f"[{'DRY' if dry_run else 'OK'}] {c.name}(id={c.id}): {updates}")
                if not dry_run:
                    c.save(update_fields=list(updates.keys()))
            else:
                skipped += 1

        logger.info(f"完成: 迁移 {migrated} 个, 跳过 {skipped} 个 (共 {total} 个)")
