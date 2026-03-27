# Azure Deployment — Standalone Package

This folder contains **all Azure-specific files** for deploying the MuleSoft-to-SpringBoot Agentic AI Platform on Azure Cloud. No existing project files are modified.

## Folder Structure

```
azure-deployment/
├── terraform/              # Azure Infrastructure as Code
│   ├── providers.tf        # Azure RM, Kubernetes, Helm providers
│   ├── variables.tf        # Configurable variables (region, SKUs)
│   ├── main.tf             # Resource group, ACR, Key Vault
│   ├── networking.tf       # VNet, subnets, NSGs, private endpoints
│   ├── aks.tf              # AKS cluster + App Gateway
│   ├── databases.tf        # PostgreSQL Flexible + Redis Cache
│   ├── openai.tf           # Azure OpenAI (GPT-4o + embeddings)
│   ├── monitoring.tf       # Log Analytics, App Insights, alerts
│   ├── outputs.tf          # Connection strings, endpoints
│   └── scripts/
│       ├── setup-azure.sh  # One-command initial setup
│       └── deploy.sh       # Subsequent deployments
├── helm/
│   └── values-azure.yaml   # Helm values override for Azure
├── api/                    # Backend enhancements
│   ├── telemetry.py        # OpenTelemetry + Azure Monitor
│   ├── llm/
│   │   └── azure_openai.py # Azure OpenAI provider (GPT-4o)
│   ├── auth/
│   │   └── azure_ad.py     # Azure Entra ID authentication
│   ├── middleware/
│   │   └── security_headers.py  # CSP, HSTS, X-Frame-Options
│   └── services/
│       └── xml_validator.py     # XXE prevention with defusedxml
├── frontend/
│   └── src/
│       ├── auth/
│       │   └── msalConfig.ts    # MSAL.js Azure AD config
│       └── components/
│           └── ErrorBoundary.tsx # React error boundary
├── tests/                  # Test suite
│   ├── conftest.py         # pytest fixtures
│   ├── test_health.py
│   ├── test_security_headers.py
│   ├── test_migrations_api.py
│   ├── test_xml_validator.py
│   └── test_path_traversal.py
├── azure-pipelines.yml     # Azure DevOps CI/CD pipeline
├── pytest.ini              # pytest configuration
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## How to Deploy to Azure

### Prerequisites
- Azure CLI (`az`) installed and logged in
- Terraform >= 1.6
- kubectl, helm, docker

### Step 1: Infrastructure Setup
```bash
cd azure-deployment/terraform/scripts
chmod +x setup-azure.sh deploy.sh
./setup-azure.sh
```

This creates all Azure resources (AKS, PostgreSQL, Redis, OpenAI, etc.) and deploys the app.

### Step 2: Subsequent Deployments
```bash
./deploy.sh                    # Build, push, deploy
./deploy.sh -t v1.2.3         # Deploy specific tag
./deploy.sh -s -t latest      # Skip build, just redeploy
./deploy.sh -m                # Include DB migrations
./deploy.sh -d                # Dry run
```

## How to Integrate with Existing Project

To use these files in the main project, copy them to the appropriate locations:

```bash
# Copy to project
cp -r azure-deployment/terraform/ deploy/azure/
cp azure-deployment/helm/values-azure.yaml deploy/helm/migrator-platform/
cp azure-deployment/api/telemetry.py api/
cp azure-deployment/api/llm/azure_openai.py api/llm/
cp azure-deployment/api/auth/azure_ad.py api/auth/
cp azure-deployment/api/middleware/security_headers.py api/middleware/
cp azure-deployment/api/services/xml_validator.py api/services/
cp azure-deployment/frontend/src/auth/msalConfig.ts frontend/src/auth/
cp azure-deployment/frontend/src/components/ErrorBoundary.tsx frontend/src/components/
cp -r azure-deployment/tests/ tests/
cp azure-deployment/azure-pipelines.yml .
cp azure-deployment/pytest.ini .
```

Then add these lines to `api/main.py`:
```python
# In lifespan startup:
from api.telemetry import init_telemetry
init_telemetry(settings)

# In create_app():
from api.middleware.security_headers import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)
```

And in `api/config.py`, add:
```python
class AzureSettings(BaseSettings):
    azure_ad_tenant_id: str = ""
    azure_ad_client_id: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
```

## Estimated Azure Costs

| Service | SKU | Monthly |
|---------|-----|---------|
| AKS (3x D2s_v3) | Standard | $300 |
| PostgreSQL Flexible | B2s, 32GB | $50 |
| Redis Cache | Standard C1 | $50 |
| Azure OpenAI | Pay-as-you-go | $50-200 |
| Container Registry | Basic | $5 |
| App Insights | Pay-as-you-go | $30 |
| Key Vault | Standard | $1 |
| App Gateway | Standard_v2 | $150 |
| **Total** | | **~$650-850/mo** |
