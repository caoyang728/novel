"""
Rerank 工厂

支持用户配置的5种模式:
- api_only:     仅云API
- docker_only:  仅Docker
- api_first:    API优先，Docker兜底
- docker_first: Docker优先，API兜底
- disabled:     关闭

配置来源: UserEmbeddingConfig (DB)
Rerank API 兼容 Cohere/Jina 等标准 /rerank 接口
"""
import os
from loguru import logger
from dataclasses import dataclass


@dataclass
class RerankResult:
    """Rerank 结果"""
    index: int
    relevance_score: float
    text: str


class BaseReranker:
    def rerank(self, query: str, documents: list[str], top_n: int = None) -> list[RerankResult]:
        raise NotImplementedError


class DockerReranker(BaseReranker):
    """连接本地 Docker Rerank 服务"""

    def __init__(self, url=None, timeout=None):
        import requests
        self._url = url or os.getenv("RERANK_DOCKER_URL", "http://rerank:8000/rerank")
        self._timeout = int(timeout or os.getenv("RERANK_DOCKER_TIMEOUT", "30"))
        health_url = self._url.rsplit("/", 1)[0] + "/health"
        resp = requests.get(health_url, timeout=5)
        resp.raise_for_status()
        info = resp.json()
        logger.info(f"Docker Rerank 服务已连接: {self._url} (model={info.get('model', 'unknown')})")

    def rerank(self, query: str, documents: list[str], top_n: int = None) -> list[RerankResult]:
        import requests
        payload = {"query": query, "documents": documents}
        if top_n is not None:
            payload["top_n"] = top_n
        resp = requests.post(self._url, json=payload, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in data.get("results", []):
            results.append(RerankResult(
                index=r.get("index", 0),
                relevance_score=r.get("relevance_score", 0.0),
                text=documents[r.get("index", 0)] if r.get("index", 0) < len(documents) else "",
            ))
        return results


class ApiReranker(BaseReranker):
    """调用云 Rerank API（兼容 Cohere/Jina /rerank 接口）"""

    def __init__(self, api_key=None, base_url=None, model=None):
        import requests
        self._api_key = api_key or os.getenv("RERANK_API_KEY", "")
        self._base_url = base_url or os.getenv("RERANK_BASE_URL", "")
        self._model = model or os.getenv("RERANK_MODEL", "")
        self._requests = requests
        logger.info(f"Rerank API 已初始化: model={self._model}, base_url={self._base_url}")

    def rerank(self, query: str, documents: list[str], top_n: int = None) -> list[RerankResult]:
        url = f"{self._base_url.rstrip('/')}/rerank"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self._model,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n
        resp = self._requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in data.get("results", []):
            results.append(RerankResult(
                index=r.get("index", 0),
                relevance_score=r.get("relevance_score", 0.0),
                text=documents[r.get("index", 0)] if r.get("index", 0) < len(documents) else "",
            ))
        return results


class DisabledReranker(BaseReranker):
    """Rerank 关闭时的占位实现，直接返回原文顺序"""

    def rerank(self, query: str, documents: list[str], top_n: int = None) -> list[RerankResult]:
        n = top_n or len(documents)
        return [
            RerankResult(index=i, relevance_score=1.0 - i * 0.01, text=doc)
            for i, doc in enumerate(documents[:n])
        ]


class FallbackReranker(BaseReranker):
    """主备切换 Reranker"""

    def __init__(self, primary: BaseReranker, fallback: BaseReranker, primary_name="primary", fallback_name="fallback"):
        self._primary = primary
        self._fallback = fallback
        self._primary_name = primary_name
        self._fallback_name = fallback_name

    def rerank(self, query: str, documents: list[str], top_n: int = None) -> list[RerankResult]:
        try:
            return self._primary.rerank(query, documents, top_n)
        except Exception as e:
            logger.warning(f"Rerank {self._primary_name} 失败 ({e})，切换到 {self._fallback_name}")
            return self._fallback.rerank(query, documents, top_n)


class RerankerFactory:
    _instance = None

    @classmethod
    def reset(cls):
        """清除缓存的 Reranker 单例"""
        cls._instance = None

    @classmethod
    def create(cls) -> BaseReranker:
        """单例模式创建 Reranker"""
        if cls._instance is None:
            cls._instance = cls._create_from_config()
        return cls._instance

    @classmethod
    def create_optional(cls) -> BaseReranker | None:
        """创建 Reranker，disabled 时返回 None"""
        reranker = cls.create()
        if isinstance(reranker, DisabledReranker):
            return None
        return reranker

    @classmethod
    def _create_from_config(cls) -> BaseReranker:
        mode, api_cfg, docker_cfg = cls._load_user_config()

        if mode == 'disabled':
            logger.info("Rerank 已由用户配置关闭")
            return DisabledReranker()

        if mode == 'api_only':
            return cls._create_api_reranker(api_cfg)

        if mode == 'docker_only':
            return cls._create_docker_reranker(docker_cfg)

        if mode == 'api_first':
            primary = cls._create_api_reranker(api_cfg)
            fallback = cls._create_docker_reranker(docker_cfg)
            return FallbackReranker(primary, fallback, "API", "Docker")

        if mode == 'docker_first':
            primary = cls._create_docker_reranker(docker_cfg)
            fallback = cls._create_api_reranker(api_cfg)
            return FallbackReranker(primary, fallback, "Docker", "API")

        logger.warning(f"未知的 Rerank 模式: {mode}，默认关闭")
        return DisabledReranker()

    @classmethod
    def _load_user_config(cls):
        """从数据库加载用户 Rerank 配置"""
        mode = 'disabled'
        api_cfg = {}
        docker_cfg = {}

        try:
            from apps.user.models import UserEmbeddingConfig
            config = UserEmbeddingConfig.objects.order_by('-updated_at').first()
            if config:
                mode = config.rerank_mode
                api_cfg = {
                    'api_key': config.get_rerank_api_key() if config.rerank_api_key else '',
                    'base_url': config.rerank_api_base_url,
                    'model': config.rerank_api_model,
                }
                docker_cfg = {
                    'url': config.rerank_docker_url,
                    'timeout': config.rerank_docker_timeout,
                }
                logger.debug(f"从 DB 加载 Rerank 配置: mode={mode}")
        except Exception as e:
            logger.debug(f"读取 DB Rerank 配置失败 ({e})，默认关闭")

        return mode, api_cfg, docker_cfg

    @staticmethod
    def _create_api_reranker(cfg: dict) -> ApiReranker:
        return ApiReranker(
            api_key=cfg.get('api_key') or None,
            base_url=cfg.get('base_url') or None,
            model=cfg.get('model') or None,
        )

    @staticmethod
    def _create_docker_reranker(cfg: dict) -> DockerReranker:
        return DockerReranker(
            url=cfg.get('url') or None,
            timeout=cfg.get('timeout') or None,
        )
