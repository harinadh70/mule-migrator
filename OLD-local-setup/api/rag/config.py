"""
RAG-specific configuration for the MuleSoft-to-SpringBoot migration platform.

Centralizes all tunable parameters for embedding models, chunking strategies,
vector search, collection management, and caching.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class EmbeddingConfig:
    """Configuration for the sentence-transformer embedding model."""

    model_name: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    batch_size: int = 64
    max_seq_length: int = 256
    normalize: bool = True


@dataclass(frozen=True)
class ChunkConfig:
    """Configuration for document chunking."""

    min_tokens: int = 100
    max_tokens: int = 512
    overlap_ratio: float = 0.15
    sentence_boundary: bool = True


@dataclass(frozen=True)
class SearchConfig:
    """Configuration for vector search and retrieval."""

    top_k: int = 10
    rerank_top_k: int = 5
    similarity_threshold: float = 0.65
    query_expansion_count: int = 3
    context_token_budget: int = 4096


@dataclass(frozen=True)
class QdrantConfig:
    """Configuration for the Qdrant vector database connection."""

    host: str = os.getenv("QDRANT_HOST", "localhost")
    port: int = int(os.getenv("QDRANT_PORT", "6333"))
    grpc_port: int = int(os.getenv("QDRANT_GRPC_PORT", "6334"))
    prefer_grpc: bool = True
    api_key: str | None = os.getenv("QDRANT_API_KEY")
    timeout: float = 30.0
    max_retries: int = 3
    retry_backoff: float = 1.0


@dataclass(frozen=True)
class RedisConfig:
    """Configuration for Redis-backed embedding cache."""

    host: str = os.getenv("REDIS_HOST", "localhost")
    port: int = int(os.getenv("REDIS_PORT", "6379"))
    db: int = int(os.getenv("REDIS_RAG_DB", "2"))
    password: str | None = os.getenv("REDIS_PASSWORD")
    key_prefix: str = "rag:emb:"
    default_ttl: int = 7 * 24 * 3600  # 7 days in seconds


@dataclass(frozen=True)
class CacheConfig:
    """TTL settings for various caches."""

    embedding_ttl: int = 7 * 24 * 3600      # 7 days
    search_result_ttl: int = 1 * 3600        # 1 hour
    collection_info_ttl: int = 5 * 60        # 5 minutes
    knowledge_base_ttl: int = 30 * 24 * 3600 # 30 days


# ---------------------------------------------------------------------------
# Collection name constants
# ---------------------------------------------------------------------------

COLLECTION_MULESOFT_DOCS: str = "mulesoft_docs"
COLLECTION_SPRINGBOOT_DOCS: str = "springboot_docs"
COLLECTION_CUSTOM_PATTERNS: str = "custom_patterns"
COLLECTION_MIGRATION_HISTORY: str = "migration_history"

ALL_COLLECTIONS: list[str] = [
    COLLECTION_MULESOFT_DOCS,
    COLLECTION_SPRINGBOOT_DOCS,
    COLLECTION_CUSTOM_PATTERNS,
    COLLECTION_MIGRATION_HISTORY,
]


@dataclass
class RAGConfig:
    """Top-level RAG configuration aggregating all sub-configs."""

    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunk: ChunkConfig = field(default_factory=ChunkConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)

    # Path to built-in knowledge documents shipped with the platform
    knowledge_base_dir: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "knowledge"
    )

    # Mapping of doc_type -> collection name
    collection_map: Dict[str, str] = field(default_factory=lambda: {
        "mulesoft": COLLECTION_MULESOFT_DOCS,
        "springboot": COLLECTION_SPRINGBOOT_DOCS,
        "custom": COLLECTION_CUSTOM_PATTERNS,
        "migration": COLLECTION_MIGRATION_HISTORY,
    })

    def get_collection(self, doc_type: str) -> str:
        """Resolve a document type to its Qdrant collection name."""
        return self.collection_map.get(doc_type, COLLECTION_CUSTOM_PATTERNS)


# Module-level singleton for convenience imports
rag_config = RAGConfig()
