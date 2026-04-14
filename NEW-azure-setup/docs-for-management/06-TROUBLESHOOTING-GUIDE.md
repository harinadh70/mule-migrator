# Troubleshooting Guide — Step-by-Step

> **Version:** 2.0 | **Date:** April 2026

---

## Table of Contents
1. [Migration Issues](#1-migration-issues)
2. [Build Failures](#2-build-failures)
3. [Validation/Deployment Issues](#3-validationdeployment-issues)
4. [Authentication Issues](#4-authentication-issues)
5. [RAG/AI Issues](#5-ragai-issues)
6. [Infrastructure Issues](#6-infrastructure-issues)
7. [Frontend Issues](#7-frontend-issues)

---

## 1. Migration Issues

### 1.1 Migration Stuck in "queued"

**Symptom:** Migration status remains "queued" for > 30 seconds

**Diagnosis Steps:**
```bash
# 1. Check health endpoint
curl {{base_url}}/api/health

# 2. Check Azure Storage Queue
az storage queue peek-messages --queue-name migration-queue \
  --account-name $STORAGE_ACCOUNT --account-key $STORAGE_KEY

# 3. Check Function App logs
az monitor app-insights query --app $APP_INSIGHTS_NAME \
  --analytics-query "traces | where message contains 'migration_worker' | top 10 by timestamp"
```

**Common Causes:**
| Cause | Fix |
|-------|-----|
| Azure Function App cold start | Wait 60s, retry |
| Queue trigger disabled | Check host.json, restart function app |
| Function App crashed | Check Application Insights for exceptions |
| Message poisoned | Delete from queue, retry migration |

**Resolution:**
```bash
# Retry the migration
curl -X POST {{base_url}}/api/v2/migrations/{id}/retry \
  -H "Authorization: Bearer $TOKEN"
```

---

### 1.2 Migration Failed with Error

**Symptom:** Status "failed" with error message

**Diagnosis:**
```bash
# Get full migration details including error
curl {{base_url}}/api/v2/migrations/{id} -H "Authorization: Bearer $TOKEN"
```

**Common Errors:**

| Error | Cause | Fix |
|-------|-------|-----|
| `XXE validation failed` | XML contains external entities | Remove `<!DOCTYPE>` and external entity references |
| `No flows found in XML` | Invalid MuleSoft XML | Verify XML has `<flow>` elements with `<mule>` root |
| `Failed to parse XML` | Malformed XML | Fix XML syntax errors |
| `LLM provider error: 401` | API key expired | Update LLM API key in settings |
| `LLM provider error: 429` | Rate limited | Wait and retry, or switch provider |
| `Database connection error` | PostgreSQL unavailable | Check DB connectivity, restart |

---

### 1.3 Generated Code Has Compilation Errors

**Symptom:** Generated Java files have import or syntax errors

**Diagnosis:**
1. Download generated files
2. Look for `// TODO:` comments (indicators of incomplete conversion)
3. Check `agent_trace` for skipped elements

**Common Issues & Fixes:**

| Issue | Automatic Fix | Manual Fix |
|-------|--------------|------------|
| Missing Lombok imports | Validation pipeline patches automatically | Add `import lombok.*` |
| Missing Spring imports | Validation pipeline patches automatically | Add specific imports |
| Unknown MuleSoft element | LLM agent generates TODO | Write Java code manually |
| DataWeave not converted | Converter falls back to comment | Implement Java equivalent |
| Duplicate dependencies | POM patcher deduplicates | Remove duplicates from pom.xml |

---

## 2. Build Failures

### 2.1 Maven Compilation Error

**Symptom:** Build status "failed", build_log contains compilation errors

**Diagnosis:**
```bash
# Get build logs
curl {{base_url}}/api/v2/builds/{build_id} -H "Authorization: Bearer $TOKEN"
```

**Common Compilation Errors:**

| Error | Cause | Fix |
|-------|-------|-----|
| `package does not exist` | Missing Maven dependency | Add dependency to pom.xml |
| `cannot find symbol` | Missing import statement | Add import to Java file |
| `Compilation failure: annotations are not supported` | Wrong Java version | Set correct `java.version` in pom.xml |
| `lombok.RequiredArgsConstructor cannot be resolved` | Missing Lombok processor | Add maven-compiler-plugin with Lombok |
| `Cannot load driver class: com.mysql.cj.jdbc.Driver` | Missing DB driver | Switch to H2 or add MySQL dependency |

**Fix Workflow:**
1. Edit files via PUT `/api/v2/migrations/{id}/files`
2. Create new build via POST `/api/v2/builds`
3. Monitor build logs

---

### 2.2 Docker Build Timeout

**Symptom:** Build exceeds timeout (usually 10 minutes)

**Causes:**
- Large project with many dependencies (first build downloads all JARs)
- ACR Task quota exhausted
- Network issues downloading from Maven Central

**Fix:**
```bash
# Check ACR task status
az acr task list --registry $ACR_NAME

# Retry build
curl -X POST {{base_url}}/api/v2/builds \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"migration_id": "{{migration_id}}", "java_version": "21"}'
```

---

## 3. Validation/Deployment Issues

### 3.1 Health Check Timeout

**Symptom:** Validation status "failed", error "Health check timeout after 180s"

**Diagnosis:**
```bash
# Get container logs
curl {{base_url}}/api/v2/validations/{id}/logs -H "Authorization: Bearer $TOKEN"
```

**Common Causes:**

| Cause | Log Indicator | Fix |
|-------|--------------|-----|
| App crash on startup | `java.lang.RuntimeException` | Fix the error in generated code |
| Port mismatch | `Tomcat started on port 8081` | Ensure `server.port=8080` in properties |
| DB connection failure | `Cannot create JDBC driver` | Use H2 for validation (auto-patched) |
| Missing config | `Could not resolve placeholder` | Add missing properties |
| Slow startup | Logs show Spring context loading | Increase keep_alive_min |

---

### 3.2 ACI Deployment Failed

**Symptom:** Status "failed" during "deploying" phase

**Diagnosis:**
```bash
# Check ACI status directly
az container show --name $ACI_NAME --resource-group $RG --query provisioningState

# Check ACI logs
az container logs --name $ACI_NAME --resource-group $RG
```

**Common Causes:**
| Cause | Fix |
|-------|-----|
| ACI quota exceeded | Teardown old containers first |
| Image not found in ACR | Check ACR build succeeded |
| Resource group permissions | Verify managed identity has Contributor role |
| Port conflict | Ensure no duplicate ACI names |

---

### 3.3 API Comparison Mismatches

**Symptom:** Comparison shows "Mismatch" for endpoints

**Diagnosis Steps:**
1. Check status code differences first
2. Compare response body structures
3. Look for field naming differences (camelCase vs snake_case)

**Common Mismatch Causes:**

| Mismatch Type | Cause | Fix |
|--------------|-------|-----|
| Status 200 vs 404 | Wrong path mapping | Fix `@GetMapping` path |
| Status 200 vs 500 | Runtime error in Spring | Check container logs |
| Same status, different body | DataWeave conversion issue | Fix transformation logic |
| Missing fields | Incomplete field mapping | Update service/controller code |
| Extra fields | Spring Boot adds metadata | May be acceptable |

---

## 4. Authentication Issues

### 4.1 401 Unauthorized

**Steps:**
1. Check if token is expired (JWT exp claim)
2. For email/password: Re-login at POST `/api/v2/auth/login`
3. For Azure AD: Acquire new token via MSAL
4. Check `ADMIN_EMAIL` in Function App Settings matches

### 4.2 Azure AD SSO Not Working

**Steps:**
1. Verify `VITE_AZURE_AD_CLIENT_ID` in frontend .env
2. Check redirect URI matches in Azure AD App Registration
3. Verify tenant ID
4. Check browser console for MSAL errors

---

## 5. RAG/AI Issues

### 5.1 RAG Returns Empty Results

**Steps:**
1. Check if knowledge base is seeded: GET `/api/v2/rag/collections`
2. If empty, run: POST `/api/v2/rag/seed`
3. Verify pgvector extension: `SELECT * FROM pg_extension WHERE extname = 'vector'`
4. Check embedding API connectivity (Azure OpenAI or GitHub Copilot)

### 5.2 LLM Provider Errors

| Provider | Error | Fix |
|----------|-------|-----|
| GitHub Copilot | 401 | Refresh GitHub PAT |
| OpenAI | 429 | Rate limited, wait or upgrade plan |
| Claude | 529 | Anthropic overloaded, retry |
| Gemini | 403 | Check GOOGLE_API_KEY |
| Ollama | Connection refused | Start Ollama: `ollama serve` |

---

## 6. Infrastructure Issues

### 6.1 Database Connection Failed

```bash
# Test PostgreSQL connectivity
az postgres flexible-server show --name $PG_SERVER --resource-group $RG

# Check firewall rules
az postgres flexible-server firewall-rule list --name $PG_SERVER --resource-group $RG

# Test from Function App
func azure functionapp logstream $FUNC_APP_NAME
```

### 6.2 Redis Connection Failed

```bash
# Check Redis status
az redis show --name $REDIS_NAME --resource-group $RG --query provisioningState

# Test connectivity
az redis list-keys --name $REDIS_NAME --resource-group $RG
```

### 6.3 Deploying Updates

```bash
# Deploy backend (Azure Functions)
cd functions
func azure functionapp publish mulesoft-migrator-prod-func-hwddm9 --python --build remote

# Deploy frontend (Static Web App)
cd frontend
npm run build
az staticwebapp deploy --app-name $SWA_NAME --source dist/
```

---

## 7. Frontend Issues

### 7.1 Blank Page After Login

1. Check browser console for JavaScript errors
2. Verify `VITE_API_BASE_URL` is correct
3. Check CORS settings on Function App
4. Clear localStorage: `localStorage.clear()`

### 7.2 API Calls Failing (Network Error)

1. Check if Function App is running
2. Verify CORS allows frontend origin
3. Check browser Network tab for details
4. Try the same request in Postman

### 7.3 WebSocket Not Connecting

1. WebSocket URL auto-detected from current location
2. Check if `VITE_WS_URL` is set correctly
3. Verify Function App supports WebSocket connections
4. Check browser console for WebSocket errors

---

## Quick Reference: Environment Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `POSTGRES_CONNECTION_STRING` | Function App Settings | Database connection |
| `REDIS_CONNECTION_STRING` | Function App Settings | Redis connection |
| `AzureWebJobsStorage` | Function App Settings | Queue + Table storage |
| `AZURE_OPENAI_ENDPOINT` | Function App Settings | Azure OpenAI API |
| `AZURE_OPENAI_API_KEY` | Key Vault | OpenAI API key |
| `GITHUB_MODELS_PAT` | Function App Settings | GitHub Copilot API |
| `ADMIN_EMAIL` | Function App Settings | Admin user email |
| `ADMIN_PASSWORD_HASH` | Function App Settings | bcrypt password hash |
| `ACR_NAME` | Function App Settings | Container Registry name |
| `AZURE_KEY_VAULT_URL` | Function App Settings | Key Vault URL |
| `AZURE_AD_CLIENT_ID` | Function App Settings | Azure AD app ID |
| `AZURE_AD_TENANT_ID` | Function App Settings | Azure AD tenant |
