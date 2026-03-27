#!/usr/bin/env bash
# =================================================================
#  One-Command Setup
#
#  Checks prerequisites, configures environment, starts all services,
#  runs DB migrations, and seeds the knowledge base.
#
#  Usage:  ./setup.sh [--no-seed]
# =================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SEED_KB=true

while [[ $# -gt 0 ]]; do
  case $1 in
    --no-seed) SEED_KB=false; shift ;;
    -h|--help)
      echo "Usage: $0 [--no-seed]"
      echo "  --no-seed   Skip knowledge-base seeding"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

echo "============================================================"
echo "  MuleSoft-to-SpringBoot Migrator — Setup"
echo "============================================================"
echo ""

# ── 1. Check prerequisites ──────────────────────────────────────
echo "[1/6] Checking prerequisites..."

MISSING=()

if ! command -v docker >/dev/null 2>&1; then
  MISSING+=("docker")
fi

if ! docker compose version >/dev/null 2>&1; then
  MISSING+=("docker compose (V2)")
fi

if [[ ${#MISSING[@]} -gt 0 ]]; then
  echo "ERROR: Missing required tools: ${MISSING[*]}"
  echo ""
  echo "Install Docker Desktop or Docker Engine with the Compose plugin:"
  echo "  https://docs.docker.com/get-docker/"
  exit 1
fi

DOCKER_VERSION=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo "      Docker ${DOCKER_VERSION} detected."
echo "      Docker Compose V2 available."
echo ""

# ── 2. Configure environment ────────────────────────────────────
echo "[2/6] Configuring environment..."

if [[ ! -f "${COMPOSE_DIR}/.env" ]]; then
  cp "${COMPOSE_DIR}/.env.example" "${COMPOSE_DIR}/.env"
  echo "      Created .env from .env.example"
  echo ""
  echo "      IMPORTANT: Edit ${COMPOSE_DIR}/.env to set:"
  echo "        - SECRET_KEY (generate a random 64-char string)"
  echo "        - POSTGRES_PASSWORD"
  echo "        - At least one LLM API key (ANTHROPIC_API_KEY, etc.)"
  echo ""
else
  echo "      Existing .env found, keeping it."
fi
echo ""

# ── 3. Pull images ──────────────────────────────────────────────
echo "[3/6] Pulling Docker images..."
cd "${COMPOSE_DIR}"
docker compose pull
echo "      Done."
echo ""

# ── 4. Start services ───────────────────────────────────────────
echo "[4/6] Starting services..."
docker compose up -d --build
echo "      Services started."
echo ""

# ── 5. Wait for health checks ───────────────────────────────────
echo "[5/6] Waiting for services to become healthy..."

SERVICES=("migrator-postgres" "migrator-redis" "migrator-qdrant" "migrator-api")
MAX_WAIT=180
INTERVAL=5

ALL_HEALTHY=true
for svc in "${SERVICES[@]}"; do
  echo -n "      ${svc}: "
  ELAPSED=0
  while [[ $ELAPSED -lt $MAX_WAIT ]]; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "missing")
    if [[ "$HEALTH" == "healthy" ]]; then
      echo "healthy"
      break
    fi
    sleep "$INTERVAL"
    ELAPSED=$((ELAPSED + INTERVAL))
  done
  if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    echo "TIMEOUT (${HEALTH})"
    ALL_HEALTHY=false
  fi
done

if [[ "$ALL_HEALTHY" != "true" ]]; then
  echo ""
  echo "WARNING: Some services did not become healthy."
  echo "Check logs: docker compose logs"
fi
echo ""

# ── 6. Run DB migrations and seed ───────────────────────────────
echo "[6/6] Running database migrations..."
docker compose exec -T api alembic upgrade head
echo "      Migrations complete."

if [[ "$SEED_KB" == "true" ]]; then
  echo ""
  echo "      Seeding knowledge base..."
  docker compose exec -T api python -m api.rag.indexer --full-reindex 2>/dev/null || {
    echo "      WARNING: Knowledge base seeding failed or indexer not available."
    echo "      You can trigger this later via the API."
  }
fi
echo ""

# ── Print access URLs ────────────────────────────────────────────
source "${COMPOSE_DIR}/.env" 2>/dev/null || true
API_PORT="${API_PORT:-8000}"
NGINX_HTTP="${NGINX_HTTP_PORT:-80}"

echo "============================================================"
echo "  Setup complete!"
echo ""
echo "  API:        http://localhost:${API_PORT}"
echo "  Nginx:      http://localhost:${NGINX_HTTP}"
echo "  Health:     http://localhost:${API_PORT}/health"
echo "  API Docs:   http://localhost:${API_PORT}/docs"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f api          # API logs"
echo "    docker compose ps                   # Service status"
echo "    docker compose down                 # Stop all"
echo "    docker compose down -v              # Stop + delete data"
echo "============================================================"
