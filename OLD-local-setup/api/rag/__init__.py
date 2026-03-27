"""
RAG (Retrieval-Augmented Generation) infrastructure for MuleSoft-to-SpringBoot migration.

Provides document indexing, embedding generation, vector search, and context
retrieval to augment LLM prompts with relevant MuleSoft/Spring Boot knowledge.
"""

from api.rag.config import RAGConfig
from api.rag.schemas import (
    Chunk,
    CollectionInfo,
    Document,
    IndexStats,
    SearchQuery,
    SearchResult,
)
from api.rag.embeddings import EmbeddingService
from api.rag.vector_store import QdrantStore
from api.rag.chunking import CodeAwareChunker
from api.rag.indexer import DocumentIndexer
from api.rag.retriever import HybridRetriever
from api.rag.cache import EmbeddingCache

__all__ = [
    "RAGConfig",
    "Document",
    "Chunk",
    "SearchResult",
    "SearchQuery",
    "IndexStats",
    "CollectionInfo",
    "EmbeddingService",
    "QdrantStore",
    "CodeAwareChunker",
    "DocumentIndexer",
    "HybridRetriever",
    "EmbeddingCache",
]
