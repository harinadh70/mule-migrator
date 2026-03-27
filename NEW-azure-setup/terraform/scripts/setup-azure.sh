#!/usr/bin/env bash
# =============================================================================
# MuleSoft-to-SpringBoot Migrator - Azure Initial Setup Script
# =============================================================================
# This script performs the full initial deployment of the migrator platform
# on Azure, including infrastructure provisioning, AKS configuration,
# and application deployment.
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$(dirname "$DEPLOY_DIR")")"

NAMESPACE="migrator"
HELM_RELEASE="migrator"
HELM_CHART_DIR="${PROJECT_ROOT}/deploy/helm/migrator"
VALUES_FILE="${PROJECT_ROOT}/deploy/helm/values-azure.yaml"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

check_command() {
    if ! command -v "$1" &>/dev/null; then
        log_error "$1 is not installed. Please install it first."
        return 1
    fi
    log_success "$1 is available ($(command -v "$1"))"
}

confirm() {
    local prompt="${1:-Continue?}"
    read -rp "$(echo -e "${YELLOW}${prompt} [y/N]: ${NC}")" response
    [[ "$response" =~ ^[Yy]$ ]]
}

# -----------------------------------------------------------------------------
# Step 1: Check Prerequisites
# -----------------------------------------------------------------------------
check_prerequisites() {
    log_info "Checking prerequisites..."
    echo ""

    local missing=0
    for cmd in az terraform kubectl helm docker; do
        if ! check_command "$cmd"; then
            missing=$((missing + 1))
        fi
    done

    echo ""
    if [[ $missing -gt 0 ]]; then
        log_error "$missing required tool(s) missing. Please install them and retry."
        exit 1
    fi

    log_success "All prerequisites satisfied."
}

# -----------------------------------------------------------------------------
# Step 2: Azure Login
# -----------------------------------------------------------------------------
azure_login() {
    log_info "Checking Azure CLI authentication..."

    if az account show &>/dev/null; then
        local account_name
        account_name=$(az account show --query 'name' -o tsv)
        local subscription_id
        subscription_id=$(az account show --query 'id' -o tsv)
        log_success "Already logged in to Azure."
        log_info "  Account:      $account_name"
        log_info "  Subscription: $subscription_id"
        echo ""

        if ! confirm "Use this subscription?"; then
            log_info "Opening Azure login..."
            az login
            az account list --output table
            read -rp "Enter subscription ID to use: " sub_id
            az account set --subscription "$sub_id"
        fi
    else
        log_info "Not logged in. Opening Azure login..."
        az login

        az account list --output table
        read -rp "Enter subscription ID to use: " sub_id
        az account set --subscription "$sub_id"
    fi

    echo ""
    log_success "Azure authentication configured."
}

# -----------------------------------------------------------------------------
# Step 3: Create Terraform State Backend
# -----------------------------------------------------------------------------
setup_terraform_backend() {
    log_info "Setting up Terraform remote state backend..."

    local rg_name="tfstate-rg"
    local sa_name="migratorterraformstate"
    local container_name="tfstate"
    local location="eastus"

    # Create resource group for state
    if ! az group show --name "$rg_name" &>/dev/null; then
        log_info "Creating resource group '$rg_name'..."
        az group create --name "$rg_name" --location "$location" --output none
    else
        log_info "Resource group '$rg_name' already exists."
    fi

    # Create storage account for state
    if ! az storage account show --name "$sa_name" --resource-group "$rg_name" &>/dev/null; then
        log_info "Creating storage account '$sa_name'..."
        az storage account create \
            --name "$sa_name" \
            --resource-group "$rg_name" \
            --location "$location" \
            --sku Standard_LRS \
            --encryption-services blob \
            --output none
    else
        log_info "Storage account '$sa_name' already exists."
    fi

    # Get storage account key
    local account_key
    account_key=$(az storage account keys list \
        --resource-group "$rg_name" \
        --account-name "$sa_name" \
        --query '[0].value' -o tsv)

    # Create blob container
    if ! az storage container show \
        --name "$container_name" \
        --account-name "$sa_name" \
        --account-key "$account_key" &>/dev/null; then
        log_info "Creating blob container '$container_name'..."
        az storage container create \
            --name "$container_name" \
            --account-name "$sa_name" \
            --account-key "$account_key" \
            --output none
    else
        log_info "Blob container '$container_name' already exists."
    fi

    log_success "Terraform backend ready."
}

# -----------------------------------------------------------------------------
# Step 4: Terraform Init, Plan, Apply
# -----------------------------------------------------------------------------
run_terraform() {
    log_info "Running Terraform..."
    cd "$DEPLOY_DIR"

    log_info "Initializing Terraform..."
    terraform init -upgrade

    echo ""
    log_info "Planning Terraform changes..."
    terraform plan -out=tfplan

    echo ""
    if confirm "Apply the Terraform plan?"; then
        log_info "Applying Terraform..."
        terraform apply tfplan
        rm -f tfplan
        log_success "Terraform apply completed."
    else
        log_warn "Terraform apply skipped."
        rm -f tfplan
        exit 0
    fi
}

# -----------------------------------------------------------------------------
# Step 5: Configure AKS Credentials
# -----------------------------------------------------------------------------
configure_aks() {
    log_info "Configuring AKS credentials..."
    cd "$DEPLOY_DIR"

    local rg_name
    rg_name=$(terraform output -raw resource_group_name)
    local aks_name
    aks_name=$(terraform output -raw aks_cluster_name)

    az aks get-credentials \
        --resource-group "$rg_name" \
        --name "$aks_name" \
        --overwrite-existing

    log_info "Verifying cluster connectivity..."
    kubectl cluster-info
    kubectl get nodes

    log_success "AKS credentials configured."
}

# -----------------------------------------------------------------------------
# Step 6: Create Kubernetes Namespace
# -----------------------------------------------------------------------------
create_namespace() {
    log_info "Creating Kubernetes namespace '$NAMESPACE'..."

    if kubectl get namespace "$NAMESPACE" &>/dev/null; then
        log_info "Namespace '$NAMESPACE' already exists."
    else
        kubectl create namespace "$NAMESPACE"
        log_success "Namespace '$NAMESPACE' created."
    fi

    # Label the namespace
    kubectl label namespace "$NAMESPACE" \
        app.kubernetes.io/managed-by=helm \
        app.kubernetes.io/part-of=migrator \
        --overwrite
}

# -----------------------------------------------------------------------------
# Step 7: Install NGINX Ingress Controller (optional, alongside AGIC)
# -----------------------------------------------------------------------------
install_nginx_ingress() {
    log_info "Installing NGINX Ingress Controller via Helm..."

    helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx 2>/dev/null || true
    helm repo update

    if helm status nginx-ingress -n ingress-nginx &>/dev/null; then
        log_info "NGINX Ingress already installed. Upgrading..."
    fi

    helm upgrade --install nginx-ingress ingress-nginx/ingress-nginx \
        --namespace ingress-nginx \
        --create-namespace \
        --set controller.replicaCount=2 \
        --set controller.nodeSelector."kubernetes\.io/os"=linux \
        --set controller.service.annotations."service\.beta\.kubernetes\.io/azure-load-balancer-health-probe-request-path"=/healthz \
        --set controller.service.externalTrafficPolicy=Local \
        --set defaultBackend.nodeSelector."kubernetes\.io/os"=linux \
        --wait \
        --timeout 5m

    log_success "NGINX Ingress Controller installed."

    # Wait for external IP
    log_info "Waiting for external IP assignment..."
    local retries=30
    local ip=""
    while [[ $retries -gt 0 && -z "$ip" ]]; do
        ip=$(kubectl get svc nginx-ingress-ingress-nginx-controller \
            -n ingress-nginx \
            -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || true)
        if [[ -z "$ip" ]]; then
            sleep 10
            retries=$((retries - 1))
        fi
    done

    if [[ -n "$ip" ]]; then
        log_success "NGINX Ingress external IP: $ip"
    else
        log_warn "External IP not yet assigned. Check later with: kubectl get svc -n ingress-nginx"
    fi
}

# -----------------------------------------------------------------------------
# Step 8: Push Docker Images to ACR
# -----------------------------------------------------------------------------
push_docker_images() {
    log_info "Building and pushing Docker images to ACR..."
    cd "$PROJECT_ROOT"

    local acr_server
    acr_server=$(cd "$DEPLOY_DIR" && terraform output -raw acr_login_server)

    log_info "Logging in to ACR ($acr_server)..."
    az acr login --name "${acr_server%%.*}"

    # Define images to build and push
    local -a images=("api" "worker" "frontend")

    for image in "${images[@]}"; do
        local dockerfile="docker/Dockerfile.${image}"
        local tag="${acr_server}/migrator-${image}:latest"

        if [[ -f "$dockerfile" ]]; then
            log_info "Building $image..."
            docker build -t "$tag" -f "$dockerfile" .
            log_info "Pushing $tag..."
            docker push "$tag"
            log_success "$image pushed to ACR."
        else
            log_warn "Dockerfile not found: $dockerfile (skipping)"
        fi
    done
}

# -----------------------------------------------------------------------------
# Step 9: Deploy Application via Helm
# -----------------------------------------------------------------------------
deploy_application() {
    log_info "Deploying migrator application via Helm..."
    cd "$DEPLOY_DIR"

    local acr_server
    acr_server=$(terraform output -raw acr_login_server)
    local postgres_fqdn
    postgres_fqdn=$(terraform output -raw postgres_fqdn)
    local redis_host
    redis_host=$(terraform output -raw redis_hostname)
    local redis_port
    redis_port=$(terraform output -raw redis_ssl_port)
    local openai_endpoint
    openai_endpoint=$(terraform output -raw openai_endpoint)
    local keyvault_name
    keyvault_name=$(terraform output -raw keyvault_name)
    local appinsights_key
    appinsights_key=$(terraform output -json appinsights_instrumentation_key | tr -d '"')

    helm upgrade --install "$HELM_RELEASE" "$HELM_CHART_DIR" \
        --namespace "$NAMESPACE" \
        --values "$VALUES_FILE" \
        --set global.imageRegistry="${acr_server}" \
        --set global.keyvaultName="${keyvault_name}" \
        --set api.image.tag="latest" \
        --set worker.image.tag="latest" \
        --set frontend.image.tag="latest" \
        --set postgresql.host="${postgres_fqdn}" \
        --set postgresql.database="migrator" \
        --set redis.host="${redis_host}" \
        --set redis.port="${redis_port}" \
        --set openai.endpoint="${openai_endpoint}" \
        --set monitoring.appInsightsKey="${appinsights_key}" \
        --wait \
        --timeout 10m

    log_success "Application deployed."
}

# -----------------------------------------------------------------------------
# Step 10: Run Database Migrations
# -----------------------------------------------------------------------------
run_migrations() {
    log_info "Running database migrations (Alembic)..."

    # Run migration as a Kubernetes Job
    kubectl run migrator-migration \
        --namespace "$NAMESPACE" \
        --image="$(cd "$DEPLOY_DIR" && terraform output -raw acr_login_server)/migrator-api:latest" \
        --restart=Never \
        --rm \
        --attach \
        --command -- alembic upgrade head

    log_success "Database migrations completed."
}

# -----------------------------------------------------------------------------
# Step 11: Print Access URLs & Summary
# -----------------------------------------------------------------------------
print_summary() {
    cd "$DEPLOY_DIR"

    local appgw_ip
    appgw_ip=$(terraform output -raw application_gateway_public_ip 2>/dev/null || echo "pending")
    local acr_server
    acr_server=$(terraform output -raw acr_login_server)
    local aks_name
    aks_name=$(terraform output -raw aks_cluster_name)
    local rg_name
    rg_name=$(terraform output -raw resource_group_name)
    local keyvault_uri
    keyvault_uri=$(terraform output -raw keyvault_uri)
    local openai_endpoint
    openai_endpoint=$(terraform output -raw openai_endpoint)

    echo ""
    echo "============================================================================="
    echo "  MuleSoft-to-SpringBoot Migrator - Deployment Summary"
    echo "============================================================================="
    echo ""
    echo "  Application URLs:"
    echo "  -----------------------------------------------------------------"
    echo "  Application Gateway:  http://${appgw_ip}"
    echo "  API Endpoint:         http://${appgw_ip}/api"
    echo "  Frontend:             http://${appgw_ip}"
    echo ""
    echo "  Infrastructure:"
    echo "  -----------------------------------------------------------------"
    echo "  Resource Group:       ${rg_name}"
    echo "  AKS Cluster:          ${aks_name}"
    echo "  ACR Login Server:     ${acr_server}"
    echo "  Key Vault:            ${keyvault_uri}"
    echo "  OpenAI Endpoint:      ${openai_endpoint}"
    echo ""
    echo "  Useful Commands:"
    echo "  -----------------------------------------------------------------"
    echo "  Get AKS credentials:  az aks get-credentials --resource-group ${rg_name} --name ${aks_name}"
    echo "  View pods:            kubectl get pods -n ${NAMESPACE}"
    echo "  View services:        kubectl get svc -n ${NAMESPACE}"
    echo "  View logs (api):      kubectl logs -n ${NAMESPACE} -l app=migrator-api -f"
    echo "  View logs (worker):   kubectl logs -n ${NAMESPACE} -l app=migrator-worker -f"
    echo "  ACR login:            az acr login --name ${acr_server%%.*}"
    echo "  Terraform outputs:    cd deploy/azure && terraform output"
    echo ""
    echo "============================================================================="
    echo ""
}

# =============================================================================
# Main Execution
# =============================================================================
main() {
    echo ""
    echo "============================================================================="
    echo "  MuleSoft-to-SpringBoot Migrator - Azure Setup"
    echo "============================================================================="
    echo ""

    check_prerequisites
    echo ""

    azure_login
    echo ""

    setup_terraform_backend
    echo ""

    run_terraform
    echo ""

    configure_aks
    echo ""

    create_namespace
    echo ""

    install_nginx_ingress
    echo ""

    push_docker_images
    echo ""

    deploy_application
    echo ""

    run_migrations
    echo ""

    print_summary
}

main "$@"
