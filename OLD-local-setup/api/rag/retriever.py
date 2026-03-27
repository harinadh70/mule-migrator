"""
Hybrid retriever for the RAG subsystem.

Performs dense vector search with query expansion, deduplication, relevance
filtering, and context-window packing.  Provides specialized retrieval
methods for MuleSoft connectors, Spring Boot patterns, migration history,
and custom code patterns.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any, Dict, List, Optional

from api.rag.chunking import _count_tokens
from api.rag.config import (
    ALL_COLLECTIONS,
    COLLECTION_CUSTOM_PATTERNS,
    COLLECTION_MIGRATION_HISTORY,
    COLLECTION_MULESOFT_DOCS,
    COLLECTION_SPRINGBOOT_DOCS,
    RAGConfig,
    rag_config,
)
from api.rag.embeddings import EmbeddingService
from api.rag.schemas import Chunk, SearchQuery, SearchResult
from api.rag.vector_store import QdrantStore

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Retrieval engine that combines dense embedding search with query expansion,
    result deduplication, relevance thresholding, and token-budget packing.

    Usage::

        retriever = HybridRetriever()
        results = retriever.search("How to convert HTTP Listener to RestController")
        context = retriever.retrieve_mulesoft_context("http:listener", "<xml>...</xml>")
    """

    def __init__(
        self,
        config: RAGConfig | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: QdrantStore | None = None,
    ) -> None:
        self._config = config or rag_config
        self._embedder = embedding_service or EmbeddingService.get_instance(self._config)
        self._store = vector_store or QdrantStore(self._config)
        self._search_cfg = self._config.search

    # ------------------------------------------------------------------
    # Primary search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        collection: str | None = None,
        filters: Dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> List[SearchResult]:
        """
        Execute a hybrid search across one or more collections.

        1. Generate query embedding.
        2. Optionally expand query into alternate phrasings.
        3. Search each target collection.
        4. Merge, deduplicate, threshold-filter, and pack results.

        Args:
            query: Natural-language search query.
            collection: Target collection (None searches all).
            filters: Optional Qdrant payload filters.
            top_k: Max results to return.

        Returns:
            Ranked list of ``SearchResult`` objects.
        """
        top_k = top_k or self._search_cfg.top_k
        collections = [collection] if collection else ALL_COLLECTIONS

        # Build query variants for expansion
        query_variants = self._expand_query(query)
        all_query_texts = [query] + query_variants

        # Embed all queries in a batch
        query_embeddings = self._embedder.embed_batch(all_query_texts)

        # Search each collection with each query variant
        all_results: List[SearchResult] = []
        for coll in collections:
            for qvec in query_embeddings:
                try:
                    scored_points = self._store.search(
                        collection=coll,
                        query_vector=qvec,
                        top_k=top_k,
                        filters=filters,
                        score_threshold=self._search_cfg.similarity_threshold,
                    )
                    all_results.extend(self._scored_points_to_results(scored_points, coll))
                except Exception:
                    logger.warning("Search failed on collection '%s'; skipping.", coll, exc_info=True)

        # Post-process
        results = self._deduplicate(all_results)
        results = self._filter_threshold(results)
        results.sort(key=lambda r: r.score, reverse=True)
        results = self._pack_context_window(results)
        return results[:top_k]

    def search_query(self, sq: SearchQuery) -> List[SearchResult]:
        """Convenience wrapper accepting a ``SearchQuery`` Pydantic model."""
        return self.search(
            query=sq.query,
            collection=sq.collection,
            filters=sq.filters,
            top_k=sq.top_k,
        )

    # ------------------------------------------------------------------
    # Domain-specific retrievers
    # ------------------------------------------------------------------

    def retrieve_mulesoft_context(
        self,
        connector_name: str,
        xml_snippet: str = "",
    ) -> List[SearchResult]:
        """
        Retrieve documentation and examples for a MuleSoft connector.

        Args:
            connector_name: e.g. ``http:listener``, ``db:select``.
            xml_snippet: Optional XML fragment for additional context.
        """
        query = f"MuleSoft {connector_name} connector configuration and usage"
        if xml_snippet:
            query += f"\n\n{xml_snippet[:300]}"
        return self.search(
            query=query,
            collection=COLLECTION_MULESOFT_DOCS,
            top_k=self._search_cfg.rerank_top_k,
        )

    def retrieve_spring_pattern(
        self,
        annotation: str,
        use_case: str = "",
    ) -> List[SearchResult]:
        """
        Retrieve Spring Boot patterns matching an annotation or use case.

        Args:
            annotation: e.g. ``@RestController``, ``@JpaRepository``.
            use_case: Optional description such as "CRUD REST API".
        """
        query = f"Spring Boot {annotation} pattern"
        if use_case:
            query += f" for {use_case}"
        return self.search(
            query=query,
            collection=COLLECTION_SPRINGBOOT_DOCS,
            top_k=self._search_cfg.rerank_top_k,
        )

    def retrieve_similar_migrations(
        self,
        parsed_flow: str,
    ) -> List[SearchResult]:
        """
        Retrieve past migration examples similar to a parsed MuleSoft flow.

        Args:
            parsed_flow: Textual description or serialized parse tree of the flow.
        """
        query = f"Migration example for MuleSoft flow:\n{parsed_flow[:500]}"
        return self.search(
            query=query,
            collection=COLLECTION_MIGRATION_HISTORY,
            top_k=self._search_cfg.rerank_top_k,
        )

    def retrieve_custom_patterns(
        self,
        code_snippet: str,
    ) -> List[SearchResult]:
        """
        Retrieve custom code patterns similar to a given snippet.
        """
        query = f"Code pattern similar to:\n{code_snippet[:500]}"
        return self.search(
            query=query,
            collection=COLLECTION_CUSTOM_PATTERNS,
            top_k=self._search_cfg.rerank_top_k,
        )

    # ------------------------------------------------------------------
    # Query expansion
    # ------------------------------------------------------------------

    def _expand_query(self, query: str) -> List[str]:
        """
        Generate alternate phrasings to improve recall.

        Uses simple heuristic reformulations rather than an LLM call
        (to keep latency low and avoid external API dependency during search).
        """
        variants: List[str] = []
        q_lower = query.lower()

        # Variant 1: Rephrase as a "how to" question
        if not q_lower.startswith("how"):
            variants.append(f"How to {query}")

        # Variant 2: Add migration context
        if "migrat" not in q_lower and "convert" not in q_lower:
            variants.append(f"Migrate MuleSoft to Spring Boot: {query}")

        # Variant 3: Focus on the Spring Boot equivalent
        if "spring" not in q_lower:
            variants.append(f"Spring Boot equivalent of {query}")

        return variants[: self._search_cfg.query_expansion_count]

    # ------------------------------------------------------------------
    # Post-processing
    # ------------------------------------------------------------------

    def _scored_points_to_results(
        self, scored_points, collection: str
    ) -> List[SearchResult]:
        """Convert Qdrant ScoredPoint list to SearchResult list."""
        results: List[SearchResult] = []
        for sp in scored_points:
            payload = sp.payload or {}
            chunk = Chunk(
                id=str(sp.id),
                content=payload.get("content", ""),
                metadata={
                    "source_type": payload.get("source_type", ""),
                    "section_name": payload.get("section_name", ""),
                    "line_start": payload.get("line_start", 0),
                    "line_end": payload.get("line_end", 0),
                    "collection": collection,
                },
                doc_id=payload.get("doc_id", ""),
                chunk_index=payload.get("chunk_index", 0),
                token_count=payload.get("token_count", 0),
            )
            results.append(SearchResult(
                chunk=chunk,
                score=sp.score,
                source=payload.get("source", ""),
                metadata=payload,
            ))
        return results

    @staticmethod
    def _content_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _deduplicate(self, results: List[SearchResult]) -> List[SearchResult]:
        """Remove duplicate chunks (same content hash), keeping highest score."""
        seen: Dict[str, SearchResult] = {}
        for r in results:
            h = self._content_hash(r.chunk.content)
            if h not in seen or r.score > seen[h].score:
                seen[h] = r
        return list(seen.values())

    def _filter_threshold(self, results: List[SearchResult]) -> List[SearchResult]:
        """Drop results below the configured similarity threshold."""
        threshold = self._search_cfg.similarity_threshold
        return [r for r in results if r.score >= threshold]

    def _pack_context_window(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Greedily pack results into the token budget (highest score first).

        Ensures the total token count of selected results does not exceed
        ``context_token_budget``.
        """
        budget = self._search_cfg.context_token_budget
        packed: List[SearchResult] = []
        used_tokens = 0

        for r in results:
            tok = r.chunk.token_count or _count_tokens(r.chunk.content)
            if used_tokens + tok > budget:
                continue
            packed.append(r)
            used_tokens += tok

        return packed
