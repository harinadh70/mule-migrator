# MuleSoft-to-SpringBoot Migrator — Azure Functions Deployment

Serverless deployment of the MuleSoft-to-SpringBoot Migrator on Azure Functions with full infrastructure-as-code via Terraform.

## Architecture

```
                        +-----------------------+
                        |   Static Web App      |
                        |   (React Frontend)    |
                        +----------+------------+
                                   |
                          Azure AD Auth
                                   |
                        +----------v------------+
                        |   Azure Functions     |
                        |   (Python 3.12)       |
                        |                       |
                        |  HTTP Triggers:       |
                        |   /api/v2/migrations  |
                        |   /api/v2/builds      |
                        |   /api/v2/rag/search  |
                        |   /api/v2/github/push |
                        |   /api/health         |
                        |                       |
                        |  Queue Triggers:      |
                        |   migration-queue     |
                        |   build-queue         |
                        +--+-------+-------+----+
                           |       |       |
              +------------+   +---+---+   +------------+
              |                |       |                |
    +---------v---------+  +--v---+ +-v---------+  +---v---------+
    | PostgreSQL Flex   |  |Redis | |Azure      |  |Azure OpenAI |
    | (B1ms + pgvector) |  |Basic | |Key Vault  |  |GPT-4.1      |
    +-------------------+  |C0   | +-----------+  |Embeddings   |
                           +-----+                +-------------+
```

## Prerequisites

- [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli) >= 2.60
- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- [Azure Functions Core Tools](https://docs.microsoft.com/azure/azure-functions/functions-run-local) >= 4.x
- Python 3.12+
- An Azure subscription with Owner or Contributor role

## Quick Start

### One-command deployment

```bash
cd azure-deployment/functions/scripts
chmod +x setup.sh deploy.sh
./setup.sh --subscription <your-subscription-id>
```

The setup script will:
1. Check all prerequisites
2. Log in to Azure (if needed)
3. Create Terraform state storage
4. Provision all infrastructure via Terraform
5. Deploy the Function App code
6. Configure Azure AD authentication
7. Print all URLs and next steps

### Subsequent deploys (code only)

```bash
./scripts/deploy.sh
```

## Project Structure

```
functions/
  function_app.py        # All HTTP + Queue triggers (Python v2 model)
  db.py                  # Async PostgreSQL via asyncpg
  engine.py              # Static migration engine wrapper
  build_service.py       # Maven build execution
  rag_service.py         # Semantic search (Azure OpenAI + pgvector)
  github_service.py      # Push files to GitHub
  security.py            # Azure AD auth, RBAC, rate limiting, XXE prevention
  host.json              # Functions host config
  local.settings.json    # Local dev settings (gitignored)
  requirements.txt       # Python dependencies
  .funcignore            # Deploy ignore patterns
  staticwebapp.config.json  # SWA routing and auth

  terraform/
    providers.tf         # azurerm + azuread providers
    main.tf              # Resource group, Function App, Key Vault, Storage
    databases.tf         # PostgreSQL Flexible + Redis Cache
    openai.tf            # Azure OpenAI (GPT-4.1 + embeddings)
    networking.tf        # VNet, subnets, private endpoints
    security.tf          # Azure AD app registration, managed identity, RBAC
    monitoring.tf        # App Insights, Log Analytics, alerts
    variables.tf         # All configurable variables
    outputs.tf           # Deployment outputs

  scripts/
    setup.sh             # First-time setup (infra + code)
    deploy.sh            # Subsequent code deploys
```

## API Endpoints

### Migrations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v2/migrations` | Create migration (returns 202) |
| GET | `/api/v2/migrations` | List migrations (paginated) |
| GET | `/api/v2/migrations/{id}` | Get migration detail |
| GET | `/api/v2/migrations/{id}/files` | List generated files |
| GET | `/api/v2/migrations/{id}/files/{path}` | Get single file content |
| DELETE | `/api/v2/migrations/{id}` | Soft delete |
| POST | `/api/v2/migrations/{id}/cancel` | Cancel running migration |
| GET | `/api/v2/migrations/stats` | Aggregate statistics |

### Builds

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v2/builds` | Trigger Maven build |
| GET | `/api/v2/builds/{id}` | Build status and logs |

### Other

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v2/rag/search` | Semantic search |
| POST | `/api/v2/github/push` | Push files to GitHub |
| GET | `/api/health` | Health check |

## Authentication

All API endpoints (except `/api/health`) require Azure AD authentication. The Function App uses App Service EasyAuth which injects the `x-ms-client-principal` header after validating the user's token.

In development mode (`ENVIRONMENT=development`), endpoints accept unauthenticated requests with a default dev user.

## Infrastructure Details

### Region Strategy

| Resource | Region | Reason |
|----------|--------|--------|
| Function App, PostgreSQL, Redis, Key Vault | East Asia (Hong Kong) | Primary region |
| Azure OpenAI | Southeast Asia (Singapore) | GPT-4.1 availability |

### Pricing Tier Summary

| Resource | SKU | Estimated Monthly Cost |
|----------|-----|----------------------|
| Function App | Consumption (Y1) | Pay-per-execution |
| PostgreSQL Flexible | B1ms | ~$13/month |
| Redis Cache | Basic C0 | ~$16/month |
| Azure OpenAI | Pay-per-token | Variable |
| Static Web App | Standard | ~$9/month |
| Key Vault | Standard | ~$0.03/10k ops |

### Security

- All secrets stored in Azure Key Vault
- Managed Identity for service-to-service auth (no API keys in code)
- Private endpoints for PostgreSQL and Redis
- VNet integration for the Function App
- Azure AD for user authentication with RBAC
- XXE prevention on all XML inputs via defusedxml
- Rate limiting via Redis sliding window
- TLS 1.2+ enforced everywhere

## Local Development

1. Copy and configure local settings:
   ```bash
   cp local.settings.json local.settings.dev.json
   # Edit local.settings.dev.json with your values
   ```

2. Start local PostgreSQL and Redis:
   ```bash
   docker run -d --name pg -p 5432:5432 \
     -e POSTGRES_DB=migrator \
     -e POSTGRES_USER=migrator \
     -e POSTGRES_PASSWORD=migrator_secret \
     pgvector/pgvector:pg16

   docker run -d --name redis -p 6379:6379 redis:7-alpine
   ```

3. Start the function app locally:
   ```bash
   func start
   ```

4. Test the health endpoint:
   ```bash
   curl http://localhost:7071/api/health
   ```

## Terraform Variables

Override defaults by creating a `terraform.tfvars` file:

```hcl
subscription_id  = "your-subscription-id"
environment      = "prod"
location         = "eastasia"
openai_location  = "southeastasia"
alert_email      = "admin@example.com"

postgresql_sku   = "B_Standard_B1ms"
redis_sku        = "Basic"
redis_capacity   = 0
```

## Troubleshooting

### Function App not responding
```bash
# Check function app status
az functionapp show --name <app-name> --resource-group <rg> --query state

# View recent logs
az monitor app-insights events show \
  --app <app-insights-name> \
  --type traces \
  --order-by timestamp desc \
  --top 20
```

### Database connection issues
```bash
# Test connectivity from Function App
az webapp ssh --name <func-app-name> --resource-group <rg>
# Then: python3 -c "import asyncpg; ..."
```

### Queue messages not processing
```bash
# Check queue message count
az storage message peek \
  --queue-name migration-queue \
  --account-name <storage-account> \
  --num-messages 5
```

## Destroy

To tear down all resources:

```bash
./scripts/setup.sh --subscription <id> --destroy
```
