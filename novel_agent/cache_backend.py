"""Redis 缓存降级后端 — 当 Redis 不可用时自动降级到本地内存缓存"""
import threading
from django.core.cache.backends.locmem import LocMemCache
from django_redis.cache import RedisCache
from loguru import logger


class RedisFallbackCache(RedisCache):
    """继承 django-redis 的 RedisCache，Redis 不可用时自动降级为 LocMemCache。

    设计要点：
    - 启动时不会因 Redis 不可达而崩溃，静默降级
    - 降级后定期重试 Redis（每 60 秒一次），Redis 恢复后自动切回
    - LocMemCache 是线程安全的，适合开发环境
    """

    _fallback_cache = None
    _fallback_lock = threading.Lock()
    _redis_available = True       # 当前是否可用
    _last_check_time = 0          # 上次重试时间戳
    _retry_interval = 60          # 降级后重试间隔（秒）
    _check_lock = threading.Lock()

    def __init__(self, server, params):
        # 先创建 LocMem 降级缓存（无论 Redis 是否可用都初始化）
        with RedisFallbackCache._fallback_lock:
            if RedisFallbackCache._fallback_cache is None:
                RedisFallbackCache._fallback_cache = LocMemCache('redis-fallback', {})

        try:
            super().__init__(server, params)
            # 启动时做一次连通性检测
            self.client.get_client().ping()
            RedisFallbackCache._redis_available = True
            logger.info("Redis 连接成功，使用 Redis 缓存")
        except Exception:
            RedisFallbackCache._redis_available = False
            logger.warning("Redis 不可用，降级到本地内存缓存（LocMemCache）")

    def _check_redis(self):
        """定期检测 Redis 是否恢复，恢复后自动切回"""
        if RedisFallbackCache._redis_available:
            return True
        if not hasattr(self, 'client'):
            return False

        import time
        now = time.monotonic()
        with RedisFallbackCache._check_lock:
            if now - RedisFallbackCache._last_check_time < RedisFallbackCache._retry_interval:
                return False
            RedisFallbackCache._last_check_time = now

        try:
            self.client.get_client().ping()
            RedisFallbackCache._redis_available = True
            logger.info("Redis 已恢复，切回 Redis 缓存")
            return True
        except Exception:
            return False

    def _get_backend(self):
        """返回当前实际使用的缓存后端"""
        if self._check_redis():
            return self
        return RedisFallbackCache._fallback_cache

    # ---- 基础操作 ----

    def get(self, key, default=None, version=None):
        backend = self._get_backend()
        if backend is self:
            try:
                return super().get(key, default=default, version=version)
            except Exception:
                RedisFallbackCache._redis_available = False
                return RedisFallbackCache._fallback_cache.get(key, default=default, version=version)
        return backend.get(key, default=default, version=version)

    def set(self, key, value, timeout=None, version=None):
        backend = self._get_backend()
        if backend is self:
            try:
                super().set(key, value, timeout=timeout, version=version)
                return
            except Exception:
                RedisFallbackCache._redis_available = False
        RedisFallbackCache._fallback_cache.set(key, value, timeout=timeout, version=version)

    def delete(self, key, version=None):
        backend = self._get_backend()
        if backend is self:
            try:
                super().delete(key, version=version)
                return
            except Exception:
                RedisFallbackCache._redis_available = False
        RedisFallbackCache._fallback_cache.delete(key, version=version)

    def clear(self):
        backend = self._get_backend()
        if backend is self:
            try:
                super().clear()
                return
            except Exception:
                RedisFallbackCache._redis_available = False
        RedisFallbackCache._fallback_cache.clear()

    # ---- 多键操作 ----

    def get_many(self, keys, version=None):
        backend = self._get_backend()
        if backend is self:
            try:
                return super().get_many(keys, version=version)
            except Exception:
                RedisFallbackCache._redis_available = False
        return RedisFallbackCache._fallback_cache.get_many(keys, version=version)

    def set_many(self, data, timeout=None, version=None):
        backend = self._get_backend()
        if backend is self:
            try:
                super().set_many(data, timeout=timeout, version=version)
                return
            except Exception:
                RedisFallbackCache._redis_available = False
        RedisFallbackCache._fallback_cache.set_many(data, timeout=timeout, version=version)

    def delete_many(self, keys, version=None):
        backend = self._get_backend()
        if backend is self:
            try:
                super().delete_many(keys, version=version)
                return
            except Exception:
                RedisFallbackCache._redis_available = False
        RedisFallbackCache._fallback_cache.delete_many(keys, version=version)

    # ---- 原子操作 ----

    def incr(self, key, delta=1, version=None):
        backend = self._get_backend()
        if backend is self:
            try:
                return super().incr(key, delta=delta, version=version)
            except Exception:
                RedisFallbackCache._redis_available = False
        return RedisFallbackCache._fallback_cache.incr(key, delta=delta, version=version)

    def decr(self, key, delta=1, version=None):
        backend = self._get_backend()
        if backend is self:
            try:
                return super().decr(key, delta=delta, version=version)
            except Exception:
                RedisFallbackCache._redis_available = False
        return RedisFallbackCache._fallback_cache.decr(key, delta=delta, version=version)

    def add(self, key, value, timeout=None, version=None):
        """仅在 key 不存在时设置"""
        backend = self._get_backend()
        if backend is self:
            try:
                return super().add(key, value, timeout=timeout, version=version)
            except Exception:
                RedisFallbackCache._redis_available = False
        return RedisFallbackCache._fallback_cache.add(key, value, timeout=timeout, version=version)

    # ---- 过期时间 ----

    def touch(self, key, timeout=None, version=None):
        backend = self._get_backend()
        if backend is self:
            try:
                return super().touch(key, timeout=timeout, version=version)
            except Exception:
                RedisFallbackCache._redis_available = False
        return RedisFallbackCache._fallback_cache.touch(key, timeout=timeout, version=version)
