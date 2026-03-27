"""
Redis-backed embedding cache for the RAG subsystem.

Caches embedding vectors keyed by a SHA-256 hash of (text + model_name) to
avoid redundant inference calls.  Tracks hit/miss counters for observability.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from typing import List, Optional

from api.rag.config import RAGConfig, rag_config

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """
    Redis-backed cache for embedding vectors.

    Usage::

        cache = EmbeddingCache()
        vec = cache.get("some text")
        if vec is None:
            vec = embedder.embed("some text")
            cache.set("some text", vec)
        print(cache.hit_rate)
    """

    def __init__(self, config: RAGConfig | None = None) -> None:
        self._config = config or rag_config
        self._redis_cfg = self._config.redis
        self._model_name = self._config.embedding.model_name
        self._default_ttl = self._redis_cfg.default_ttl
        self._prefix = self._redis_cfg.key_prefix

        # Counters
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()

        # Lazy Redis connection
        self._client = None
        self._connect_attempted = False

    # ------------------------------------------------------------------
    # Lazy connection
    # ------------------------------------------------------------------

    def _ensure_client(self):
        """Create the Redis client on first use (fail-open: cache misses are OK)."""
        if self._client is not None:
            return True
        if self._connect_attempted:
            return False  # already failed once; don't retry on every call
        self._connect_attempted = True
        try:
            import redis

            self._client = redis.Redis(
                host=self._redis_cfg.host,
                port=self._redis_cfg.port,
                db=self._redis_cfg.db,
                password=self._redis_cfg.password,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            # Verify connectivity
            self._client.ping()
            logger.info(
                "EmbeddingCache connected to Redis at %s:%d (db=%d).",
                self._redis_cfg.host,
                self._redis_cfg.port,
                self._redis_cfg.db,
            )
            return True
        except Exception:
            logger.warning(
                "Redis unavailable at %s:%d — embedding cache disabled.",
                self._redis_cfg.host,
                self._redis_cfg.port,
                exc_info=True,
            )
            self._client = None
            return False

    # ------------------------------------------------------------------
    # Cache key
    # ------------------------------------------------------------------

    def _cache_key(self, text: str) -> str:
        """Compute a deterministic cache key from text and model name."""
        raw = f"{text}||{self._model_name}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{self._prefix}{digest}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, text: str) -> Optional[List[float]]:
        """
        Look up a cached embedding for *text*.

        Returns:
            The embedding vector if cached, else ``None``.
        """
        if not self._ensure_client():
            with self._lock:
                self._misses += 1
            return None

        try:
            key = self._cache_key(text)
            raw = self._client.get(key)  # type: ignore[union-attr]
            if raw is not None:
                with self._lock:
                    self._hits += 1
                return json.loads(raw)
            else:
                with self._lock:
                    self._misses += 1
                return None
        except Exception:
            logger.debug("Redis GET failed for embedding cache.", exc_info=True)
            with self._lock:
                self._misses += 1
            return None

    def set(self, text: str, embedding: List[float], ttl: int | None = None) -> None:
        """
        Store an embedding in the cache.

        Args:
            text: The source text.
            embedding: The embedding vector.
            ttl: Time-to-live in seconds (defaults to config value).
        """
        if not self._ensure_client():
            return

        try:
            key = self._cache_key(text)
            value = json.dumps(embedding)
            self._client.setex(key, ttl or self._default_ttl, value)  # type: ignore[union-attr]
        except Exception:
            logger.debug("Redis SET failed for embedding cache.", exc_info=True)

    def clear(self) -> int:
        """
        Delete all cached embeddings (matching the key prefix).

        Returns:
            Number of keys deleted.
        """
        if not self._ensure_client():
            return 0

        try:
            pattern = f"{self._prefix}*"
            keys = []
            cursor = 0
            while True:
                cursor, batch = self._client.scan(cursor, match=pattern, count=500)  # type: ignore[union-attr]
                keys.extend(batch)
                if cursor == 0:
                    break
            if keys:
                deleted = self._client.delete(*keys)  # type: ignore[union-attr]
                logger.info("Cleared %d cached embeddings.", deleted)
                return deleted
            return 0
        except Exception:
            logger.warning("Failed to clear embedding cache.", exc_info=True)
            return 0

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @property
    def hits(self) -> int:
        """Total cache hits since instantiation."""
        return self._hits

    @property
    def misses(self) -> int:
        """Total cache misses since instantiation."""
        return self._misses

    @property
    def hit_rate(self) -> float:
        """Hit rate as a float in [0, 1]. Returns 0.0 if no lookups yet."""
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return self._hits / total

    def stats(self) -> dict:
        """Return a dict with hit/miss/rate counters."""
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self.hit_rate, 4),
            "total_lookups": self._hits + self._misses,
        }

    def reset_stats(self) -> None:
        """Reset hit/miss counters."""
        with self._lock:
            self._hits = 0
            self._misses = 0
