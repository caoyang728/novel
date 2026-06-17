"""
Embedding 工厂

支持两种 provider:
- deepseek: 调用 DeepSeek Embedding API（复用现有 LLM 配置）
- local: 使用本地 sentence-transformers 模型或独立的 Embedding 服务
"""
import os
from loguru import logger


class BaseEmbedder:
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError


class DeepSeekEmbedder(BaseEmbedder):
    """使用 DeepSeek API 做 embedding"""

    def __init__(self):
        from langchain_openai import OpenAIEmbeddings
        self._client = OpenAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "deepseek-embedding"),
            openai_api_key=os.getenv("LLM_API_KEY", ""),
            openai_api_base=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
        )

    def embed(self, text: str) -> list[float]:
        return self._client.embed_query(text)


class LocalEmbedder(BaseEmbedder):
    """
    本地 Embedding
    - 如果配置了 LOCAL_EMBEDDING_URL, 调用独立的 Embedding HTTP 服务
    - 否则直接加载 sentence-transformers 模型
    """

    def __init__(self):
        self._base_url = os.getenv("LOCAL_EMBEDDING_URL", "")
        self._local_model = None

        if self._base_url:
            logger.info(f"使用远程 Embedding 服务: {self._base_url}")
        else:
            # 直接加载本地模型
            model_name = os.getenv("LOCAL_EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")
            device = os.getenv("LOCAL_EMBEDDING_DEVICE", "cpu")
            try:
                from sentence_transformers import SentenceTransformer
                self._local_model = SentenceTransformer(model_name, device=device)
                logger.info(f"本地 Embedding 模型已加载: {model_name} (device={device})")
            except ImportError:
                logger.error("sentence-transformers 未安装, 请执行: pip install sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"加载本地 Embedding 模型失败: {e}")
                raise

    def embed(self, text: str) -> list[float]:
        if self._local_model:
            import numpy as np
            result = self._local_model.encode([text], normalize_embeddings=True)
            if isinstance(result, np.ndarray):
                return result[0].tolist()
            return list(result[0])
        else:
            import requests
            resp = requests.post(
                self._base_url,
                json={"texts": [text]},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()["embeddings"][0]


class EmbedderFactory:
    _instance = None

    @classmethod
    def create(cls) -> BaseEmbedder:
        """单例模式创建 Embedder"""
        if cls._instance is None:
            provider = os.getenv("EMBEDDING_PROVIDER", "deepseek")
            if provider == "local":
                cls._instance = LocalEmbedder()
            else:
                cls._instance = DeepSeekEmbedder()
        return cls._instance
