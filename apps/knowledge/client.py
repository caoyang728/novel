"""
Milvus 连接管理

支持两种模式:
- local: 使用 pymilvus 嵌入式 (Milvus Lite), 数据存储在本地文件中
- docker: 连接独立部署的 Milvus Standalone 服务

采用懒加载 + 双重检查锁模式, 避免启动时阻塞和线程安全问题
"""
import os
import threading
from loguru import logger

_connection_lock = threading.Lock()
_collection = None
_collection_initialized = False


def get_collection():
    """懒加载获取 Milvus Collection, 首次调用时初始化"""
    global _collection, _collection_initialized

    if _collection_initialized:
        return _collection

    with _connection_lock:
        if _collection_initialized:
            return _collection

        try:
            from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility

            mode = os.getenv("MILVUS_MODE", "local")
            embedding_dim = int(os.getenv("EMBEDDING_DIM", "1024"))
            coll_name = os.getenv("MILVUS_COLLECTION_NAME", "novel_knowledge")

            if mode == "docker":
                milvus_host = os.getenv("MILVUS_HOST", "milvus")
                milvus_port = os.getenv("MILVUS_PORT", "19530")
                connections.connect(
                    alias="default",
                    host=milvus_host,
                    port=milvus_port,
                )
                logger.info(f"Milvus 连接成功: {milvus_host}:{milvus_port}")
            else:
                # Milvus Lite 模式, 使用本地文件
                db_path = os.getenv("MILVUS_LOCAL_DB", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "milvus_demo.db"))
                connections.connect(
                    alias="default",
                    uri=db_path,
                )
                logger.info(f"Milvus Lite 连接成功: {db_path}")

            if not utility.has_collection(coll_name):
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=256),
                    FieldSchema(name="project_id", dtype=DataType.VARCHAR, max_length=64),
                    FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=32),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embedding_dim),
                    FieldSchema(name="metadata", dtype=DataType.JSON),
                ]
                schema = CollectionSchema(fields, description="Novel knowledge base")
                _collection = Collection(name=coll_name, schema=schema)

                # 创建向量索引
                index_params = {
                    "metric_type": "COSINE",
                    "index_type": "IVF_FLAT",
                    "params": {"nlist": 128},
                }
                _collection.create_index(field_name="embedding", index_params=index_params)
                logger.info(f"Milvus Collection '{coll_name}' 创建完成, 维度: {embedding_dim}")
            else:
                _collection = Collection(name=coll_name)

            _collection.load()
            _collection_initialized = True
            logger.info(f"Milvus Collection '{coll_name}' 加载完成")

        except Exception as e:
            logger.warning(f"Milvus 连接失败, 将使用降级模式: {e}")
            _collection = None
            _collection_initialized = True

        return _collection


def get_collection_available():
    """检查 Milvus 是否可用"""
    return get_collection() is not None
