#!/usr/bin/env bash
# =============================================================================
# MuleSoft-to-SpringBoot Migrator - Subsequent Deployment Script
# =============================================================================
# Use this script for application updates after the initial setup.
# It builds new Docker images, pushes them to ACR, and performs
# a Helm upgrade with health verification.
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

IMAGE_TAG="${IMAGE_TAG:-$(git -C "$PROJECT_ROOT" rev-parse --short HEAD 2>/dev/null || echo "latest")}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------
log_info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $*"; }

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -t, --tag TAG        Docker image tag (default: git short SHA or 'latest')"
    echo "  -s, --skip-build     Skip Docker build, only deploy"
    echo "  -i, --images IMAGES  Comma-separated list of images to build (default: api,worker,frontend)"
    echo "  -m, --migrate        Run database migrations after deploy"
    echo "  -d, --dry-run        Show what would be done without executing"
    echo "  -h, --help           Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Build all, deploy with git SHA tag"
    echo "  $0 -t v1.2.3               # Build all, deploy with specific tag"
    echo "  $0 -i api,worker -m        # Build api+worker, deploy, run migrations"
    echo "  $0 -s -t v1.2.3            # Skip build, just deploy tag v1.2.3"
    exit 0
}

# -----------------------------------------------------------------------------
# Parse Arguments
# -----------------------------------------------------------------------------
SKIP_BUILD=false
RUN_MIGRATE=false
DRY_RUN=false
IMAGES="api,worker,frontend"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -t|--tag)      IMAGE_TAG="$2"; shift 2 ;;
        -s|--skip-build) SKIP_BUILD=true; shift ;;
        -i|--images)   IMAGES="$2"; shift 2 ;;
        -m|--migrate)  RUN_MIGRATE=true; shift ;;
        -d|--dry-run)  DRY_RUN=true; shift ;;
        -h|--help)     usage ;;
        *)             log_error "Unknown option: $1"; usage ;;
    esac
done

IFS=',' read -ra IMAGE_LIST <<< "$IMAGES"

# -----------------------------------------------------------------------------
# Step 1: Get Terraform Outputs
# -----------------------------------------------------------------------------
get_config() {
    log_info "Reading Terraform outputs..."
    cd "$DEPLOY_DIR"

    ACR_SERVER=$(terraform output -raw acr_login_server)
    AKS_CLUSTER=$(terraform output -raw aks_cluster_name)
    RG_NAME=$(terraform output -raw resource_group_name)
    POSTGRES_FQDN=$(terraform output -raw postgres_fqdn)
    REDIS_HOST=$(terraform output -raw redis_hostname)
    REDIS_PORT=$(terraform output -raw redis_ssl_port)
    OPENAI_ENDPOINT=$(terraform output -raw openai_endpoint)
    KEYVAULT_NAME=$(terraform output -raw keyvault_name)
    APPINSIGHTS_KEY=$(terraform output -json appinsights_instrumentation_key | tr -d '"')

    log_success "Configuration loaded."
    log_info "  ACR:   ${ACR_SERVER}"
    log_info "  AKS:   ${AKS_CLUSTER}"
    log_info "  Tag:   ${IMAGE_TAG}"
}

# -----------------------------------------------------------------------------
# Step 2: Build Docker Images
# -----------------------------------------------------------------------------
build_images() {
    if [[ "$SKIP_BUILD" == "true" ]]; then
        log_info "Skipping Docker build (--skip-build)."
        return 0
    fi

    log_info "Building Docker images (tag: ${IMAGE_TAG})..."
    cd "$PROJECT_ROOT"

    for image in "${IMAGE_LIST[@]}"; do
        local dockerfile="docker/Dockerfile.${image}"
        local full_tag="${ACR_SERVER}/migrator-${image}:${IMAGE_TAG}"

        if [[ ! -f "$dockerfile" ]]; then
            log_warn "Dockerfile not found: $dockerfile (skipping $image)"
            continue
        fi

        if [[ "$DRY_RUN" == "true" ]]; then
            log_info "[DRY RUN] Would build: docker build -t ${full_tag} -f ${dockerfile} ."
        else
            log_info "Building ${image}..."
            docker build -t "$full_tag" -f "$dockerfile" .

            # Also tag as latest
            docker tag "$full_tag" "${ACR_SERVER}/migrator-${image}:latest"
            log_success "${image} built: ${full_tag}"
        fi
    done
}

# -----------------------------------------------------------------------------
# Step 3: Push Docker Images to ACR
# -----------------------------------------------------------------------------
push_images() {
    if [[ "$SKIP_BUILD" == "true" ]]; then
        log_info "Skipping Docker push (--skip-build)."
        return 0
    fi

    log_info "Pushing Docker images to ACR..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would log in to ACR and push images."
        return 0
    fi

    az acr login --name "${ACR_SERVER%%.*}"

    for image in "${IMAGE_LIST[@]}"; do
        local full_tag="${ACR_SERVER}/migrator-${image}:${IMAGE_TAG}"
        local latest_tag="${ACR_SERVER}/migrator-${image}:latest"

        if docker image inspect "$full_tag" &>/dev/null; then
            log_info "Pushing ${full_tag}..."
            docker push "$full_tag"
            docker push "$latest_tag"
            log_success "${image} pushed."
        else
            log_warn "Image ${full_tag} not found locally (skipping push)."
        fi
    done
}

# -----------------------------------------------------------------------------
# Step 4: Helm Upgrade
# -----------------------------------------------------------------------------
helm_upgrade() {
    log_info "Deploying via Helm upgrade (release: ${HELM_RELEASE}, tag: ${IMAGE_TAG})..."
    cd "$DEPLOY_DIR"

    local helm_args=(
        upgrade --install "$HELM_RELEASE" "$HELM_CHART_DIR"
        --namespace "$NAMESPACE"
        --values "$VALUES_FILE"
        --set "global.imageRegistry=${ACR_SERVER}"
        --set "global.keyvaultName=${KEYVAULT_NAME}"
        --set "api.image.tag=${IMAGE_TAG}"
        --set "worker.image.tag=${IMAGE_TAG}"
        --set "frontend.image.tag=${IMAGE_TAG}"
        --set "postgresql.host=${POSTGRES_FQDN}"
        --set "postgresql.database=migrator"
        --set "redis.host=${REDIS_HOST}"
        --set "redis.port=${REDIS_PORT}"
        --set "openai.endpoint=${OPENAI_ENDPOINT}"
        --set "monitoring.appInsightsKey=${APPINSIGHTS_KEY}"
        --wait
        --timeout 10m
    )

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run: helm ${helm_args[*]}"
        helm "${helm_args[@]}" --dry-run
    else
        helm "${helm_args[@]}"
        log_success "Helm upgrade completed."
    fi
}

# -----------------------------------------------------------------------------
# Step 5: Run Migrations (optional)
# -----------------------------------------------------------------------------
run_migrations() {
    if [[ "$RUN_MIGRATE" != "true" ]]; then
        return 0
    fi

    log_info "Running database migrations..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run alembic upgrade head via k8s job."
        return 0
    fi

    # Delete old migration job if it exists
    kubectl delete job migrator-migration -n "$NAMESPACE" --ignore-not-found

    kubectl run migrator-migration \
        --namespace "$NAMESPACE" \
        --image="${ACR_SERVER}/migrator-api:${IMAGE_TAG}" \
        --restart=Never \
        --rm \
        --attach \
        --command -- alembic upgrade head

    log_success "Database migrations completed."
}

# -----------------------------------------------------------------------------
# Step 6: Verify Health
# -----------------------------------------------------------------------------
verify_health() {
    log_info "Verifying deployment health..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would verify pod and service health."
        return 0
    fi

    echo ""
    log_info "Pod Status:"
    kubectl get pods -n "$NAMESPACE" -o wide

    echo ""
    log_info "Service Status:"
    kubectl get svc -n "$NAMESPACE"

    echo ""
    log_info "Recent Events:"
    kubectl get events -n "$NAMESPACE" --sort-by='.lastTimestamp' | tail -10

    # Check rollout status for deployments
    echo ""
    log_info "Checking rollout status..."
    local -a deployments
    mapfile -t deployments < <(kubectl get deployments -n "$NAMESPACE" -o jsonpath='{.items[*].metadata.name}')

    local all_healthy=true
    for deployment in "${deployments[@]}"; do
        if [[ -z "$deployment" ]]; then continue; fi
        if kubectl rollout status deployment/"$deployment" -n "$NAMESPACE" --timeout=120s; then
            log_success "Deployment '$deployment' is healthy."
        else
            log_error "Deployment '$deployment' failed rollout check."
            all_healthy=false
        fi
    done

    # Health check via HTTP (if available)
    echo ""
    local appgw_ip
    appgw_ip=$(cd "$DEPLOY_DIR" && terraform output -raw application_gateway_public_ip 2>/dev/null || echo "")

    if [[ -n "$appgw_ip" ]]; then
        log_info "Running HTTP health check against http://${appgw_ip}/api/health..."
        local http_code
        http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://${appgw_ip}/api/health" --connect-timeout 10 || echo "000")

        if [[ "$http_code" == "200" ]]; then
            log_success "API health check passed (HTTP $http_code)."
        else
            log_warn "API health check returned HTTP $http_code (may still be starting)."
        fi
    fi

    echo ""
    if [[ "$all_healthy" == "true" ]]; then
        log_success "Deployment verification complete. All services healthy."
    else
        log_error "Some services are unhealthy. Review the output above."
        return 1
    fi
}

# =============================================================================
# Main Execution
# =============================================================================
main() {
    echo ""
    echo "============================================================================="
    echo "  MuleSoft-to-SpringBoot Migrator - Deploy (tag: ${IMAGE_TAG})"
    echo "============================================================================="
    echo ""

    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "DRY RUN mode enabled. No changes will be made."
        echo ""
    fi

    get_config
    echo ""

    build_images
    echo ""

    push_images
    echo ""

    helm_upgrade
    echo ""

    run_migrations
    echo ""

    verify_health

    echo ""
    log_success "Deployment complete! Tag: ${IMAGE_TAG}"
    echo ""
}

main "$@"
