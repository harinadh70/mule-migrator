"""
Pydantic models for the RAG subsystem.

Defines the data contracts for documents, chunks, search queries/results,
and collection metadata used across indexing, retrieval, and API layers.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DocType(str, Enum):
    """Supported document types for RAG indexing."""

    MULESOFT = "mulesoft"
    SPRINGBOOT = "springboot"
    CUSTOM = "custom"
    MIGRATION = "migration"


class CollectionStatus(str, Enum):
    """Status of a Qdrant collection."""

    READY = "ready"
    INDEXING = "indexing"
    ERROR = "error"
    NOT_FOUND = "not_found"


# ---------------------------------------------------------------------------
# Core data models
# ---------------------------------------------------------------------------

class Document(BaseModel):
    """A source document before chunking."""

    id: str = Field(..., description="Unique document identifier (usually SHA256 of content).")
    content: str = Field(..., description="Raw text content of the document.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary key-value metadata.")
    source: str = Field(..., description="File path or URI where the document originated.")
    doc_type: DocType = Field(..., description="Category of the document.")

    class Config:
        use_enum_values = True


class Chunk(BaseModel):
    """A chunk produced by splitting a Document."""

    id: str = Field(..., description="Unique chunk identifier.")
    content: str = Field(..., description="Text content of the chunk.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Chunk-level metadata (source_type, section_name, etc.).")
    doc_id: str = Field(..., description="Parent document ID.")
    chunk_index: int = Field(..., ge=0, description="Zero-based index of this chunk within its parent document.")
    token_count: int = Field(..., ge=0, description="Approximate token count (word-split based).")

    class Config:
        use_enum_values = True


class SearchResult(BaseModel):
    """A single result returned from vector search."""

    chunk: Chunk = Field(..., description="The matched chunk.")
    score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0-1, higher is better).")
    source: str = Field(..., description="Source file path or URI.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Combined metadata from chunk and document.")


class SearchQuery(BaseModel):
    """Parameters for a RAG search request."""

    query: str = Field(..., min_length=1, description="The natural-language search query.")
    collection: Optional[str] = Field(None, description="Target collection name. None searches all collections.")
    filters: Optional[Dict[str, Any]] = Field(None, description="Payload filters to apply (Qdrant filter format).")
    top_k: int = Field(10, ge=1, le=100, description="Maximum number of results to return.")


# ---------------------------------------------------------------------------
# Collection / index metadata
# ---------------------------------------------------------------------------

class IndexStats(BaseModel):
    """Statistics about an indexed collection."""

    collection: str = Field(..., description="Collection name.")
    doc_count: int = Field(0, ge=0, description="Number of distinct documents indexed.")
    chunk_count: int = Field(0, ge=0, description="Total number of chunks stored.")
    embedding_dim: int = Field(384, description="Dimensionality of stored vectors.")
    last_indexed: Optional[datetime] = Field(None, description="Timestamp of the most recent indexing run.")


class CollectionInfo(BaseModel):
    """Summary information for a Qdrant collection."""

    name: str = Field(..., description="Collection name.")
    doc_count: int = Field(0, ge=0, description="Approximate number of points in the collection.")
    status: CollectionStatus = Field(CollectionStatus.NOT_FOUND, description="Current collection status.")

    class Config:
        use_enum_values = True


# ---------------------------------------------------------------------------
# API request / response wrappers
# ---------------------------------------------------------------------------

class RAGSearchRequest(BaseModel):
    """API-level search request."""

    query: str = Field(..., min_length=1)
    collections: Optional[List[str]] = Field(None, description="Collections to search; None = all.")
    filters: Optional[Dict[str, Any]] = None
    top_k: int = Field(10, ge=1, le=100)


class RAGSearchResponse(BaseModel):
    """API-level search response."""

    results: List[SearchResult] = Field(default_factory=list)
    query: str
    total_results: int = 0
    search_time_ms: float = 0.0


class RAGIndexRequest(BaseModel):
    """API-level indexing request."""

    path: Optional[str] = Field(None, description="Directory or file path to index.")
    collection: str
    doc_type: DocType


class RAGIndexResponse(BaseModel):
    """API-level indexing response."""

    collection: str
    documents_indexed: int = 0
    chunks_created: int = 0
    skipped: int = 0
    errors: List[str] = Field(default_factory=list)
