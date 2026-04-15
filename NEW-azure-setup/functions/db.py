"""
Database layer for Azure Functions — async PostgreSQL via asyncpg.

Provides:
  - Connection pool management (lazy init, graceful shutdown)
  - Auto-create tables on first run (no Alembic needed)
  - Full CRUD for migrations, builds, and users
  - Connection string resolved from Key Vault via managed identity
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg

logger = logging.getLogger("db")

# ---------------------------------------------------------------------------
#  Module-level pool (lazy singleton)
# ---------------------------------------------------------------------------

_pool: Optional[asyncpg.Pool] = None


async def _resolve_connection_string() -> str:
    """
    Resolve the PostgreSQL connection string.

    In production the string is fetched from Azure Key Vault via managed
    identity.  Locally it falls back to the POSTGRESQL_CONNECTION_STRING
    environment variable.
    """
    key_vault_uri = os.getenv("KEY_VAULT_URI", "")
    if key_vault_uri and os.getenv("ENVIRONMENT", "production") != "development":
        try:
            from azure.identity.aio import DefaultAzureCredential
            from azure.keyvault.secrets.aio import SecretClient

            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=key_vault_uri, credential=credential)
            try:
                secret = await client.get_secret("postgresql-connection-string")
                return secret.value
            finally:
                await client.close()
                await credential.close()
        except Exception as exc:
            logger.warning("keyvault.connection_string_fetch_failed: %s", exc)

    conn_str = os.getenv("POSTGRESQL_CONNECTION_STRING", "")
    if not conn_str:
        raise RuntimeError(
            "POSTGRESQL_CONNECTION_STRING is not set and Key Vault lookup failed."
        )
    return conn_str


def _parse_dsn(raw: str) -> dict:
    """
    Normalise the connection string into kwargs that asyncpg accepts.

    Supports both keyword=value format and postgresql:// URIs.
    Returns a dict of connection kwargs to avoid URL-encoding issues
    with special characters in passwords.
    """
    if raw.startswith("postgresql://") or raw.startswith("postgres://"):
        return {"dsn": raw}
    # keyword=value -> separate params (avoids URL-encoding password issues)
    parts = dict(token.split("=", 1) for token in raw.split() if "=" in token)
    return {
        "host": parts.get("host", "localhost"),
        "port": int(parts.get("port", "5432")),
        "database": parts.get("dbname", "migrator"),
        "user": parts.get("user", "migrator"),
        "password": parts.get("password", ""),
        "ssl": parts.get("sslmode", "require") in ("require", "verify-ca", "verify-full"),
    }


async def get_pool() -> asyncpg.Pool:
    """Return the module-level connection pool, creating it if needed."""
    global _pool
    if _pool is None or _pool._closed:
        raw = await _resolve_connection_string()
        conn_kwargs = _parse_dsn(raw)
        conn_kwargs.update({
            "min_size": 2,
            "max_size": 10,
            "command_timeout": 60,
            "server_settings": {"application_name": "mulesoft-migrator-functions"},
        })
        _pool = await asyncpg.create_pool(**conn_kwargs)
        logger.info("db.pool_created")
        await _ensure_tables()
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool."""
    global _pool
    if _pool and not _pool._closed:
        await _pool.close()
        _pool = None
        logger.info("db.pool_closed")


# ---------------------------------------------------------------------------
#  DDL — Auto-create tables
# ---------------------------------------------------------------------------

_DDL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgvector";

CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    azure_ad_oid    TEXT UNIQUE,
    email           TEXT NOT NULL,
    display_name    TEXT NOT NULL DEFAULT '',
    role            TEXT NOT NULL DEFAULT 'user',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS migrations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID REFERENCES users(id),
    project_name    TEXT NOT NULL,
    group_id        TEXT NOT NULL DEFAULT 'com.example',
    java_version    TEXT NOT NULL DEFAULT '17',
    status          TEXT NOT NULL DEFAULT 'queued',
    input_xml_files JSONB NOT NULL DEFAULT '[]',
    dataweave_scripts JSONB DEFAULT '{}',
    llm_config      JSONB DEFAULT '{}',
    output_files    JSONB DEFAULT '{}',
    agent_trace     JSONB DEFAULT '{}',
    summary         JSONB DEFAULT '{}',
    total_tokens_used BIGINT DEFAULT 0,
    total_cost_usd  DOUBLE PRECISION DEFAULT 0.0,
    duration_ms     BIGINT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS builds (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    migration_id    UUID NOT NULL REFERENCES migrations(id),
    build_tool      TEXT NOT NULL DEFAULT 'maven',
    status          TEXT NOT NULL DEFAULT 'pending',
    exit_code       INTEGER,
    build_log       TEXT DEFAULT '',
    duration_ms     BIGINT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS rag_documents (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,
    category        TEXT DEFAULT 'general',
    embedding       vector(3072),
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_migrations_status ON migrations(status);
CREATE INDEX IF NOT EXISTS idx_migrations_user ON migrations(user_id);
CREATE INDEX IF NOT EXISTS idx_migrations_deleted ON migrations(deleted_at);
CREATE INDEX IF NOT EXISTS idx_builds_migration ON builds(migration_id);
CREATE INDEX IF NOT EXISTS idx_users_oid ON users(azure_ad_oid);

CREATE TABLE IF NOT EXISTS validations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    migration_id    UUID NOT NULL REFERENCES migrations(id),
    user_id         UUID REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'pending',
    mode            TEXT NOT NULL DEFAULT 'auto',
    java_version    TEXT NOT NULL DEFAULT '17',
    keep_alive_min  INTEGER NOT NULL DEFAULT 15,
    aci_name        TEXT,
    aci_fqdn        TEXT,
    app_url         TEXT,
    acr_image_tag   TEXT,
    mulesoft_base_url TEXT,
    test_endpoints  JSONB DEFAULT '[]',
    comparison_mode TEXT DEFAULT 'server',
    test_results    JSONB DEFAULT '[]',
    user_verdict    TEXT,
    error           TEXT,
    deployed_at     TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    torn_down_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_validations_migration ON validations(migration_id);
CREATE INDEX IF NOT EXISTS idx_validations_status ON validations(status);
"""


async def _ensure_tables() -> None:
    """Create tables if they don't exist. Safe to call on every cold start."""
    pool = _pool
    if pool is None:
        return
    try:
        async with pool.acquire() as conn:
            # Run each statement separately so one failure doesn't block others
            for stmt in _DDL.split(";"):
                stmt = stmt.strip()
                if stmt:
                    try:
                        await conn.execute(stmt)
                    except Exception as stmt_exc:
                        logger.debug("db.stmt_skipped: %s", stmt_exc)
        logger.info("db.tables_ensured")
    except Exception as exc:
        logger.warning("db.ensure_tables_failed: %s", exc)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

_JSONB_FIELDS = {
    "input_xml_files", "dataweave_scripts", "llm_config",
    "output_files", "agent_trace", "summary", "metadata",
    "test_endpoints", "test_results",
}


def _row_to_dict(row: asyncpg.Record) -> dict[str, Any]:
    """Convert an asyncpg Record to a JSON-serialisable dict."""
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
        elif isinstance(v, uuid.UUID):
            d[k] = str(v)
        elif k in _JSONB_FIELDS and isinstance(v, str):
            try:
                d[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
#  Users CRUD
# ---------------------------------------------------------------------------

async def upsert_user(
    azure_ad_oid: str,
    email: str,
    display_name: str = "",
) -> dict[str, Any]:
    """Insert or update a user identified by Azure AD OID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO users (azure_ad_oid, email, display_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (azure_ad_oid) DO UPDATE
                SET email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    updated_at = NOW()
            RETURNING *
            """,
            azure_ad_oid, email, display_name,
        )
    return _row_to_dict(row)


async def get_user_by_oid(azure_ad_oid: str) -> Optional[dict[str, Any]]:
    """Fetch a user by their Azure AD object ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM users WHERE azure_ad_oid = $1", azure_ad_oid
        )
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
#  Migrations CRUD
# ---------------------------------------------------------------------------

async def create_migration(data: dict[str, Any], user_id: Optional[str] = None) -> dict[str, Any]:
    """Insert a new migration job and return its row."""
    pool = await get_pool()
    migration_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO migrations
                (id, user_id, project_name, group_id, java_version,
                 status, input_xml_files, dataweave_scripts, llm_config)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9::jsonb)
            RETURNING *
            """,
            uuid.UUID(migration_id),
            uuid.UUID(user_id) if user_id else None,
            data.get("project_name", "migrated-app"),
            data.get("group_id", "com.example"),
            data.get("java_version", "17"),
            "queued",
            json.dumps(data.get("input_xml_files", [])),
            json.dumps(data.get("dataweave_scripts", {})),
            json.dumps(data.get("llm_config", {})),
        )
    return _row_to_dict(row)


async def get_migration(migration_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single migration by ID (excluding soft-deleted)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM migrations WHERE id = $1 AND deleted_at IS NULL",
            uuid.UUID(migration_id),
        )
    return _row_to_dict(row) if row else None


async def list_migrations(
    page: int = 1,
    size: int = 20,
    status_filter: Optional[str] = None,
    user_id: Optional[str] = None,
) -> dict[str, Any]:
    """Return a paginated list of migration jobs."""
    pool = await get_pool()
    offset = (page - 1) * size

    where_clauses = ["deleted_at IS NULL"]
    params: list[Any] = []
    idx = 1

    if status_filter:
        where_clauses.append(f"status = ${idx}")
        params.append(status_filter)
        idx += 1

    if user_id:
        where_clauses.append(f"user_id = ${idx}")
        params.append(uuid.UUID(user_id))
        idx += 1

    where_sql = " AND ".join(where_clauses)

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM migrations WHERE {where_sql}", *params
        )
        rows = await conn.fetch(
            f"""
            SELECT id, user_id, project_name, group_id, java_version,
                   status, total_tokens_used, total_cost_usd, duration_ms,
                   started_at, completed_at, created_at, updated_at
            FROM migrations
            WHERE {where_sql}
            ORDER BY created_at DESC
            OFFSET ${idx} LIMIT ${idx + 1}
            """,
            *params, offset, size,
        )

    pages = max(1, (total + size - 1) // size)
    return {
        "items": [_row_to_dict(r) for r in rows],
        "total": total,
        "page": page,
        "size": size,
        "pages": pages,
    }


async def update_migration(migration_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    """
    Update specific columns on a migration row.

    ``updates`` keys must match column names. JSONB values are auto-serialised.
    """
    pool = await get_pool()
    if not updates:
        return await get_migration(migration_id)

    set_parts: list[str] = []
    params: list[Any] = []
    idx = 1

    for col, val in updates.items():
        if col in ("input_xml_files", "dataweave_scripts", "llm_config",
                    "output_files", "agent_trace", "summary"):
            set_parts.append(f"{col} = ${idx}::jsonb")
            params.append(json.dumps(val) if not isinstance(val, str) else val)
        else:
            set_parts.append(f"{col} = ${idx}")
            params.append(val)
        idx += 1

    set_parts.append(f"updated_at = ${idx}")
    params.append(_now())
    idx += 1

    params.append(uuid.UUID(migration_id))
    set_sql = ", ".join(set_parts)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE migrations SET {set_sql} WHERE id = ${idx} AND deleted_at IS NULL RETURNING *",
            *params,
        )
    return _row_to_dict(row) if row else None


async def soft_delete_migration(migration_id: str) -> bool:
    """Soft-delete a migration. Returns True if a row was updated."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE migrations SET deleted_at = NOW(), updated_at = NOW() WHERE id = $1 AND deleted_at IS NULL",
            uuid.UUID(migration_id),
        )
    return result == "UPDATE 1"


async def get_migration_stats(user_id: Optional[str] = None) -> dict[str, Any]:
    """Compute aggregate statistics across non-deleted migrations."""
    pool = await get_pool()
    where = "deleted_at IS NULL"
    params: list[Any] = []
    if user_id:
        where += " AND user_id = $1"
        params.append(uuid.UUID(user_id))

    async with pool.acquire() as conn:
        total = await conn.fetchval(
            f"SELECT COUNT(*) FROM migrations WHERE {where}", *params
        )
        status_rows = await conn.fetch(
            f"SELECT status, COUNT(*) as cnt FROM migrations WHERE {where} GROUP BY status",
            *params,
        )
        avg_dur = await conn.fetchval(
            f"SELECT AVG(duration_ms) FROM migrations WHERE {where} AND status = 'completed' AND duration_ms IS NOT NULL",
            *params,
        )
        totals = await conn.fetchrow(
            f"SELECT COALESCE(SUM(total_tokens_used), 0) as tokens, COALESCE(SUM(total_cost_usd), 0.0) as cost FROM migrations WHERE {where}",
            *params,
        )

    by_status = {row["status"]: row["cnt"] for row in status_rows}
    return {
        "total": total,
        "by_status": by_status,
        "avg_duration_ms": float(round(avg_dur, 2)) if avg_dur else None,
        "total_tokens_used": int(totals["tokens"]),
        "total_cost_usd": float(round(float(totals["cost"]), 4)),
    }


# ---------------------------------------------------------------------------
#  Builds CRUD
# ---------------------------------------------------------------------------

async def create_build(migration_id: str, build_tool: str = "maven") -> dict[str, Any]:
    """Create a new build job for a migration."""
    pool = await get_pool()
    build_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO builds (id, migration_id, build_tool, status)
            VALUES ($1, $2, $3, 'pending')
            RETURNING *
            """,
            uuid.UUID(build_id),
            uuid.UUID(migration_id),
            build_tool,
        )
    return _row_to_dict(row)


async def get_build(build_id: str) -> Optional[dict[str, Any]]:
    """Fetch a build job by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM builds WHERE id = $1",
            uuid.UUID(build_id),
        )
    return _row_to_dict(row) if row else None


async def update_build(build_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Update specific columns on a build row."""
    pool = await get_pool()
    if not updates:
        return await get_build(build_id)

    set_parts: list[str] = []
    params: list[Any] = []
    idx = 1
    for col, val in updates.items():
        set_parts.append(f"{col} = ${idx}")
        params.append(val)
        idx += 1

    params.append(uuid.UUID(build_id))
    set_sql = ", ".join(set_parts)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE builds SET {set_sql} WHERE id = ${idx} RETURNING *",
            *params,
        )
    return _row_to_dict(row) if row else None


# ---------------------------------------------------------------------------
#  Validations CRUD
# ---------------------------------------------------------------------------

async def create_validation(data: dict[str, Any], user_id: Optional[str] = None) -> dict[str, Any]:
    """Insert a new validation job and return its row."""
    pool = await get_pool()
    validation_id = str(uuid.uuid4())
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO validations
                (id, migration_id, user_id, status, mode, java_version,
                 keep_alive_min, mulesoft_base_url, test_endpoints, comparison_mode)
            VALUES ($1, $2, $3, 'pending', $4, $5, $6, $7, $8::jsonb, $9)
            RETURNING *
            """,
            uuid.UUID(validation_id),
            uuid.UUID(data["migration_id"]),
            uuid.UUID(user_id) if user_id else None,
            data.get("mode", "auto"),
            data.get("java_version", "17"),
            data.get("keep_alive_min", 15),
            data.get("mulesoft_base_url", ""),
            json.dumps(data.get("test_endpoints", [])),
            data.get("comparison_mode", "server"),
        )
    return _row_to_dict(row)


async def get_validation(validation_id: str) -> Optional[dict[str, Any]]:
    """Fetch a single validation by ID."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM validations WHERE id = $1",
            uuid.UUID(validation_id),
        )
    return _row_to_dict(row) if row else None


async def update_validation(validation_id: str, updates: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Update specific columns on a validation row."""
    pool = await get_pool()
    if not updates:
        return await get_validation(validation_id)

    set_parts: list[str] = []
    params: list[Any] = []
    idx = 1

    for col, val in updates.items():
        if col in ("test_endpoints", "test_results"):
            set_parts.append(f"{col} = ${idx}::jsonb")
            params.append(json.dumps(val) if not isinstance(val, str) else val)
        else:
            set_parts.append(f"{col} = ${idx}")
            params.append(val)
        idx += 1

    params.append(uuid.UUID(validation_id))
    set_sql = ", ".join(set_parts)

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"UPDATE validations SET {set_sql} WHERE id = ${idx} RETURNING *",
            *params,
        )
    return _row_to_dict(row) if row else None


async def list_validations_for_migration(migration_id: str) -> list[dict[str, Any]]:
    """Return all validations for a given migration, newest first."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM validations WHERE migration_id = $1 ORDER BY created_at DESC",
            uuid.UUID(migration_id),
        )
    return [_row_to_dict(r) for r in rows]
