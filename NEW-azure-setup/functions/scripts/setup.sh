#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
#  One-command setup for MuleSoft-to-SpringBoot Migrator (Azure Functions)
#
#  Usage:
#    ./setup.sh                         # interactive (prompts for sub ID)
#    ./setup.sh --subscription <id>     # non-interactive
#    ./setup.sh --destroy               # tear down everything
#
#  Prerequisites: az, terraform, func (Azure Functions Core Tools)
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

# ---------------------------------------------------------------------------
#  Prerequisite checks
# ---------------------------------------------------------------------------
check_prerequisites() {
    local missing=0

    log "Checking prerequisites..."

    if ! command -v az &>/dev/null; then
        error "Azure CLI (az) not found. Install: https://aka.ms/installazurecli"
        missing=1
    else
        ok "Azure CLI $(az version --output tsv --query '\"azure-cli\"' 2>/dev/null || echo 'found')"
    fi

    if ! command -v terraform &>/dev/null; then
        error "Terraform not found. Install: https://developer.hashicorp.com/terraform/install"
        missing=1
    else
        ok "Terraform $(terraform version -json 2>/dev/null | python3 -c 'import json,sys; print(json.load(sys.stdin)["terraform_version"])' 2>/dev/null || echo 'found')"
    fi

    if ! command -v func &>/dev/null; then
        error "Azure Functions Core Tools (func) not found. Install: https://aka.ms/azfunc-install"
        missing=1
    else
        ok "Azure Functions Core Tools $(func --version 2>/dev/null || echo 'found')"
    fi

    if ! command -v python3 &>/dev/null; then
        error "Python 3 not found."
        missing=1
    else
        ok "Python $(python3 --version 2>/dev/null)"
    fi

    if [ "$missing" -ne 0 ]; then
        error "Missing prerequisites. Please install them and retry."
        exit 1
    fi
    echo ""
}

# ---------------------------------------------------------------------------
#  Azure login
# ---------------------------------------------------------------------------
ensure_azure_login() {
    log "Checking Azure login status..."
    if ! az account show &>/dev/null; then
        log "Not logged in. Starting Azure login..."
        az login
    fi
    ok "Logged in as $(az account show --query user.name -o tsv 2>/dev/null)"
    echo ""
}

# ---------------------------------------------------------------------------
#  Parse arguments
# ---------------------------------------------------------------------------
SUBSCRIPTION_ID=""
DESTROY=false
ENVIRONMENT="prod"
ALERT_EMAIL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --subscription|-s)  SUBSCRIPTION_ID="$2"; shift 2 ;;
        --environment|-e)   ENVIRONMENT="$2"; shift 2 ;;
        --alert-email)      ALERT_EMAIL="$2"; shift 2 ;;
        --destroy)          DESTROY=true; shift ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --subscription, -s  Azure subscription ID"
            echo "  --environment, -e   Environment (dev/staging/prod, default: prod)"
            echo "  --alert-email       Email for alert notifications"
            echo "  --destroy           Tear down all resources"
            echo "  --help, -h          Show this help"
            exit 0
            ;;
        *) error "Unknown option: $1"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------
check_prerequisites
ensure_azure_login

# Get subscription if not provided
if [ -z "$SUBSCRIPTION_ID" ]; then
    log "Available subscriptions:"
    az account list --output table --query "[].{Name:name, SubscriptionId:id, State:state}"
    echo ""
    read -rp "Enter subscription ID: " SUBSCRIPTION_ID
fi

az account set --subscription "$SUBSCRIPTION_ID"
ok "Using subscription: $(az account show --query name -o tsv)"
echo ""

# ---------------------------------------------------------------------------
#  Terraform state storage (one-time bootstrap)
# ---------------------------------------------------------------------------
bootstrap_tfstate() {
    log "Ensuring Terraform state storage exists..."
    if ! az group show --name "tfstate-rg" &>/dev/null; then
        az group create --name "tfstate-rg" --location "eastasia" --output none
        az storage account create \
            --name "tfstatemigrator" \
            --resource-group "tfstate-rg" \
            --location "eastasia" \
            --sku Standard_LRS \
            --output none
        az storage container create \
            --name "tfstate" \
            --account-name "tfstatemigrator" \
            --output none
        ok "Terraform state storage created"
    else
        ok "Terraform state storage already exists"
    fi
    echo ""
}

# ---------------------------------------------------------------------------
#  Terraform
# ---------------------------------------------------------------------------
run_terraform() {
    log "Initialising Terraform..."
    cd "$TF_DIR"

    terraform init -upgrade

    if [ "$DESTROY" = true ]; then
        warn "Destroying all resources..."
        terraform destroy \
            -var="subscription_id=$SUBSCRIPTION_ID" \
            -var="environment=$ENVIRONMENT" \
            -auto-approve
        ok "All resources destroyed."
        exit 0
    fi

    log "Planning Terraform changes..."
    terraform plan \
        -var="subscription_id=$SUBSCRIPTION_ID" \
        -var="environment=$ENVIRONMENT" \
        ${ALERT_EMAIL:+-var="alert_email=$ALERT_EMAIL"} \
        -out=tfplan

    echo ""
    read -rp "Apply the plan? (y/N): " CONFIRM
    if [[ "$CONFIRM" != [yY] ]]; then
        warn "Aborted."
        exit 0
    fi

    log "Applying Terraform..."
    terraform apply tfplan
    rm -f tfplan

    ok "Infrastructure deployed."
    echo ""

    # Export outputs
    FUNC_APP_NAME=$(terraform output -raw function_app_name)
    RG_NAME=$(terraform output -raw resource_group_name)
    FUNC_APP_URL=$(terraform output -raw function_app_url)
    SWA_URL=$(terraform output -raw static_web_app_url)
    SWA_NAME=$(terraform output -raw static_web_app_name)
    TENANT_ID=$(terraform output -raw azure_ad_tenant_id)
    CLIENT_ID=$(terraform output -raw azure_ad_client_id)

    cd "$SCRIPT_DIR"
}

# ---------------------------------------------------------------------------
#  Deploy Function App code
# ---------------------------------------------------------------------------
deploy_function_app() {
    log "Deploying Function App code..."
    cd "$FUNC_DIR"

    # Install dependencies
    if [ ! -d ".python_packages" ]; then
        log "Installing Python dependencies..."
        pip install --target=".python_packages/lib/site-packages" -r requirements.txt --quiet
    fi

    func azure functionapp publish "$FUNC_APP_NAME" --python

    ok "Function App deployed: $FUNC_APP_URL"
    echo ""
    cd "$SCRIPT_DIR"
}

# ---------------------------------------------------------------------------
#  Configure Azure AD auth on Function App
# ---------------------------------------------------------------------------
configure_auth() {
    log "Configuring Azure AD authentication on Function App..."
    az webapp auth microsoft update \
        --name "$FUNC_APP_NAME" \
        --resource-group "$RG_NAME" \
        --client-id "$CLIENT_ID" \
        --issuer "https://login.microsoftonline.com/$TENANT_ID/v2.0" \
        --allowed-audiences "api://$CLIENT_ID" \
        --output none 2>/dev/null || warn "Auth config may need manual setup via Azure Portal"

    ok "Azure AD auth configured"
    echo ""
}

# ---------------------------------------------------------------------------
#  Print summary
# ---------------------------------------------------------------------------
print_summary() {
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Deployment Complete!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  Function App URL:     ${BLUE}${FUNC_APP_URL}${NC}"
    echo -e "  Static Web App URL:   ${BLUE}${SWA_URL}${NC}"
    echo -e "  Health Check:         ${BLUE}${FUNC_APP_URL}/api/health${NC}"
    echo -e "  API Base:             ${BLUE}${FUNC_APP_URL}/api/v2${NC}"
    echo ""
    echo -e "  Azure AD Tenant:      ${TENANT_ID}"
    echo -e "  Azure AD Client ID:   ${CLIENT_ID}"
    echo ""
    echo -e "  Resource Group:       ${RG_NAME}"
    echo -e "  Function App:         ${FUNC_APP_NAME}"
    echo -e "  Static Web App:       ${SWA_NAME}"
    echo ""
    echo -e "  ${YELLOW}Next steps:${NC}"
    echo -e "  1. Deploy the frontend to the Static Web App"
    echo -e "  2. Configure CORS origins in the Function App settings"
    echo -e "  3. Add users to Azure AD app roles"
    echo -e "  4. Store GitHub PAT in Key Vault (optional)"
    echo ""
}

# ---------------------------------------------------------------------------
#  Execute
# ---------------------------------------------------------------------------
bootstrap_tfstate
run_terraform
deploy_function_app
configure_auth
print_summary
