# 修复 PostgreSQL 主键序列脚本 (PowerShell)

$DB_USER = "novel_agent"
$DB_NAME = "novel_agent"
$CONTAINER = "novel-postgres-1"

Write-Host "正在修复数据库序列..." -ForegroundColor Cyan

$sql = @"
DO `$`$
DECLARE
    r RECORD;
    max_val BIGINT;
BEGIN
    FOR r IN 
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
    LOOP
        EXECUTE format('SELECT COALESCE(MAX(id), 0) FROM %I', r.table_name) INTO max_val;
        IF EXISTS (SELECT 1 FROM pg_class WHERE relname = r.table_name || '_id_seq') THEN
            EXECUTE format('SELECT setval(%L, %s, false)', r.table_name || '_id_seq', max_val + 1);
            RAISE NOTICE 'Fixed: % -> %', r.table_name, max_val + 1;
        END IF;
    END LOOP;
END
`$`$;
"@

docker exec $CONTAINER psql -U $DB_USER -d $DB_NAME -c $sql

Write-Host "完成！" -ForegroundColor Green
