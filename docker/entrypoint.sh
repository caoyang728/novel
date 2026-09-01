#!/bin/bash
set -e

echo "=== Novel Agent 容器启动 ==="

# 等待 PostgreSQL 就绪
PG_HOST="${PG_DB_HOST:-localhost}"
PG_PORT="${PG_DB_PORT:-5432}"
PG_USER="${PG_DB_USER:-novel_agent}"
PG_DB="${PG_DB_DATABASE:-novel_agent}"
echo "等待 PostgreSQL 就绪 ($PG_HOST:$PG_PORT/$PG_DB)..."
while ! PGPASSWORD="$PG_DB_PASSWORD" pg_isready -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" -q 2>/dev/null; do
    sleep 2
done
echo "PostgreSQL 已就绪"

# 首次启动确保 vector 扩展与索引（即便迁移文件一般不管扩展，提前 CREATE EXTENSION 给 DB superuser 权限更高）
echo "确保 pgvector 扩展已创建..."
PGPASSWORD="$PG_DB_PASSWORD" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
    -c "CREATE EXTENSION IF NOT EXISTS vector;" 2>/dev/null || echo "[WARN] 创建扩展失败，迁移阶段会再尝试一次"

# 执行数据库迁移
# 先尝试 delete note 的旧迁移记录，解决跨版本迁移依赖断裂
echo "清理可能断裂的迁移记录..."
PGPASSWORD="$PG_DB_PASSWORD" psql -h "$PG_HOST" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
    -c "DELETE FROM django_migrations WHERE app = 'note';" 2>/dev/null || true

echo "执行数据库迁移..."
python manage.py migrate --noinput --fake-initial

# 收集静态文件（输出到 STATIC_ROOT=/app/staticfiles，供 nginx 直接服务）
echo "收集静态文件..."
python manage.py collectstatic --noinput --clear

# 兼容不同启动角色：DJANGO_ROLE=[web|worker|beat]，默认 web
ROLE="${DJANGO_ROLE:-web}"
echo "启动角色: $ROLE"
if [ "$ROLE" = "worker" ]; then
    exec celery -A novel_agent worker -l info --concurrency="${CELERY_CONCURRENCY:-4}" \
        --pool=prefork
elif [ "$ROLE" = "beat" ]; then
    # beat 必须确保 DB 中 PeriodicTask 表存在（上面 migrate 已建好）
    exec celery -A novel_agent beat -l info \
        --scheduler django_celery_beat.schedulers:DatabaseScheduler \
        --pidfile=
else
    echo "启动 Gunicorn (gthread worker，支持 SSE)..."
    exec gunicorn novel_agent.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers 2 \
        --threads 2 \
        --worker-class gthread \
        --timeout 600 \
        --access-logfile - \
        --error-logfile -
fi
