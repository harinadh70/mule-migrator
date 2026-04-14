# MuleSoft-to-Spring Boot Agentic AI Migrator — Architecture Overview

> **Version:** 2.0 | **Date:** April 2026 | **Classification:** Internal / CG Management
> **Author:** Harinadh | **Platform:** Microsoft Azure

---

## 1. Executive Summary

The **MuleSoft-to-Spring Boot Migrator** is an enterprise-grade, AI-powered platform that automates the migration of MuleSoft 4 ESB applications to Spring Boot 3.2+ microservices. It combines deterministic rule-based parsing with agentic AI (LLM orchestration + RAG) to produce production-ready, compilable Java projects — including controllers, services, configurations, tests, Dockerfiles, and CI/CD pipelines.

**Key Metrics:**
- 30+ MuleSoft connector types supported
- 7 LLM providers integrated (GitHub Copilot, Claude, GPT-4, Gemini, DeepSeek, Groq, Ollama)
- End-to-end: XML upload → running Spring Boot container in < 5 minutes
- Real-time validation via Azure Container Instances (ACI)

---

## 2. High-Level Architecture Diagram

```
+=====================================================================+
|                        USERS / CLIENTS                              |
|   Browser (React SPA)  |  Postman  |  CI/CD Pipeline  |  CLI       |
+============+============+==========+====================+===========+
             |                       |
             v                       v
+---------------------------+  +---------------------------+
|    Azure Static Web App   |  |   Azure API Management    |
|    (React Frontend)       |  |   (Optional Gateway)      |
|    - MSAL Auth (Azure AD) |  +---------------------------+
|    - Monaco Code Editor   |              |
|    - Real-time WebSocket  |              |
+----------+----------------+              |
           |                               |
           v                               v
+=====================================================================+
|                AZURE FUNCTIONS (Python v2 — Serverless)              |
|                                                                     |
|  +-------------------+  +-------------------+  +-----------------+  |
|  | HTTP Triggers     |  | Queue Triggers    |  | Timer Triggers  |  |
|  | - /migrations     |  | - migration-queue |  | - cleanup jobs  |  |
|  | - /builds         |  | - build-queue     |  +-----------------+  |
|  | - /validations    |  | - validation-queue|                       |
|  | - /rag/search     |  | - teardown-queue  |                       |
|  | - /github/push    |  +-------------------+                       |
|  | - /auth/login     |           |                                  |
|  +--------+----------+           |                                  |
|           |                      v                                  |
|  +=====================================================+            |
|  |          MIGRATION ENGINE (Orchestrator)             |            |
|  |                                                     |            |
|  |  1. XML Validation (defusedxml — XXE prevention)    |            |
|  |  2. MuleSoft Parser (30+ namespaces)                |            |
|  |  3. DataWeave Converter (DW 2.0 → Java Streams)     |            |
|  |  4. Connector Mapper (Mule → Maven Dependencies)    |            |
|  |  5. Flow Converter (Flows → Controllers/Listeners)  |            |
|  |  6. Spring Boot Generator (Full project structure)  |            |
|  |  7. LLM Validator (Multi-provider code review)      |            |
|  |  8. LLM Agent (Unknown element conversion)          |            |
|  +=====================================================+            |
|           |                      |                                  |
|           v                      v                                  |
|  +------------------+   +------------------+                        |
|  | RAG Service      |   | Build Service    |                        |
|  | (pgvector)       |   | (ACR Tasks)      |                        |
|  | - Embeddings     |   | - Maven Build    |                        |
|  | - Semantic Search|   | - Docker Image   |                        |
|  +------------------+   +------------------+                        |
|           |                      |                                  |
+===========+======================+==================================+
            |                      |
            v                      v
+=====================================================================+
|                    AZURE DATA & AI SERVICES                         |
|                                                                     |
|  +------------------+  +------------------+  +------------------+   |
|  | PostgreSQL       |  | Redis Cache      |  | Azure OpenAI     |   |
|  | Flexible Server  |  | - Session store  |  | - GPT-4o         |   |
|  | - Migrations DB  |  | - Rate limiting  |  | - text-embedding |   |
|  | - RAG (pgvector) |  | - Queue cache    |  |   -3-large       |   |
|  | - Users & Auth   |  +------------------+  +------------------+   |
|  +------------------+                                               |
|                                                                     |
|  +------------------+  +------------------+  +------------------+   |
|  | Azure Container  |  | Azure Container  |  | Azure Key Vault  |   |
|  | Registry (ACR)   |  | Instances (ACI)  |  | - DB Credentials |   |
|  | - Docker images  |  | - Live testing   |  | - API Keys       |   |
|  | - Build tasks    |  | - Health checks  |  | - GitHub PAT     |   |
|  +------------------+  +------------------+  +------------------+   |
|                                                                     |
|  +------------------+  +------------------+  +------------------+   |
|  | Storage Queue    |  | Table Storage    |  | App Insights     |   |
|  | - Job queuing    |  | - Build logs     |  | - Monitoring     |   |
|  | - Async work     |  | - Audit trail    |  | - Alerting       |   |
|  +------------------+  +------------------+  +------------------+   |
+=====================================================================+
```

---

## 3. Data Flow — End-to-End Migration

```
USER                    FRONTEND                  AZURE FUNCTIONS              DATA STORES
 |                         |                           |                          |
 |-- Upload MuleSoft XML ->|                           |                          |
 |                         |-- POST /migrations ------>|                          |
 |                         |                           |-- Validate XML (XXE) --> |
 |                         |                           |-- Store in PostgreSQL -->|
 |                         |                           |-- Enqueue migration ---->|
 |                         |<-- 202 Accepted ----------|                          |
 |                         |                           |                          |
 |                         |   [Queue Worker Picks Up]  |                          |
 |                         |                           |-- Parse XML              |
 |                         |                           |-- Query RAG ------------>|
 |                         |                           |<-- Migration patterns ---|
 |                         |                           |-- Convert DataWeave      |
 |                         |                           |-- Map connectors         |
 |                         |                           |-- Convert flows          |
 |                         |                           |-- Generate Spring Boot   |
 |                         |                           |-- (Optional) LLM review  |
 |                         |                           |-- Save output files ---->|
 |                         |                           |                          |
 |                         |-- Poll GET /migrations/id |                          |
 |                         |<-- status: completed -----|                          |
 |<-- Show generated code -|                           |                          |
 |                         |                           |                          |
 |-- Click "Build" ------->|                           |                          |
 |                         |-- POST /builds ---------->|                          |
 |                         |                           |-- ACR Quick Build ------>|
 |                         |                           |-- Stream logs ---------->|
 |                         |<-- Build logs (real-time) |                          |
 |                         |                           |                          |
 |-- Click "Validate" ---->|                           |                          |
 |                         |-- POST /validations ----->|                          |
 |                         |                           |-- Build Docker image --->|
 |                         |                           |-- Deploy to ACI -------->|
 |                         |                           |-- Health check           |
 |                         |<-- App URL + status ------|                          |
 |                         |                           |                          |
 |-- Click "Compare" ----->|                           |                          |
 |                         |-- POST /compare --------->|                          |
 |                         |                           |-- Call MuleSoft API      |
 |                         |                           |-- Call Spring Boot API   |
 |                         |                           |-- Compare responses      |
 |                         |<-- Comparison results ----|                          |
 |                         |                           |                          |
 |-- Click "Push GitHub" ->|                           |                          |
 |                         |-- POST /github/push ----->|                          |
 |                         |                           |-- Create branch          |
 |                         |                           |-- Push all files         |
 |                         |<-- Commit URL ------------|                          |
```

---

## 4. Agentic AI Pipeline Architecture

```
+======================================================================+
|                    AGENTIC AI MIGRATION PIPELINE                      |
+======================================================================+
|                                                                      |
|  +-----------+    +------------+    +-----------+    +------------+   |
|  |  PLANNER  |--->|   ENGINE   |--->|   CODER   |--->|  REVIEWER  |   |
|  |  Agent    |    |   Agent    |    |   Agent   |    |   Agent    |   |
|  +-----------+    +------------+    +-----------+    +------------+   |
|       |                |                 |                |           |
|       v                v                 v                v           |
|  Analyze XML      Parse & Map      Generate Code    LLM Validate     |
|  Plan strategy    Convert flows    Handle unknowns  Score quality     |
|  Identify risks   DataWeave→Java   Fill gaps        Flag issues       |
|       |                |                 |                |           |
|       +--------+-------+--------+--------+--------+------+           |
|                |                 |                 |                  |
|                v                 v                 v                  |
|         +------------+   +------------+   +--------------+           |
|         | RAG Service|   | LLM Agents |   | Code Quality |           |
|         | (pgvector) |   | (7 provdrs)|   | Checks       |           |
|         +------------+   +------------+   +--------------+           |
|                                                                      |
|  AGENT CONTEXT (Shared State):                                       |
|  - conversions: list of successful LLM code generations              |
|  - skipped: list of elements that couldn't be converted              |
|  - tokens_used: total LLM tokens consumed                           |
|  - cost_usd: total API cost                                         |
|  - trace: full audit log of every AI decision                       |
+======================================================================+
```

---

## 5. Security Architecture

```
+------------------------------------------------------------------+
|                      SECURITY LAYERS                              |
+------------------------------------------------------------------+
|                                                                  |
|  Layer 1: Authentication                                         |
|  +------------------+  +-------------------+  +---------------+  |
|  | Azure AD / MSAL  |  | Email/Password    |  | EasyAuth      |  |
|  | (SSO with OIDC)  |  | (HMAC-SHA256 JWT) |  | (App Service) |  |
|  +------------------+  +-------------------+  +---------------+  |
|                                                                  |
|  Layer 2: Authorization                                          |
|  +------------------+  +-------------------+                     |
|  | RBAC (admin/user)|  | Resource ownership|                     |
|  | via Azure AD     |  | (user_id checks)  |                     |
|  +------------------+  +-------------------+                     |
|                                                                  |
|  Layer 3: Input Validation                                       |
|  +------------------+  +-------------------+  +---------------+  |
|  | defusedxml       |  | Pydantic schemas  |  | Rate Limiting |  |
|  | (XXE prevention) |  | (request valid.)  |  | (Redis-based) |  |
|  +------------------+  +-------------------+  +---------------+  |
|                                                                  |
|  Layer 4: Secrets Management                                     |
|  +------------------+  +-------------------+                     |
|  | Azure Key Vault  |  | Managed Identity  |                     |
|  | (all credentials)|  | (no stored creds) |                     |
|  +------------------+  +-------------------+                     |
|                                                                  |
|  Layer 5: Network Security                                       |
|  +------------------+  +-------------------+  +---------------+  |
|  | VNet Integration |  | Private Endpoints |  | TLS 1.2+      |  |
|  | (isolated subnet)|  | (no public DB)    |  | (enforced)    |  |
|  +------------------+  +-------------------+  +---------------+  |
+------------------------------------------------------------------+
```

---

## 6. Azure Resource Map

| Resource | Service | Purpose | SKU/Tier |
|----------|---------|---------|----------|
| `mulesoft-migrator-prod-func` | Azure Functions | API + Workers | Consumption (Y1) |
| `mulesoft-migrator-prod-pg` | PostgreSQL Flexible | Main database + pgvector | Burstable B1ms |
| `mulesoft-migrator-prod-redis` | Azure Cache for Redis | Rate limiting + sessions | Basic C0 |
| `mulesoft-migrator-prod-acr` | Container Registry | Docker image builds | Basic |
| `mulesoft-migrator-prod-kv` | Key Vault | Secrets management | Standard |
| `mulesoft-migrator-prod-ai` | Storage Account | Queues + Tables | Standard LRS |
| `mulesoft-migrator-prod-ai` | App Insights | Monitoring + telemetry | — |
| Dynamic ACI instances | Container Instances | Validation deployments | 1 vCPU / 1.5 GB |
| Azure AD App Registration | Azure AD | SSO authentication | — |

**Estimated Monthly Cost:** ~$85–150/month (serverless consumption model)

---

## 7. Technology Stack Summary

| Layer | Technology | Version |
|-------|-----------|---------|
| **Frontend** | React + TypeScript | 18.3 / 5.6 |
| **Build Tool** | Vite | 5.4 |
| **UI Framework** | TailwindCSS | 3.4 |
| **State Management** | Zustand | 4.5 |
| **Data Fetching** | TanStack React Query | 5.56 |
| **Code Editor** | Monaco Editor | 4.6 |
| **Auth** | Azure MSAL | 5.6 |
| **Backend** | Azure Functions (Python) | v2 model |
| **Database** | PostgreSQL + pgvector | 16 |
| **Cache** | Redis | 7.x |
| **AI/LLM** | OpenAI, Claude, Gemini, etc. | Multi-provider |
| **Embeddings** | text-embedding-3-large | 3072 dims |
| **Container Build** | Azure Container Registry | Tasks |
| **Validation** | Azure Container Instances | Dynamic |
| **IaC** | Terraform | 1.5+ |
| **CI/CD** | Azure Pipelines | YAML |
| **Secrets** | Azure Key Vault | Standard |
| **Monitoring** | Application Insights | — |

---

## 8. Repository Structure

```
NEW-azure-setup/
├── frontend/                    # React SPA (TypeScript)
│   ├── src/
│   │   ├── api/                 # Axios API clients
│   │   ├── auth/                # MSAL Azure AD config
│   │   ├── components/          # React components (12 modules)
│   │   ├── hooks/               # Custom React hooks
│   │   ├── store/               # Zustand state stores
│   │   └── types/               # TypeScript type definitions
│   ├── vite.config.ts
│   └── package.json
│
├── functions/                   # Azure Functions backend
│   ├── function_app.py          # All HTTP + Queue triggers (2490 lines)
│   ├── db.py                    # PostgreSQL async layer
│   ├── engine.py                # Migration orchestrator
│   ├── security.py              # Auth, RBAC, rate limiting
│   ├── rag_service.py           # RAG semantic search
│   ├── build_service.py         # Maven build via ACR
│   ├── validation_service.py    # ACI deployment + testing
│   ├── github_service.py        # GitHub push integration
│   ├── seed_knowledge.py        # RAG knowledge base seeding
│   ├── backend/migrator/
│   │   ├── parser.py            # MuleSoft XML parser (1003 lines)
│   │   ├── dataweave_converter.py  # DW 2.0 → Java (936 lines)
│   │   ├── flow_converter.py    # Flows → Controllers (1801 lines)
│   │   ├── connector_mapper.py  # Connectors → Maven deps (495 lines)
│   │   ├── spring_generator.py  # Full project generation (1717 lines)
│   │   ├── llm_agent.py         # AI agent for unknowns (332 lines)
│   │   ├── llm_validator.py     # Multi-provider code review (704 lines)
│   │   └── swagger_generator.py # OpenAPI spec generation (706 lines)
│   ├── host.json
│   └── requirements.txt
│
├── terraform/                   # AKS infrastructure (IaC)
│   ├── main.tf, aks.tf, networking.tf, databases.tf
│   ├── openai.tf, monitoring.tf, security.tf
│   └── scripts/setup-azure.sh, deploy.sh
│
├── functions/terraform/         # Functions infrastructure (IaC)
│   ├── main.tf, databases.tf, networking.tf
│   ├── openai.tf, monitoring.tf, security.tf
│   └── outputs.tf
│
├── helm/                        # Helm charts for AKS deployment
├── azure-pipelines.yml          # CI/CD pipeline
├── docs-for-management/         # THIS DOCUMENTATION FOLDER
└── .env, .env.development, .env.production
```
