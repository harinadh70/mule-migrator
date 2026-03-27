# Air-Gap Installation Guide

This guide covers offline deployment of the MuleSoft-to-SpringBoot Agentic AI
Migration Platform in environments with no internet access.

## Overview

The air-gap bundle contains:

| Component | Description |
|-----------|-------------|
| `images/` | Docker images as `.tar` files |
| `models/` | Pre-downloaded `all-MiniLM-L6-v2` sentence-transformers model |
| `snapshots/` | Qdrant vector-store snapshot of the knowledge base |
| `docker-compose/` | Compose stack and environment template |
| `install.sh` | Automated installer script |

## Prerequisites

On the **build machine** (internet-connected):

- Docker 24+
- Python 3.12+ with `sentence-transformers` installed
- ~15 GB free disk space

On the **target machine** (air-gapped):

- Docker 24+ with Compose V2 (`docker compose`)
- Minimum 16 GB RAM, 4 CPU cores
- 50 GB free disk space

## Step 1 -- Build the Bundle (Internet-Connected Machine)

```bash
cd deploy/airgap
chmod +x bundle.sh
./bundle.sh --tag 1.0.0
```

Optional flags:

| Flag | Description |
|------|-------------|
| `--tag VERSION` | Application image tag (default: `1.0.0`) |
| `--output DIR` | Output directory for the tarball (default: `./dist`) |

The script will:

1. Build the application Docker image
2. Pull PostgreSQL 16, Redis 7, Qdrant, and Nginx images
3. Save all images as tar files
4. Download the `all-MiniLM-L6-v2` embedding model
5. Create a Qdrant snapshot of the knowledge base (if running)
6. Package everything into `migrator-airgap-bundle-<tag>.tar.gz`

## Step 2 -- Transfer the Bundle

Copy the tarball to the air-gapped target:

```bash
# USB drive, SCP over a bastion, or any other approved method
scp dist/migrator-airgap-bundle-1.0.0.tar.gz user@target:/opt/migrator/
```

## Step 3 -- Install on the Target Machine

```bash
cd /opt/migrator
tar xzf migrator-airgap-bundle-1.0.0.tar.gz
chmod +x install.sh
./install.sh
```

The installer will:

1. Verify Docker and Docker Compose are installed
2. Load all Docker images from tar files
3. Create `.env` from the template (if not present)
4. Start all services via `docker compose up -d`
5. Wait for health checks to pass
6. Run Alembic database migrations
7. Seed the Qdrant knowledge base from the bundled snapshot
8. Print access URLs

## Step 4 -- Configure

Edit the environment file before or after installation:

```bash
vi docker-compose/.env
```

Key settings to review:

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Application secret (change from default) |
| `POSTGRES_PASSWORD` | Database password |
| `CORS_ORIGINS` | Allowed origins for the UI |

After editing, restart:

```bash
cd docker-compose
docker compose down
docker compose up -d
```

## Verification

```bash
# Check all services are healthy
docker compose ps

# Test the API
curl http://localhost:8000/health

# View logs
docker compose logs -f api
```

## Updating

To update an air-gapped deployment:

1. Build a new bundle with `./bundle.sh --tag <new-version>` on the connected machine
2. Transfer to the target
3. Extract and run `./install.sh` -- it will load the new images and re-migrate

## Troubleshooting

**Services fail to start:**
Check `docker compose logs <service>` for errors. Ensure the host has enough
RAM (16 GB minimum) and disk space (50 GB).

**Database migration fails:**
Wait for PostgreSQL to finish starting, then retry:
```bash
docker compose exec api alembic upgrade head
```

**Knowledge base is empty:**
Trigger a full re-index:
```bash
docker compose exec api python -m api.rag.indexer --full-reindex
```

**Image load fails:**
Ensure the tar files are not corrupted. Re-run `bundle.sh` on the source machine.
