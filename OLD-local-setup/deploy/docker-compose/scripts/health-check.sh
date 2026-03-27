#!/usr/bin/env bash
# =================================================================
#  Health Check Script
#
#  Checks the health of all platform services and prints a status
#  table. Exits 1 if any service is unhealthy.
#
#  Usage:  ./health-check.sh [--json]
# =================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
JSON_OUTPUT=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --json) JSON_OUTPUT=true; shift ;;
    -h|--help)
      echo "Usage: $0 [--json]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

source "${COMPOSE_DIR}/.env" 2>/dev/null || true

API_PORT="${API_PORT:-8000}"
QDRANT_PORT="${QDRANT_HTTP_PORT:-6333}"
REDIS_PORT="${REDIS_PORT:-6379}"

# ── Service definitions ──────────────────────────────────────────
declare -A SERVICES
SERVICES=(
  ["API"]="http://localhost:${API_PORT}/health"
  ["PostgreSQL"]="docker:migrator-postgres"
  ["Redis"]="docker:migrator-redis"
  ["Qdrant"]="http://localhost:${QDRANT_PORT}/healthz"
  ["Nginx"]="http://localhost:${NGINX_HTTP_PORT:-80}/health"
  ["Celery Migration"]="docker:migrator-celery-migration"
  ["Celery Build"]="docker:migrator-celery-build"
  ["Celery Indexing"]="docker:migrator-celery-indexing"
  ["Celery Beat"]="docker:migrator-celery-beat"
)

# Ordered list for consistent output
SERVICE_ORDER=(
  "API"
  "PostgreSQL"
  "Redis"
  "Qdrant"
  "Nginx"
  "Celery Migration"
  "Celery Build"
  "Celery Indexing"
  "Celery Beat"
)

ALL_HEALTHY=true
declare -A RESULTS

# ── Check each service ───────────────────────────────────────────
for svc in "${SERVICE_ORDER[@]}"; do
  CHECK="${SERVICES[$svc]}"

  if [[ "$CHECK" == docker:* ]]; then
    # Docker health check
    CONTAINER="${CHECK#docker:}"
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER" 2>/dev/null || echo "not found")
    RUNNING=$(docker inspect --format='{{.State.Running}}' "$CONTAINER" 2>/dev/null || echo "false")

    if [[ "$HEALTH" == "healthy" ]]; then
      RESULTS[$svc]="healthy"
    elif [[ "$RUNNING" == "true" && "$HEALTH" == "" ]]; then
      RESULTS[$svc]="running (no healthcheck)"
    elif [[ "$RUNNING" == "true" ]]; then
      RESULTS[$svc]="unhealthy (${HEALTH})"
      ALL_HEALTHY=false
    else
      RESULTS[$svc]="stopped"
      ALL_HEALTHY=false
    fi
  elif [[ "$CHECK" == http* ]]; then
    # HTTP health check
    HTTP_STATUS=$(curl -sf -o /dev/null -w '%{http_code}' --connect-timeout 5 "$CHECK" 2>/dev/null || echo "000")
    if [[ "$HTTP_STATUS" == "200" ]]; then
      RESULTS[$svc]="healthy (HTTP 200)"
    elif [[ "$HTTP_STATUS" == "000" ]]; then
      RESULTS[$svc]="unreachable"
      ALL_HEALTHY=false
    else
      RESULTS[$svc]="unhealthy (HTTP ${HTTP_STATUS})"
      ALL_HEALTHY=false
    fi
  fi
done

# ── Output ───────────────────────────────────────────────────────
if [[ "$JSON_OUTPUT" == "true" ]]; then
  echo "{"
  FIRST=true
  for svc in "${SERVICE_ORDER[@]}"; do
    if [[ "$FIRST" == "true" ]]; then
      FIRST=false
    else
      echo ","
    fi
    STATUS="${RESULTS[$svc]:-unknown}"
    IS_HEALTHY="true"
    if [[ "$STATUS" != *"healthy"* && "$STATUS" != *"running"* ]]; then
      IS_HEALTHY="false"
    fi
    printf '  "%s": {"status": "%s", "healthy": %s}' "$svc" "$STATUS" "$IS_HEALTHY"
  done
  echo ""
  echo "}"
else
  echo ""
  echo "============================================================"
  echo "  Platform Health Check"
  echo "============================================================"
  printf "  %-22s %s\n" "SERVICE" "STATUS"
  printf "  %-22s %s\n" "----------------------" "--------------------"

  for svc in "${SERVICE_ORDER[@]}"; do
    STATUS="${RESULTS[$svc]:-unknown}"
    if [[ "$STATUS" == *"healthy"* || "$STATUS" == *"running"* ]]; then
      ICON="OK"
    else
      ICON="FAIL"
    fi
    printf "  %-22s [%-4s] %s\n" "$svc" "$ICON" "$STATUS"
  done

  echo "  ---------------------- --------------------"

  if [[ "$ALL_HEALTHY" == "true" ]]; then
    echo "  All services healthy."
  else
    echo "  WARNING: One or more services are unhealthy."
  fi
  echo "============================================================"
fi

if [[ "$ALL_HEALTHY" != "true" ]]; then
  exit 1
fi
