"""
Azure Functions app — MuleSoft-to-SpringBoot Migrator.

Python v2 programming model.  All HTTP triggers and Queue triggers are
registered on a single ``FunctionApp`` instance.

HTTP Triggers:
  POST   /api/v2/migrations          Create migration (enqueue)
  GET    /api/v2/migrations           List migrations (paginated)
  GET    /api/v2/migrations/{id}      Get migration detail
  GET    /api/v2/migrations/{id}/files          Get generated files
  GET    /api/v2/migrations/{id}/files/{path}   Get single file
  DELETE /api/v2/migrations/{id}      Soft delete
  POST   /api/v2/migrations/{id}/cancel         Cancel
  GET    /api/v2/migrations/stats     Aggregate stats
  POST   /api/v2/builds              Trigger build (enqueue)
  GET    /api/v2/builds/{id}         Build status
  POST   /api/v2/rag/search          RAG semantic search
  POST   /api/v2/rag/seed            Seed RAG knowledge base (admin only)
  GET    /api/v2/rag/collections     List RAG collections (all users)
  GET    /api/v2/rag/documents       List RAG documents (all users)
  POST   /api/v2/rag/documents       Add RAG document (admin only)
  DELETE /api/v2/rag/documents/{id}  Delete RAG document (admin + password)
  DELETE /api/v2/rag/collections/{n} Delete RAG collection (admin + password)
  GET    /api/v2/auth/me             Get current user info + role
  POST   /api/v2/github/push         Push files to GitHub
  GET    /api/health                 Health check

Queue Triggers:
  migration-queue     Run static engine + optional LLM agents
  build-queue         Run Maven build
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone

import azure.functions as func

# ---------------------------------------------------------------------------
#  Bootstrap
# ---------------------------------------------------------------------------

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

logger = logging.getLogger("function_app")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _cors_headers() -> dict[str, str]:
    """Return standard CORS headers."""
    return {
        "Access-Control-Allow-Origin": CORS_ORIGINS,
        "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, x-ms-client-principal",
        "Access-Control-Max-Age": "86400",
    }


def _json_response(
    body: dict | list,
    status_code: int = 200,
    headers: dict[str, str] | None = None,
) -> func.HttpResponse:
    """Build a JSON HTTP response with CORS headers."""
    hdrs = _cors_headers()
    if headers:
        hdrs.update(headers)
    return func.HttpResponse(
        body=json.dumps(body, default=str),
        status_code=status_code,
        mimetype="application/json",
        headers=hdrs,
    )


def _error_response(
    detail: str,
    status_code: int = 400,
    error_code: str = "BAD_REQUEST",
) -> func.HttpResponse:
    return _json_response(
        {"error": error_code, "detail": detail},
        status_code=status_code,
    )


def _get_headers(req: func.HttpRequest) -> dict[str, str]:
    """Extract request headers as a plain dict."""
    return {k.lower(): v for k, v in req.headers.items()}


def _enqueue_message(queue_name: str, message: dict) -> None:
    """
    Send a message to an Azure Storage Queue.

    Uses the AzureWebJobsStorage connection string.
    """
    from azure.storage.queue import QueueClient
    import base64

    conn_str = os.getenv("AzureWebJobsStorage", "UseDevelopmentStorage=true")
    client = QueueClient.from_connection_string(conn_str, queue_name)
    try:
        client.create_queue()
    except Exception:
        pass  # queue already exists
    encoded = base64.b64encode(json.dumps(message).encode()).decode()
    client.send_message(encoded)


def _get_user_from_header(req: func.HttpRequest) -> dict:
    """
    Extract user info from the x-ms-client-principal header.
    Returns a dict with 'email', 'name', 'roles', 'oid'.
    """
    import base64 as b64mod

    principal_header = req.headers.get("x-ms-client-principal", "")
    if not principal_header:
        # Development fallback
        if os.getenv("ENVIRONMENT", "production") == "development":
            return {
                "email": "dev@localhost",
                "name": "Development User",
                "roles": ["admin"],
                "oid": "dev-user",
            }
        return {"email": "", "name": "", "roles": ["user"], "oid": ""}

    try:
        decoded = b64mod.b64decode(principal_header)
        principal = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return {"email": "", "name": "", "roles": ["user"], "oid": ""}

    claims = {}
    for claim in principal.get("claims", []):
        typ = claim.get("typ", "")
        val = claim.get("val", "")
        claims[typ] = val

    email = (
        claims.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress")
        or claims.get("preferred_username")
        or claims.get("email")
        or ""
    )
    name = (
        claims.get("name")
        or claims.get("http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name")
        or ""
    )
    oid = (
        claims.get("http://schemas.microsoft.com/identity/claims/objectidentifier")
        or claims.get("oid")
        or principal.get("userId", "")
    )
    roles = principal.get("roles", [])
    if not roles:
        role_claim = claims.get(
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/role", ""
        )
        if role_claim:
            roles = [r.strip() for r in role_claim.split(",")]
        else:
            roles = ["user"]

    return {"email": email, "name": name, "roles": roles, "oid": oid}


def _is_admin(req: func.HttpRequest) -> bool:
    """
    Check if the current request is from an admin user.
    Admin if email matches ADMIN_EMAIL env var or Azure AD roles contain 'admin'.
    """
    admin_email = os.environ.get("ADMIN_EMAIL", "HARINADH70@outlook.com")
    user = _get_user_from_header(req)
    return (
        user.get("email", "").lower() == admin_email.lower()
        or "admin" in user.get("roles", [])
    )


def _verify_admin_password(req: func.HttpRequest) -> tuple[bool, str]:
    """
    Verify the admin password from the request body.
    Returns (success: bool, error_message: str).
    The ADMIN_PASSWORD env var should contain a bcrypt hash.
    """
    try:
        body = req.get_json()
    except (ValueError, AttributeError):
        return False, "Request body must be JSON with a 'password' field."

    password = body.get("password", "")
    if not password:
        return False, "Password is required for this action."

    stored_hash = os.environ.get("ADMIN_PASSWORD", "")
    if not stored_hash:
        logger.error("admin_password.not_configured: ADMIN_PASSWORD env var not set")
        return False, "Admin password not configured on server."

    try:
        import bcrypt
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return True, ""
        else:
            return False, "Incorrect password"
    except ImportError:
        # Fallback: plain-text comparison (not recommended for production)
        logger.warning("admin_password.bcrypt_not_available: falling back to plain comparison")
        if password == stored_hash:
            return True, ""
        return False, "Incorrect password"
    except Exception as exc:
        logger.error("admin_password.verification_error: %s", exc)
        return False, "Incorrect password"


# ═══════════════════════════════════════════════════════════════════════════
#  AUTH — Current User Info
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/auth/me", methods=["GET"])
async def auth_me(req: func.HttpRequest) -> func.HttpResponse:
    """Return current user information and role."""
    user = _get_user_from_header(req)
    admin_email = os.environ.get("ADMIN_EMAIL", "HARINADH70@outlook.com")

    is_admin = (
        user.get("email", "").lower() == admin_email.lower()
        or "admin" in user.get("roles", [])
    )

    return _json_response({
        "email": user.get("email", ""),
        "name": user.get("name", ""),
        "role": "admin" if is_admin else "user",
        "is_admin": is_admin,
    })


# ═══════════════════════════════════════════════════════════════════════════
#  HEALTH
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="health", methods=["GET"])
async def health(req: func.HttpRequest) -> func.HttpResponse:
    """Liveness probe."""
    import db as database

    checks = {}
    overall = True

    try:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
        overall = False

    return _json_response({
        "status": "ok" if overall else "degraded",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }, status_code=200 if overall else 503)


# ═══════════════════════════════════════════════════════════════════════════
#  MIGRATIONS — Create
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/migrations", methods=["POST"])
async def create_migration(req: func.HttpRequest) -> func.HttpResponse:
    """Create a new migration job and enqueue it for processing."""
    from security import require_auth, validate_xml_files, check_rate_limit
    import db as database

    headers = _get_headers(req)

    # Authenticate
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    # Rate limit
    allowed, rate_info = check_rate_limit(user.oid, max_requests=30, window_seconds=60)
    if not allowed:
        return _json_response(
            {"error": "RATE_LIMITED", "detail": "Too many requests.", **rate_info},
            status_code=429,
            headers={"Retry-After": str(rate_info.get("reset_at", 60) - int(time.time()))},
        )

    # Parse body
    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Invalid JSON body.")

    # Normalise field names (camelCase or snake_case)
    project_name = body.get("project_name") or body.get("projectName")
    if not project_name:
        return _error_response("project_name is required.")

    xml_files = body.get("input_xml_files") or body.get("muleXmlFiles") or []
    single_xml = body.get("mule_xml") or body.get("muleXml") or ""
    if not xml_files and single_xml.strip():
        xml_files = [{"name": "main.xml", "content": single_xml}]
    if not xml_files:
        return _error_response("At least one MuleSoft XML file is required.")

    # Validate XML (XXE prevention)
    try:
        xml_files = validate_xml_files(xml_files)
    except ValueError as exc:
        return _error_response(str(exc))

    # Upsert user
    db_user = await database.upsert_user(user.oid, user.email, user.name)

    # Create migration row
    migration_data = {
        "project_name": project_name,
        "group_id": body.get("group_id") or body.get("groupId") or "com.example",
        "java_version": body.get("java_version") or body.get("javaVersion") or "17",
        "input_xml_files": xml_files,
        "dataweave_scripts": body.get("dataweave_scripts") or body.get("dataweaveScripts") or {},
        "llm_config": body.get("llm_config") or body.get("llmConfig") or {},
    }
    migration = await database.create_migration(migration_data, user_id=db_user["id"])

    # Enqueue for background processing
    _enqueue_message("migration-queue", {
        "migration_id": migration["id"],
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.info("migration.created: id=%s project=%s", migration["id"], project_name)

    return _json_response(migration, status_code=202)


# ═══════════════════════════════════════════════════════════════════════════
#  MIGRATIONS — List
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/migrations", methods=["GET"])
async def list_migrations(req: func.HttpRequest) -> func.HttpResponse:
    """List migrations with pagination."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    page = int(req.params.get("page", "1"))
    size = min(int(req.params.get("size", "20")), 100)
    status_filter = req.params.get("status")

    result = await database.list_migrations(
        page=page,
        size=size,
        status_filter=status_filter,
        user_id=None,  # admins see all; filter by user_id for non-admins
    )

    return _json_response(result)


# ═══════════════════════════════════════════════════════════════════════════
#  MIGRATIONS — Stats (must be before /{id} route)
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/stats/migrations", methods=["GET"])
async def migration_stats(req: func.HttpRequest) -> func.HttpResponse:
    """Return aggregate migration statistics."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    stats = await database.get_migration_stats()
    return _json_response(stats)


# ═══════════════════════════════════════════════════════════════════════════
#  MIGRATIONS — Get single
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/migrations/{migration_id}", methods=["GET"])
async def get_migration(req: func.HttpRequest) -> func.HttpResponse:
    """Get a single migration by ID."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    migration_id = req.route_params.get("migration_id", "")
    # Validate UUID format
    try:
        uuid.UUID(migration_id)
    except (ValueError, AttributeError):
        return _error_response(f"Invalid migration ID: {migration_id}", 400, "BAD_REQUEST")
    migration = await database.get_migration(migration_id)
    if not migration:
        return _error_response("Migration not found.", 404, "NOT_FOUND")

    return _json_response(migration)


# ═══════════════════════════════════════════════════════════════════════════
#  MIGRATIONS — Get files
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/migrations/{migration_id}/files", methods=["GET"])
async def get_migration_files(req: func.HttpRequest) -> func.HttpResponse:
    """Get all generated files for a migration."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    migration_id = req.route_params.get("migration_id", "")
    migration = await database.get_migration(migration_id)
    if not migration:
        return _error_response("Migration not found.", 404, "NOT_FOUND")

    output_files = migration.get("output_files") or "{}"
    if isinstance(output_files, str):
        output_files = json.loads(output_files)
    if not output_files:
        return _error_response(
            "No output files available. Migration may still be in progress.",
            409, "NO_OUTPUT",
        )

    # Return {path: content} format that the frontend expects
    return _json_response({
        "migration_id": migration_id,
        "total_files": len(output_files),
        "files": output_files,
    })


# ═══════════════════════════════════════════════════════════════════════════
#  MIGRATIONS — Get single file
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/migrations/{migration_id}/files/{file_path}", methods=["GET"])
async def get_migration_file(req: func.HttpRequest) -> func.HttpResponse:
    """Get a single generated file by path."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    migration_id = req.route_params.get("migration_id", "")
    file_path = req.route_params.get("file_path", "")

    migration = await database.get_migration(migration_id)
    if not migration:
        return _error_response("Migration not found.", 404, "NOT_FOUND")

    output_files = migration.get("output_files") or {}
    content = output_files.get(file_path)
    if content is None:
        return _error_response(f"File '{file_path}' not found.", 404, "NOT_FOUND")

    # Determine content type
    if file_path.endswith(".java"):
        mimetype = "text/x-java-source"
    elif file_path.endswith(".xml"):
        mimetype = "application/xml"
    elif file_path.endswith((".yml", ".yaml")):
        mimetype = "text/yaml"
    elif file_path.endswith(".properties"):
        mimetype = "text/plain"
    else:
        mimetype = "text/plain"

    return func.HttpResponse(
        body=content,
        status_code=200,
        mimetype=mimetype,
        headers=_cors_headers(),
    )


# ═══════════════════════════════════════════════════════════════════════════
#  MIGRATIONS — Delete (soft)
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/migrations/{migration_id}", methods=["DELETE"])
async def delete_migration(req: func.HttpRequest) -> func.HttpResponse:
    """Soft-delete a migration."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    migration_id = req.route_params.get("migration_id", "")
    deleted = await database.soft_delete_migration(migration_id)
    if not deleted:
        return _error_response("Migration not found.", 404, "NOT_FOUND")

    return _json_response({"status": "deleted", "migration_id": migration_id})


# ═══════════════════════════════════════════════════════════════════════════
#  MIGRATIONS — Cancel
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/migrations/{migration_id}/cancel", methods=["POST"])
async def cancel_migration(req: func.HttpRequest) -> func.HttpResponse:
    """Cancel a running or queued migration."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    migration_id = req.route_params.get("migration_id", "")
    migration = await database.get_migration(migration_id)
    if not migration:
        return _error_response("Migration not found.", 404, "NOT_FOUND")

    if migration["status"] not in ("queued", "pending", "running"):
        return _error_response(
            f"Cannot cancel migration in '{migration['status']}' state.",
            409, "INVALID_STATE",
        )

    now = datetime.now(timezone.utc)
    updates = {
        "status": "cancelled",
        "completed_at": now,
    }
    if migration.get("started_at"):
        started = migration["started_at"]
        if isinstance(started, str):
            started = datetime.fromisoformat(started)
        delta = now - started
        updates["duration_ms"] = int(delta.total_seconds() * 1000)

    await database.update_migration(migration_id, updates)

    return _json_response({"status": "cancelled", "migration_id": migration_id})


# ═══════════════════════════════════════════════════════════════════════════
#  BUILDS — Create
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/builds", methods=["POST"])
async def create_build(req: func.HttpRequest) -> func.HttpResponse:
    """Trigger a Maven build for a completed migration."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Invalid JSON body.")

    migration_id = body.get("migration_id") or body.get("migrationId")
    if not migration_id:
        return _error_response("migration_id is required.")

    # Validate migration exists and has output
    migration = await database.get_migration(migration_id)
    if not migration:
        return _error_response("Migration not found.", 404, "NOT_FOUND")

    output_files = migration.get("output_files") or {}
    if not output_files:
        return _error_response(
            "Migration has no output files. Wait for migration to complete.",
            409, "NO_OUTPUT",
        )

    build_tool = body.get("build_tool", "maven")
    build = await database.create_build(migration_id, build_tool)

    # Enqueue
    _enqueue_message("build-queue", {
        "build_id": build["id"],
        "migration_id": migration_id,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    })

    logger.info("build.created: id=%s migration=%s", build["id"], migration_id)

    return _json_response(build, status_code=202)


# ═══════════════════════════════════════════════════════════════════════════
#  BUILDS — Get status
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/builds/{build_id}", methods=["GET"])
async def get_build(req: func.HttpRequest) -> func.HttpResponse:
    """Get build status by ID."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    build_id = req.route_params.get("build_id", "")
    build = await database.get_build(build_id)
    if not build:
        return _error_response("Build not found.", 404, "NOT_FOUND")

    return _json_response(build)


# ═══════════════════════════════════════════════════════════════════════════
#  RAG — Search
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/rag/search", methods=["POST"])
async def rag_search(req: func.HttpRequest) -> func.HttpResponse:
    """Semantic search over migration knowledge base."""
    from security import require_auth
    import rag_service

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Invalid JSON body.")

    query = body.get("query", "").strip()
    if not query:
        return _error_response("query is required.")

    top_k = min(int(body.get("top_k", 5)), 20)
    score_threshold = float(body.get("score_threshold", 0.65))
    category = body.get("category")

    try:
        results = await rag_service.search(
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            category=category,
        )
    except Exception as exc:
        logger.error("rag.search_failed: %s", exc, exc_info=True)
        return _error_response(f"RAG search failed: {exc}", 500, "RAG_ERROR")

    return _json_response({
        "query": query,
        "results": results,
        "total": len(results),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  RAG — Seed Knowledge Base
# ═══════════════════════════════════════════════════════════════════════════
#  RAG — Collections (Knowledge Base overview)
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/rag/collections", methods=["GET"])
async def rag_collections(req: func.HttpRequest) -> func.HttpResponse:
    """Get RAG knowledge base collections overview."""
    import db as database

    try:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            # Get category stats
            rows = await conn.fetch("""
                SELECT category, COUNT(*) as doc_count,
                       MAX(created_at) as last_updated
                FROM rag_documents
                GROUP BY category
                ORDER BY category
            """)
            total = await conn.fetchval("SELECT COUNT(*) FROM rag_documents")

        collections = [
            {
                "name": row["category"],
                "documentCount": row["doc_count"],
                "document_count": row["doc_count"],
                "lastUpdated": row["last_updated"].isoformat() if row["last_updated"] else None,
                "status": "active",
            }
            for row in rows
        ]

        return _json_response({
            "collections": collections,
            "total_documents": total,
            "status": "active",
        })
    except Exception as exc:
        return _json_response({
            "collections": [],
            "total_documents": 0,
            "status": "error",
            "error": str(exc),
        })


@app.route(route="api/v2/rag/documents", methods=["GET"])
async def rag_documents(req: func.HttpRequest) -> func.HttpResponse:
    """List RAG documents with pagination, optionally filtered by category."""
    import db as database

    category = req.params.get("category", "")
    limit = min(int(req.params.get("limit", "20")), 50)
    offset = int(req.params.get("offset", "0"))
    summary = req.params.get("summary", "false") == "true"

    try:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            # Get total count
            if category:
                total_row = await conn.fetchrow(
                    "SELECT COUNT(*) as cnt FROM rag_documents WHERE category = $1", category
                )
                rows = await conn.fetch(
                    "SELECT id, title, content, category, created_at FROM rag_documents WHERE category = $1 ORDER BY title LIMIT $2 OFFSET $3",
                    category, limit, offset,
                )
            else:
                total_row = await conn.fetchrow("SELECT COUNT(*) as cnt FROM rag_documents")
                rows = await conn.fetch(
                    "SELECT id, title, content, category, created_at FROM rag_documents ORDER BY category, title LIMIT $1 OFFSET $2",
                    limit, offset,
                )

            total = total_row["cnt"] if total_row else 0

        docs = []
        for row in rows:
            doc = {
                "id": str(row["id"]),
                "title": row["title"],
                "content": row["content"][:200] + ("..." if len(row["content"]) > 200 else ""),
                "category": row["category"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
            if not summary:
                doc["full_content"] = row["content"]
            docs.append(doc)

        return _json_response({"documents": docs, "total": total})
    except Exception as exc:
        return _json_response({"documents": [], "total": 0, "error": str(exc)})


@app.route(route="api/v2/rag/seed", methods=["POST"])
async def rag_seed(req: func.HttpRequest) -> func.HttpResponse:
    """Seed the RAG knowledge base with MuleSoft->Spring Boot migration patterns. Admin only."""
    from security import require_auth
    import seed_knowledge

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    # Admin check
    if not _is_admin(req):
        return _error_response(
            "Admin access required to seed the knowledge base.",
            403,
            "FORBIDDEN",
        )

    # Parse optional body
    clear_existing = False
    try:
        body = req.get_json()
        clear_existing = body.get("clear_existing", False)
    except (ValueError, AttributeError):
        pass  # No body or invalid JSON — use defaults

    try:
        logger.info("rag.seed_started: clear_existing=%s user=%s", clear_existing, user.email)
        result = await seed_knowledge.seed_all(clear_existing=clear_existing)
        logger.info("rag.seed_completed: indexed=%d errors=%d", result["indexed"], len(result["errors"]))
    except Exception as exc:
        logger.error("rag.seed_failed: %s", exc, exc_info=True)
        return _error_response(f"Knowledge base seeding failed: {exc}", 500, "SEED_ERROR")

    return _json_response(result, status_code=200 if result["status"] == "completed" else 207)


# ═══════════════════════════════════════════════════════════════════════════
#  RAG — Add Document (admin only)
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/rag/documents", methods=["POST"])
async def rag_add_document(req: func.HttpRequest) -> func.HttpResponse:
    """Add a document to the RAG knowledge base. Admin only."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    if not _is_admin(req):
        return _error_response(
            "Admin access required to add documents.",
            403,
            "FORBIDDEN",
        )

    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Invalid JSON body.")

    title = body.get("title", "").strip()
    content = body.get("content", "").strip()
    category = body.get("category", "general").strip()

    if not title or not content:
        return _error_response("title and content are required.")

    try:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO rag_documents (title, content, category, created_at)
                   VALUES ($1, $2, $3, NOW())
                   RETURNING id, title, category, created_at""",
                title,
                content,
                category,
            )

        return _json_response(
            {
                "id": str(row["id"]),
                "title": row["title"],
                "category": row["category"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            },
            status_code=201,
        )
    except Exception as exc:
        logger.error("rag.add_document_failed: %s", exc, exc_info=True)
        return _error_response(f"Failed to add document: {exc}", 500, "RAG_ERROR")


# ═══════════════════════════════════════════════════════════════════════════
#  RAG — Get Single Document
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/rag/documents/{doc_id}", methods=["GET"])
async def rag_document_detail(req: func.HttpRequest) -> func.HttpResponse:
    """Get a single RAG document by ID with full content."""
    import db as database

    doc_id = req.route_params.get("doc_id", "")
    try:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, title, content, category, created_at FROM rag_documents WHERE id = $1::uuid",
                doc_id,
            )
        if not row:
            return _error_response("Document not found", 404, "NOT_FOUND")
        return _json_response({
            "id": str(row["id"]),
            "title": row["title"],
            "content": row["content"][:200] + ("..." if len(row["content"]) > 200 else ""),
            "full_content": row["content"],
            "category": row["category"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        })
    except Exception as exc:
        return _error_response(f"Failed to get document: {exc}", 500, "RAG_ERROR")

# ═══════════════════════════════════════════════════════════════════════════
#  RAG — Delete Document (admin + password)
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/rag/documents/{doc_id}", methods=["DELETE"])
async def rag_delete_document(req: func.HttpRequest) -> func.HttpResponse:
    """Delete a RAG document. Admin only, requires password verification."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    if not _is_admin(req):
        return _error_response(
            "Admin access required to delete documents.",
            403,
            "FORBIDDEN",
        )

    # Verify password
    pw_ok, pw_err = _verify_admin_password(req)
    if not pw_ok:
        return _error_response(pw_err, 403, "FORBIDDEN")

    doc_id = req.route_params.get("doc_id", "")

    try:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            # Delete embeddings first (if any)
            await conn.execute(
                "DELETE FROM rag_embeddings WHERE document_id = $1", doc_id
            )
            result = await conn.execute(
                "DELETE FROM rag_documents WHERE id = $1", doc_id
            )
            if result == "DELETE 0":
                return _error_response("Document not found.", 404, "NOT_FOUND")

        logger.info("rag.document_deleted: id=%s by=%s", doc_id, user.email)
        return _json_response({"status": "deleted", "document_id": doc_id})
    except Exception as exc:
        logger.error("rag.delete_document_failed: %s", exc, exc_info=True)
        return _error_response(f"Failed to delete document: {exc}", 500, "RAG_ERROR")


# ═══════════════════════════════════════════════════════════════════════════
#  RAG — Delete Collection (admin + password)
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/rag/collections/{collection_name}", methods=["DELETE"])
async def rag_delete_collection(req: func.HttpRequest) -> func.HttpResponse:
    """Delete an entire RAG collection. Admin only, requires password verification."""
    from security import require_auth
    import db as database

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    if not _is_admin(req):
        return _error_response(
            "Admin access required to delete collections.",
            403,
            "FORBIDDEN",
        )

    # Verify password
    pw_ok, pw_err = _verify_admin_password(req)
    if not pw_ok:
        return _error_response(pw_err, 403, "FORBIDDEN")

    collection_name = req.route_params.get("collection_name", "")
    if not collection_name:
        return _error_response("Collection name is required.", 400, "BAD_REQUEST")

    try:
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            # Get document IDs in this collection
            doc_ids = await conn.fetch(
                "SELECT id FROM rag_documents WHERE category = $1",
                collection_name,
            )
            if not doc_ids:
                return _error_response(
                    f"Collection '{collection_name}' not found.",
                    404,
                    "NOT_FOUND",
                )

            id_list = [row["id"] for row in doc_ids]
            # Delete embeddings for all documents in this collection
            await conn.execute(
                "DELETE FROM rag_embeddings WHERE document_id = ANY($1::uuid[])",
                id_list,
            )
            # Delete the documents
            await conn.execute(
                "DELETE FROM rag_documents WHERE category = $1",
                collection_name,
            )

        logger.info(
            "rag.collection_deleted: name=%s docs=%d by=%s",
            collection_name,
            len(doc_ids),
            user.email,
        )
        return _json_response({
            "status": "deleted",
            "collection": collection_name,
            "documents_deleted": len(doc_ids),
        })
    except Exception as exc:
        logger.error("rag.delete_collection_failed: %s", exc, exc_info=True)
        return _error_response(f"Failed to delete collection: {exc}", 500, "RAG_ERROR")


# ═══════════════════════════════════════════════════════════════════════════
#  GITHUB — Push
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="api/v2/github/push", methods=["POST"])
async def github_push(req: func.HttpRequest) -> func.HttpResponse:
    """Push generated migration files to a GitHub repository."""
    from security import require_auth
    import db as database
    import github_service

    headers = _get_headers(req)
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    try:
        body = req.get_json()
    except ValueError:
        return _error_response("Invalid JSON body.")

    migration_id = body.get("migration_id") or body.get("migrationId")
    repo_name = body.get("repo_name") or body.get("repoName")
    if not migration_id or not repo_name:
        return _error_response("migration_id and repo_name are required.")

    migration = await database.get_migration(migration_id)
    if not migration:
        return _error_response("Migration not found.", 404, "NOT_FOUND")

    output_files = migration.get("output_files") or {}
    if not output_files:
        return _error_response("No output files to push.", 409, "NO_OUTPUT")

    try:
        result = await github_service.push_to_github(
            files=output_files,
            repo_name=repo_name,
            branch=body.get("branch", "main"),
            commit_message=body.get("commit_message", "feat: add migrated Spring Boot project"),
            pat=body.get("pat") or body.get("github_pat"),
            base_path=body.get("base_path", ""),
        )
    except ValueError as exc:
        return _error_response(str(exc), 400, "GITHUB_ERROR")
    except Exception as exc:
        logger.error("github.push_failed: %s", exc, exc_info=True)
        return _error_response(f"GitHub push failed: {exc}", 500, "GITHUB_ERROR")

    return _json_response(result)


# ═══════════════════════════════════════════════════════════════════════════
#  QUEUE TRIGGER — Migration Worker
# ═══════════════════════════════════════════════════════════════════════════

@app.queue_trigger(
    arg_name="msg",
    queue_name="migration-queue",
    connection="AzureWebJobsStorage",
)
async def migration_worker(msg: func.QueueMessage) -> None:
    """
    Process a migration job from the queue.

    Runs the static engine and optional LLM agents.  Updates the
    database row with results or error status.
    """
    import db as database
    from engine import run_migration_pipeline

    raw = msg.get_body().decode("utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("migration_worker.invalid_message: %s", raw[:200])
        return

    migration_id = payload.get("migration_id")
    if not migration_id:
        logger.error("migration_worker.missing_migration_id")
        return

    logger.info("migration_worker.started: id=%s", migration_id)

    # Load migration from DB
    migration = await database.get_migration(migration_id)
    if not migration:
        logger.error("migration_worker.not_found: id=%s", migration_id)
        return

    if migration["status"] == "cancelled":
        logger.info("migration_worker.already_cancelled: id=%s", migration_id)
        return

    # Mark as running
    await database.update_migration(migration_id, {
        "status": "running",
        "started_at": datetime.now(timezone.utc),
    })

    try:
        # Build XML files dict (asyncpg returns JSONB as str)
        xml_files = {}
        raw_xml = migration.get("input_xml_files") or "[]"
        if isinstance(raw_xml, str):
            raw_xml = json.loads(raw_xml)
        for entry in raw_xml:
            if isinstance(entry, str):
                entry = json.loads(entry)
            name = entry.get("name", "unknown.xml")
            content = entry.get("content", "")
            xml_files[name] = content

        config = {
            "group_id": migration.get("group_id", "com.example"),
            "artifact_id": migration.get("project_name", "migrated-app"),
            "java_version": migration.get("java_version", "17"),
        }

        # Parse JSONB fields
        llm_cfg = migration.get("llm_config") or "{}"
        if isinstance(llm_cfg, str):
            llm_cfg = json.loads(llm_cfg)
        dw_scripts = migration.get("dataweave_scripts") or "{}"
        if isinstance(dw_scripts, str):
            dw_scripts = json.loads(dw_scripts)

        result = await run_migration_pipeline(
            migration_id=migration_id,
            xml_files=xml_files,
            config=config,
            llm_config=llm_cfg,
            dataweave_scripts=dw_scripts,
        )

        # Persist results
        now = datetime.now(timezone.utc)
        await database.update_migration(migration_id, {
            "status": "completed",
            "output_files": result["files"],
            "agent_trace": result.get("agent_trace", {}),
            "summary": {
                "status": "completed",
                "errors": result.get("errors", []),
                "total_files": len(result["files"]),
                "unknown_elements": len(result.get("unknown_elements", [])),
            },
            "total_tokens_used": result.get("total_tokens", 0),
            "total_cost_usd": result.get("total_cost_usd", 0.0),
            "duration_ms": result.get("duration_ms", 0),
            "completed_at": now,
        })

        logger.info(
            "migration_worker.completed: id=%s files=%d duration=%dms",
            migration_id, len(result["files"]), result.get("duration_ms", 0),
        )

    except Exception as exc:
        logger.error(
            "migration_worker.failed: id=%s error=%s",
            migration_id, exc, exc_info=True,
        )
        await database.update_migration(migration_id, {
            "status": "failed",
            "completed_at": datetime.now(timezone.utc),
            "summary": {"status": "failed", "error": str(exc)},
        })


# ═══════════════════════════════════════════════════════════════════════════
#  QUEUE TRIGGER — Build Worker
# ═══════════════════════════════════════════════════════════════════════════

@app.queue_trigger(
    arg_name="msg",
    queue_name="build-queue",
    connection="AzureWebJobsStorage",
)
async def build_worker(msg: func.QueueMessage) -> None:
    """
    Process a build job from the queue.

    Extracts generated files, runs Maven, and updates the build row.
    """
    import db as database
    from build_service import execute_build

    raw = msg.get_body().decode("utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("build_worker.invalid_message: %s", raw[:200])
        return

    build_id = payload.get("build_id")
    migration_id = payload.get("migration_id")
    if not build_id or not migration_id:
        logger.error("build_worker.missing_ids: %s", payload)
        return

    logger.info("build_worker.started: build=%s migration=%s", build_id, migration_id)

    # Mark build as running
    await database.update_build(build_id, {"status": "running"})

    # Load migration output
    migration = await database.get_migration(migration_id)
    if not migration:
        await database.update_build(build_id, {
            "status": "failed",
            "build_log": f"Migration {migration_id} not found.",
            "completed_at": datetime.now(timezone.utc),
        })
        return

    output_files = migration.get("output_files") or {}
    if not output_files:
        await database.update_build(build_id, {
            "status": "failed",
            "build_log": "No output files to build.",
            "completed_at": datetime.now(timezone.utc),
        })
        return

    try:
        result = await execute_build(
            build_id=build_id,
            migration_id=migration_id,
            output_files=output_files,
            project_name=migration.get("project_name", "migrated-app"),
            group_id=migration.get("group_id", "com.example"),
            java_version=migration.get("java_version", "17"),
        )

        await database.update_build(build_id, {
            "status": result["status"],
            "exit_code": result["exit_code"],
            "build_log": result.get("build_log", ""),
            "duration_ms": result.get("duration_ms", 0),
            "completed_at": datetime.now(timezone.utc),
        })

        logger.info(
            "build_worker.finished: build=%s exit=%d",
            build_id, result["exit_code"],
        )

    except Exception as exc:
        logger.error(
            "build_worker.failed: build=%s error=%s",
            build_id, exc, exc_info=True,
        )
        await database.update_build(build_id, {
            "status": "failed",
            "build_log": f"Build error: {exc}",
            "completed_at": datetime.now(timezone.utc),
        })
