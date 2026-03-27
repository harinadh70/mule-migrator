#!/usr/bin/env bash
# =================================================================
#  Backup Script
#
#  Creates a timestamped backup of PostgreSQL, Qdrant snapshots,
#  and Redis data. Packages everything into a tarball.
#
#  Usage:  ./backup.sh [--output DIR]
# =================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="${COMPOSE_DIR}/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="migrator-backup-${TIMESTAMP}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--output DIR]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

BACKUP_DIR="${WORK_DIR}/${BACKUP_NAME}"
mkdir -p "${BACKUP_DIR}" "${OUTPUT_DIR}"

# Load env for connection details
source "${COMPOSE_DIR}/.env" 2>/dev/null || true

echo "============================================================"
echo "  MuleSoft-to-SpringBoot Migrator — Backup"
echo "  Timestamp: ${TIMESTAMP}"
echo "============================================================"
echo ""

# ── 1. PostgreSQL dump ───────────────────────────────────────────
echo "[1/3] Backing up PostgreSQL..."
PGUSER="${POSTGRES_USER:-migrator}"
PGDB="${POSTGRES_DB:-migrator}"

docker exec migrator-postgres pg_dump \
  -U "${PGUSER}" \
  -d "${PGDB}" \
  --format=custom \
  --compress=9 \
  --verbose \
  > "${BACKUP_DIR}/postgres.dump" 2>/dev/null

PG_SIZE=$(du -sh "${BACKUP_DIR}/postgres.dump" | cut -f1)
echo "      PostgreSQL dump: ${PG_SIZE}"

# ── 2. Qdrant snapshot ──────────────────────────────────────────
echo "[2/3] Backing up Qdrant..."
QDRANT_URL="http://localhost:${QDRANT_HTTP_PORT:-6333}"
COLLECTION="${QDRANT_COLLECTION:-mulesoft_knowledge}"

# Create snapshot via API
SNAPSHOT_RESP=$(curl -sf -X POST \
  "${QDRANT_URL}/collections/${COLLECTION}/snapshots" 2>/dev/null || echo "{}")

SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESP" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('result', {}).get('name', ''))
except: pass
" 2>/dev/null)

if [[ -n "$SNAPSHOT_NAME" ]]; then
  curl -sf -o "${BACKUP_DIR}/qdrant-${COLLECTION}.snapshot" \
    "${QDRANT_URL}/collections/${COLLECTION}/snapshots/${SNAPSHOT_NAME}"
  QD_SIZE=$(du -sh "${BACKUP_DIR}/qdrant-${COLLECTION}.snapshot" | cut -f1)
  echo "      Qdrant snapshot: ${QD_SIZE}"

  # Clean up the snapshot from Qdrant server
  curl -sf -X DELETE \
    "${QDRANT_URL}/collections/${COLLECTION}/snapshots/${SNAPSHOT_NAME}" \
    >/dev/null 2>&1 || true
else
  echo "      WARNING: Could not create Qdrant snapshot."
fi

# ── 3. Redis BGSAVE ─────────────────────────────────────────────
echo "[3/3] Backing up Redis..."
docker exec migrator-redis redis-cli BGSAVE >/dev/null 2>&1

# Wait for BGSAVE to complete
for _ in $(seq 1 30); do
  BGSAVE_STATUS=$(docker exec migrator-redis redis-cli LASTSAVE 2>/dev/null)
  sleep 1
  BGSAVE_STATUS_NEW=$(docker exec migrator-redis redis-cli LASTSAVE 2>/dev/null)
  if [[ "$BGSAVE_STATUS" != "$BGSAVE_STATUS_NEW" ]] || [[ -n "$BGSAVE_STATUS" ]]; then
    break
  fi
done

docker cp migrator-redis:/data/dump.rdb "${BACKUP_DIR}/redis.rdb" 2>/dev/null || {
  docker cp migrator-redis:/data/appendonlydir "${BACKUP_DIR}/redis-aof" 2>/dev/null || {
    echo "      WARNING: Could not copy Redis data."
  }
}

if [[ -f "${BACKUP_DIR}/redis.rdb" ]]; then
  REDIS_SIZE=$(du -sh "${BACKUP_DIR}/redis.rdb" | cut -f1)
  echo "      Redis dump: ${REDIS_SIZE}"
fi

# ── Save metadata ────────────────────────────────────────────────
cat > "${BACKUP_DIR}/metadata.json" <<EOF
{
  "timestamp": "${TIMESTAMP}",
  "date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "postgres_user": "${PGUSER}",
  "postgres_db": "${PGDB}",
  "qdrant_collection": "${COLLECTION}",
  "version": "1.0.0"
}
EOF

# ── Package ──────────────────────────────────────────────────────
echo ""
echo "Packaging backup..."
BACKUP_FILE="${OUTPUT_DIR}/${BACKUP_NAME}.tar.gz"
tar -czf "${BACKUP_FILE}" -C "${WORK_DIR}" "${BACKUP_NAME}"

TOTAL_SIZE=$(du -sh "${BACKUP_FILE}" | cut -f1)

echo ""
echo "============================================================"
echo "  Backup complete!"
echo ""
echo "  File : ${BACKUP_FILE}"
echo "  Size : ${TOTAL_SIZE}"
echo ""
echo "  Restore with:"
echo "    ./restore.sh ${BACKUP_FILE}"
echo "============================================================"
