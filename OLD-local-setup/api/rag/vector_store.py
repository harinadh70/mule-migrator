"""
Qdrant vector store wrapper for the RAG subsystem.

Provides collection management, point upsert/search/delete, payload indexing,
and health checks with retry logic and exponential backoff.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

from api.rag.config import RAGConfig, rag_config
from api.rag.schemas import CollectionInfo, CollectionStatus

logger = logging.getLogger(__name__)


class QdrantStore:
    """
    Thin wrapper around ``qdrant_client.QdrantClient`` that adds:

    * Automatic retry with exponential backoff on connection errors.
    * Convenience helpers for collection CRUD, search, and health checks.
    """

    def __init__(self, config: RAGConfig | None = None) -> None:
        self._config = config or rag_config
        qc = self._config.qdrant
        self._client: QdrantClient = QdrantClient(
            host=qc.host,
            port=qc.port,
            grpc_port=qc.grpc_port,
            prefer_grpc=qc.prefer_grpc,
            api_key=qc.api_key,
            timeout=qc.timeout,
        )
        self._max_retries = qc.max_retries
        self._retry_backoff = qc.retry_backoff

    # ------------------------------------------------------------------
    # Retry helper
    # ------------------------------------------------------------------

    def _retry(self, fn, *args, **kwargs):
        """Execute *fn* with exponential backoff on transient errors."""
        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except (ConnectionError, OSError, TimeoutError) as exc:
                last_exc = exc
                wait = self._retry_backoff * (2 ** (attempt - 1))
                logger.warning(
                    "Qdrant call failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt,
                    self._max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)
            except UnexpectedResponse as exc:
                # 5xx errors are retryable; 4xx are not
                if exc.status_code and exc.status_code >= 500:
                    last_exc = exc
                    wait = self._retry_backoff * (2 ** (attempt - 1))
                    logger.warning(
                        "Qdrant 5xx (attempt %d/%d): %s — retrying in %.1fs",
                        attempt,
                        self._max_retries,
                        exc,
                        wait,
                    )
                    time.sleep(wait)
                else:
                    raise
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def create_collection(
        self,
        name: str,
        vector_size: int = 384,
        distance: str = "Cosine",
        on_disk: bool = False,
    ) -> bool:
        """
        Create a Qdrant collection if it does not already exist.

        Args:
            name: Collection name.
            vector_size: Dimensionality of the vectors.
            distance: Distance metric (Cosine, Euclid, Dot).
            on_disk: Whether to store vectors on disk (reduces RAM usage).

        Returns:
            True if the collection was created, False if it already existed.
        """
        dist_map = {
            "Cosine": qmodels.Distance.COSINE,
            "Euclid": qmodels.Distance.EUCLID,
            "Dot": qmodels.Distance.DOT,
        }
        distance_enum = dist_map.get(distance, qmodels.Distance.COSINE)

        existing = self._retry(self._client.get_collections).collections
        if any(c.name == name for c in existing):
            logger.info("Collection '%s' already exists; skipping creation.", name)
            return False

        self._retry(
            self._client.create_collection,
            collection_name=name,
            vectors_config=qmodels.VectorParams(
                size=vector_size,
                distance=distance_enum,
                on_disk=on_disk,
            ),
        )
        logger.info("Created Qdrant collection '%s' (dim=%d, dist=%s).", name, vector_size, distance)
        return True

    def delete_collection(self, name: str) -> bool:
        """Delete a collection. Returns True if deleted, False if not found."""
        try:
            self._retry(self._client.delete_collection, collection_name=name)
            logger.info("Deleted collection '%s'.", name)
            return True
        except UnexpectedResponse as exc:
            if exc.status_code == 404:
                return False
            raise

    # ------------------------------------------------------------------
    # Point operations
    # ------------------------------------------------------------------

    def upsert(
        self,
        collection: str,
        points: List[Dict[str, Any]],
    ) -> None:
        """
        Upsert points into a collection.

        Each dict in *points* must have keys ``id``, ``vector``, and ``payload``.
        Points are uploaded in a single batch call.
        """
        if not points:
            return
        qdrant_points = [
            qmodels.PointStruct(
                id=p["id"],
                vector=p["vector"],
                payload=p.get("payload", {}),
            )
            for p in points
        ]
        self._retry(
            self._client.upsert,
            collection_name=collection,
            points=qdrant_points,
            wait=True,
        )
        logger.debug("Upserted %d points into '%s'.", len(qdrant_points), collection)

    def search(
        self,
        collection: str,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
    ) -> List[qmodels.ScoredPoint]:
        """
        Search for nearest neighbours in a collection.

        Args:
            collection: Target collection name.
            query_vector: Query embedding.
            top_k: Maximum number of results.
            filters: Optional Qdrant filter dict.
            score_threshold: Minimum similarity score.

        Returns:
            List of ``ScoredPoint`` objects ordered by descending score.
        """
        query_filter = None
        if filters:
            query_filter = qmodels.Filter(**filters)

        results = self._retry(
            self._client.search,
            collection_name=collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=query_filter,
            score_threshold=score_threshold,
        )
        return results

    def delete(self, collection: str, ids: List[str | int]) -> None:
        """Delete points by their IDs."""
        if not ids:
            return
        self._retry(
            self._client.delete,
            collection_name=collection,
            points_selector=qmodels.PointIdsList(points=ids),
            wait=True,
        )
        logger.debug("Deleted %d points from '%s'.", len(ids), collection)

    def scroll(
        self,
        collection: str,
        limit: int = 100,
        offset: Optional[str | int] = None,
        with_payload: bool = True,
        with_vectors: bool = False,
    ):
        """Scroll through all points in a collection (paginated)."""
        return self._retry(
            self._client.scroll,
            collection_name=collection,
            limit=limit,
            offset=offset,
            with_payload=with_payload,
            with_vectors=with_vectors,
        )

    # ------------------------------------------------------------------
    # Payload index
    # ------------------------------------------------------------------

    def create_payload_index(
        self,
        collection: str,
        field_name: str,
        field_type: str = "keyword",
    ) -> None:
        """
        Create a payload index for faster filtered search.

        Args:
            field_type: One of 'keyword', 'integer', 'float', 'bool', 'text'.
        """
        schema_map = {
            "keyword": qmodels.PayloadSchemaType.KEYWORD,
            "integer": qmodels.PayloadSchemaType.INTEGER,
            "float": qmodels.PayloadSchemaType.FLOAT,
            "bool": qmodels.PayloadSchemaType.BOOL,
            "text": qmodels.PayloadSchemaType.TEXT,
        }
        schema = schema_map.get(field_type, qmodels.PayloadSchemaType.KEYWORD)
        self._retry(
            self._client.create_payload_index,
            collection_name=collection,
            field_name=field_name,
            field_schema=schema,
            wait=True,
        )
        logger.info("Created payload index on '%s.%s' (%s).", collection, field_name, field_type)

    # ------------------------------------------------------------------
    # Metadata / health
    # ------------------------------------------------------------------

    def get_collection_info(self, name: str) -> CollectionInfo:
        """Return summary information for a collection."""
        try:
            info = self._retry(self._client.get_collection, collection_name=name)
            return CollectionInfo(
                name=name,
                doc_count=info.points_count or 0,
                status=CollectionStatus.READY if info.status == "green" else CollectionStatus.INDEXING,
            )
        except (UnexpectedResponse, Exception) as exc:
            logger.warning("Could not fetch info for collection '%s': %s", name, exc)
            return CollectionInfo(name=name, doc_count=0, status=CollectionStatus.NOT_FOUND)

    def health_check(self) -> bool:
        """Return True if Qdrant is reachable."""
        try:
            self._client.get_collections()
            return True
        except Exception as exc:
            logger.warning("Qdrant health check failed: %s", exc)
            return False
