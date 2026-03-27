"""
Celery tasks for knowledge-base indexing and periodic maintenance.

These tasks run on the lower-priority 'indexing' queue and handle
operations like embedding knowledge documents into Qdrant and cleaning
up old migration data.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import structlog
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import delete, select

from api.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------


def _run_async(coro):
    """Run an async coroutine from synchronous Celery task context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


async def _get_session():
    """Create a standalone async session for Celery workers."""
    from api.database import _get_session_factory
    factory = _get_session_factory()
    return factory()


# ---------------------------------------------------------------------------
#  Task: index_knowledge_base
# ---------------------------------------------------------------------------


@celery_app.task(
    name="api.tasks.indexing_tasks.index_knowledge_base",
    bind=True,
    acks_late=True,
    ignore_result=False,
    priority=1,
)
def index_knowledge_base(self) -> Dict[str, Any]:
    """
    Index all built-in knowledge documents into the vector store.

    Reads Markdown/text files from the configured knowledge directory,
    chunks them, generates embeddings, and upserts into Qdrant.

    Returns:
        Summary dict with document and chunk counts.
    """
    logger.info(
        "indexing.knowledge_base_started",
        task_id=self.request.id,
    )

    try:
        result = _run_async(_do_index_knowledge_base())
        logger.info(
            "indexing.knowledge_base_completed",
            **result,
        )
        return result
    except SoftTimeLimitExceeded:
        logger.error("indexing.knowledge_base_timeout")
        return {"status": "timed_out"}
    except Exception as exc:
        logger.error(
            "indexing.knowledge_base_failed",
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc, max_retries=2)


async def _do_index_knowledge_base() -> Dict[str, Any]:
    """Core indexing logic for the full knowledge base."""
    from api.config import get_settings
    from api.dependencies import init_embedding_service, init_qdrant

    settings = get_settings()
    knowledge_dir = Path(settings.rag.knowledge_dir)

    if not knowledge_dir.exists():
        logger.warning(
            "indexing.knowledge_dir_not_found",
            path=str(knowledge_dir),
        )
        return {
            "status": "skipped",
            "reason": "knowledge directory not found",
            "path": str(knowledge_dir),
        }

    # Discover documents
    doc_extensions = {".md", ".txt", ".rst", ".json", ".yaml", ".yml"}
    doc_files = [
        f for f in knowledge_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in doc_extensions
    ]

    if not doc_files:
        return {"status": "skipped", "reason": "no documents found", "documents": 0}

    # Initialize services
    embedder = init_embedding_service(settings)
    qdrant = await init_qdrant(settings)

    # Chunk documents
    chunks = []
    chunk_size = settings.rag.chunk_size
    chunk_overlap = settings.rag.chunk_overlap

    for doc_path in doc_files:
        try:
            content = doc_path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.warning(
                "indexing.read_failed",
                path=str(doc_path),
                error=str(exc),
            )
            continue

        # Simple sliding-window chunking
        words = content.split()
        for i in range(0, len(words), chunk_size - chunk_overlap):
            chunk_words = words[i:i + chunk_size]
            if len(chunk_words) < 20:  # skip tiny trailing chunks
                continue
            chunk_text = " ".join(chunk_words)
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "source": str(doc_path.relative_to(knowledge_dir)),
                    "type": doc_path.suffix.lstrip("."),
                    "chunk_index": i // (chunk_size - chunk_overlap),
                },
            })

    if not chunks:
        return {"status": "completed", "documents": len(doc_files), "chunks": 0}

    # Generate embeddings in batches
    batch_size = 64
    all_vectors = []
    for i in range(0, len(chunks), batch_size):
        batch_texts = [c["text"] for c in chunks[i:i + batch_size]]
        vectors = embedder.encode(batch_texts)
        all_vectors.extend(vectors)

    # Upsert into Qdrant
    from qdrant_client.models import PointStruct
    import uuid

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "text": chunk["text"],
                **chunk["metadata"],
            },
        )
        for chunk, vector in zip(chunks, all_vectors)
    ]

    # Upsert in batches of 100
    collection_name = settings.qdrant.collection
    for i in range(0, len(points), 100):
        batch = points[i:i + 100]
        await qdrant.upsert(
            collection_name=collection_name,
            points=batch,
        )

    return {
        "status": "completed",
        "documents": len(doc_files),
        "chunks": len(chunks),
        "collection": collection_name,
    }


# ---------------------------------------------------------------------------
#  Task: index_collection
# ---------------------------------------------------------------------------


@celery_app.task(
    name="api.tasks.indexing_tasks.index_collection",
    bind=True,
    acks_late=True,
    ignore_result=False,
    priority=1,
)
def index_collection(
    self,
    collection: str,
    path: str,
) -> Dict[str, Any]:
    """
    Index documents from a specific directory into a named Qdrant collection.

    Args:
        collection: Target Qdrant collection name.
        path: Filesystem path containing documents to index.

    Returns:
        Summary dict with indexing results.
    """
    logger.info(
        "indexing.collection_started",
        collection=collection,
        path=path,
        task_id=self.request.id,
    )

    try:
        result = _run_async(_do_index_collection(collection, path))
        logger.info("indexing.collection_completed", **result)
        return result
    except SoftTimeLimitExceeded:
        logger.error("indexing.collection_timeout", collection=collection)
        return {"status": "timed_out", "collection": collection}
    except Exception as exc:
        logger.error(
            "indexing.collection_failed",
            collection=collection,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc, max_retries=2)


async def _do_index_collection(collection: str, path: str) -> Dict[str, Any]:
    """Index a specific collection from a given path."""
    from api.config import get_settings
    from api.dependencies import init_embedding_service, init_qdrant

    settings = get_settings()
    source_dir = Path(path)

    if not source_dir.exists():
        return {
            "status": "error",
            "collection": collection,
            "reason": f"Path does not exist: {path}",
        }

    doc_extensions = {".md", ".txt", ".rst", ".json", ".yaml", ".yml"}
    doc_files = [
        f for f in source_dir.rglob("*")
        if f.is_file() and f.suffix.lower() in doc_extensions
    ]

    if not doc_files:
        return {"status": "completed", "collection": collection, "documents": 0, "chunks": 0}

    embedder = init_embedding_service(settings)
    qdrant = await init_qdrant(settings)

    # Ensure collection exists
    from qdrant_client.models import Distance, VectorParams

    collections = await qdrant.get_collections()
    existing = {c.name for c in collections.collections}
    if collection not in existing:
        await qdrant.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=settings.rag.embedding_dimension,
                distance=Distance.COSINE,
            ),
        )

    # Chunk and embed
    chunk_size = settings.rag.chunk_size
    chunk_overlap = settings.rag.chunk_overlap
    chunks = []

    for doc_path in doc_files:
        try:
            content = doc_path.read_text(encoding="utf-8")
        except Exception:
            continue

        words = content.split()
        for i in range(0, len(words), chunk_size - chunk_overlap):
            chunk_words = words[i:i + chunk_size]
            if len(chunk_words) < 20:
                continue
            chunks.append({
                "text": " ".join(chunk_words),
                "metadata": {
                    "source": str(doc_path.relative_to(source_dir)),
                    "type": doc_path.suffix.lstrip("."),
                    "chunk_index": i // max(chunk_size - chunk_overlap, 1),
                },
            })

    if not chunks:
        return {"status": "completed", "collection": collection, "documents": len(doc_files), "chunks": 0}

    # Embed and upsert
    import uuid
    from qdrant_client.models import PointStruct

    batch_size = 64
    all_vectors = []
    for i in range(0, len(chunks), batch_size):
        batch_texts = [c["text"] for c in chunks[i:i + batch_size]]
        vectors = embedder.encode(batch_texts)
        all_vectors.extend(vectors)

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={"text": chunk["text"], **chunk["metadata"]},
        )
        for chunk, vector in zip(chunks, all_vectors)
    ]

    for i in range(0, len(points), 100):
        await qdrant.upsert(collection_name=collection, points=points[i:i + 100])

    return {
        "status": "completed",
        "collection": collection,
        "documents": len(doc_files),
        "chunks": len(chunks),
    }


# ---------------------------------------------------------------------------
#  Task: reindex_collection
# ---------------------------------------------------------------------------


@celery_app.task(
    name="api.tasks.indexing_tasks.reindex_collection",
    bind=True,
    acks_late=True,
    ignore_result=False,
    priority=1,
)
def reindex_collection(self, collection: str) -> Dict[str, Any]:
    """
    Drop and rebuild a Qdrant collection from the knowledge directory.

    Args:
        collection: The Qdrant collection name to reindex.

    Returns:
        Summary dict with reindex results.
    """
    logger.info(
        "indexing.reindex_started",
        collection=collection,
        task_id=self.request.id,
    )

    try:
        result = _run_async(_do_reindex_collection(collection))
        logger.info("indexing.reindex_completed", **result)
        return result
    except Exception as exc:
        logger.error(
            "indexing.reindex_failed",
            collection=collection,
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc, max_retries=1)


async def _do_reindex_collection(collection: str) -> Dict[str, Any]:
    """Drop and recreate a collection, then re-index from knowledge dir."""
    from api.config import get_settings
    from api.dependencies import init_qdrant
    from qdrant_client.models import Distance, VectorParams

    settings = get_settings()
    qdrant = await init_qdrant(settings)

    # Drop collection if it exists
    try:
        await qdrant.delete_collection(collection_name=collection)
        logger.info("indexing.collection_dropped", collection=collection)
    except Exception:
        pass  # collection may not exist

    # Recreate
    await qdrant.create_collection(
        collection_name=collection,
        vectors_config=VectorParams(
            size=settings.rag.embedding_dimension,
            distance=Distance.COSINE,
        ),
    )

    # Re-run indexing with the knowledge directory
    knowledge_dir = str(Path(settings.rag.knowledge_dir))
    result = await _do_index_collection(collection, knowledge_dir)
    result["reindexed"] = True
    return result


# ---------------------------------------------------------------------------
#  Task: cleanup_old_migrations
# ---------------------------------------------------------------------------


@celery_app.task(
    name="api.tasks.indexing_tasks.cleanup_old_migrations",
    bind=True,
    acks_late=True,
    ignore_result=False,
    priority=0,
)
def cleanup_old_migrations(self, days: int = 30) -> Dict[str, Any]:
    """
    Soft-delete migration jobs older than *days* that are completed or failed.

    This periodic task keeps the database from growing unbounded while
    preserving recent runs and any still-active migrations.

    Args:
        days: Number of days after which completed/failed migrations are cleaned.

    Returns:
        Summary dict with count of cleaned-up records.
    """
    logger.info(
        "cleanup.started",
        days=days,
        task_id=self.request.id,
    )

    try:
        result = _run_async(_do_cleanup(days))
        logger.info("cleanup.completed", **result)
        return result
    except Exception as exc:
        logger.error(
            "cleanup.failed",
            error=str(exc),
            exc_info=True,
        )
        raise self.retry(exc=exc, max_retries=1)


async def _do_cleanup(days: int) -> Dict[str, Any]:
    """Core cleanup logic: soft-delete old completed/failed migrations."""
    from api.models.migration import MigrationJob, MigrationStatus

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    session = await _get_session()
    try:
        # Find old completed/failed migrations that haven't been soft-deleted
        result = await session.execute(
            select(MigrationJob).where(
                MigrationJob.created_at < cutoff,
                MigrationJob.status.in_([
                    MigrationStatus.COMPLETED,
                    MigrationStatus.FAILED,
                    MigrationStatus.CANCELLED,
                ]),
                MigrationJob.deleted_at.is_(None),
            )
        )
        jobs = result.scalars().all()

        count = 0
        for job in jobs:
            job.soft_delete()
            # Clear large JSONB fields to reclaim space
            job.output_files = {}
            job.agent_trace = {}
            count += 1

        await session.commit()

        # Also clean up Redis event logs
        import redis.asyncio as aioredis
        from api.config import get_settings
        settings = get_settings()
        redis = aioredis.from_url(settings.redis.url, decode_responses=True)
        try:
            for job in jobs:
                await redis.delete(f"migration:{job.id}:event_log")
                await redis.delete(f"migration:{job.id}:task_id")
        finally:
            await redis.close()

        return {
            "status": "completed",
            "cleaned_up": count,
            "cutoff_date": cutoff.isoformat(),
        }
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
