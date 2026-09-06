"""
Embedding 工厂

支持用户配置的5种模式:
- api_only:     仅云API
- docker_only:  仅Docker
- api_first:    API优先，Docker兜底
- docker_first: Docker优先，API兜底
- disabled:     关闭

配置来源: UserEmbeddingConfig (DB) → 环境变量 (fallback)
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

    def __init__(self, url=None, timeout=None):
        import requests
        self._url = url or os.getenv("EMBEDDING_DOCKER_URL", "http://embedding:8000/embed")
        self._timeout = int(timeout or os.getenv("EMBEDDING_DOCKER_TIMEOUT", "30"))
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


class ApiEmbedder(BaseEmbedder):
    """调用 OpenAI 兼容 Embedding API"""

    def __init__(self, api_key=None, base_url=None, model=None):
        from openai import OpenAI
        self._api_key = api_key or os.getenv("EMBEDDING_API_KEY", "")
        self._base_url = base_url or os.getenv("EMBEDDING_BASE_URL", "https://open.bigmodel.cn/api/paas/v4/")
        self._model = model or os.getenv("EMBEDDING_MODEL", "embedding-2")
        self._client = OpenAI(api_key=self._api_key, base_url=self._base_url)
        logger.info(f"Embedding API 已初始化: model={self._model}, base_url={self._base_url}")

    def embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(input=text, model=self._model)
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量获取 embedding，一次 API 调用处理多个文本"""
        if not texts:
            return []
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [d.embedding for d in response.data]


class DisabledEmbedder(BaseEmbedder):
    """Embedding 关闭时的占位实现"""

    def embed(self, text: str) -> list[float]:
        raise RuntimeError("Embedding 已关闭，请在配置页面开启")

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("Embedding 已关闭，请在配置页面开启")


class FallbackEmbedder(BaseEmbedder):
    """主备切换 Embedder：先尝试 primary，失败则 fallback"""

    def __init__(self, primary: BaseEmbedder, fallback: BaseEmbedder, primary_name="primary", fallback_name="fallback"):
        self._primary = primary
        self._fallback = fallback
        self._primary_name = primary_name
        self._fallback_name = fallback_name

    def embed(self, text: str) -> list[float]:
        try:
            return self._primary.embed(text)
        except Exception as e:
            logger.warning(f"Embedding {self._primary_name} 失败 ({e})，切换到 {self._fallback_name}")
            return self._fallback.embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._primary.embed_batch(texts)
        except Exception as e:
            logger.warning(f"Embedding {self._primary_name} 批量失败 ({e})，切换到 {self._fallback_name}")
            return self._fallback.embed_batch(texts)


class EmbedderFactory:
    _instance = None

    @classmethod
    def reset(cls):
        """清除缓存的 Embedder 单例，配置变更后调用"""
        cls._instance = None

    @classmethod
    def create(cls) -> BaseEmbedder:
        """单例模式创建 Embedder，读取用户配置"""
        if cls._instance is None:
            cls._instance = cls._create_from_config()
        return cls._instance

    @classmethod
    def _create_from_config(cls) -> BaseEmbedder:
        """根据用户配置创建 Embedder"""
        mode, api_cfg, docker_cfg = cls._load_user_config()

        if mode == 'disabled':
            logger.info("Embedding 已由用户配置关闭")
            return DisabledEmbedder()

        if mode == 'api_only':
            return cls._create_api_embedder(api_cfg)

        if mode == 'docker_only':
            return cls._create_docker_embedder(docker_cfg)

        if mode == 'api_first':
            primary = cls._create_api_embedder(api_cfg)
            fallback = cls._create_docker_embedder(docker_cfg)
            return FallbackEmbedder(primary, fallback, "API", "Docker")

        if mode == 'docker_first':
            primary = cls._create_docker_embedder(docker_cfg)
            fallback = cls._create_api_embedder(api_cfg)
            return FallbackEmbedder(primary, fallback, "Docker", "API")

        # 不应到达这里，兜底用旧行为
        logger.warning(f"未知的 Embedding 模式: {mode}，使用默认 Docker -> API 兜底")
        return cls._create_legacy()

    @classmethod
    def _load_user_config(cls):
        """从数据库加载用户 Embedding 配置，不存在则返回环境变量默认值"""
        mode = 'docker_first'  # 默认行为与旧版一致：Docker 优先，API 兜底
        api_cfg = {}
        docker_cfg = {}

        try:
            from apps.user.models import UserEmbeddingConfig
            # 取最新一条配置（单用户部署场景）
            config = UserEmbeddingConfig.objects.order_by('-updated_at').first()
            if config:
                mode = config.embedding_mode
                api_cfg = {
                    'api_key': config.get_embedding_api_key() if config.embedding_api_key else '',
                    'base_url': config.embedding_api_base_url,
                    'model': config.embedding_api_model,
                }
                docker_cfg = {
                    'url': config.embedding_docker_url,
                    'timeout': config.embedding_docker_timeout,
                }
                logger.debug(f"从 DB 加载 Embedding 配置: mode={mode}")
                return mode, api_cfg, docker_cfg
        except Exception as e:
            logger.debug(f"读取 DB Embedding 配置失败 ({e})，使用环境变量")

        return mode, api_cfg, docker_cfg

    @staticmethod
    def _create_api_embedder(cfg: dict) -> ApiEmbedder:
        return ApiEmbedder(
            api_key=cfg.get('api_key') or None,
            base_url=cfg.get('base_url') or None,
            model=cfg.get('model') or None,
        )

    @staticmethod
    def _create_docker_embedder(cfg: dict) -> DockerEmbedder:
        return DockerEmbedder(
            url=cfg.get('url') or None,
            timeout=cfg.get('timeout') or None,
        )

    @classmethod
    def _create_legacy(cls) -> BaseEmbedder:
        """旧版默认行为：Docker 优先，API 兜底"""
        try:
            return DockerEmbedder()
        except Exception as e:
            logger.warning(f"Docker Embedding 服务不可用 ({e})，fallback 到 Embedding API")
            return ApiEmbedder()


# 保持向后兼容的别名
DeepSeekEmbedder = ApiEmbedder
