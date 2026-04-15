"""
Azure Functions app — MuleSoft-to-SpringBoot Migrator.

Python v2 programming model.  All HTTP triggers and Queue triggers are
registered on a single ``FunctionApp`` instance.

HTTP Triggers:
  POST   /api/v2/migrations          Create migration (enqueue)
  POST   /api/v2/migrations/upload   Upload ZIP / folder (multipart)
  GET    /api/v2/migrations           List migrations (paginated)
  GET    /api/v2/migrations/{id}      Get migration detail
  GET    /api/v2/migrations/{id}/files          Get generated files
  GET    /api/v2/migrations/{id}/files/{path}   Get single file
  DELETE /api/v2/migrations/{id}      Soft delete
  POST   /api/v2/migrations/{id}/cancel         Cancel
  POST   /api/v2/migrations/{id}/retry          Retry failed/stuck migration
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


def _enqueue_message_delayed(queue_name: str, message: dict, visibility_timeout: int = 0) -> None:
    """Send a message with visibility timeout (delayed delivery)."""
    from azure.storage.queue import QueueClient
    import base64

    conn_str = os.getenv("AzureWebJobsStorage", "UseDevelopmentStorage=true")
    client = QueueClient.from_connection_string(conn_str, queue_name)
    try:
        client.create_queue()
    except Exception:
        pass
    encoded = base64.b64encode(json.dumps(message).encode()).decode()
    client.send_message(encoded, visibility_timeout=visibility_timeout)


def _get_user_from_header(req: func.HttpRequest) -> dict:
    """
    Extract user info from:
      1. Authorization: Bearer <custom-token> (email/password login)
      2. x-ms-client-principal header (Azure EasyAuth / MSAL)
      3. Development fallback
    Returns a dict with 'email', 'name', 'roles', 'oid'.
    """
    import base64 as b64mod
    import hashlib, hmac

    # --- Check Bearer token first ---
    auth_header = req.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and auth_header != "Bearer msal":
        token = auth_header[7:]
        jwt_parts = token.split(".")

        # Azure AD JWT (3-part: header.payload.signature)
        if len(jwt_parts) == 3:
            try:
                # Decode payload (middle part) without signature verification
                # (EasyAuth or app-level validation handles trust;
                #  we just extract claims for user identification)
                payload_b64 = jwt_parts[1]
                padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
                payload = json.loads(b64mod.urlsafe_b64decode(padded))

                import time
                # Verify token isn't expired
                if payload.get("exp", 0) > time.time():
                    # Verify audience matches our app
                    aud = payload.get("aud", "")
                    expected_client_id = os.environ.get("AZURE_AD_CLIENT_ID", "562164fe-698a-4b4a-b874-40025140f008")
                    if aud == expected_client_id or aud == f"api://{expected_client_id}":
                        email = payload.get("preferred_username") or payload.get("email") or payload.get("upn", "")
                        name = payload.get("name", "")
                        oid = payload.get("oid", "")
                        roles = payload.get("roles", ["user"])
                        if isinstance(roles, list) and len(roles) == 0:
                            roles = ["user"]
                        return {
                            "email": email,
                            "name": name,
                            "roles": roles,
                            "oid": oid or email,
                        }
                    else:
                        logger.warning("azure_ad_jwt.audience_mismatch: got=%s expected=%s", aud, expected_client_id)
            except Exception as exc:
                logger.warning("azure_ad_jwt.decode_error: %s", exc)

        # Custom 2-part token (payload.hmac-signature) for email/password login
        elif len(jwt_parts) == 2:
            try:
                payload_b64, sig = jwt_parts
                # Verify HMAC signature
                secret = os.environ.get("JWT_SECRET", os.environ.get("AzureWebJobsStorage", "default-secret"))
                expected_sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:32]
                if hmac.compare_digest(sig, expected_sig):
                    padded = payload_b64 + "=" * (4 - len(payload_b64) % 4)
                    payload = json.loads(b64mod.urlsafe_b64decode(padded))
                    import time
                    if payload.get("exp", 0) > time.time():
                        return {
                            "email": payload.get("email", ""),
                            "name": payload.get("name", ""),
                            "roles": [payload.get("role", "user")],
                            "oid": payload.get("email", ""),
                        }
            except Exception as exc:
                logger.warning("bearer_token.decode_error: %s", exc)

    # --- Check x-ms-client-principal (Azure EasyAuth / MSAL) ---
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
#  AUTH — Login (email / password)
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="v2/auth/login", methods=["POST"])
async def auth_login(req: func.HttpRequest) -> func.HttpResponse:
    """
    Simple email/password login.
    Returns a JWT-like token that the frontend stores in localStorage.
    """
    import hashlib, hmac, base64 as b64

    try:
        body = req.get_json()
    except (ValueError, AttributeError):
        return _json_response({"error": "Invalid JSON body"}, 400)

    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""

    if not email or not password:
        return _json_response({"error": "Email and password are required"}, 400)

    admin_email = os.environ.get("ADMIN_EMAIL", "HARINADH70@outlook.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "")

    if email != admin_email:
        return _json_response({"error": "Invalid credentials"}, 401)

    # Check password — support both plain-text and bcrypt
    password_ok = False
    try:
        import bcrypt
        if admin_password.startswith("$2"):
            password_ok = bcrypt.checkpw(password.encode(), admin_password.encode())
        else:
            password_ok = (password == admin_password)
    except ImportError:
        password_ok = (password == admin_password)

    if not password_ok:
        return _json_response({"error": "Invalid credentials"}, 401)

    # Build a simple signed token (HMAC-SHA256)
    secret = os.environ.get("JWT_SECRET", os.environ.get("AzureWebJobsStorage", "default-secret"))
    payload = json.dumps({"email": email, "name": email.split("@")[0], "role": "admin", "exp": int(__import__("time").time()) + 86400})
    payload_b64 = b64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()[:32]
    token = f"{payload_b64}.{sig}"

    return _json_response({
        "token": token,
        "user": {"id": email, "email": email, "name": email.split("@")[0], "role": "admin"},
    })


# ═══════════════════════════════════════════════════════════════════════════
#  AUTH — Current User Info
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="v2/auth/me", methods=["GET"])
async def auth_me(req: func.HttpRequest) -> func.HttpResponse:
    """Return current user information and role."""
    user = _get_user_from_header(req)
    admin_email = os.environ.get("ADMIN_EMAIL", "HARINADH70@outlook.com")

    is_admin = (
        user.get("email", "").lower() == admin_email.lower()
        or "admin" in user.get("roles", [])
    )

    return _json_response({
        "id": user.get("oid", user.get("email", "")),
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

@app.route(route="v2/migrations", methods=["POST"])
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
#  MIGRATIONS — Upload ZIP / Folder
# ═══════════════════════════════════════════════════════════════════════════

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

# Directories and files to skip when scanning ZIPs
_SKIP_NAMES = {"__MACOSX", ".DS_Store", "__pycache__", ".git", "target", "node_modules", ".mule"}


def _is_mule_xml(content: str) -> bool:
    """Return True if *content* looks like a MuleSoft XML file (has <mule root)."""
    # Quick heuristic — look in first 2 KB for the <mule element
    head = content[:2048]
    return "<mule" in head and ("http://www.mulesoft.org" in head or "mule-" in head)


def _extract_mule_project_from_zip(zip_bytes: bytes) -> dict:
    """
    Extract ALL important MuleSoft project files from a ZIP.

    Handles multi-project ZIPs by detecting all projects and processing
    them together (combining all XML flows into one migration).

    Returns dict with keys:
      xml_files      – list[dict] of {name, content, size}  (Mule flow XMLs)
      config_files   – list[dict] of {name, content}        (YAML/properties)
      raml_files     – list[dict] of {name, content}        (RAML API defs)
      java_files     – list[dict] of {name, content}        (custom Java)
      dataweave_files – list[dict] of {name, content}       (DWL scripts)
      global_xml_files – list[dict] of {name, content}      (resource XMLs)
      pom_xml        – str | None                           (pom.xml content)
      mule_artifact  – str | None                           (mule-artifact.json)
      log4j2_xml     – str | None                           (log4j2.xml content)
      project_root   – str, detected project root within the ZIP
      pom_metadata   – dict with groupId, artifactId, version, connectors
      projects_found – int, number of MuleSoft projects detected
    """
    import zipfile
    import io
    import fnmatch

    zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    all_names = zf.namelist()

    # ── Detect ALL project roots (handle multi-project ZIPs) ─────────
    project_roots = []
    for name in all_names:
        parts = name.split("/")
        if any(p in _SKIP_NAMES for p in parts):
            continue
        # A project root has pom.xml with mule-application packaging
        if parts[-1] == "pom.xml":
            root = "/".join(parts[:-1])
            if root not in project_roots:
                project_roots.append(root)

    # If too many projects (>20), find the ones with src/main/mule/
    if len(project_roots) > 20:
        mule_projects = []
        for root in project_roots:
            prefix = (root + "/") if root else ""
            mule_dir = f"{prefix}src/main/mule/"
            if any(n.startswith(mule_dir) and n.endswith(".xml") for n in all_names):
                mule_projects.append(root)
        if mule_projects:
            project_roots = mule_projects

    # Use first project as primary (for pom.xml metadata)
    project_root = project_roots[0] if project_roots else ""

    # Fallback: find src/main/mule if no pom.xml found
    if not project_roots:
        for name in all_names:
            parts = name.split("/")
            if any(p in _SKIP_NAMES for p in parts):
                continue
            try:
                idx = parts.index("src")
                if parts[idx + 1] == "main" and parts[idx + 2] == "mule":
                    project_root = "/".join(parts[:idx])
                    break
            except (ValueError, IndexError):
                continue
        project_roots = [project_root] if project_root else [""]

    prefix = (project_root + "/") if project_root else ""

    # ── Helper: read a ZIP entry as UTF-8 text ───────────────────────
    def _read_text(entry_name: str) -> str | None:
        try:
            raw = zf.read(entry_name)
            return raw.decode("utf-8", errors="replace")
        except Exception:
            return None

    # ── Collect all important files ──────────────────────────────────
    xml_files: list[dict] = []
    config_files: list[dict] = []
    raml_files: list[dict] = []
    java_files: list[dict] = []
    dataweave_files: list[dict] = []
    global_xml_files: list[dict] = []
    pom_xml: str | None = None
    mule_artifact: str | None = None
    log4j2_xml: str | None = None

    # Build prefix sets for ALL detected projects
    all_mule_dirs = set()
    all_resources_dirs = set()
    all_java_dirs = set()
    for root in project_roots:
        p = (root + "/") if root else ""
        all_mule_dirs.add(f"{p}src/main/mule/")
        all_resources_dirs.add(f"{p}src/main/resources/")
        all_java_dirs.add(f"{p}src/main/java/")

    prefix = (project_root + "/") if project_root else ""
    mule_dir = f"{prefix}src/main/mule/"
    resources_dir = f"{prefix}src/main/resources/"
    java_dir = f"{prefix}src/main/java/"

    MAX_XML_FILES = 100  # Safety limit
    MAX_TOTAL_SIZE = 20_000_000  # 20MB text content limit
    total_text_size = 0

    for name in sorted(all_names):
        # Skip directories and junk
        if name.endswith("/"):
            continue
        parts = name.split("/")
        if any(p in _SKIP_NAMES for p in parts):
            continue

        lower = name.lower()
        rel_name = name[len(prefix):] if prefix else name
        basename = parts[-1]
        basename_lower = basename.lower()

        # ── pom.xml ──────────────────────────────────────────────
        if rel_name == "pom.xml":
            pom_xml = _read_text(name)
            continue

        # ── mule-artifact.json ───────────────────────────────────
        if rel_name == "mule-artifact.json":
            mule_artifact = _read_text(name)
            continue

        # ── log4j2.xml ───────────────────────────────────────────
        if rel_name == "src/main/resources/log4j2.xml":
            log4j2_xml = _read_text(name)
            continue

        # ── Mule XML files in src/main/mule/ (ANY project) or root ────
        if lower.endswith(".xml"):
            in_any_mule_dir = any(name.startswith(d) for d in all_mule_dirs)
            at_root = (prefix and name.startswith(prefix) and "/" not in name[len(prefix):])
            at_zip_root = (not prefix and "/" not in name)

            if (in_any_mule_dir or at_root or at_zip_root) and len(xml_files) < MAX_XML_FILES:
                content = _read_text(name)
                if content and _is_mule_xml(content):
                    total_text_size += len(content)
                    if total_text_size > MAX_TOTAL_SIZE:
                        continue
                    xml_files.append({
                        "name": rel_name,
                        "content": content,
                        "size": len(content.encode("utf-8")),
                    })
                    continue

            # ── Global XML configs in src/main/resources/ ────────
            if name.startswith(resources_dir) and basename_lower != "log4j2.xml":
                content = _read_text(name)
                if content:
                    global_xml_files.append({"name": rel_name, "content": content})
                continue

        # ── Config YAML / properties files ───────────────────────
        if basename_lower in ("config.yaml", "config.yml", "config.properties",
                              "application.yaml", "application.yml",
                              "application.properties", "mule-app.properties"):
            if name.startswith(resources_dir) or name.startswith(prefix):
                content = _read_text(name)
                if content:
                    config_files.append({"name": rel_name, "content": content})
            continue

        # ── Properties files in resources (e.g. env-specific) ────
        if lower.endswith(".properties") and name.startswith(resources_dir):
            content = _read_text(name)
            if content:
                config_files.append({"name": rel_name, "content": content})
            continue

        # ── RAML files (anywhere in project) ─────────────────────
        if lower.endswith(".raml"):
            content = _read_text(name)
            if content:
                raml_files.append({"name": rel_name, "content": content})
            continue

        # ── DataWeave .dwl files ─────────────────────────────────
        if lower.endswith(".dwl"):
            content = _read_text(name)
            if content:
                dataweave_files.append({"name": rel_name, "content": content})
            continue

        # ── Java source files ────────────────────────────────────
        if lower.endswith(".java") and name.startswith(java_dir):
            content = _read_text(name)
            if content:
                java_files.append({"name": rel_name, "content": content})
            continue

    # ── Fallback: if no XMLs found in standard dirs, scan ALL xml files ──
    if not xml_files:
        for name in sorted(all_names):
            if name.endswith("/"):
                continue
            parts = name.split("/")
            if any(p in _SKIP_NAMES for p in parts):
                continue
            if not name.lower().endswith(".xml"):
                continue
            content = _read_text(name)
            if content and _is_mule_xml(content):
                rel_name = name[len(prefix):] if prefix else name
                xml_files.append({
                    "name": rel_name,
                    "content": content,
                    "size": len(content.encode("utf-8")),
                })

    # ── Extract metadata from pom.xml ────────────────────────────────
    pom_metadata = _parse_pom_metadata(pom_xml) if pom_xml else {}

    # ── Extract mule version from mule-artifact.json ─────────────────
    mule_version = ""
    if mule_artifact:
        try:
            artifact_data = json.loads(mule_artifact)
            mule_version = artifact_data.get("minMuleVersion", "")
        except (json.JSONDecodeError, AttributeError):
            pass

    return {
        "xml_files": xml_files,
        "config_files": config_files,
        "raml_files": raml_files,
        "java_files": java_files,
        "dataweave_files": dataweave_files,
        "global_xml_files": global_xml_files,
        "pom_xml": pom_xml,
        "mule_artifact": mule_artifact,
        "log4j2_xml": log4j2_xml,
        "project_root": project_root,
        "pom_metadata": pom_metadata,
        "mule_version": mule_version,
        "projects_found": len(project_roots),
    }


def _parse_pom_metadata(pom_content: str) -> dict:
    """
    Extract groupId, artifactId, version, and MuleSoft connector dependencies
    from a pom.xml string.
    """
    import re

    metadata: dict = {}

    # Extract top-level groupId, artifactId, version (not inside <parent> or <dependency>)
    # We use a simple approach: find the first occurrence outside of nested blocks
    # Remove comments first
    clean = re.sub(r"<!--.*?-->", "", pom_content, flags=re.DOTALL)

    # Try to find project-level groupId (not inside <parent> or <dependencies>)
    # Strategy: find <groupId> that appears before any <dependencies> block
    deps_start = clean.find("<dependencies>")
    parent_start = clean.find("<parent>")
    parent_end = clean.find("</parent>")
    header = clean[:deps_start] if deps_start > 0 else clean[:2000]

    # Remove <parent> block from header to avoid picking up parent groupId
    if parent_start >= 0 and parent_end > parent_start:
        header_clean = header[:parent_start] + header[parent_end + len("</parent>"):]
    else:
        header_clean = header

    gid_match = re.search(r"<groupId>\s*([^<]+?)\s*</groupId>", header_clean)
    aid_match = re.search(r"<artifactId>\s*([^<]+?)\s*</artifactId>", header_clean)
    ver_match = re.search(r"<version>\s*([^<]+?)\s*</version>", header_clean)

    # Fallback to parent groupId if project-level not found
    if not gid_match and parent_start >= 0 and parent_end > parent_start:
        parent_block = clean[parent_start:parent_end]
        gid_match = re.search(r"<groupId>\s*([^<]+?)\s*</groupId>", parent_block)

    metadata["group_id"] = gid_match.group(1).strip() if gid_match else ""
    metadata["artifact_id"] = aid_match.group(1).strip() if aid_match else ""
    metadata["version"] = ver_match.group(1).strip() if ver_match else ""

    # ── Extract MuleSoft connector dependencies ──────────────────────
    connectors: list[dict] = []
    # Known MuleSoft connector groupId prefixes
    mule_group_prefixes = (
        "org.mule.connectors",
        "org.mule.modules",
        "com.mulesoft.connectors",
        "com.mulesoft.modules",
        "org.mule.tooling",
    )
    dep_pattern = re.compile(
        r"<dependency>\s*"
        r"<groupId>\s*([^<]+?)\s*</groupId>\s*"
        r"<artifactId>\s*([^<]+?)\s*</artifactId>\s*"
        r"(?:<version>\s*([^<]*?)\s*</version>)?",
        re.DOTALL,
    )
    for m in dep_pattern.finditer(clean):
        dep_gid = m.group(1).strip()
        dep_aid = m.group(2).strip()
        dep_ver = (m.group(3) or "").strip()
        if any(dep_gid.startswith(p) for p in mule_group_prefixes):
            connectors.append({
                "groupId": dep_gid,
                "artifactId": dep_aid,
                "version": dep_ver,
            })

    metadata["connectors"] = connectors
    return metadata


@app.route(route="v2/migrations/upload", methods=["POST"])
async def upload_migration_zip(req: func.HttpRequest) -> func.HttpResponse:
    """
    Accept a multipart/form-data upload containing a MuleSoft project ZIP.

    Form fields:
      file            – the ZIP file (required)
      project_name    – optional, defaults to ZIP filename
      group_id        – optional, defaults to "com.example"
      java_version    – optional, defaults to "17"
      ai_enhancement  – optional, defaults to "false"
    """
    from security import require_auth, validate_xml_files, check_rate_limit
    import db as database

    headers = _get_headers(req)

    # Authenticate
    try:
        user = require_auth(headers)
    except ValueError as exc:
        return _error_response(str(exc), 401, "UNAUTHORIZED")

    # Rate limit
    allowed, rate_info = check_rate_limit(user.oid, max_requests=10, window_seconds=60)
    if not allowed:
        return _json_response(
            {"error": "RATE_LIMITED", "detail": "Too many upload requests.", **rate_info},
            status_code=429,
            headers={"Retry-After": str(rate_info.get("reset_at", 60) - int(time.time()))},
        )

    # ── Read the uploaded file from the multipart body ────────────────
    # Azure Functions exposes files via req.files for multipart uploads
    uploaded_file = req.files.get("file")
    if not uploaded_file:
        return _error_response("No file provided. Send a ZIP file as the 'file' field in multipart form data.")

    # Read raw bytes
    zip_bytes = uploaded_file.read()
    if not zip_bytes:
        return _error_response("Uploaded file is empty.")

    # Size check
    if len(zip_bytes) > MAX_UPLOAD_SIZE:
        return _json_response(
            {"error": "PAYLOAD_TOO_LARGE", "detail": f"ZIP file exceeds {MAX_UPLOAD_SIZE // (1024*1024)}MB limit."},
            status_code=413,
        )

    # Validate it is a real ZIP
    import zipfile, io
    if not zipfile.is_zipfile(io.BytesIO(zip_bytes)):
        return _error_response("Uploaded file is not a valid ZIP archive.", 400, "INVALID_FILE")

    # ── Extract MuleSoft files ────────────────────────────────────────
    try:
        extracted = _extract_mule_project_from_zip(zip_bytes)
    except Exception as exc:
        logger.exception("upload.extract_error")
        return _error_response(f"Failed to extract ZIP: {exc}", 400, "EXTRACT_ERROR")

    xml_files = extracted["xml_files"]
    if not xml_files:
        return _error_response(
            "No MuleSoft XML files found in the ZIP. "
            "Expected XML files with a <mule> root element in src/main/mule/ or at the project root.",
            400,
            "NO_XML_FOUND",
        )

    # Validate XML (XXE prevention)
    try:
        xml_files = validate_xml_files(xml_files)
    except ValueError as exc:
        return _error_response(str(exc))

    # ── Read optional form fields ─────────────────────────────────────
    zip_filename = uploaded_file.filename or "uploaded-project"
    if zip_filename.lower().endswith(".zip"):
        zip_filename = zip_filename[:-4]

    form = req.form or {}
    pom_meta = extracted.get("pom_metadata") or {}
    # Prefer pom.xml metadata, then form fields, then defaults
    project_name = (
        form.get("project_name")
        or pom_meta.get("artifact_id")
        or zip_filename
    )
    group_id = (
        form.get("group_id")
        or pom_meta.get("group_id")
        or "com.example"
    )
    java_version = form.get("java_version") or "17"
    ai_enhancement_str = form.get("ai_enhancement", "false")
    ai_enabled = ai_enhancement_str.lower() in ("true", "1", "yes")

    # ── Build DataWeave scripts dict ─────────────────────────────────
    dataweave_scripts = {
        f["name"]: f["content"] for f in extracted.get("dataweave_files", [])
    }

    # ── Build config YAML content (first config.yaml found) ──────────
    config_yaml_content = ""
    for cf in extracted.get("config_files", []):
        if cf["name"].lower().endswith((".yaml", ".yml")):
            config_yaml_content = cf["content"]
            break

    # ── Build LLM config with all extra MuleSoft context ─────────────
    llm_config = {
        "provider": "azure_openai" if ai_enabled else "",
        "model": "gpt-4.1" if ai_enabled else "",
        "enabled": ai_enabled,
        # Extra MuleSoft project context for the engine/LLM
        "mule_config_yaml": config_yaml_content,
        "mule_pom_xml": extracted.get("pom_xml") or "",
        "mule_raml": {f["name"]: f["content"] for f in extracted.get("raml_files", [])},
        "mule_java_files": {f["name"]: f["content"] for f in extracted.get("java_files", [])},
        "mule_global_xml": {f["name"]: f["content"] for f in extracted.get("global_xml_files", [])},
        "mule_log4j2": extracted.get("log4j2_xml") or "",
        "mule_version": extracted.get("mule_version") or "",
        "mule_artifact_json": extracted.get("mule_artifact") or "",
        "pom_metadata": pom_meta,
        "all_config_files": {f["name"]: f["content"] for f in extracted.get("config_files", [])},
    }

    # Upsert user
    db_user = await database.upsert_user(user.oid, user.email, user.name)

    # Create migration row
    migration_data = {
        "project_name": project_name,
        "group_id": group_id,
        "java_version": java_version,
        "input_xml_files": xml_files,
        "dataweave_scripts": dataweave_scripts,
        "llm_config": llm_config,
    }
    migration = await database.create_migration(migration_data, user_id=db_user["id"])

    # Enqueue for background processing
    _enqueue_message("migration-queue", {
        "migration_id": migration["id"],
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
    })

    # ── Build enhanced upload summary ────────────────────────────────
    total_files = (
        len(xml_files)
        + len(extracted.get("config_files", []))
        + len(extracted.get("raml_files", []))
        + len(extracted.get("java_files", []))
        + len(extracted.get("dataweave_files", []))
        + len(extracted.get("global_xml_files", []))
        + (1 if extracted.get("pom_xml") else 0)
        + (1 if extracted.get("log4j2_xml") else 0)
        + (1 if extracted.get("mule_artifact") else 0)
    )

    upload_summary = {
        "xml_files": [f["name"] for f in xml_files],
        "config_files": [f["name"] for f in extracted.get("config_files", [])],
        "raml_files": [f["name"] for f in extracted.get("raml_files", [])],
        "java_files": [f["name"] for f in extracted.get("java_files", [])],
        "dataweave_files": [f["name"] for f in extracted.get("dataweave_files", [])],
        "global_xml_files": [f["name"] for f in extracted.get("global_xml_files", [])],
        "log4j2": bool(extracted.get("log4j2_xml")),
        "pom_detected": bool(extracted.get("pom_xml")),
        "mule_artifact_detected": bool(extracted.get("mule_artifact")),
        "project_name": project_name,
        "group_id": group_id,
        "mule_version": extracted.get("mule_version") or "",
        "pom_connectors": pom_meta.get("connectors", []),
        "project_root": extracted["project_root"],
        "total_files": total_files,
    }

    logger.info(
        "migration.uploaded: id=%s project=%s xml=%d config=%d raml=%d java=%d dwl=%d total=%d",
        migration["id"], project_name,
        len(xml_files), len(extracted.get("config_files", [])),
        len(extracted.get("raml_files", [])), len(extracted.get("java_files", [])),
        len(extracted.get("dataweave_files", [])), total_files,
    )

    return _json_response({
        **migration,
        "upload_summary": upload_summary,
    }, status_code=202)


# ═══════════════════════════════════════════════════════════════════════════
#  MIGRATIONS — List
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="v2/migrations", methods=["GET"])
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

@app.route(route="v2/stats/migrations", methods=["GET"])
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

@app.route(route="v2/migrations/{migration_id}", methods=["GET"])
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

@app.route(route="v2/migrations/{migration_id}/files", methods=["GET"])
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

@app.route(route="v2/migrations/{migration_id}/files/{file_path}", methods=["GET"])
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

@app.route(route="v2/migrations/{migration_id}", methods=["DELETE"])
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

@app.route(route="v2/migrations/{migration_id}/cancel", methods=["POST"])
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
#  MIGRATIONS — Retry (re-enqueue failed/stuck)
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="v2/migrations/{migration_id}/retry", methods=["POST"])
async def retry_migration(req: func.HttpRequest) -> func.HttpResponse:
    """
    Retry a failed or stuck migration by resetting its status to 'queued'
    and re-enqueuing it to the migration queue.

    Allowed source states: failed, running (stuck for >10 min), cancelled.
    """
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

    status = migration["status"]
    retryable = {"failed", "cancelled"}

    # Also allow retrying "running" if stuck for more than 10 minutes
    if status == "running":
        started = migration.get("started_at")
        if started:
            if isinstance(started, str):
                started = datetime.fromisoformat(started)
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            if elapsed > 600:  # >10 min = stuck
                retryable.add("running")
            else:
                return _error_response(
                    f"Migration is still running (started {int(elapsed)}s ago). "
                    "Wait at least 10 minutes before retrying.",
                    409, "STILL_RUNNING",
                )
        else:
            retryable.add("running")  # No start time = definitely stuck

    if status not in retryable:
        return _error_response(
            f"Cannot retry migration in '{status}' state. "
            "Only failed, cancelled, or stuck (>10min running) migrations can be retried.",
            409, "INVALID_STATE",
        )

    # Reset status and re-enqueue
    await database.update_migration(migration_id, {
        "status": "queued",
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
        "summary": None,
    })

    # Re-enqueue to migration queue
    _enqueue_message("migration-queue", {
        "migration_id": migration_id,
        "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "retry": True,
    })

    logger.info("migration.retried: id=%s previous_status=%s user=%s",
                migration_id, status, user.get("email", "unknown"))

    return _json_response({
        "status": "queued",
        "migration_id": migration_id,
        "message": f"Migration re-queued for processing (was '{status}').",
    })


# ═══════════════════════════════════════════════════════════════════════════
#  BUILDS — Create
# ═══════════════════════════════════════════════════════════════════════════

@app.route(route="v2/builds", methods=["POST"])
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

@app.route(route="v2/builds/{build_id}", methods=["GET"])
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

@app.route(route="v2/rag/search", methods=["POST"])
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

@app.route(route="v2/rag/collections", methods=["GET"])
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


@app.route(route="v2/rag/documents", methods=["GET"])
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


@app.route(route="v2/rag/seed", methods=["POST"])
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

@app.route(route="v2/rag/documents", methods=["POST"])
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

@app.route(route="v2/rag/documents/{doc_id}", methods=["GET"])
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

@app.route(route="v2/rag/documents/{doc_id}", methods=["DELETE"])
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

@app.route(route="v2/rag/collections/{collection_name}", methods=["DELETE"])
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

@app.route(route="v2/github/push", methods=["POST"])
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

    # If already completed, skip (idempotency for queue retries)
    if migration["status"] == "completed":
        logger.info("migration_worker.already_completed: id=%s", migration_id)
        return

    # If already "running" from a previous crashed attempt, log and continue
    if migration["status"] == "running":
        logger.warning(
            "migration_worker.recovering_stuck: id=%s started_at=%s",
            migration_id, migration.get("started_at"),
        )

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

        logger.info("worker.llm_config: migration_id=%s enabled=%s provider=%s model=%s keys=%s",
                    migration_id, llm_cfg.get("enabled"), llm_cfg.get("provider"),
                    llm_cfg.get("model"), list(llm_cfg.keys()) if isinstance(llm_cfg, dict) else type(llm_cfg).__name__)

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


# ============================================================================
#  VALIDATION ENDPOINTS — Deploy & compare Spring Boot vs MuleSoft
# ============================================================================

@app.route(
    route="v2/validations",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
async def create_validation(req: func.HttpRequest) -> func.HttpResponse:
    """Create a validation job → enqueue deploy."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())
    try:
        import db as database
        user = _get_user_from_header(req)
        body = req.get_json()

        if not body.get("migration_id"):
            return _error_response("migration_id is required")

        # Verify migration exists and is completed
        migration = await database.get_migration(body["migration_id"])
        if not migration:
            return _error_response("Migration not found", 404)
        if migration.get("status") != "completed":
            return _error_response("Migration must be completed before validation")

        validation = await database.create_validation(body, user_id=None)

        # Enqueue the deploy job
        _enqueue_message("validation-queue", {
            "validation_id": validation["id"],
            "migration_id": body["migration_id"],
        })

        return _json_response(validation, 201)
    except Exception as exc:
        logger.error("create_validation.error: %s", exc, exc_info=True)
        return _error_response(str(exc), 500)


@app.route(
    route="v2/validations/{validation_id}",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
async def get_validation(req: func.HttpRequest) -> func.HttpResponse:
    """Get validation status + app URL."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())
    try:
        import db as database
        validation_id = req.route_params.get("validation_id", "")
        validation = await database.get_validation(validation_id)
        if not validation:
            return _error_response("Validation not found", 404)
        return _json_response(validation)
    except Exception as exc:
        logger.error("get_validation.error: %s", exc, exc_info=True)
        return _error_response(str(exc), 500)


@app.route(
    route="v2/migrations/{migration_id}/validations",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
async def list_migration_validations(req: func.HttpRequest) -> func.HttpResponse:
    """List all validations for a migration."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())
    try:
        import db as database
        migration_id = req.route_params.get("migration_id", "")
        validations = await database.list_validations_for_migration(migration_id)
        return _json_response({"items": validations, "total": len(validations)})
    except Exception as exc:
        logger.error("list_validations.error: %s", exc, exc_info=True)
        return _error_response(str(exc), 500)


@app.route(
    route="v2/validations/{validation_id}/compare",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
async def run_validation_compare(req: func.HttpRequest) -> func.HttpResponse:
    """Run server-side auto-compare: call both MuleSoft & Spring Boot endpoints."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())
    try:
        import db as database
        from validation_service import run_comparison, _detect_api_base_path

        validation_id = req.route_params.get("validation_id", "")
        validation = await database.get_validation(validation_id)
        if not validation:
            return _error_response("Validation not found", 404)
        if validation.get("status") != "running":
            return _error_response("Validation must be in 'running' state to compare")

        mulesoft_url = validation.get("mulesoft_base_url", "")
        springboot_url = validation.get("app_url", "")
        test_endpoints = validation.get("test_endpoints", [])

        if not mulesoft_url or not springboot_url:
            return _error_response("Both MuleSoft and Spring Boot URLs are required")

        # Detect controller base path (e.g. "/api/v1") to prepend to Spring Boot URLs
        migration_id = validation.get("migration_id", "")
        springboot_base_path = ""
        if migration_id:
            migration = await database.get_migration(str(migration_id))
            if migration:
                output_files = migration.get("output_files") or {}
                springboot_base_path = _detect_api_base_path(output_files)
                if springboot_base_path:
                    logger.info("run_compare.base_path: %s", springboot_base_path)

        results = await run_comparison(
            mulesoft_url, springboot_url, test_endpoints,
            springboot_base_path=springboot_base_path,
        )

        await database.update_validation(validation_id, {
            "test_results": results,
        })

        return _json_response({"results": results})
    except Exception as exc:
        logger.error("run_compare.error: %s", exc, exc_info=True)
        return _error_response(str(exc), 500)


@app.route(
    route="v2/validations/{validation_id}/verdict",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
async def submit_validation_verdict(req: func.HttpRequest) -> func.HttpResponse:
    """Submit a manual verdict (pass/fail/partial) for a validation."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())
    try:
        import db as database
        validation_id = req.route_params.get("validation_id", "")
        body = req.get_json()
        verdict = body.get("verdict", "")
        if verdict not in ("pass", "fail", "partial"):
            return _error_response("verdict must be 'pass', 'fail', or 'partial'")

        validation = await database.get_validation(validation_id)
        if not validation:
            return _error_response("Validation not found", 404)

        updated = await database.update_validation(validation_id, {
            "user_verdict": verdict,
            "status": "completed",
        })
        return _json_response(updated)
    except Exception as exc:
        logger.error("submit_verdict.error: %s", exc, exc_info=True)
        return _error_response(str(exc), 500)


@app.route(
    route="v2/validations/{validation_id}/teardown",
    methods=["POST", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
async def manual_teardown(req: func.HttpRequest) -> func.HttpResponse:
    """Manually tear down the ACI container early."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())
    try:
        import db as database
        from validation_service import teardown_aci

        validation_id = req.route_params.get("validation_id", "")
        validation = await database.get_validation(validation_id)
        if not validation:
            return _error_response("Validation not found", 404)

        aci_name = validation.get("aci_name")
        if not aci_name:
            return _error_response("No ACI container to tear down")

        success = await teardown_aci(validation_id, aci_name)
        if success:
            await database.update_validation(validation_id, {
                "status": "completed",
                "torn_down_at": datetime.now(timezone.utc),
            })
            return _json_response({"message": "Container torn down successfully"})
        else:
            return _error_response("Teardown failed", 500)
    except Exception as exc:
        logger.error("manual_teardown.error: %s", exc, exc_info=True)
        return _error_response(str(exc), 500)


@app.route(
    route="v2/validations/{validation_id}/logs",
    methods=["GET", "OPTIONS"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
async def get_validation_logs(req: func.HttpRequest) -> func.HttpResponse:
    """Fetch container logs from ACI."""
    if req.method == "OPTIONS":
        return func.HttpResponse(status_code=204, headers=_cors_headers())
    try:
        import db as database
        from validation_service import get_container_logs

        validation_id = req.route_params.get("validation_id", "")
        validation = await database.get_validation(validation_id)
        if not validation:
            return _error_response("Validation not found", 404)

        aci_name = validation.get("aci_name")
        if not aci_name:
            # Fall back to table storage logs (deploy phase)
            client = None
            try:
                from azure.data.tables.aio import TableServiceClient
                conn_str = os.getenv("AzureWebJobsStorage", "")
                if conn_str and conn_str != "UseDevelopmentStorage=true":
                    service = TableServiceClient.from_connection_string(conn_str)
                    client = service.get_table_client("validationlogs")
                    entities = []
                    async for entity in client.query_entities(f"PartitionKey eq '{validation_id}'"):
                        entities.append(entity)
                    entities.sort(key=lambda e: e.get("RowKey", ""))
                    lines = [e.get("line", "") for e in entities]
                    return _json_response({"logs": "\n".join(lines)})
            except Exception:
                pass
            return _json_response({"logs": "No logs available yet"})

        logs = await get_container_logs(aci_name)
        return _json_response({"logs": logs})
    except Exception as exc:
        logger.error("get_validation_logs.error: %s", exc, exc_info=True)
        return _error_response(str(exc), 500)


# ---------------------------------------------------------------------------
#  Queue Triggers — Validation
# ---------------------------------------------------------------------------

@app.queue_trigger(
    arg_name="msg",
    queue_name="validation-queue",
    connection="AzureWebJobsStorage",
)
async def validation_worker(msg: func.QueueMessage) -> None:
    """
    Build image via ACR Tasks → Deploy ACI → Health check → Set running
    → Enqueue delayed teardown.
    """
    import db as database
    from validation_service import build_and_push_image, deploy_aci, wait_for_health, _detect_server_port

    payload = json.loads(msg.get_body().decode("utf-8"))
    validation_id = payload["validation_id"]
    migration_id = payload["migration_id"]

    logger.info("validation_worker.start: %s", validation_id)

    try:
        # Update status to building
        await database.update_validation(validation_id, {"status": "building_image"})

        # Get migration output files
        migration = await database.get_migration(migration_id)
        if not migration:
            await database.update_validation(validation_id, {
                "status": "failed",
                "error": f"Migration {migration_id} not found",
            })
            return

        output_files = migration.get("output_files") or {}
        if not output_files:
            await database.update_validation(validation_id, {
                "status": "failed",
                "error": "No output files to deploy",
            })
            return

        validation = await database.get_validation(validation_id)
        java_version = validation.get("java_version", "17")
        keep_alive_min = validation.get("keep_alive_min", 15)

        # Step 1: Build and push Docker image via ACR Tasks
        image_ref = await build_and_push_image(
            validation_id, output_files, java_version
        )
        await database.update_validation(validation_id, {
            "status": "deploying",
            "acr_image_tag": image_ref,
        })

        # Detect server port from generated config (matches Dockerfile HEALTHCHECK)
        server_port = _detect_server_port(output_files)

        # Step 2: Deploy to ACI
        aci_info = await deploy_aci(
            validation_id, image_ref, java_version, keep_alive_min, server_port
        )
        await database.update_validation(validation_id, {
            "aci_name": aci_info["aci_name"],
            "aci_fqdn": aci_info["aci_fqdn"],
            "app_url": aci_info["app_url"],
        })

        # Step 3: Wait for health check
        healthy = await wait_for_health(aci_info["app_url"], timeout=180)
        if not healthy:
            await database.update_validation(validation_id, {
                "status": "failed",
                "error": "Health check timed out after 180s",
            })
            return

        # Step 4: Mark as running
        now = datetime.now(timezone.utc)
        from datetime import timedelta
        expires_at = now + timedelta(minutes=keep_alive_min)

        await database.update_validation(validation_id, {
            "status": "running",
            "deployed_at": now,
            "expires_at": expires_at,
        })

        # Step 5: Enqueue delayed teardown
        _enqueue_message_delayed(
            "validation-teardown-queue",
            {"validation_id": validation_id, "aci_name": aci_info["aci_name"]},
            visibility_timeout=keep_alive_min * 60,
        )

        logger.info(
            "validation_worker.deployed: %s url=%s expires=%s",
            validation_id, aci_info["app_url"], expires_at.isoformat(),
        )

    except Exception as exc:
        logger.error(
            "validation_worker.failed: %s error=%s",
            validation_id, exc, exc_info=True,
        )
        await database.update_validation(validation_id, {
            "status": "failed",
            "error": str(exc),
        })


@app.queue_trigger(
    arg_name="msg",
    queue_name="validation-teardown-queue",
    connection="AzureWebJobsStorage",
)
async def validation_teardown_worker(msg: func.QueueMessage) -> None:
    """Auto-teardown ACI container after keep_alive expires."""
    import db as database
    from validation_service import teardown_aci

    payload = json.loads(msg.get_body().decode("utf-8"))
    validation_id = payload["validation_id"]
    aci_name = payload["aci_name"]

    logger.info("validation_teardown.start: %s", validation_id)

    # Check if already torn down or completed
    validation = await database.get_validation(validation_id)
    if validation and validation.get("status") in ("completed", "failed"):
        logger.info("validation_teardown.skip: %s already %s", validation_id, validation["status"])
        return
    if validation and validation.get("torn_down_at"):
        logger.info("validation_teardown.skip: %s already torn down", validation_id)
        return

    success = await teardown_aci(validation_id, aci_name)
    await database.update_validation(validation_id, {
        "status": "expired",
        "torn_down_at": datetime.now(timezone.utc),
    })
