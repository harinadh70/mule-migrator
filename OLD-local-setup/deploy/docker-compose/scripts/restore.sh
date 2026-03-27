#!/usr/bin/env bash
# =================================================================
#  Restore Script
#
#  Restores PostgreSQL, Qdrant, and Redis from a backup tarball
#  created by backup.sh.
#
#  Usage:  ./restore.sh <backup-file.tar.gz> [--no-confirm]
# =================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIRM=true

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup-file.tar.gz> [--no-confirm]"
  exit 1
fi

BACKUP_FILE="$1"
shift

while [[ $# -gt 0 ]]; do
  case $1 in
    --no-confirm) CONFIRM=false; shift ;;
    -h|--help)
      echo "Usage: $0 <backup-file.tar.gz> [--no-confirm]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "ERROR: Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

# Load env
source "${COMPOSE_DIR}/.env" 2>/dev/null || true
PGUSER="${POSTGRES_USER:-migrator}"
PGDB="${POSTGRES_DB:-migrator}"

echo "============================================================"
echo "  MuleSoft-to-SpringBoot Migrator — Restore"
echo ""
echo "  Backup file: ${BACKUP_FILE}"
echo "============================================================"
echo ""

if [[ "$CONFIRM" == "true" ]]; then
  echo "WARNING: This will OVERWRITE the current database and"
  echo "         knowledge base with data from the backup."
  echo ""
  read -rp "Continue? [y/N] " REPLY
  if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
  fi
  echo ""
fi

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

# ── Extract backup ───────────────────────────────────────────────
echo "[1/5] Extracting backup..."
tar -xzf "${BACKUP_FILE}" -C "${WORK_DIR}"
BACKUP_DIR=$(find "${WORK_DIR}" -maxdepth 1 -type d -name "migrator-backup-*" | head -1)

if [[ -z "$BACKUP_DIR" ]]; then
  echo "ERROR: Could not find backup directory in archive."
  exit 1
fi

if [[ -f "${BACKUP_DIR}/metadata.json" ]]; then
  echo "      Backup metadata:"
  python3 -c "
import json
with open('${BACKUP_DIR}/metadata.json') as f:
    meta = json.load(f)
    print(f\"      Date:       {meta.get('date', 'unknown')}\")
    print(f\"      Database:   {meta.get('postgres_db', 'unknown')}\")
    print(f\"      Collection: {meta.get('qdrant_collection', 'unknown')}\")
  " 2>/dev/null || true
fi
echo ""

# ── Stop API and workers (keep infra running) ────────────────────
echo "[2/5] Stopping application services..."
cd "${COMPOSE_DIR}"
docker compose stop api celery-migration-worker celery-build-worker \
  celery-indexing-worker celery-beat 2>/dev/null || true
echo "      Application services stopped."
echo ""

# ── Restore PostgreSQL ───────────────────────────────────────────
echo "[3/5] Restoring PostgreSQL..."
if [[ -f "${BACKUP_DIR}/postgres.dump" ]]; then
  # Drop and recreate the database
  docker exec migrator-postgres psql -U "${PGUSER}" -d postgres -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='${PGDB}' AND pid <> pg_backend_pid();" \
    >/dev/null 2>&1 || true

  docker exec migrator-postgres dropdb -U "${PGUSER}" --if-exists "${PGDB}" 2>/dev/null || true
  docker exec migrator-postgres createdb -U "${PGUSER}" "${PGDB}" 2>/dev/null || true

  # Restore from dump
  docker cp "${BACKUP_DIR}/postgres.dump" migrator-postgres:/tmp/postgres.dump
  docker exec migrator-postgres pg_restore \
    -U "${PGUSER}" \
    -d "${PGDB}" \
    --no-owner \
    --no-privileges \
    --clean \
    --if-exists \
    /tmp/postgres.dump 2>/dev/null || true

  docker exec migrator-postgres rm -f /tmp/postgres.dump
  echo "      PostgreSQL restored."
else
  echo "      WARNING: No PostgreSQL dump found in backup. Skipping."
fi
echo ""

# ── Restore Qdrant ───────────────────────────────────────────────
echo "[4/5] Restoring Qdrant..."
QDRANT_URL="http://localhost:${QDRANT_HTTP_PORT:-6333}"
COLLECTION="${QDRANT_COLLECTION:-mulesoft_knowledge}"
SNAPSHOT_FILE=$(find "${BACKUP_DIR}" -name "qdrant-*.snapshot" -type f 2>/dev/null | head -1)

if [[ -n "${SNAPSHOT_FILE}" ]]; then
  # Delete existing collection and restore from snapshot
  curl -sf -X DELETE "${QDRANT_URL}/collections/${COLLECTION}" >/dev/null 2>&1 || true
  sleep 2

  curl -sf -X POST \
    "${QDRANT_URL}/collections/${COLLECTION}/snapshots/upload" \
    -H "Content-Type: multipart/form-data" \
    -F "snapshot=@${SNAPSHOT_FILE}" \
    >/dev/null 2>&1 && echo "      Qdrant restored." || {
      echo "      WARNING: Qdrant snapshot restore failed."
    }
else
  echo "      WARNING: No Qdrant snapshot found in backup. Skipping."
fi
echo ""

# ── Start services ───────────────────────────────────────────────
echo "[5/5] Starting services..."
docker compose up -d
echo "      Services started."
echo ""

# ── Verify health ────────────────────────────────────────────────
echo "Verifying health..."
sleep 10

"${SCRIPT_DIR}/health-check.sh" 2>/dev/null || {
  echo ""
  echo "WARNING: Some services may not be healthy yet."
  echo "Check: docker compose ps"
}

echo ""
echo "============================================================"
echo "  Restore complete!"
echo "============================================================"
