from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = '修复所有表的主键序列，确保与实际数据同步'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # 获取所有表名
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            fixed_count = 0
            for table in tables:
                # 检查表是否有 id 序列
                seq_name = f"{table}_id_seq"
                cursor.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM pg_class WHERE relname = %s
                    )
                """, [seq_name])
                has_seq = cursor.fetchone()[0]

                if has_seq:
                    # 获取表中最大 ID
                    cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}")
                    max_id = cursor.fetchone()[0]

                    # 重置序列
                    cursor.execute(f"SELECT setval('{seq_name}', {max_id + 1}, false)")
                    self.stdout.write(f"✓ {table}: 序列重置为 {max_id + 1}")
                    fixed_count += 1

            self.stdout.write(self.style.SUCCESS(f"\n成功修复 {fixed_count} 个表的序列"))
