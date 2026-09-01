"""
知识库存储后端初始化（替换原 Milvus client）

- 确保 `vector` 扩展已创建
- 确保 KnowledgeVector 表/HNSW 索引已就绪（Django migrate 搞定）
- 对外暴露 `get_client_available()` 等兼容旧接口（永远返回 True，因为就是同库）
"""
import threading
from loguru import logger
from django.db import connection

_initialized = False
_init_lock = threading.Lock()


def ensure_vector_extension():
    """创建 vector 扩展（需要 superuser；若当前角色没权限则跳过，报错交给迁移阶段）"""
    try:
        with connection.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        logger.debug("PostgreSQL vector extension 已就绪")
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"创建 vector 扩展失败（Django migrate 会再尝试）：{e}")
        return False


def ensure_backend_ready():
    """懒加载 + 双重检查。保证第一次调用时扩展创建 + 表/索引存在。"""
    global _initialized
    if _initialized:
        return True
    with _init_lock:
        if _initialized:
            return True
        # 1) 扩展
        ensure_vector_extension()
        # 2) 确保表存在（在 Django 启动后 makemigrations/migrate 已跑；这里只做可用性探测）
        try:
            from .models import KnowledgeVector  # noqa: F401
            # 用一次 explain 查不到不报错即可
            with connection.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'knowledge_vector' LIMIT 1"
                )
                exists = cur.fetchone() is not None
            if exists:
                logger.info("知识库后端（PG+pgvector）已就绪")
            else:
                logger.warning("knowledge_vector 表尚未创建，请先运行 python manage.py migrate")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"知识库后端初始化检查失败：{e}")
        _initialized = True
    return True


def get_client():
    """兼容旧代码：原来返回 MilvusClient，这里返回 None 并让上层直接走 ORM。

    新代码请直接 from apps.knowledge.models import KnowledgeVector 操作；
    我们只保留接口占位，旧代码引用会在 indexer/retriever 重写时一起替换，不触发这里。
    """
    ensure_backend_ready()
    return None


def get_client_available():
    """知识库存储是否可用：对 PG+同库合一场景永远 True（除非 DB 挂，那 Django 也挂了）。"""
    ensure_backend_ready()
    return True


def get_collection_name():
    """兼容旧接口：返回表名。"""
    return 'knowledge_vector'


# 模块被 import 时不连 DB，真正调用 get_client_available/ensure_backend_ready 才初始化
