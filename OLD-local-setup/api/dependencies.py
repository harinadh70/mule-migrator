"""
FastAPI dependency injection providers.

Each function here is designed to be used with ``Depends()`` in route
handlers.  Connections are pooled / cached at the application level and
individual request-scoped resources are yielded where needed.
"""

from __future__ import annotations

from functools import lru_cache
from typing import AsyncGenerator, Optional

import redis.asyncio as aioredis
from fastapi import Depends
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import Settings, get_settings
from api.database import get_db_session

# ── Singleton caches ──────────────────────────────────────────────

_redis_pool: Optional[aioredis.Redis] = None
_qdrant_client: Optional[AsyncQdrantClient] = None
_embedding_service: Optional[object] = None  # SentenceTransformer


# ── Settings ──────────────────────────────────────────────────────


def get_app_settings() -> Settings:
    """Return the cached application settings singleton."""
    return get_settings()


# ── Database Session ──────────────────────────────────────────────


async def get_db(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[AsyncSession, None]:
    """
    Thin wrapper that exposes the DB session through a Depends-friendly
    interface.  The actual lifecycle is managed in ``database.py``.
    """
    yield session


# ── Redis ─────────────────────────────────────────────────────────


async def init_redis(settings: Optional[Settings] = None) -> aioredis.Redis:
    """Initialise (or return existing) Redis connection pool."""
    global _redis_pool
    if _redis_pool is None:
        if settings is None:
            settings = get_settings()
        _redis_pool = aioredis.from_url(
            settings.redis.url,
            max_connections=settings.redis.max_connections,
            socket_timeout=settings.redis.socket_timeout,
            decode_responses=True,
        )
    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


async def get_redis(
    settings: Settings = Depends(get_app_settings),
) -> aioredis.Redis:
    """FastAPI dependency: return the shared Redis client."""
    return await init_redis(settings)


# ── Qdrant ────────────────────────────────────────────────────────


async def init_qdrant(settings: Optional[Settings] = None) -> AsyncQdrantClient:
    """Initialise (or return existing) Qdrant async client."""
    global _qdrant_client
    if _qdrant_client is None:
        if settings is None:
            settings = get_settings()
        _qdrant_client = AsyncQdrantClient(
            url=settings.qdrant.url,
            api_key=settings.qdrant.api_key,
            grpc_port=settings.qdrant.grpc_port,
            prefer_grpc=settings.qdrant.prefer_grpc,
            timeout=30,
        )
    return _qdrant_client


async def close_qdrant() -> None:
    """Close the Qdrant client."""
    global _qdrant_client
    if _qdrant_client is not None:
        await _qdrant_client.close()
        _qdrant_client = None


async def get_qdrant(
    settings: Settings = Depends(get_app_settings),
) -> AsyncQdrantClient:
    """FastAPI dependency: return the shared Qdrant client."""
    return await init_qdrant(settings)


# ── Embedding Service ─────────────────────────────────────────────


class EmbeddingService:
    """Thin wrapper around sentence-transformers for generating embeddings."""

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.model_name = model_name

    def encode(self, texts: list[str], **kwargs) -> list[list[float]]:
        """Encode a batch of texts into dense vectors."""
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,
            **kwargs,
        )
        return embeddings.tolist()

    def encode_single(self, text: str) -> list[float]:
        """Encode a single text string."""
        return self.encode([text])[0]


def init_embedding_service(settings: Optional[Settings] = None) -> EmbeddingService:
    """Initialise (or return cached) embedding service."""
    global _embedding_service
    if _embedding_service is None:
        if settings is None:
            settings = get_settings()
        _embedding_service = EmbeddingService(settings.rag.embedding_model)
    return _embedding_service


def get_embedding_service(
    settings: Settings = Depends(get_app_settings),
) -> EmbeddingService:
    """FastAPI dependency: return the shared embedding service."""
    return init_embedding_service(settings)


# ── Retriever ─────────────────────────────────────────────────────


class Retriever:
    """
    Vector-similarity retriever backed by Qdrant + sentence-transformers.

    Wraps embedding generation and Qdrant search into a single
    ``retrieve()`` call that returns scored document chunks.
    """

    def __init__(
        self,
        qdrant_client: AsyncQdrantClient,
        embedding_service: EmbeddingService,
        collection_name: str,
        top_k: int = 5,
        score_threshold: float = 0.65,
    ):
        self.qdrant = qdrant_client
        self.embedder = embedding_service
        self.collection = collection_name
        self.top_k = top_k
        self.score_threshold = score_threshold

    async def retrieve(self, query: str) -> list[dict]:
        """
        Retrieve the most relevant document chunks for a query.

        Returns a list of dicts with ``text``, ``score``, and ``metadata``.
        """
        from qdrant_client.models import models

        query_vector = self.embedder.encode_single(query)

        results = await self.qdrant.query_points(
            collection_name=self.collection,
            query=query_vector,
            limit=self.top_k,
            score_threshold=self.score_threshold,
        )

        return [
            {
                "text": point.payload.get("text", ""),
                "score": point.score,
                "metadata": {
                    k: v for k, v in point.payload.items() if k != "text"
                },
            }
            for point in results.points
        ]


async def get_retriever(
    qdrant: AsyncQdrantClient = Depends(get_qdrant),
    embedder: EmbeddingService = Depends(get_embedding_service),
    settings: Settings = Depends(get_app_settings),
) -> Retriever:
    """FastAPI dependency: build a Retriever wired to Qdrant + embeddings."""
    return Retriever(
        qdrant_client=qdrant,
        embedding_service=embedder,
        collection_name=settings.qdrant.collection,
        top_k=settings.rag.top_k,
        score_threshold=settings.rag.score_threshold,
    )
