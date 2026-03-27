"""
AgentMemory — short-term (in-process) and long-term (Qdrant-backed) memory.

Short-term memory lives for the duration of a single migration run.
Long-term memory persists across runs and is used to recall similar
past migrations so agents can learn from prior patterns.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, List, Optional, TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from api.agents.context import AgentContext
    from api.agents.result import AgentResult

logger = structlog.get_logger(__name__)

# Default Qdrant collection for migration history
_HISTORY_COLLECTION = "migration_history"


class AgentMemory:
    """Dual-layer memory system for agents.

    Short-term layer
    ~~~~~~~~~~~~~~~~
    Plain ``dict``-based store scoped to the current migration run.
    Keys are arbitrary strings; values are any serialisable object.

    Long-term layer
    ~~~~~~~~~~~~~~~
    Backed by Qdrant via the existing ``QdrantStore`` from ``api.rag``.
    Each entry is a small JSON document with an embedding vector so that
    future agents can search for similar past patterns.
    """

    def __init__(
        self,
        qdrant_store: Optional[Any] = None,
        embedding_service: Optional[Any] = None,
        collection: str = _HISTORY_COLLECTION,
    ) -> None:
        # Short-term (session-scoped)
        self._short_term: Dict[str, Any] = {}
        self._short_term_timestamps: Dict[str, float] = {}

        # Long-term (Qdrant-backed)
        self._qdrant = qdrant_store
        self._embedder = embedding_service
        self._collection = collection

    # ------------------------------------------------------------------
    #  Short-term operations
    # ------------------------------------------------------------------

    def set(self, key: str, value: Any) -> None:
        """Store a value in short-term memory."""
        self._short_term[key] = value
        self._short_term_timestamps[key] = time.time()

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve from short-term memory."""
        return self._short_term.get(key, default)

    def has(self, key: str) -> bool:
        return key in self._short_term

    def list_keys(self) -> List[str]:
        return list(self._short_term.keys())

    def clear_short_term(self) -> None:
        """Reset short-term memory for a new migration run."""
        count = len(self._short_term)
        self._short_term.clear()
        self._short_term_timestamps.clear()
        logger.info("memory.short_term.cleared", entries_removed=count)

    # ------------------------------------------------------------------
    #  Combined store / recall
    # ------------------------------------------------------------------

    def store(self, context: "AgentContext", result: "AgentResult") -> None:
        """Persist an agent result to both memory layers.

        Short-term: keyed by ``<run_id>:<agent_name>``.
        Long-term: written to Qdrant with an embedding of the result summary.
        """
        # Always store short-term
        st_key = f"{context.id}:latest_result"
        self.set(st_key, result.to_dict())

        # Long-term storage (best-effort)
        self._store_long_term(context, result)

    def _store_long_term(
        self, context: "AgentContext", result: "AgentResult"
    ) -> None:
        """Attempt to persist to Qdrant. Silently no-ops if unavailable."""
        if self._qdrant is None or self._embedder is None:
            return

        try:
            summary_text = json.dumps(
                {
                    "run_id": context.id,
                    "pipeline_state": {
                        k: v.get("status", "unknown") if isinstance(v, dict) else str(v)
                        for k, v in context.pipeline_state.items()
                    },
                    "token_usage": context.token_usage,
                    "result_status": result.status,
                },
                default=str,
            )

            # Generate embedding
            vector = self._embedder.embed(summary_text)
            if vector is None:
                return

            # Deterministic ID from run_id
            point_id = hashlib.md5(context.id.encode()).hexdigest()

            self._qdrant.upsert(
                collection_name=self._collection,
                points=[
                    {
                        "id": point_id,
                        "vector": vector,
                        "payload": {
                            "run_id": context.id,
                            "summary": summary_text,
                            "token_usage": sum(context.token_usage.values()),
                            "total_cost_usd": context.total_cost_usd,
                            "created_at": context.created_at.isoformat(),
                            "result_status": result.status,
                        },
                    }
                ],
            )
            logger.info("memory.long_term.stored", run_id=context.id)
        except Exception as exc:
            logger.warning("memory.long_term.store_failed", error=str(exc))

    def recall(
        self,
        query: str,
        collection: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search long-term memory for past migration patterns.

        Args:
            query: Natural-language description of what to look for.
            collection: Qdrant collection to search (defaults to migration_history).
            top_k: Maximum number of results to return.

        Returns:
            List of payload dicts from matching Qdrant points, ordered by
            relevance.  Returns an empty list when Qdrant is not available.
        """
        if self._qdrant is None or self._embedder is None:
            return []

        target_collection = collection or self._collection
        try:
            vector = self._embedder.embed(query)
            if vector is None:
                return []

            results = self._qdrant.search(
                collection_name=target_collection,
                query_vector=vector,
                limit=top_k,
            )
            return [
                {
                    "score": r.score if hasattr(r, "score") else 0.0,
                    **r.payload,
                }
                for r in results
                if hasattr(r, "payload")
            ]
        except Exception as exc:
            logger.warning(
                "memory.recall.failed",
                collection=target_collection,
                error=str(exc),
            )
            return []

    # ------------------------------------------------------------------
    #  Maintenance
    # ------------------------------------------------------------------

    def prune_low_quality(self, threshold: float = 5.0) -> int:
        """Remove long-term entries with an overall score below *threshold*.

        Returns the number of entries removed.  No-ops when Qdrant is not
        available.
        """
        if self._qdrant is None:
            return 0

        try:
            # Scroll through all points and filter by score
            removed = 0
            scroll_result = self._qdrant.scroll(
                collection_name=self._collection,
                limit=200,
            )
            points_to_delete = []
            for point in scroll_result[0] if isinstance(scroll_result, tuple) else scroll_result:
                payload = point.payload if hasattr(point, "payload") else {}
                score = payload.get("overall_score", 10.0)
                if score < threshold:
                    points_to_delete.append(point.id)

            if points_to_delete:
                self._qdrant.delete(
                    collection_name=self._collection,
                    points_selector=points_to_delete,
                )
                removed = len(points_to_delete)

            logger.info(
                "memory.prune.complete",
                removed=removed,
                threshold=threshold,
            )
            return removed
        except Exception as exc:
            logger.warning("memory.prune.failed", error=str(exc))
            return 0
