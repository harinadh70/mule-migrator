"""
RAG Service — semantic search over migration pattern knowledge base.

Uses GitHub Copilot (Models API) for embeddings (text-embedding-3-large, 3072 dims)
and PostgreSQL with pgvector for vector storage and similarity search.

The GitHub Models API is OpenAI-compatible and uses a GitHub Personal Access Token.
Endpoint: https://models.inference.ai.azure.com
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Optional

logger = logging.getLogger("rag_service")

# ---------------------------------------------------------------------------
#  GitHub Copilot (Models API) embedding client (lazy singleton)
# ---------------------------------------------------------------------------

_openai_client = None

# GitHub Models API endpoint
GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"


def _get_openai_client():
    """
    Return an OpenAI-compatible client pointed at GitHub Models API.

    Uses GITHUB_TOKEN (Personal Access Token) for authentication.
    Falls back to Azure OpenAI if AZURE_OPENAI_ENDPOINT is set (backward compat).
    """
    global _openai_client
    if _openai_client is not None:
        return _openai_client

    from openai import OpenAI

    github_token = os.getenv("GITHUB_TOKEN", "")

    if github_token:
        # Primary: GitHub Copilot (Models API)
        _openai_client = OpenAI(
            base_url=GITHUB_MODELS_ENDPOINT,
            api_key=github_token,
        )
        logger.info("rag_service.client_initialized: provider=github_copilot")
    else:
        # Fallback: Azure OpenAI (backward compatibility)
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        api_key = os.getenv("AZURE_OPENAI_API_KEY", os.getenv("AZURE_OPENAI_KEY", ""))
        if azure_endpoint and api_key:
            from openai import AzureOpenAI
            _openai_client = AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_key=api_key,
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-14"),
            )
            logger.info("rag_service.client_initialized: provider=azure_openai (fallback)")
        else:
            raise RuntimeError(
                "No AI provider configured. Set GITHUB_TOKEN for GitHub Copilot "
                "or AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_API_KEY for Azure OpenAI."
            )

    return _openai_client


# ---------------------------------------------------------------------------
#  Embedding generation
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")
EMBEDDING_DIMENSION = 3072


def generate_embedding(text: str) -> list[float]:
    """Generate an embedding vector for the given text using GitHub Copilot."""
    client = _get_openai_client()
    response = client.embeddings.create(
        input=text,
        model=EMBEDDING_MODEL,
    )
    return response.data[0].embedding


# ---------------------------------------------------------------------------
#  Document indexing
# ---------------------------------------------------------------------------

async def index_document(
    title: str,
    content: str,
    category: str = "general",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Index a document: generate its embedding and store in PostgreSQL
    with pgvector.
    """
    from db import get_pool

    embedding = generate_embedding(content)
    doc_id = str(uuid.uuid4())
    meta_json = json.dumps(metadata or {})

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO rag_documents (id, title, content, category, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5::vector, $6::jsonb)
            RETURNING id, title, category, created_at
            """,
            uuid.UUID(doc_id),
            title,
            content,
            category,
            str(embedding),
            meta_json,
        )

    logger.info("rag.document_indexed: id=%s title=%s", doc_id, title)
    return {
        "id": str(row["id"]),
        "title": row["title"],
        "category": row["category"],
        "created_at": row["created_at"].isoformat(),
    }


# ---------------------------------------------------------------------------
#  Semantic search
# ---------------------------------------------------------------------------

async def search(
    query: str,
    top_k: int = 5,
    score_threshold: float = 0.35,
    category: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Perform semantic search over the knowledge base.

    Args:
        query:            Natural-language search query.
        top_k:            Maximum number of results.
        score_threshold:  Minimum cosine similarity score (0..1).
        category:         Optional category filter.

    Returns:
        List of matching documents with similarity scores.
    """
    from db import get_pool

    query_embedding = generate_embedding(query)
    embedding_str = str(query_embedding)

    pool = await get_pool()

    where_clause = ""
    params: list[Any] = [embedding_str, top_k]
    if category:
        where_clause = "AND category = $3"
        params.append(category)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT
                id, title, content, category, metadata, created_at,
                1 - (embedding <=> $1::vector) AS similarity
            FROM rag_documents
            WHERE 1=1 {where_clause}
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            *params,
        )

    results = []
    for row in rows:
        sim = float(row["similarity"])
        if sim < score_threshold:
            continue
        results.append({
            "id": str(row["id"]),
            "title": row["title"],
            "content": row["content"][:2000],  # truncate for response
            "category": row["category"],
            "similarity": round(sim, 4),
            "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
            "created_at": row["created_at"].isoformat(),
        })

    logger.info("rag.search: query_len=%d results=%d", len(query), len(results))
    return results


# ---------------------------------------------------------------------------
#  Batch indexing for knowledge base bootstrap
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
#  Migration-context retrieval (used by engine.py)
# ---------------------------------------------------------------------------

# Patterns we look for in MuleSoft XML to build targeted RAG queries.
_XML_PATTERN_QUERIES: list[tuple[str, str]] = [
    ("http:listener",       "MuleSoft HTTP Listener to Spring Boot RestController mapping"),
    ("http:request",        "MuleSoft HTTP Request to Spring Boot RestTemplate WebClient"),
    ("db:select",           "MuleSoft database select to Spring Boot JdbcTemplate JPA query"),
    ("db:insert",           "MuleSoft database insert to Spring Boot JdbcTemplate JPA save"),
    ("db:update",           "MuleSoft database update to Spring Boot JdbcTemplate JPA"),
    ("db:delete",           "MuleSoft database delete to Spring Boot JdbcTemplate JPA"),
    ("db:stored-procedure", "MuleSoft stored procedure to Spring Boot JPA Procedure JdbcTemplate call"),
    ("on-error-propagate",  "MuleSoft on-error-propagate to Spring Boot ExceptionHandler throw"),
    ("on-error-continue",   "MuleSoft on-error-continue to Spring Boot try catch logging"),
    ("error-handler",       "MuleSoft error handler to Spring Boot ControllerAdvice"),
    ("vm:publish",          "MuleSoft VM connector to Spring Events EventListener"),
    ("vm:listener",         "MuleSoft VM connector to Spring Events EventListener"),
    ("jms:",                "MuleSoft JMS connector to Spring Boot JmsListener JmsTemplate"),
    ("amqp:",               "MuleSoft AMQP connector to Spring Boot RabbitListener RabbitTemplate"),
    ("file:",               "MuleSoft File connector to Java NIO WatchService"),
    ("sftp:",               "MuleSoft SFTP connector to Spring Integration Apache Commons Net"),
    ("ftp:",                "MuleSoft FTP connector to Spring Integration Apache Commons Net"),
    ("%dw",                 "DataWeave transformation to Java Stream map filter reduce"),
    ("map {",               "DataWeave map to Java Stream map transformation"),
    ("filter ",             "DataWeave filter to Java Stream filter"),
    ("reduce ",             "DataWeave reduce to Java Stream reduce"),
    ("groupBy",             "DataWeave groupBy to Java Collectors groupingBy"),
    ("upper(",              "DataWeave string functions to Java String methods"),
    ("lower(",              "DataWeave string functions to Java String methods"),
    ("++",                  "DataWeave concatenation to Java String or List operations"),
]


async def get_migration_context(xml_content: str, top_k: int = 5) -> str:
    """
    Analyse MuleSoft XML content, query the RAG knowledge base for relevant
    migration patterns, and return a formatted context string suitable for
    inclusion in an LLM prompt.

    Args:
        xml_content: Raw MuleSoft XML (may include DataWeave blocks).
        top_k:       Maximum results per sub-query.

    Returns:
        A formatted string with relevant migration patterns. Returns an
        empty string if no relevant patterns are found or if RAG is
        unavailable.
    """
    # 1. Detect which patterns are present in the XML
    detected_queries: list[str] = []
    xml_lower = xml_content.lower()
    for marker, query_text in _XML_PATTERN_QUERIES:
        if marker.lower() in xml_lower:
            detected_queries.append(query_text)

    # Always include best-practices context
    detected_queries.append("Spring Boot project structure best practices")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_queries: list[str] = []
    for q in detected_queries:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)

    if not unique_queries:
        return ""

    # 2. Run RAG searches (limit total to avoid overly long prompts)
    all_results: list[dict] = []
    seen_ids: set[str] = set()

    for query_text in unique_queries[:8]:  # cap sub-queries
        try:
            results = await search(
                query=query_text,
                top_k=top_k,
                score_threshold=0.55,  # slightly lower threshold for broader recall
            )
            for r in results:
                if r["id"] not in seen_ids:
                    seen_ids.add(r["id"])
                    all_results.append(r)
        except Exception as exc:
            logger.warning("rag.migration_context_query_failed: %s — %s", query_text, exc)

    if not all_results:
        return ""

    # 3. Sort by similarity and take the top results
    all_results.sort(key=lambda r: r["similarity"], reverse=True)
    top_results = all_results[:10]  # cap total context docs

    # 4. Format for LLM consumption
    sections: list[str] = []
    for i, r in enumerate(top_results, 1):
        sections.append(
            f"### Pattern {i}: {r['title']} (similarity: {r['similarity']:.2f})\n"
            f"{r['content']}"
        )

    context = (
        "=== RAG Knowledge Base — Relevant Migration Patterns ===\n\n"
        + "\n\n---\n\n".join(sections)
        + "\n\n=== End of RAG Context ==="
    )
    logger.info(
        "rag.migration_context: queries=%d results=%d chars=%d",
        len(unique_queries), len(top_results), len(context),
    )
    return context


async def index_batch(
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Index multiple documents at once.

    Each document should have: title, content, and optionally category
    and metadata.

    Returns summary with indexed count and any errors.
    """
    indexed = 0
    errors = []

    for doc in documents:
        try:
            await index_document(
                title=doc["title"],
                content=doc["content"],
                category=doc.get("category", "general"),
                metadata=doc.get("metadata"),
            )
            indexed += 1
        except Exception as exc:
            errors.append({"title": doc.get("title", "?"), "error": str(exc)})

    return {
        "indexed": indexed,
        "errors": errors,
        "total_submitted": len(documents),
    }
