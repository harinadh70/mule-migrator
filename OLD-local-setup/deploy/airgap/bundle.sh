#!/usr/bin/env bash
# =================================================================
#  Air-Gap Bundle Builder
#
#  Pulls all required Docker images, downloads the embedding model,
#  creates a Qdrant knowledge-base snapshot, and packages everything
#  into a single tarball for offline installation.
#
#  Usage:  ./bundle.sh [--output DIR] [--tag VERSION]
# =================================================================
set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/dist"
APP_TAG="1.0.0"
BUNDLE_NAME="migrator-airgap-bundle"

# ── Parse args ───────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    --tag)    APP_TAG="$2";    shift 2 ;;
    -h|--help)
      echo "Usage: $0 [--output DIR] [--tag VERSION]"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

# ── Image list ───────────────────────────────────────────────────
APP_IMAGE="mulesoft-to-springboot-migrator:${APP_TAG}"
IMAGES=(
  "${APP_IMAGE}"
  "postgres:16-alpine"
  "redis:7-alpine"
  "qdrant/qdrant:latest"
  "nginx:alpine"
)

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

echo "============================================================"
echo "  Air-Gap Bundle Builder"
echo "  App tag : ${APP_TAG}"
echo "  Output  : ${OUTPUT_DIR}"
echo "============================================================"
echo ""

mkdir -p "${OUTPUT_DIR}"
IMAGES_DIR="${WORK_DIR}/images"
MODELS_DIR="${WORK_DIR}/models"
SNAPSHOTS_DIR="${WORK_DIR}/snapshots"
mkdir -p "${IMAGES_DIR}" "${MODELS_DIR}" "${SNAPSHOTS_DIR}"

# ── 1. Build application image (if not already present) ──────────
echo "[1/5] Building application image..."
if ! docker image inspect "${APP_IMAGE}" >/dev/null 2>&1; then
  docker build -t "${APP_IMAGE}" -f "${ROOT_DIR}/Dockerfile" "${ROOT_DIR}"
fi
echo "      Done."

# ── 2. Pull infrastructure images ────────────────────────────────
echo "[2/5] Pulling infrastructure images..."
for img in "${IMAGES[@]}"; do
  if [[ "$img" == "$APP_IMAGE" ]]; then
    continue  # already built above
  fi
  echo "      Pulling ${img}..."
  docker pull "${img}"
done
echo "      Done."

# ── 3. Save images as tar files ─────────────────────────────────
echo "[3/5] Saving Docker images to tar files..."
for img in "${IMAGES[@]}"; do
  SAFE_NAME=$(echo "$img" | tr '/:' '_')
  TAR_FILE="${IMAGES_DIR}/${SAFE_NAME}.tar"
  echo "      Saving ${img} -> $(basename ${TAR_FILE})..."
  docker save -o "${TAR_FILE}" "${img}"
done
echo "      Done."

# ── 4. Download sentence-transformers model ──────────────────────
echo "[4/5] Downloading sentence-transformers embedding model..."
python3 -c "
from sentence_transformers import SentenceTransformer
import shutil, os

model = SentenceTransformer('all-MiniLM-L6-v2')
cache_dir = model._model_card_vars.get('model_name_or_path', '')
# Save model to the bundle
model.save('${MODELS_DIR}/all-MiniLM-L6-v2')
print('      Model saved to bundle.')
" 2>/dev/null || {
  echo "      WARNING: Could not download model via Python."
  echo "      Attempting download via huggingface-cli..."
  if command -v huggingface-cli >/dev/null 2>&1; then
    huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 \
      --local-dir "${MODELS_DIR}/all-MiniLM-L6-v2"
  else
    echo "      SKIP: Install sentence-transformers or huggingface-cli to include the model."
  fi
}
echo "      Done."

# ── 5. Create Qdrant snapshot (if running locally) ───────────────
echo "[5/5] Creating Qdrant knowledge-base snapshot..."
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
COLLECTION="${QDRANT_COLLECTION:-mulesoft_knowledge}"

if curl -sf "${QDRANT_URL}/healthz" >/dev/null 2>&1; then
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
    curl -sf -o "${SNAPSHOTS_DIR}/${SNAPSHOT_NAME}" \
      "${QDRANT_URL}/collections/${COLLECTION}/snapshots/${SNAPSHOT_NAME}"
    echo "      Snapshot saved: ${SNAPSHOT_NAME}"
  else
    echo "      WARNING: Could not create Qdrant snapshot (collection may not exist)."
  fi
else
  echo "      SKIP: Qdrant not reachable at ${QDRANT_URL}."
  echo "      Start the platform first to include a knowledge-base snapshot."
fi
echo "      Done."

# ── Package everything ───────────────────────────────────────────
echo ""
echo "Packaging air-gap bundle..."

# Copy install scripts and compose files
cp "${SCRIPT_DIR}/install.sh" "${WORK_DIR}/"
cp "${SCRIPT_DIR}/README.md" "${WORK_DIR}/" 2>/dev/null || true
cp -r "${ROOT_DIR}/deploy/docker-compose" "${WORK_DIR}/docker-compose"
cp "${ROOT_DIR}/Dockerfile" "${WORK_DIR}/"

# Create the tarball
BUNDLE_FILE="${OUTPUT_DIR}/${BUNDLE_NAME}-${APP_TAG}.tar.gz"
tar -czf "${BUNDLE_FILE}" -C "${WORK_DIR}" .

BUNDLE_SIZE=$(du -sh "${BUNDLE_FILE}" | cut -f1)

echo ""
echo "============================================================"
echo "  Air-gap bundle created successfully!"
echo ""
echo "  File : ${BUNDLE_FILE}"
echo "  Size : ${BUNDLE_SIZE}"
echo ""
echo "  Transfer this file to the target host and run:"
echo ""
echo "    tar xzf $(basename ${BUNDLE_FILE})"
echo "    chmod +x install.sh"
echo "    ./install.sh"
echo "============================================================"
