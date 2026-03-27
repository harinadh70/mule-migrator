"""
Document indexer for the RAG subsystem.

Handles recursive directory scanning, deduplication via content hashing,
incremental indexing, chunking, embedding, and upserting into Qdrant.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

from api.rag.cache import EmbeddingCache
from api.rag.chunking import CodeAwareChunker, RawChunk, _count_tokens
from api.rag.config import (
    COLLECTION_MULESOFT_DOCS,
    COLLECTION_SPRINGBOOT_DOCS,
    RAGConfig,
    rag_config,
)
from api.rag.embeddings import EmbeddingService
from api.rag.schemas import Chunk, Document, DocType, IndexStats
from api.rag.vector_store import QdrantStore

logger = logging.getLogger(__name__)

# File extensions we know how to index
INDEXABLE_EXTENSIONS: Set[str] = {
    ".xml", ".java", ".kt", ".md", ".markdown", ".txt",
    ".json", ".yaml", ".yml", ".properties", ".gradle",
    ".py", ".groovy", ".html",
}

ProgressCallback = Callable[[int, int, str], None]
"""Signature: (current, total, message) -> None"""


class DocumentIndexer:
    """
    Orchestrates the full indexing pipeline:

    1. Scan files from disk or accept ``Document`` objects directly.
    2. Deduplicate by content SHA-256 hash.
    3. Chunk using ``CodeAwareChunker``.
    4. Embed chunks (with optional cache lookup).
    5. Upsert into Qdrant via ``QdrantStore``.
    """

    def __init__(
        self,
        config: RAGConfig | None = None,
        embedding_service: EmbeddingService | None = None,
        vector_store: QdrantStore | None = None,
        chunker: CodeAwareChunker | None = None,
        cache: EmbeddingCache | None = None,
    ) -> None:
        self._config = config or rag_config
        self._embedder = embedding_service or EmbeddingService.get_instance(self._config)
        self._store = vector_store or QdrantStore(self._config)
        self._chunker = chunker or CodeAwareChunker(self._config)
        self._cache = cache  # Optional; may be None if Redis unavailable

        # Track content hashes already indexed so we can skip duplicates.
        # Populated lazily on first call that needs it.
        self._known_hashes: Dict[str, Set[str]] = {}

    # ------------------------------------------------------------------
    # Hash helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _content_hash(content: str) -> str:
        """SHA-256 hex digest of the content string."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _is_already_indexed(self, collection: str, content_hash: str) -> bool:
        """Check if a content hash is already known for the given collection."""
        return content_hash in self._known_hashes.get(collection, set())

    def _record_hash(self, collection: str, content_hash: str) -> None:
        self._known_hashes.setdefault(collection, set()).add(content_hash)

    # ------------------------------------------------------------------
    # High-level public API
    # ------------------------------------------------------------------

    def index_directory(
        self,
        path: str,
        collection: str,
        doc_type: str = "custom",
        progress: ProgressCallback | None = None,
    ) -> IndexStats:
        """
        Recursively index all supported files under *path*.

        Args:
            path: Root directory to scan.
            collection: Target Qdrant collection.
            doc_type: Document type label.
            progress: Optional callback for UI updates.

        Returns:
            An ``IndexStats`` summarising the indexing run.
        """
        self._ensure_collection(collection)
        files = self._scan_directory(path)
        total = len(files)
        logger.info("Found %d indexable files in '%s'.", total, path)

        doc_count = 0
        chunk_count = 0

        for idx, filepath in enumerate(files, start=1):
            if progress:
                progress(idx, total, f"Indexing {os.path.basename(filepath)}")
            try:
                content = Path(filepath).read_text(encoding="utf-8", errors="replace")
                content_hash = self._content_hash(content)
                if self._is_already_indexed(collection, content_hash):
                    logger.debug("Skipping unchanged file: %s", filepath)
                    continue

                doc = Document(
                    id=content_hash,
                    content=content,
                    metadata={"file_path": filepath, "file_ext": Path(filepath).suffix},
                    source=filepath,
                    doc_type=doc_type,
                )
                n_chunks = self.index_document(doc, collection)
                doc_count += 1
                chunk_count += n_chunks
                self._record_hash(collection, content_hash)
            except Exception:
                logger.exception("Error indexing file '%s'.", filepath)

        return IndexStats(
            collection=collection,
            doc_count=doc_count,
            chunk_count=chunk_count,
            embedding_dim=self._config.embedding.embedding_dim,
            last_indexed=datetime.now(timezone.utc),
        )

    def index_document(self, doc: Document, collection: str) -> int:
        """
        Chunk, embed, and upsert a single ``Document``.

        Returns:
            The number of chunks created and indexed.
        """
        self._ensure_collection(collection)

        raw_chunks = self._chunker.chunk_auto(doc.content, filename=doc.source)
        if not raw_chunks:
            logger.debug("No chunks produced for document %s.", doc.id)
            return 0

        texts = [rc.content for rc in raw_chunks]
        embeddings = self._embed_texts(texts)

        points: List[Dict[str, Any]] = []
        for i, (rc, embedding) in enumerate(zip(raw_chunks, embeddings)):
            chunk_id = str(uuid4())
            payload = {
                "content": rc.content,
                "doc_id": doc.id,
                "chunk_index": i,
                "token_count": _count_tokens(rc.content),
                "source": doc.source,
                "doc_type": doc.doc_type,
                "source_type": rc.metadata.get("source_type", ""),
                "section_name": rc.metadata.get("section_name", ""),
                "line_start": rc.line_start,
                "line_end": rc.line_end,
                "content_hash": self._content_hash(rc.content),
            }
            points.append({"id": chunk_id, "vector": embedding, "payload": payload})

        self._store.upsert(collection, points)
        logger.debug("Indexed %d chunks for document '%s' into '%s'.", len(points), doc.source, collection)
        return len(points)

    # ------------------------------------------------------------------
    # Built-in knowledge base indexing
    # ------------------------------------------------------------------

    def index_mulesoft_knowledge(
        self, progress: ProgressCallback | None = None
    ) -> IndexStats:
        """Index the bundled MuleSoft knowledge base documents."""
        kb_dir = os.path.join(self._config.knowledge_base_dir, "mulesoft")
        if not os.path.isdir(kb_dir):
            logger.warning("MuleSoft knowledge directory not found: %s", kb_dir)
            return IndexStats(collection=COLLECTION_MULESOFT_DOCS)
        return self.index_directory(
            path=kb_dir,
            collection=COLLECTION_MULESOFT_DOCS,
            doc_type="mulesoft",
            progress=progress,
        )

    def index_springboot_knowledge(
        self, progress: ProgressCallback | None = None
    ) -> IndexStats:
        """Index the bundled Spring Boot knowledge base documents."""
        kb_dir = os.path.join(self._config.knowledge_base_dir, "springboot")
        if not os.path.isdir(kb_dir):
            logger.warning("Spring Boot knowledge directory not found: %s", kb_dir)
            return IndexStats(collection=COLLECTION_SPRINGBOOT_DOCS)
        return self.index_directory(
            path=kb_dir,
            collection=COLLECTION_SPRINGBOOT_DOCS,
            doc_type="springboot",
            progress=progress,
        )

    def index_all_knowledge(
        self, progress: ProgressCallback | None = None
    ) -> Dict[str, IndexStats]:
        """Index both MuleSoft and Spring Boot built-in knowledge bases."""
        return {
            "mulesoft": self.index_mulesoft_knowledge(progress),
            "springboot": self.index_springboot_knowledge(progress),
        }

    # ------------------------------------------------------------------
    # Re-indexing
    # ------------------------------------------------------------------

    def reindex_collection(
        self,
        collection: str,
        path: str | None = None,
        doc_type: str = "custom",
        progress: ProgressCallback | None = None,
    ) -> IndexStats:
        """
        Drop and recreate the collection, then re-index from scratch.

        Args:
            collection: The collection to reindex.
            path: Directory to scan. If None, uses knowledge base dir.
            doc_type: Document type label.
            progress: Optional progress callback.
        """
        logger.info("Reindexing collection '%s' ...", collection)
        self._store.delete_collection(collection)
        self._known_hashes.pop(collection, None)

        if path is None:
            # Determine path from known collections
            if collection == COLLECTION_MULESOFT_DOCS:
                return self.index_mulesoft_knowledge(progress)
            elif collection == COLLECTION_SPRINGBOOT_DOCS:
                return self.index_springboot_knowledge(progress)
            else:
                logger.warning("No default path for collection '%s'; nothing to reindex.", collection)
                return IndexStats(collection=collection)

        return self.index_directory(path, collection, doc_type, progress)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_collection(self, collection: str) -> None:
        """Create the Qdrant collection if it doesn't already exist."""
        self._store.create_collection(
            name=collection,
            vector_size=self._config.embedding.embedding_dim,
            distance="Cosine",
        )

    def _embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a list of texts, using the cache when available.
        """
        if not texts:
            return []

        if self._cache is None:
            return self._embedder.embed_batch(texts)

        embeddings: List[Optional[List[float]]] = [None] * len(texts)
        uncached_indices: List[int] = []

        for i, text in enumerate(texts):
            cached = self._cache.get(text)
            if cached is not None:
                embeddings[i] = cached
            else:
                uncached_indices.append(i)

        if uncached_indices:
            uncached_texts = [texts[i] for i in uncached_indices]
            new_embeddings = self._embedder.embed_batch(uncached_texts)
            for idx, emb in zip(uncached_indices, new_embeddings):
                embeddings[idx] = emb
                self._cache.set(texts[idx], emb)

        return embeddings  # type: ignore[return-value]

    @staticmethod
    def _scan_directory(root: str) -> List[str]:
        """Recursively list indexable files under *root*."""
        files: List[str] = []
        for dirpath, _, filenames in os.walk(root):
            for fname in sorted(filenames):
                ext = os.path.splitext(fname)[1].lower()
                if ext in INDEXABLE_EXTENSIONS:
                    files.append(os.path.join(dirpath, fname))
        return files
