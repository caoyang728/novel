#!/bin/bash
set -e

echo "=== Novel Agent 容器启动 ==="

# 等待 MySQL 就绪
echo "等待 MySQL 就绪 ($MYSQL_DB_HOST:$MYSQL_DB_PORT)..."
while ! mysqladmin ping -h"$MYSQL_DB_HOST" -P"$MYSQL_DB_PORT" -u"$MYSQL_DB_USER" -p"$MYSQL_DB_PASSWORD" --silent 2>/dev/null; do
    sleep 2
done
echo "MySQL 已就绪"

# 执行数据库迁移
echo "执行数据库迁移..."
python manage.py migrate --noinput

# 收集静态文件（输出到 STATIC_ROOT=/app/staticfiles，供 nginx 直接服务）
echo "收集静态文件..."
python manage.py collectstatic --noinput --clear

echo "启动 Gunicorn (UvicornWorker)..."
exec gunicorn novel_agent.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 600 \
    --access-logfile - \
    --error-logfile -
