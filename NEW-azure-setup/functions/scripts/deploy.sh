#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  Quick re-deployment script for code-only changes.
#
#  This script deploys ONLY the Function App code (no infrastructure
#  changes).  Use setup.sh for initial deployment or infrastructure
#  changes.
#
#  Usage:
#    ./deploy.sh                         # auto-detect from Terraform state
#    ./deploy.sh --app-name <name> --rg <resource-group>
#    ./deploy.sh --frontend              # also deploy frontend SWA
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="${SCRIPT_DIR}/../terraform"
FUNC_DIR="${SCRIPT_DIR}/.."

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()   { echo -e "${BLUE}[INFO]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }

# Parse args
FUNC_APP_NAME=""
RG_NAME=""
DEPLOY_FRONTEND=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --app-name|-a)  FUNC_APP_NAME="$2"; shift 2 ;;
        --rg|-g)        RG_NAME="$2"; shift 2 ;;
        --frontend|-f)  DEPLOY_FRONTEND=true; shift ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --app-name, -a   Function App name"
            echo "  --rg, -g         Resource group name"
            echo "  --frontend, -f   Also deploy the frontend SWA"
            echo "  --help, -h       Show this help"
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

# Auto-detect from Terraform if not provided
if [ -z "$FUNC_APP_NAME" ]; then
    log "Reading Function App name from Terraform state..."
    cd "$TF_DIR"
    FUNC_APP_NAME=$(terraform output -raw function_app_name 2>/dev/null || true)
    RG_NAME=$(terraform output -raw resource_group_name 2>/dev/null || true)
    cd "$SCRIPT_DIR"

    if [ -z "$FUNC_APP_NAME" ]; then
        error "Cannot determine Function App name. Pass --app-name or run setup.sh first."
        exit 1
    fi
fi

log "Deploying to: $FUNC_APP_NAME"
echo ""

# ---------------------------------------------------------------------------
#  Deploy Function App
# ---------------------------------------------------------------------------
log "Installing Python dependencies..."
cd "$FUNC_DIR"
pip install --target=".python_packages/lib/site-packages" -r requirements.txt --quiet 2>/dev/null

log "Publishing Function App..."
func azure functionapp publish "$FUNC_APP_NAME" --python

FUNC_URL="https://${FUNC_APP_NAME}.azurewebsites.net"
ok "Function App deployed: $FUNC_URL"

# ---------------------------------------------------------------------------
#  Health check
# ---------------------------------------------------------------------------
log "Running health check..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${FUNC_URL}/api/health" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    ok "Health check passed (HTTP $HTTP_CODE)"
else
    warn "Health check returned HTTP $HTTP_CODE (may take a moment to warm up)"
fi

# ---------------------------------------------------------------------------
#  Deploy frontend (optional)
# ---------------------------------------------------------------------------
if [ "$DEPLOY_FRONTEND" = true ]; then
    log "Deploying frontend..."
    cd "$TF_DIR"
    SWA_NAME=$(terraform output -raw static_web_app_name 2>/dev/null || true)
    SWA_TOKEN=$(terraform output -raw static_web_app_api_key 2>/dev/null || true)
    cd "$SCRIPT_DIR"

    FRONTEND_DIR="${SCRIPT_DIR}/../../../frontend"
    if [ -d "$FRONTEND_DIR" ]; then
        cd "$FRONTEND_DIR"
        if [ -f "package.json" ]; then
            npm run build 2>/dev/null || yarn build 2>/dev/null || warn "Frontend build failed"
            if [ -n "$SWA_TOKEN" ]; then
                npx @azure/static-web-apps-cli deploy \
                    --deployment-token "$SWA_TOKEN" \
                    --app-location "./dist" \
                    --output-location "" 2>/dev/null || warn "SWA deploy failed"
                ok "Frontend deployed to SWA"
            else
                warn "No SWA token found. Deploy frontend manually."
            fi
        fi
        cd "$SCRIPT_DIR"
    else
        warn "Frontend directory not found at $FRONTEND_DIR"
    fi
fi

echo ""
echo -e "${GREEN}Deployment complete.${NC}"
echo -e "  API:     ${BLUE}${FUNC_URL}/api/v2${NC}"
echo -e "  Health:  ${BLUE}${FUNC_URL}/api/health${NC}"
