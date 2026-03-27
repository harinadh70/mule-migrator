"""
RAGService — business logic for the Retrieval-Augmented Generation subsystem.

Wraps the RAG indexer, retriever, and vector store modules to provide a
clean service interface for API routers.  All operations are async-safe
(blocking calls are offloaded to a thread pool where necessary).
"""

from __future__ import annotations

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

import structlog

from api.exceptions import NotFoundError, RAGError, ValidationError

logger = structlog.get_logger(__name__)

# Shared thread pool for blocking RAG operations (embedding, indexing)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="rag")


class RAGService:
    """
    Async facade over the synchronous RAG subsystem in ``api.rag``.

    Each method instantiates the required RAG component on demand so
    there is no shared mutable state.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _run_in_thread(fn, *args, **kwargs) -> Any:
        """Run a blocking function in the shared thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))

    @staticmethod
    def _get_retriever():
        """Build a HybridRetriever instance."""
        try:
            from api.rag.retriever import HybridRetriever

            return HybridRetriever()
        except Exception as exc:
            raise RAGError(detail=f"Failed to initialise retriever: {exc}", stage="init")

    @staticmethod
    def _get_indexer():
        """Build a DocumentIndexer instance."""
        try:
            from api.rag.indexer import DocumentIndexer

            return DocumentIndexer()
        except Exception as exc:
            raise RAGError(detail=f"Failed to initialise indexer: {exc}", stage="init")

    @staticmethod
    def _get_store():
        """Build a QdrantStore instance."""
        try:
            from api.rag.vector_store import QdrantStore

            return QdrantStore()
        except Exception as exc:
            raise RAGError(detail=f"Failed to initialise vector store: {exc}", stage="init")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    @staticmethod
    async def search(
        query: str,
        collection: Optional[str] = None,
        top_k: int = 10,
        filters: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Execute a semantic search across one or all RAG collections.

        Args:
            query: Natural-language search query.
            collection: Target collection name (None searches all).
            top_k: Maximum number of results.
            filters: Optional Qdrant payload filters.

        Returns:
            Dict with results list, query, total_results, and search_time_ms.
        """
        if not query or not query.strip():
            raise ValidationError(detail="Search query cannot be empty.")

        retriever = RAGService._get_retriever()
        start = time.perf_counter()

        try:
            results = await RAGService._run_in_thread(
                retriever.search,
                query,
                collection,
                filters,
                top_k,
            )
        except Exception as exc:
            raise RAGError(detail=f"Search failed: {exc}", stage="search")

        elapsed_ms = (time.perf_counter() - start) * 1000

        serialised = []
        for r in results:
            serialised.append({
                "content": r.chunk.content if hasattr(r, "chunk") else str(r),
                "score": r.score if hasattr(r, "score") else 0.0,
                "source": r.source if hasattr(r, "source") else "",
                "metadata": r.metadata if hasattr(r, "metadata") else {},
            })

        return {
            "results": serialised,
            "query": query,
            "total_results": len(serialised),
            "search_time_ms": round(elapsed_ms, 2),
        }

    # ------------------------------------------------------------------
    # Index a single document
    # ------------------------------------------------------------------

    @staticmethod
    async def index_document(
        content: str,
        collection: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Index a single document (string content) into a collection.

        Args:
            content: The text content to index.
            collection: Target collection name.
            metadata: Optional metadata to attach to the document.

        Returns:
            Dict with collection, documents_indexed, chunks_created.
        """
        if not content or not content.strip():
            raise ValidationError(detail="Document content cannot be empty.")
        if not collection:
            raise ValidationError(detail="Collection name is required.")

        indexer = RAGService._get_indexer()

        try:
            from api.rag.schemas import DocType, Document

            doc_type = metadata.get("doc_type", "custom") if metadata else "custom"
            import hashlib

            doc_id = hashlib.sha256(content.encode()).hexdigest()
            doc = Document(
                id=doc_id,
                content=content,
                metadata=metadata or {},
                source=metadata.get("source", "api_upload") if metadata else "api_upload",
                doc_type=doc_type,
            )

            result = await RAGService._run_in_thread(
                indexer.index_documents, [doc], collection,
            )

            logger.info("rag.document_indexed", collection=collection, doc_id=doc_id)
            return {
                "collection": collection,
                "documents_indexed": 1,
                "chunks_created": result.get("chunks_created", 0) if isinstance(result, dict) else 0,
            }
        except (ValidationError, RAGError):
            raise
        except Exception as exc:
            raise RAGError(detail=f"Failed to index document: {exc}", stage="indexing")

    # ------------------------------------------------------------------
    # Index a directory
    # ------------------------------------------------------------------

    @staticmethod
    async def index_directory(
        path: str,
        collection: str,
    ) -> dict[str, Any]:
        """
        Recursively index all supported files in a directory.

        Args:
            path: Filesystem path to scan.
            collection: Target collection name.

        Returns:
            Dict with collection, documents_indexed, chunks_created, skipped, errors.
        """
        if not path:
            raise ValidationError(detail="Directory path is required.")
        if not collection:
            raise ValidationError(detail="Collection name is required.")

        indexer = RAGService._get_indexer()

        try:
            result = await RAGService._run_in_thread(
                indexer.index_directory, path, collection,
            )
            logger.info("rag.directory_indexed", collection=collection, path=path)
            if isinstance(result, dict):
                return result
            return {
                "collection": collection,
                "documents_indexed": 0,
                "chunks_created": 0,
                "skipped": 0,
                "errors": [],
            }
        except (ValidationError, RAGError):
            raise
        except Exception as exc:
            raise RAGError(detail=f"Failed to index directory: {exc}", stage="indexing")

    # ------------------------------------------------------------------
    # List collections
    # ------------------------------------------------------------------

    @staticmethod
    async def get_collections() -> list[dict[str, Any]]:
        """
        Return summary information for all known RAG collections.

        Returns:
            List of dicts with name, doc_count, and status.
        """
        store = RAGService._get_store()

        try:
            from api.rag.config import ALL_COLLECTIONS

            collections = []
            for coll_name in ALL_COLLECTIONS:
                try:
                    info = await RAGService._run_in_thread(
                        store.collection_info, coll_name,
                    )
                    if info:
                        collections.append({
                            "name": info.name if hasattr(info, "name") else coll_name,
                            "doc_count": info.doc_count if hasattr(info, "doc_count") else 0,
                            "status": info.status if hasattr(info, "status") else "ready",
                        })
                    else:
                        collections.append({
                            "name": coll_name,
                            "doc_count": 0,
                            "status": "not_found",
                        })
                except Exception:
                    collections.append({
                        "name": coll_name,
                        "doc_count": 0,
                        "status": "error",
                    })

            return collections
        except (RAGError,):
            raise
        except Exception as exc:
            raise RAGError(detail=f"Failed to list collections: {exc}", stage="list")

    # ------------------------------------------------------------------
    # Collection stats
    # ------------------------------------------------------------------

    @staticmethod
    async def get_collection_stats(collection: str) -> dict[str, Any]:
        """
        Return detailed statistics for a single collection.

        Args:
            collection: Collection name.

        Returns:
            Dict with collection, doc_count, chunk_count, embedding_dim,
            last_indexed.
        """
        if not collection:
            raise ValidationError(detail="Collection name is required.")

        store = RAGService._get_store()

        try:
            info = await RAGService._run_in_thread(
                store.collection_info, collection,
            )
            if not info:
                raise NotFoundError(resource="Collection", identifier=collection)

            return {
                "collection": collection,
                "doc_count": info.doc_count if hasattr(info, "doc_count") else 0,
                "chunk_count": getattr(info, "chunk_count", 0),
                "embedding_dim": getattr(info, "embedding_dim", 384),
                "status": info.status if hasattr(info, "status") else "unknown",
            }
        except (NotFoundError, RAGError):
            raise
        except Exception as exc:
            raise RAGError(
                detail=f"Failed to get stats for collection '{collection}': {exc}",
                stage="stats",
            )

    # ------------------------------------------------------------------
    # Reindex
    # ------------------------------------------------------------------

    @staticmethod
    async def reindex(collection: str) -> dict[str, Any]:
        """
        Drop and re-index a collection from its configured knowledge source.

        This is an expensive operation and should be called sparingly.

        Args:
            collection: Collection name to re-index.

        Returns:
            Dict with collection and status info.
        """
        if not collection:
            raise ValidationError(detail="Collection name is required.")

        store = RAGService._get_store()
        indexer = RAGService._get_indexer()

        try:
            # Delete existing collection
            await RAGService._run_in_thread(store.delete_collection, collection)
            logger.info("rag.collection_deleted_for_reindex", collection=collection)

            # Re-create and re-index from knowledge directory
            from api.rag.config import rag_config

            knowledge_dir = rag_config.knowledge_dir
            if knowledge_dir:
                result = await RAGService._run_in_thread(
                    indexer.index_directory, str(knowledge_dir), collection,
                )
                logger.info("rag.reindex_complete", collection=collection)
                if isinstance(result, dict):
                    return {"collection": collection, "status": "reindexed", **result}

            return {
                "collection": collection,
                "status": "reindexed",
                "documents_indexed": 0,
            }
        except (ValidationError, RAGError):
            raise
        except Exception as exc:
            raise RAGError(
                detail=f"Reindex failed for collection '{collection}': {exc}",
                stage="reindex",
            )

    # ------------------------------------------------------------------
    # Delete collection
    # ------------------------------------------------------------------

    @staticmethod
    async def delete_collection(collection: str) -> dict[str, Any]:
        """
        Permanently delete a collection and all its vectors.

        Args:
            collection: Collection name to delete.

        Returns:
            Confirmation dict.
        """
        if not collection:
            raise ValidationError(detail="Collection name is required.")

        store = RAGService._get_store()

        try:
            await RAGService._run_in_thread(store.delete_collection, collection)
            logger.info("rag.collection_deleted", collection=collection)
            return {"collection": collection, "deleted": True}
        except Exception as exc:
            raise RAGError(
                detail=f"Failed to delete collection '{collection}': {exc}",
                stage="delete",
            )
