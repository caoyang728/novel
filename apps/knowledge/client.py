"""
Milvus 连接管理

支持两种模式:
- docker: 连接独立部署的 Milvus Standalone 服务（primary）
- local: 使用 pymilvus 嵌入式 (Milvus Lite)（fallback，数据存储在本地文件中）

docker 连接失败时自动降级到 local 模式
采用懒加载 + 双重检查锁模式, 避免启动时阻塞和线程安全问题

使用 MilvusClient API（非 ORM-style Collection），兼容 PyMilvus 3.x
"""
import os
import threading
from loguru import logger

_client = None
_client_initialized = False
_client_lock = threading.Lock()


def _connect_milvus(mode, embedding_dim, coll_name):
    """尝试连接 Milvus，返回 MilvusClient 或 None"""
    from pymilvus import MilvusClient

    if mode == "docker":
        milvus_host = os.getenv("MILVUS_HOST", "milvus")
        milvus_port = os.getenv("MILVUS_PORT", "19530")
        milvus_uri = f"http://{milvus_host}:{milvus_port}"
        client = MilvusClient(uri=milvus_uri, timeout=30)
        logger.info(f"Milvus 连接成功: {milvus_uri}")
    else:
        db_path = os.getenv("MILVUS_LOCAL_DB", os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "milvus_demo.db",
        ))
        client = MilvusClient(uri=db_path, timeout=30)
        logger.info(f"Milvus Lite 连接成功: {db_path}")

    if not client.has_collection(coll_name):
        client.create_collection(
            collection_name=coll_name,
            dimension=embedding_dim,
            metric_type="COSINE",
            primary_field_name="id",
            id_type="string",
            max_length=256,
            vector_field_name="embedding",
            auto_id=False,
            enable_dynamic_field=True,
        )
        logger.info(f"Milvus Collection '{coll_name}' 创建完成, 维度: {embedding_dim}")
    else:
        logger.info(f"Milvus Collection '{coll_name}' 已存在")

    return client


def get_client():
    """懒加载获取 MilvusClient, 首次调用时初始化"""
    global _client, _client_initialized

    if _client_initialized:
        return _client

    with _client_lock:
        if _client_initialized:
            return _client

        try:
            mode = os.getenv("MILVUS_MODE", "docker")
            embedding_dim = int(os.getenv("EMBEDDING_DIM", "1024"))
            coll_name = os.getenv("MILVUS_COLLECTION_NAME", "novel_knowledge")

            try:
                _client = _connect_milvus(mode, embedding_dim, coll_name)
            except Exception as e:
                logger.warning(f"Milvus {mode} 模式连接失败: {e}")
                fallback_mode = "local" if mode == "docker" else "docker"
                logger.info(f"尝试 fallback 到 {fallback_mode} 模式...")
                try:
                    _client = _connect_milvus(fallback_mode, embedding_dim, coll_name)
                except Exception as e2:
                    logger.warning(f"Milvus {fallback_mode} 模式也失败: {e2}, 将使用降级模式")
                    _client = None

            _client_initialized = True

        except Exception as e:
            logger.warning(f"Milvus 初始化异常, 将使用降级模式: {e}")
            _client = None
            _client_initialized = True

        return _client


def get_client_available():
    """检查 Milvus 是否可用"""
    return get_client() is not None


def get_collection_name():
    """获取当前使用的 Milvus Collection 名称"""
    return os.getenv("MILVUS_COLLECTION_NAME", "novel_knowledge")
