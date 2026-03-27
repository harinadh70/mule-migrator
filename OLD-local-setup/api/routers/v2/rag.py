"""
V2 RAG admin endpoints — knowledge-base management and semantic search.

Routes:
  POST   /rag/search                         → Semantic search
  GET    /rag/collections                     → List collections
  GET    /rag/collections/{name}/stats        → Collection statistics
  POST   /rag/collections/{name}/index        → Trigger indexing
  POST   /rag/collections/{name}/reindex      → Full re-index
  DELETE /rag/collections/{name}              → Delete collection
  POST   /rag/documents                       → Upload custom document
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.config import Settings
from api.dependencies import get_app_settings
from api.services.rag_service import RAGService

router = APIRouter()


# ── Request / Response Schemas ────────────────────────────────────────


class RAGSearchRequest(BaseModel):
    """Payload for a semantic search query."""

    query: str = Field(..., min_length=1, description="Natural-language search query.")
    collection: Optional[str] = Field(
        default=None, description="Target collection (None searches all).",
    )
    top_k: int = Field(default=10, ge=1, le=100, description="Max results.")
    filters: Optional[dict[str, Any]] = Field(
        default=None, description="Qdrant payload filters.",
    )


class RAGIndexRequest(BaseModel):
    """Payload for triggering directory indexing."""

    path: str = Field(..., min_length=1, description="Filesystem directory path to index.")


class RAGDocumentUploadRequest(BaseModel):
    """Payload for uploading a single document to the index."""

    content: str = Field(..., min_length=1, description="Document text content.")
    collection: str = Field(..., min_length=1, description="Target collection name.")
    metadata: Optional[dict[str, Any]] = Field(
        default=None, description="Metadata to attach to the document.",
    )


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post(
    "/rag/search",
    summary="Semantic search",
    description="Search the RAG knowledge base using natural-language queries.",
)
async def rag_search(
    body: RAGSearchRequest,
    settings: Settings = Depends(get_app_settings),
) -> JSONResponse:
    if not settings.rag.enabled:
        return JSONResponse(
            status_code=503,
            content={"error": "RAG_DISABLED", "detail": "RAG subsystem is disabled."},
        )

    result = await RAGService.search(
        query=body.query,
        collection=body.collection,
        top_k=body.top_k,
        filters=body.filters,
    )
    return JSONResponse(content=result)


@router.get(
    "/rag/collections",
    summary="List collections",
    description="Return summary information for all known RAG collections.",
)
async def list_collections(
    settings: Settings = Depends(get_app_settings),
) -> JSONResponse:
    if not settings.rag.enabled:
        return JSONResponse(
            status_code=503,
            content={"error": "RAG_DISABLED", "detail": "RAG subsystem is disabled."},
        )

    collections = await RAGService.get_collections()
    return JSONResponse(content={"collections": collections})


@router.get(
    "/rag/collections/{name}/stats",
    summary="Collection statistics",
    description="Return detailed statistics for a single RAG collection.",
)
async def collection_stats(
    name: str = Path(..., description="Collection name."),
    settings: Settings = Depends(get_app_settings),
) -> JSONResponse:
    if not settings.rag.enabled:
        return JSONResponse(
            status_code=503,
            content={"error": "RAG_DISABLED", "detail": "RAG subsystem is disabled."},
        )

    stats = await RAGService.get_collection_stats(name)
    return JSONResponse(content=stats)


@router.post(
    "/rag/collections/{name}/index",
    status_code=202,
    summary="Trigger indexing",
    description="Start indexing documents from a directory into the specified collection.",
    response_description="Indexing result with document and chunk counts.",
)
async def trigger_index(
    name: str = Path(..., description="Collection name."),
    body: RAGIndexRequest = ...,
    settings: Settings = Depends(get_app_settings),
) -> JSONResponse:
    if not settings.rag.enabled:
        return JSONResponse(
            status_code=503,
            content={"error": "RAG_DISABLED", "detail": "RAG subsystem is disabled."},
        )

    result = await RAGService.index_directory(path=body.path, collection=name)
    return JSONResponse(status_code=202, content=result)


@router.post(
    "/rag/collections/{name}/reindex",
    status_code=202,
    summary="Re-index collection",
    description="Drop and fully re-index a collection from its configured knowledge source.",
)
async def reindex_collection(
    name: str = Path(..., description="Collection name."),
    settings: Settings = Depends(get_app_settings),
) -> JSONResponse:
    if not settings.rag.enabled:
        return JSONResponse(
            status_code=503,
            content={"error": "RAG_DISABLED", "detail": "RAG subsystem is disabled."},
        )

    result = await RAGService.reindex(name)
    return JSONResponse(status_code=202, content=result)


@router.delete(
    "/rag/collections/{name}",
    summary="Delete collection",
    description="Permanently delete a collection and all its vector data.",
)
async def delete_collection(
    name: str = Path(..., description="Collection name."),
    settings: Settings = Depends(get_app_settings),
) -> JSONResponse:
    if not settings.rag.enabled:
        return JSONResponse(
            status_code=503,
            content={"error": "RAG_DISABLED", "detail": "RAG subsystem is disabled."},
        )

    result = await RAGService.delete_collection(name)
    return JSONResponse(content=result)


@router.post(
    "/rag/documents",
    status_code=201,
    summary="Upload document",
    description="Upload a single custom document to be indexed in the specified collection.",
)
async def upload_document(
    body: RAGDocumentUploadRequest,
    settings: Settings = Depends(get_app_settings),
) -> JSONResponse:
    if not settings.rag.enabled:
        return JSONResponse(
            status_code=503,
            content={"error": "RAG_DISABLED", "detail": "RAG subsystem is disabled."},
        )

    result = await RAGService.index_document(
        content=body.content,
        collection=body.collection,
        metadata=body.metadata,
    )
    return JSONResponse(status_code=201, content=result)
