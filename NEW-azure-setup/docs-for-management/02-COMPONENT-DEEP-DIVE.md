# Component Deep Dive — Every Module Explained

> **Version:** 2.0 | **Date:** April 2026

---

## Table of Contents

1. [MuleSoft XML Parser](#1-mulesoft-xml-parser)
2. [DataWeave Converter](#2-dataweave-converter)
3. [Flow Converter](#3-flow-converter)
4. [Connector Mapper](#4-connector-mapper)
5. [Spring Boot Generator](#5-spring-boot-generator)
6. [LLM Agent](#6-llm-agent)
7. [LLM Validator](#7-llm-validator)
8. [RAG Service](#8-rag-service)
9. [Build Service](#9-build-service)
10. [Validation Service](#10-validation-service)
11. [GitHub Service](#11-github-service)
12. [Security Module](#12-security-module)
13. [Database Layer](#13-database-layer)
14. [Migration Engine](#14-migration-engine-orchestrator)
15. [Function App (API Layer)](#15-function-app-api-layer)
16. [Frontend Application](#16-frontend-application)

---

## 1. MuleSoft XML Parser

**File:** `functions/backend/migrator/parser.py` (1,003 lines)

### What It Does
Parses MuleSoft 4 XML configuration files into a structured Python dictionary. This is the first step of every migration — converting raw XML into a machine-readable intermediate representation.

### How It Works
1. Uses `lxml` with `defusedxml` for XXE-safe XML parsing
2. Automatically detects and strips 30+ MuleSoft XML namespaces
3. Walks the XML tree depth-first, categorizing each element

### Supported MuleSoft Namespaces (30+)

| Category | Namespace | Elements Parsed |
|----------|-----------|-----------------|
| **Core** | `mule:`, `ee:` | flows, sub-flows, transforms |
| **HTTP** | `http:` | listener, listener-config, request |
| **Database** | `db:` | select, insert, update, delete, stored-procedure |
| **JMS** | `jms:` | listener, publish, consume |
| **AMQP** | `amqp:` | listener, publish |
| **Kafka** | `kafka:` | consumer, producer |
| **File/SFTP** | `file:`, `sftp:`, `ftp:` | read, write, list, listener |
| **Email** | `email:` | listener-imap, listener-pop3, send |
| **Salesforce** | `salesforce:` | query, create, update, upsert |
| **AWS** | `s3:`, `sqs:`, `sns:` | get-object, put-object, send-message |
| **NoSQL** | `mongo:`, `redis:`, `elasticsearch:` | find, insert, get, set |
| **API** | `apikit:` | router, config |
| **Web Services** | `ws:`, `wsc:` | consumer |
| **Security** | `oauth:`, `spring-security:` | providers, token validation |
| **Batch** | `batch:` | job, step, aggregator |
| **VM** | `vm:` | listener, publish |

### Output Structure
```python
{
    "global_configs": [
        {"type": "http-listener-config", "name": "HTTP_Listener_config",
         "host": "0.0.0.0", "port": "8081", "basePath": "/api"}
    ],
    "flows": [
        {
            "name": "getCustomersFlow",
            "source": {
                "type": "http-listener",
                "config_ref": "HTTP_Listener_config",
                "method": "GET",
                "path": "/customers"
            },
            "processors": [
                {"type": "logger", "level": "INFO", "message": "Fetching customers"},
                {"type": "db:select", "sql": "SELECT * FROM customers"},
                {"type": "ee:transform", "dataweave": "%dw 2.0\noutput application/json\n---\npayload"}
            ],
            "error_handlers": [
                {"type": "on-error-propagate", "errorType": "DB:CONNECTIVITY",
                 "processors": [{"type": "set-payload", "value": "{\"error\": \"DB unavailable\"}"}]}
            ]
        }
    ],
    "sub_flows": [...],
    "connectors": {"http", "db", "ee"},
    "global_properties": {"db.host": "localhost", "db.port": "3306"},
    "batch_jobs": [...],
    "apikit_configs": [...],
    "warnings": ["Unknown element: custom:processor at line 45"]
}
```

### Key Design Decisions
- **Namespace stripping first** — simplifies all downstream processing
- **LLM fallback** — unknown elements are recorded and optionally sent to LLM Agent
- **Multi-XML merge** — `merge_parsed_results()` combines multiple parsed files, deduplicating flows

---

## 2. DataWeave Converter

**File:** `functions/backend/migrator/dataweave_converter.py` (936 lines)

### What It Does
Converts MuleSoft DataWeave 2.0 expressions to equivalent Java code using Java Streams API, lambda expressions, and standard library functions.

### How It Works
1. Parses DataWeave expression syntax (operators, functions, pattern matching)
2. Maps each DW construct to its Java equivalent
3. Handles inline expressions (`#[payload.name]`) and full DW scripts with headers

### Conversion Examples

| DataWeave 2.0 | Java Equivalent |
|---------------|-----------------|
| `payload map (item) -> item.name` | `payload.stream().map(item -> item.getName()).collect(Collectors.toList())` |
| `payload filter (item) -> item.age > 18` | `payload.stream().filter(item -> item.getAge() > 18).collect(Collectors.toList())` |
| `payload reduce (acc, item) -> acc + item` | `payload.stream().reduce(0, (acc, item) -> acc + item)` |
| `sizeOf(payload)` | `payload.size()` |
| `upper(payload.name)` | `payload.getName().toUpperCase()` |
| `payload.price as Number` | `Double.parseDouble(payload.getPrice())` |
| `payload.date as Date` | `LocalDate.parse(payload.getDate())` |
| `now()` | `LocalDateTime.now()` |
| `payload.name default "Unknown"` | `Optional.ofNullable(payload.getName()).orElse("Unknown")` |
| `#[payload]` | `payload` (MEL compatibility) |
| `#[flowVars.customerId]` | `customerId` (variable reference) |

### Supported Operators
- **Collection**: `map`, `filter`, `reduce`, `pluck`, `flatMap`, `flatten`, `groupBy`, `orderBy`, `distinctBy`
- **String**: `upper`, `lower`, `trim`, `capitalize`, `replace`, `match`, `startsWith`, `endsWith`, `splitBy`, `joinBy`
- **Array**: `sizeOf`, `indexOf`, `min`, `max`, `avg`, `sum`, `first`, `last`
- **Object**: `keys`, `values`, `entries`, `merge` (`++`), `remove` (`--`)
- **Type Coercion**: `as String`, `as Number`, `as Boolean`, `as Date`, `as DateTime`
- **Null Safety**: `default`, `when/otherwise`
- **Pattern Matching**: `if-else`, `match/case`

---

## 3. Flow Converter

**File:** `functions/backend/migrator/flow_converter.py` (1,801 lines)

### What It Does
Takes the parsed MuleSoft structure and converts each flow into Spring Boot Java classes. This is the core conversion engine that produces controllers, listeners, schedulers, and service classes.

### Flow Categorization Logic

```
                       MuleSoft Flow Source
                              |
              +---------------+----------------+
              |               |                |
        http:listener    scheduler:*      jms:listener
              |               |                |
              v               v                v
      @RestController   @Scheduled       @JmsListener
      @GetMapping       ScheduledTasks   JmsMessageListener
      @PostMapping      class            class
```

| Source Type | Spring Boot Output | Annotations |
|------------|-------------------|-------------|
| `http:listener` (GET) | RestController method | `@GetMapping("/path")` |
| `http:listener` (POST) | RestController method | `@PostMapping("/path")` |
| `scheduler:scheduling-strategy` | Scheduled method | `@Scheduled(fixedDelay=1000)` |
| `jms:listener` | JMS Listener class | `@JmsListener(destination="queue")` |
| `amqp:listener` | RabbitMQ Listener | `@RabbitListener(queues="queue")` |
| `kafka:consumer` | Kafka Listener | `@KafkaListener(topics="topic")` |
| `vm:listener` | Spring Event Listener | `@EventListener` |
| `file:listener` | WatchService | `WatchService` polling loop |
| `sftp:listener` | SFTP adapter | `SftpInboundChannelAdapter` |
| `apikit:router` | Grouped Controller | Multiple `@*Mapping` methods |

### Processor Conversion (30+ Types)

| MuleSoft Processor | Java Code Generated |
|-------------------|-------------------|
| `logger` | `log.info("message")` |
| `set-payload` | `String payload = "value"` |
| `set-variable` | `String varName = "value"` |
| `choice` (when/otherwise) | `if (condition) { ... } else { ... }` |
| `for-each` | `for (Object item : collection) { ... }` |
| `try` / `catch` | `try { ... } catch (Exception e) { ... }` |
| `http:request` | `restTemplate.exchange(url, method, ...)` |
| `db:select` | `jdbcTemplate.queryForList(sql)` |
| `db:insert` | `jdbcTemplate.update(sql, params)` |
| `jms:publish` | `jmsTemplate.convertAndSend(dest, msg)` |
| `kafka:publish` | `kafkaTemplate.send(topic, msg)` |
| `ee:transform` | Converted DataWeave expression |
| `raise-error` | `throw new CustomException(...)` |
| `scatter-gather` | `CompletableFuture.allOf(...)` |
| `flow-ref` | `methodCall()` (same class or injected service) |

### Generated File Structure
```
src/main/java/com/example/
├── controller/
│   ├── CustomerController.java          # From HTTP flows
│   └── OrderApiController.java          # From APIkit router
├── listener/
│   ├── OrderJmsListener.java            # From JMS flows
│   └── EventKafkaListener.java          # From Kafka flows
├── scheduler/
│   └── ScheduledTasks.java              # From scheduler flows
├── service/
│   ├── CustomerService.java             # Extracted business logic
│   └── OrderProcessingService.java
└── exception/
    ├── ResourceNotFoundException.java
    └── BadRequestException.java
```

---

## 4. Connector Mapper

**File:** `functions/backend/migrator/connector_mapper.py` (495 lines)

### What It Does
Maps detected MuleSoft connectors to their Spring Boot Maven dependency equivalents and generates appropriate `application.properties` configuration stubs.

### Connector → Dependency Mapping

| MuleSoft Connector | Maven Dependencies | Spring Config |
|-------------------|-------------------|---------------|
| `http` | spring-boot-starter-web, spring-boot-starter-webflux | server.port=8080 |
| `db` | spring-boot-starter-data-jpa, spring-boot-starter-jdbc | spring.datasource.* |
| `jms` | spring-boot-starter-activemq | spring.activemq.* |
| `amqp` | spring-boot-starter-amqp | spring.rabbitmq.* |
| `kafka` | spring-kafka | spring.kafka.* |
| `email` | spring-boot-starter-mail | spring.mail.* |
| `redis` | spring-boot-starter-data-redis | spring.redis.* |
| `mongo` | spring-boot-starter-data-mongodb | spring.data.mongodb.* |
| `salesforce` | (RestTemplate/WebClient) | salesforce.* (custom) |
| `s3` | software.amazon.awssdk:s3 | aws.s3.* (custom) |
| `sqs` | software.amazon.awssdk:sqs | aws.sqs.* (custom) |
| `batch` | spring-boot-starter-batch | spring.batch.* |
| `oauth` | spring-boot-starter-oauth2-client | spring.security.oauth2.* |
| `elasticsearch` | spring-boot-starter-data-elasticsearch | spring.elasticsearch.* |

### Error Type Mapping
| MuleSoft Error | Spring Boot Exception |
|---------------|---------------------|
| `HTTP:NOT_FOUND` | `ResourceNotFoundException` (custom, returns 404) |
| `HTTP:UNAUTHORIZED` | `UnauthorizedException` (custom, returns 401) |
| `HTTP:BAD_REQUEST` | `BadRequestException` (custom, returns 400) |
| `HTTP:INTERNAL_SERVER_ERROR` | `InternalServerErrorException` (returns 500) |
| `DB:CONNECTIVITY` | `DataAccessException` (Spring built-in) |
| `EXPRESSION_VALIDATION_ERROR` | `IllegalArgumentException` |

---

## 5. Spring Boot Generator

**File:** `functions/backend/migrator/spring_generator.py` (1,717 lines)

### What It Does
Takes all converted code and generates a complete, runnable Spring Boot 3.2 project with proper Maven structure, configuration files, Docker support, and test templates.

### Generated Project Structure (Complete)

```
{project-name}/
├── pom.xml                              # Maven POM with all dependencies
├── Dockerfile                           # Multi-stage build (Maven + JRE)
├── docker-compose.yml                   # Local dev with databases
├── .gitignore                           # Java/Maven/IDE ignores
│
├── src/main/java/{groupId}/
│   ├── {ProjectName}Application.java    # @SpringBootApplication
│   │
│   ├── config/
│   │   ├── RestTemplateConfig.java      # RestTemplate bean
│   │   ├── WebClientConfig.java         # WebClient bean
│   │   ├── CorsConfig.java             # CORS configuration
│   │   ├── SchedulingConfig.java       # @EnableScheduling (if needed)
│   │   ├── JmsConfig.java              # JMS factories (if needed)
│   │   ├── KafkaConfig.java            # Kafka consumer/producer (if needed)
│   │   ├── CacheConfig.java            # @EnableCaching (if needed)
│   │   ├── SecurityConfig.java         # Spring Security (if needed)
│   │   ├── AsyncConfig.java            # @EnableAsync (if needed)
│   │   ├── BatchConfig.java            # Spring Batch (if needed)
│   │   ├── SftpConfig.java             # SFTP adapter (if needed)
│   │   └── AwsS3Config.java            # AWS S3 client (if needed)
│   │
│   ├── controller/                      # REST controllers
│   ├── service/                         # Business logic services
│   ├── listener/                        # Message listeners
│   ├── scheduler/                       # Scheduled tasks
│   ├── exception/                       # Custom exceptions + @ControllerAdvice
│   └── util/                            # Utility classes
│
├── src/main/resources/
│   ├── application.properties           # Default config
│   ├── application.yml                  # YAML config alternative
│   ├── application-dev.properties       # Dev profile
│   ├── application-prod.properties      # Prod profile
│   └── logback-spring.xml              # Logging config
│
└── src/test/java/{groupId}/
    ├── {ProjectName}ApplicationTests.java  # Context load test
    └── controller/
        └── {Controller}Tests.java       # @WebMvcTest
```

### POM.xml Generation
- Parent: `spring-boot-starter-parent:3.2.0`
- Always included: spring-boot-starter-web, spring-boot-starter-actuator, lombok, h2 (test)
- Conditionally included: Based on connectors detected
- Maven compiler plugin with Lombok annotation processor configured
- Spring Boot Maven plugin for fat JAR packaging

### Dockerfile (Multi-Stage)
```dockerfile
FROM maven:3.9-eclipse-temurin-{javaVersion} AS build
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn clean package -Dmaven.test.skip=true -B

FROM eclipse-temurin:{javaVersion}-jre-alpine
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1
ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

## 6. LLM Agent

**File:** `functions/backend/migrator/llm_agent.py` (332 lines)

### What It Does
Provides real-time AI assistance during migration for handling unknown or complex MuleSoft elements that the rule-based engine cannot convert. Acts as a "coding co-pilot" that generates Java code on-the-fly.

### Agent Functions

| Function | Trigger | Output |
|----------|---------|--------|
| `convert_unknown_element()` | Unknown XML processor | Java method body |
| `convert_unknown_dataweave()` | Unparseable DW expression | Java equivalent code |
| `suggest_connector_mapping()` | Unknown connector | Maven deps + config |
| `convert_unknown_source()` | Unknown message source | Listener configuration |

### Triple Fallback Strategy
```
1. Try LLM → Generate Java code
         ↓ (if fails)
2. Insert TODO comment → "// TODO: Manually convert <element>"
         ↓ (always)
3. Log warning → Recorded in agent_trace for audit
```

### AgentContext (Shared State)
```python
class AgentContext:
    enabled: bool                    # Is LLM enabled?
    llm_config: dict                 # Provider, model, API key
    conversions: list                # Successful AI conversions
    skipped: list                    # Skipped elements (with reasons)

    def record_conversion(element, prompt_summary, code)
    def record_skipped(element, reason)
    def to_summary() → dict         # For API response
```

---

## 7. LLM Validator

**File:** `functions/backend/migrator/llm_validator.py` (704 lines)

### What It Does
After the migration engine generates all files, the LLM Validator reviews the entire codebase for quality, correctness, security, and Spring Boot best practices. Supports 7 different LLM providers.

### Supported LLM Providers

| Provider | Models | Auth |
|----------|--------|------|
| **GitHub Copilot** | gpt-4.1, gpt-4o, gpt-4o-mini, o3-mini, claude-sonnet-4 | GitHub PAT |
| **Anthropic Claude** | claude-sonnet-4, claude-3-5-sonnet, claude-3-opus | ANTHROPIC_API_KEY |
| **OpenAI** | gpt-4o, gpt-4-turbo, gpt-4o-mini, o3-mini | OPENAI_API_KEY |
| **Google Gemini** | gemini-2.5-pro, gemini-2.0-flash, gemini-1.5-pro | GOOGLE_API_KEY |
| **DeepSeek** | deepseek-chat, deepseek-coder, deepseek-reasoner | DEEPSEEK_API_KEY |
| **Groq** | llama-3.3-70b, mixtral-8x7b, llama-3.1-8b | GROQ_API_KEY |
| **Ollama** | codellama:13b, llama3:8b, qwen2.5-coder | Local (port 11434) |

### Validation Checks Performed
1. **Compilation correctness** — Missing imports, syntax errors
2. **Spring Boot best practices** — Proper annotations, DI patterns
3. **Security vulnerabilities** — SQL injection, XXE, hardcoded credentials
4. **Missing imports/annotations** — Auto-detected and reported
5. **TODO items** — Items requiring manual review
6. **Performance suggestions** — N+1 queries, unnecessary blocking
7. **Error handling** — Missing try/catch, unhandled exceptions

### Validation Report Format
```json
{
    "overallScore": 8,
    "summary": "Well-structured code with minor improvements needed",
    "issues": [
        {
            "severity": "warning",
            "file": "CustomerController.java",
            "line": 45,
            "message": "Missing @Valid on @RequestBody",
            "suggestion": "Add @Valid for input validation"
        }
    ],
    "securityIssues": [],
    "bestPractices": ["Use constructor injection over @Autowired"],
    "missingItems": ["API documentation", "Integration tests"]
}
```

---

## 8. RAG Service

**File:** `functions/rag_service.py` (350+ lines)

### What It Does
Provides semantic search over a knowledge base of MuleSoft-to-Spring Boot migration patterns. Enhances LLM prompts with relevant examples and best practices using Retrieval Augmented Generation.

### Architecture
```
User Query → Embedding → pgvector Similarity Search → Top-K Results → LLM Context
```

### Technical Details
- **Embedding Model:** `text-embedding-3-large` (3,072 dimensions)
- **Vector Store:** PostgreSQL `pgvector` extension
- **Distance Metric:** Cosine similarity (`<=>` operator)
- **Default Top-K:** 5 results
- **Score Threshold:** 0.35 minimum similarity

### Knowledge Base Categories
- HTTP listener → REST controller patterns
- Database operations (CRUD) → JPA/JDBC patterns
- DataWeave transformations → Java Stream API patterns
- Error handling → @ControllerAdvice patterns
- Messaging (JMS/AMQP/Kafka) → Spring listener patterns
- Batch processing → Spring Batch patterns
- File operations → Spring Integration patterns
- Security/OAuth → Spring Security patterns

### How RAG Enhances Migration

```
Step 1: Parser detects connectors (http, db, jms)
                    ↓
Step 2: RAG queries for each:
        - "HTTP listener to Spring REST controller"
        - "MuleSoft db:select to Spring JPA"
        - "MuleSoft JMS listener to Spring"
                    ↓
Step 3: Returns relevant patterns with code examples
                    ↓
Step 4: Patterns injected into LLM prompt context
                    ↓
Step 5: LLM generates code with domain-specific knowledge
```

---

## 9. Build Service

**File:** `functions/build_service.py` (472 lines)

### What It Does
Executes Maven builds of generated Spring Boot projects using Azure Container Registry (ACR) Tasks. Compiles the code, runs tests (optional), and produces Docker images — all without requiring a local build environment.

### Build Pipeline
```
1. Extract generated files to temp directory
2. Patch pom.xml (fix LLM-generated issues)
3. Create Dockerfile (multi-stage Maven build)
4. Submit to ACR Quick Build
5. Stream build logs to Azure Table Storage
6. Return build status + logs
```

### Build Log Streaming
Build logs are stored in Azure Table Storage line-by-line for real-time display:
```python
{
    "PartitionKey": build_id,
    "RowKey": f"{line_number:06d}",
    "Line": "BUILD SUCCESS",
    "Level": "info",
    "Timestamp": "2026-04-14T10:30:00Z"
}
```

---

## 10. Validation Service

**File:** `functions/validation_service.py` (1,400+ lines)

### What It Does
Deploys the generated Spring Boot application as a live container and validates it against the original MuleSoft endpoints. Provides side-by-side API response comparison.

### Validation Workflow
```
1. Build Docker image (ACR Quick Build)
2. Deploy to Azure Container Instances (ACI)
3. Wait for /actuator/health (up to 180s)
4. App is live and accessible
5. User triggers comparison:
   - Call MuleSoft endpoint → capture response
   - Call Spring Boot endpoint → capture response
   - Compare status codes, response bodies
6. Display side-by-side results
7. User submits verdict (pass/fail/partial)
8. Auto-teardown after keep_alive_min expires
```

### Safety-Net Patches
Before building, the service applies automatic fixes:
- **`_patch_java_sources()`** — Adds missing Lombok + Spring imports
- **`_patch_pom_xml()`** — Adds missing plugins, fixes dependencies
- **`_patch_application_properties()`** — Fixes driver class references, falls back to H2

---

## 11. GitHub Service

**File:** `functions/github_service.py` (143 lines)

### What It Does
Pushes generated Spring Boot project files directly to a GitHub repository using the GitHub API (via PyGithub).

### Workflow
```
1. Authenticate with GitHub PAT (from request or Key Vault)
2. Get or create target branch
3. Build Git tree from files dict
4. Create commit with all files
5. Return commit SHA + URL
```

---

## 12. Security Module

**File:** `functions/security.py` (250+ lines)

### What It Does
Handles all authentication, authorization, input validation, and rate limiting for the platform.

### Authentication Methods (3 Supported)

| Method | How It Works | When Used |
|--------|-------------|-----------|
| **Azure AD (MSAL)** | JWT token via OIDC flow | Production SSO |
| **Email/Password** | HMAC-SHA256 signed JWT | Non-Azure environments |
| **EasyAuth** | Azure App Service header | Auto-injected by Azure |

### Rate Limiting
- **Mechanism:** Redis sliding window
- **Default:** 30 requests per 60 seconds per user
- **Response:** 429 Too Many Requests with `Retry-After` header

### XXE Prevention
- All XML parsed via `defusedxml`
- Rejects: external entities, DTD expansion, billion-laughs attacks
- Applied before any migration processing

---

## 13. Database Layer

**File:** `functions/db.py` (350+ lines)

### Schema (5 Tables)

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `users` | User accounts | azure_ad_oid, email, role |
| `migrations` | Migration jobs | status, input_xml_files (JSONB), output_files (JSONB) |
| `builds` | Build executions | migration_id, exit_code, build_log |
| `rag_documents` | Knowledge base | content, embedding (vector 3072), category |
| `validations` | Validation jobs | aci_name, test_results (JSONB), user_verdict |

### Connection Management
- Async connection pooling via `asyncpg` (min 2, max 10 connections)
- Prepared statements for SQL injection prevention
- Key Vault credential resolution at startup
- Soft delete pattern (deleted_at timestamp)

---

## 14. Migration Engine (Orchestrator)

**File:** `functions/engine.py` (200+ lines)

### What It Does
Orchestrates the complete migration pipeline, calling each component in sequence and managing the shared `AgentContext`.

### Pipeline Steps
```python
async def run_migration_pipeline(migration_id, xml_files, config, llm_config, dataweave_scripts):
    # Step 1: Validate XML (XXE check)
    validated_xmls = validate_all_xml(xml_files)

    # Step 2: Parse MuleSoft XML
    parsed = parser.parse(xml_content, agent_context)

    # Step 3: Convert DataWeave
    converted_dw = dataweave_converter.convert(parsed.transforms)

    # Step 4: Map connectors → Maven deps
    connector_info = connector_mapper.map(parsed.connectors)

    # Step 5: Convert flows → Java classes
    spring_files = flow_converter.convert(parsed, converted_dw, agent_context)

    # Step 6: Generate complete Spring Boot project
    output_files = spring_generator.generate(spring_files, connector_info, parsed)

    # Step 7: (Optional) LLM validation
    if llm_config.get("enabled"):
        validation_report = llm_validator.validate(output_files, llm_config)

    # Step 8: Return results
    return {
        "files": output_files,
        "errors": errors,
        "agent_trace": agent_context.to_summary(),
        "total_tokens": agent_context.total_tokens,
        "duration_ms": elapsed
    }
```

---

## 15. Function App (API Layer)

**File:** `functions/function_app.py` (2,490 lines)

### What It Does
The main entry point — defines all HTTP endpoints and queue workers for the Azure Functions serverless backend.

### API Endpoints (25+)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v2/migrations` | Create new migration |
| GET | `/api/v2/migrations` | List migrations (paginated) |
| GET | `/api/v2/migrations/{id}` | Get migration details |
| POST | `/api/v2/migrations/upload` | Upload ZIP/folder |
| POST | `/api/v2/migrations/{id}/cancel` | Cancel migration |
| POST | `/api/v2/migrations/{id}/retry` | Retry failed migration |
| GET | `/api/v2/migrations/{id}/files` | List generated files |
| GET | `/api/v2/migrations/{id}/files/{path}` | Download single file |
| POST | `/api/v2/builds` | Trigger Maven build |
| GET | `/api/v2/builds/{id}` | Build status + logs |
| POST | `/api/v2/validations` | Create validation job |
| GET | `/api/v2/validations/{id}` | Validation status |
| POST | `/api/v2/validations/{id}/compare` | Run API comparison |
| POST | `/api/v2/validations/{id}/verdict` | Submit test verdict |
| POST | `/api/v2/validations/{id}/teardown` | Teardown ACI |
| GET | `/api/v2/validations/{id}/logs` | Container logs |
| POST | `/api/v2/rag/search` | Semantic search |
| POST | `/api/v2/rag/seed` | Seed knowledge base |
| GET | `/api/v2/rag/collections` | List RAG collections |
| POST | `/api/v2/github/push` | Push to GitHub |
| POST | `/api/v2/auth/login` | Email/password login |
| GET | `/api/v2/auth/me` | Current user info |
| GET | `/api/health` | Health check |

### Queue Workers (4)

| Queue | Worker | Purpose |
|-------|--------|---------|
| `migration-queue` | `migration_worker()` | Run migration pipeline |
| `build-queue` | `build_worker()` | Execute Maven build |
| `validation-queue` | `validation_worker()` | Build image + deploy ACI |
| `validation-teardown-queue` | `validation_teardown_worker()` | Auto-cleanup expired ACI |

---

## 16. Frontend Application

**Path:** `frontend/src/`

### Pages & Features

| Page | Route | Features |
|------|-------|----------|
| **Dashboard** | `/dashboard` | Stats cards, recent migrations, weekly activity chart |
| **New Migration** | `/migrate` | XML upload/paste, AI config, project settings |
| **Migration View** | `/migrate/:id` | Agent pipeline, code viewer/editor, live feed |
| **History** | `/history` | Filterable list with pagination |
| **Swagger** | `/swagger/:id` | OpenAPI spec viewer |
| **GitHub Push** | `/github/:id` | Push to repo form |
| **Validation** | `/validate/:id` | Deploy, compare, verdict |
| **Knowledge Base** | `/knowledge` | RAG management, search playground |
| **Settings** | `/settings` | LLM config, defaults, theme |
| **Login** | `/login` | Azure AD SSO + email/password |

### Key UI Components
- **Monaco Editor** — Full IDE experience for viewing/editing generated code
- **Agent Pipeline** — Visual progress bar showing each AI agent's status
- **Agent Live Feed** — Real-time streaming of agent decisions and code generation
- **File Tree** — Hierarchical browser for generated project files
- **Comparison Results** — Side-by-side MuleSoft vs Spring Boot API responses
- **Container Logs** — XTerm.js terminal for live container output
