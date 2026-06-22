"""
Embedding 工厂

两种模式:
- docker: 连接本地 Docker Embedding 服务（primary）
- api:    调用智谱 BigModel API（fallback，使用 embedding-2）
"""
import os
from loguru import logger


class BaseEmbedder:
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量获取 embedding，默认逐条调用（子类可覆盖为批量 API）"""
        return [self.embed(t) for t in texts]


class DockerEmbedder(BaseEmbedder):
    """连接本地 Docker Embedding 服务（sentence-transformers）"""

    def __init__(self):
        import requests
        self._url = os.getenv("EMBEDDING_DOCKER_URL", "http://localhost:8080/embed")
        self._timeout = int(os.getenv("EMBEDDING_DOCKER_TIMEOUT", "30"))
        resp = requests.get(self._url.rsplit("/", 1)[0] + "/health", timeout=5)
        resp.raise_for_status()
        info = resp.json()
        logger.info(f"Docker Embedding 服务已连接: {self._url} (model={info.get('model', 'unknown')})")

    def embed(self, text: str) -> list[float]:
        import requests
        resp = requests.post(
            self._url,
            json={"texts": [text]},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量获取 embedding"""
        if not texts:
            return []
        import requests
        resp = requests.post(
            self._url,
            json={"texts": texts},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()["embeddings"]


class DeepSeekEmbedder(BaseEmbedder):
    """调用 OpenAI 兼容 Embedding API（fallback，默认智谱 BigModel embedding-2）"""

    def __init__(self):
        from openai import OpenAI
        api_key = os.getenv("EMBEDDING_API_KEY", "")
        base_url = os.getenv("EMBEDDING_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
        self._model = os.getenv("EMBEDDING_MODEL", "embedding-2")
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        logger.info(f"Embedding API 已初始化: model={self._model}, base_url={base_url}")

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(input=text, model=self._model)
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量获取 embedding，一次 API 调用处理多个文本"""
        if not texts:
            return []
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [d.embedding for d in response.data]


class EmbedderFactory:
    _instance = None

    @classmethod
    def create(cls) -> BaseEmbedder:
        """单例模式创建 Embedder：优先 Docker，失败则 fallback Embedding API"""
        if cls._instance is None:
            try:
                cls._instance = DockerEmbedder()
            except Exception as e:
                logger.warning(f"Docker Embedding 服务不可用 ({e})，fallback 到 Embedding API")
                cls._instance = DeepSeekEmbedder()
        return cls._instance
