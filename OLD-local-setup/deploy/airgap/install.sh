#!/usr/bin/env bash
# =================================================================
#  Air-Gap Offline Installer
#
#  Loads Docker images from tar files, starts all services, runs
#  database migrations, and seeds the RAG knowledge base.
#
#  Usage:  ./install.sh [--compose-dir DIR]
# =================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGES_DIR="${SCRIPT_DIR}/images"
MODELS_DIR="${SCRIPT_DIR}/models"
SNAPSHOTS_DIR="${SCRIPT_DIR}/snapshots"
COMPOSE_DIR="${SCRIPT_DIR}/docker-compose"

# ── Parse args ───────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --compose-dir) COMPOSE_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--compose-dir DIR]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "============================================================"
echo "  MuleSoft-to-SpringBoot Migrator — Offline Installer"
echo "============================================================"
echo ""

# ── Prerequisite checks ─────────────────────────────────────────
echo "[1/7] Checking prerequisites..."

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is not installed. Install Docker first."
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: Docker Compose V2 is not available."
  echo "       Install docker-compose-plugin or upgrade Docker Desktop."
  exit 1
fi

echo "      Docker $(docker --version | grep -oP '\d+\.\d+\.\d+' | head -1) detected."
echo "      Docker Compose available."
echo ""

# ── Load Docker images ───────────────────────────────────────────
echo "[2/7] Loading Docker images from tar files..."

if [[ ! -d "${IMAGES_DIR}" ]]; then
  echo "ERROR: Images directory not found: ${IMAGES_DIR}"
  echo "       Run bundle.sh first on a machine with internet access."
  exit 1
fi

for tarfile in "${IMAGES_DIR}"/*.tar; do
  if [[ -f "$tarfile" ]]; then
    echo "      Loading $(basename "$tarfile")..."
    docker load -i "$tarfile"
  fi
done
echo "      All images loaded."
echo ""

# ── Set up environment ───────────────────────────────────────────
echo "[3/7] Configuring environment..."

if [[ ! -f "${COMPOSE_DIR}/.env" ]]; then
  if [[ -f "${COMPOSE_DIR}/.env.example" ]]; then
    cp "${COMPOSE_DIR}/.env.example" "${COMPOSE_DIR}/.env"
    echo "      Created .env from .env.example"
  else
    echo "      WARNING: No .env.example found. Using defaults."
  fi
else
  echo "      Existing .env found, keeping it."
fi
echo ""

# ── Start services ───────────────────────────────────────────────
echo "[4/7] Starting services with Docker Compose..."
cd "${COMPOSE_DIR}"
docker compose up -d
echo "      Services started."
echo ""

# ── Wait for health checks ──────────────────────────────────────
echo "[5/7] Waiting for services to become healthy..."

MAX_WAIT=180
INTERVAL=5
ELAPSED=0
SERVICES=("migrator-postgres" "migrator-redis" "migrator-qdrant" "migrator-api")

for svc in "${SERVICES[@]}"; do
  echo -n "      Waiting for ${svc}..."
  while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "missing")
    if [[ "$HEALTH" == "healthy" ]]; then
      echo " healthy"
      break
    fi
    sleep "$INTERVAL"
    ELAPSED=$((ELAPSED + INTERVAL))
    echo -n "."
  done
  if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    echo " TIMEOUT (status: ${HEALTH})"
    echo "WARNING: ${svc} did not become healthy within ${MAX_WAIT}s."
  fi
  ELAPSED=0
done
echo ""

# ── Run database migration ──────────────────────────────────────
echo "[6/7] Running database migrations..."
docker compose exec -T api alembic upgrade head 2>/dev/null || {
  echo "      Retrying migration after 10s..."
  sleep 10
  docker compose exec -T api alembic upgrade head
}
echo "      Migrations complete."
echo ""

# ── Seed knowledge base from Qdrant snapshot ─────────────────────
echo "[7/7] Seeding RAG knowledge base..."

QDRANT_URL="http://localhost:6333"
COLLECTION="mulesoft_knowledge"

SNAPSHOT_FILE=$(find "${SNAPSHOTS_DIR}" -name "*.snapshot" -type f 2>/dev/null | head -1)

if [[ -n "${SNAPSHOT_FILE:-}" && -f "${SNAPSHOT_FILE}" ]]; then
  echo "      Restoring Qdrant snapshot: $(basename "$SNAPSHOT_FILE")"

  # Upload snapshot to Qdrant
  curl -sf -X POST \
    "${QDRANT_URL}/collections/${COLLECTION}/snapshots/upload" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@${SNAPSHOT_FILE}" \
    >/dev/null 2>&1 && echo "      Snapshot restored." || {
      echo "      WARNING: Snapshot restore failed. Running indexer instead..."
      docker compose exec -T api python -m api.rag.indexer --full-reindex 2>/dev/null || true
    }
else
  echo "      No snapshot found. Running full indexing..."
  docker compose exec -T api python -m api.rag.indexer --full-reindex 2>/dev/null || {
    echo "      WARNING: Indexer not available or failed. Knowledge base will be empty."
    echo "      You can trigger re-indexing later via the API."
  }
fi
echo ""

# ── Copy embedding model into container (if bundled) ─────────────
if [[ -d "${MODELS_DIR}/all-MiniLM-L6-v2" ]]; then
  echo "      Copying embedding model into API container..."
  docker cp "${MODELS_DIR}/all-MiniLM-L6-v2" \
    migrator-api:/home/appuser/.cache/torch/sentence_transformers/sentence-transformers_all-MiniLM-L6-v2 \
    2>/dev/null || true
fi

# ── Print access URLs ────────────────────────────────────────────
API_PORT=$(grep -E '^API_PORT=' "${COMPOSE_DIR}/.env" 2>/dev/null | cut -d= -f2 || echo "8000")
NGINX_PORT=$(grep -E '^NGINX_HTTP_PORT=' "${COMPOSE_DIR}/.env" 2>/dev/null | cut -d= -f2 || echo "80")
HOSTNAME=$(hostname -f 2>/dev/null || hostname)

echo ""
echo "============================================================"
echo "  Installation complete!"
echo ""
echo "  API:        http://${HOSTNAME}:${API_PORT:-8000}"
echo "  Nginx:      http://${HOSTNAME}:${NGINX_PORT:-80}"
echo "  Health:     http://${HOSTNAME}:${API_PORT:-8000}/health"
echo "  API Docs:   http://${HOSTNAME}:${API_PORT:-8000}/docs"
echo ""
echo "  Manage:"
echo "    cd ${COMPOSE_DIR}"
echo "    docker compose logs -f api"
echo "    docker compose ps"
echo "    docker compose down"
echo "============================================================"
