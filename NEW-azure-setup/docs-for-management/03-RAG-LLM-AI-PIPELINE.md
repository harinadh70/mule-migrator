# Agentic AI Pipeline — RAG, LLM, Parsers & Code Generation

> **Version:** 2.0 | **Date:** April 2026 | **For:** CG Management Technical Review

---

## 1. What is "Agentic AI" in This Context?

Traditional code migration tools are rule-based — they match patterns and output templates. Our platform goes beyond this by deploying **autonomous AI agents** that can reason about code, fill gaps in understanding, and generate novel solutions when rules don't cover a scenario.

```
TRADITIONAL MIGRATION TOOL          OUR AGENTIC AI MIGRATOR
========================          ========================
Rule match → Template output       Rule match → Template output
Unknown → Error / Skip             Unknown → AI Agent generates code
No adaptation                      RAG provides domain knowledge
No quality check                   LLM reviews entire codebase
No improvement suggestions         AI suggests optimizations
```

### The 4 AI Agent Roles

| Agent | Role | When Active |
|-------|------|-------------|
| **Planner Agent** | Analyzes XML, identifies risks, plans strategy | Start of migration |
| **Engine Agent** | Converts unknown elements using LLM | During flow conversion |
| **Coder Agent** | Generates Java code for complex scenarios | When rules insufficient |
| **Reviewer Agent** | Reviews all generated code for quality | After generation complete |

---

## 2. The Complete AI Pipeline

```
+======================================================================+
|                     AGENTIC AI MIGRATION PIPELINE                     |
+======================================================================+

PHASE 1: INPUT ANALYSIS
========================
  MuleSoft XML Files
       ↓
  [XXE Validation - defusedxml]
       ↓
  [XML Parser - 30+ namespaces]
       ↓
  Structured Dict: flows, configs, processors, connectors

PHASE 2: RAG CONTEXT BUILDING
==============================
  Detected Connectors (http, db, jms, etc.)
       ↓
  [RAG Service - Semantic Search]
       ↓
  For each connector type:
    → Generate embedding (text-embedding-3-large, 3072 dims)
    → Query pgvector (cosine similarity)
    → Retrieve top-5 migration patterns
       ↓
  Formatted context: "Here's how to convert HTTP listeners to @RestController..."

PHASE 3: DETERMINISTIC CONVERSION (Rule-Based)
===============================================
  [DataWeave Converter]
    → DW 2.0 expressions → Java Streams API
    → MEL expressions → Java references

  [Connector Mapper]
    → MuleSoft connectors → Maven dependencies
    → Connector configs → application.properties

  [Flow Converter]
    → HTTP flows → @RestController classes
    → Scheduler flows → @Scheduled methods
    → JMS/AMQP/Kafka flows → @*Listener classes
    → Sub-flows → Service methods
    → Error handlers → @ControllerAdvice

PHASE 4: AI-ASSISTED CONVERSION (For Unknowns)
===============================================
  Unknown XML element detected
       ↓
  [LLM Agent - convert_unknown_element()]
    System Prompt: "You are a senior Java/Spring Boot engineer..."
    User Prompt: "Convert this MuleSoft XML to Spring Boot Java:
                  <custom:processor operation='validate' config='...' />"
    RAG Context: [relevant migration patterns injected]
       ↓
  LLM generates Java code (with imports)
       ↓
  Code extracted from ```java``` fence
       ↓
  Inserted into generated class
       ↓
  Logged in agent_trace for audit

PHASE 5: PROJECT GENERATION
============================
  [Spring Boot Generator]
    → pom.xml with all dependencies
    → Application.java (@SpringBootApplication)
    → Config classes (JMS, Kafka, Security, etc.)
    → Controllers, Services, Listeners
    → application.properties / .yml
    → Dockerfile (multi-stage)
    → Test templates
    → .gitignore, docker-compose.yml

PHASE 6: AI CODE REVIEW
========================
  All generated files
       ↓
  [LLM Validator - 7 provider support]
    System Prompt: "Review this Spring Boot project for:
                    1. Compilation correctness
                    2. Spring Boot best practices
                    3. Security vulnerabilities
                    4. Missing imports/annotations
                    5. Performance issues"
       ↓
  Validation Report:
    - Overall Score (1-10)
    - Issues with severity levels
    - Security warnings
    - Improvement suggestions
    - Best practice recommendations

PHASE 7: OUTPUT
===============
  Complete Spring Boot project (20-50+ files)
  + Agent trace (full AI decision audit log)
  + Token usage and cost tracking
  + Warnings and manual review items
```

---

## 3. RAG (Retrieval Augmented Generation) — In Detail

### What is RAG?

RAG enhances LLM responses by providing relevant domain-specific context before asking the LLM to generate code. Instead of relying solely on the LLM's training data, we inject curated MuleSoft→Spring Boot migration patterns.

### Our RAG Architecture

```
                    INDEXING (One-time Setup)
                    ========================

Migration Pattern Documents
(100+ curated examples)
       ↓
[text-embedding-3-large]
(3072-dimensional vectors)
       ↓
PostgreSQL pgvector table
(rag_documents with vector column)


                    QUERYING (Per Migration)
                    ========================

Detected: "http:listener with db:select"
       ↓
Query 1: "HTTP listener to Spring REST controller"
Query 2: "MuleSoft db:select to Spring JDBC"
       ↓
[text-embedding-3-large] → query vectors
       ↓
pgvector cosine similarity search
(SELECT *, 1 - (embedding <=> query_vector) AS score
 FROM rag_documents
 WHERE score > 0.35
 ORDER BY score DESC LIMIT 5)
       ↓
Top-5 matching patterns returned
       ↓
Formatted into LLM prompt context
```

### Knowledge Base Contents

| Category | Pattern Count | Examples |
|----------|:------------:|---------|
| HTTP → REST Controller | 15+ | GET/POST/PUT/DELETE/PATCH mappings |
| Database → JPA/JDBC | 12+ | Select, Insert, Update, Stored Procs |
| DataWeave → Java Streams | 20+ | map, filter, reduce, groupBy |
| Error Handling | 8+ | try/catch, @ControllerAdvice |
| Messaging | 10+ | JMS, AMQP, Kafka listeners |
| File Operations | 6+ | Read, Write, SFTP |
| Batch Processing | 5+ | Spring Batch steps |
| Security | 8+ | OAuth2, JWT, Spring Security |
| Caching | 4+ | @Cacheable, Redis |
| **Total** | **100+** | |

### RAG Impact on Code Quality

| Metric | Without RAG | With RAG |
|--------|:-----------:|:--------:|
| Compilation success rate | ~65% | ~90% |
| Spring Boot best practices | Basic | Advanced |
| Correct dependency mapping | ~80% | ~95% |
| Error handling quality | Generic | Pattern-specific |
| Code review score (LLM) | 6/10 avg | 8/10 avg |

---

## 4. LLM Integration — Multi-Provider Architecture

### Why Multi-Provider?

Different LLMs excel at different tasks. Our platform abstracts the provider layer, allowing:
- **Cost optimization** — Use cheaper models for simple tasks
- **Availability** — Failover between providers
- **Quality** — Use best model for code generation
- **Privacy** — Use local Ollama for sensitive code

### Provider Architecture

```
                    LLM Request
                        ↓
              +-------------------+
              | Provider Router   |
              | (llm_validator.py)|
              +-------------------+
                        ↓
    +--------+--------+--------+--------+--------+--------+--------+
    |        |        |        |        |        |        |        |
    v        v        v        v        v        v        v        v
 GitHub   Anthropic  OpenAI  Google  DeepSeek   Groq   Ollama
 Copilot   Claude    GPT-4  Gemini   Coder    Llama3  CodeLlama
    |        |        |        |        |        |        |
    +--------+--------+--------+--------+--------+--------+
                        ↓
              Unified Response Format
              (code + explanation + score)
```

### Provider Comparison

| Provider | Best For | Cost | Speed | Quality |
|----------|---------|:----:|:-----:|:-------:|
| **GitHub Copilot** | Code generation | Free* | Fast | High |
| **Claude claude-sonnet-4** | Code review, complex logic | $$ | Medium | Highest |
| **GPT-4o** | General code tasks | $$ | Fast | High |
| **Gemini 2.5 Pro** | Long context analysis | $ | Fast | High |
| **DeepSeek Coder** | Code-specific tasks | $ | Medium | High |
| **Groq (Llama 3.3)** | Fast iteration | Free | Fastest | Good |
| **Ollama** | Private/offline use | Free | Varies | Good |

*Free with GitHub Copilot subscription

### Token & Cost Tracking

Every LLM call is tracked:
```python
{
    "provider": "github-copilot",
    "model": "gpt-4o",
    "prompt_tokens": 2500,
    "completion_tokens": 800,
    "total_tokens": 3300,
    "cost_usd": 0.012,
    "duration_ms": 3200,
    "purpose": "convert_unknown_element",
    "element": "custom:validator"
}
```

Aggregated per migration:
- Total tokens used
- Total cost (USD)
- Per-agent breakdown
- Stored in `migrations.total_tokens_used` and `migrations.total_cost_usd`

---

## 5. How the Parser Works — Step by Step

### Input (MuleSoft XML)
```xml
<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:db="http://www.mulesoft.org/schema/mule/db"
      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core">

    <http:listener-config name="HTTP_Listener_config">
        <http:listener-connection host="0.0.0.0" port="8081"/>
    </http:listener-config>

    <db:config name="Database_Config">
        <db:mysql-connection host="localhost" port="3306"
                            database="mydb" user="root" password="pass"/>
    </db:config>

    <flow name="getCustomersFlow">
        <http:listener config-ref="HTTP_Listener_config"
                       path="/api/customers" method="GET"/>
        <logger level="INFO" message="Fetching customers"/>
        <db:select config-ref="Database_Config">
            <db:sql>SELECT * FROM customers WHERE active = true</db:sql>
        </db:select>
        <ee:transform>
            <ee:message>
                <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload map (item) -> {
    id: item.id,
    name: item.first_name ++ " " ++ item.last_name,
    email: item.email
}]]></ee:set-payload>
            </ee:message>
        </ee:transform>
    </flow>
</mule>
```

### Step 1: XML Parsing
```python
# defusedxml parses safely (no XXE)
tree = defusedxml.ElementTree.fromstring(xml_content)
```

### Step 2: Namespace Stripping
```python
# Before: {http://www.mulesoft.org/schema/mule/http}listener
# After:  http:listener
```

### Step 3: Flow Extraction
```python
parsed = {
    "global_configs": [
        {"type": "http-listener-config", "name": "HTTP_Listener_config", ...},
        {"type": "db-config", "name": "Database_Config", "driver": "mysql", ...}
    ],
    "flows": [
        {
            "name": "getCustomersFlow",
            "source": {"type": "http-listener", "method": "GET", "path": "/api/customers"},
            "processors": [
                {"type": "logger", "level": "INFO", "message": "Fetching customers"},
                {"type": "db:select", "sql": "SELECT * FROM customers WHERE active = true"},
                {"type": "ee:transform", "dataweave": "%dw 2.0\noutput application/json\n---\n..."}
            ]
        }
    ],
    "connectors": {"http", "db", "ee"}
}
```

### Step 4: DataWeave Conversion
```python
# Input:  payload map (item) -> { id: item.id, name: item.first_name ++ " " ++ item.last_name }
# Output: payload.stream().map(item -> Map.of(
#             "id", item.get("id"),
#             "name", item.get("first_name") + " " + item.get("last_name")
#         )).collect(Collectors.toList())
```

### Step 5: Flow Conversion → Spring Boot Controller
```java
@RestController
@RequestMapping("/api")
@Slf4j
@RequiredArgsConstructor
public class CustomerController {

    private final JdbcTemplate jdbcTemplate;

    @GetMapping("/customers")
    public ResponseEntity<?> getCustomers() {
        log.info("Fetching customers");

        List<Map<String, Object>> result = jdbcTemplate.queryForList(
            "SELECT * FROM customers WHERE active = true"
        );

        List<Map<String, Object>> response = result.stream()
            .map(item -> Map.of(
                "id", item.get("id"),
                "name", item.get("first_name") + " " + item.get("last_name"),
                "email", item.get("email")
            ))
            .collect(Collectors.toList());

        return ResponseEntity.ok(response);
    }
}
```

---

## 6. Spring Boot Project Structure Generation

### How Files Are Created

The Spring Boot Generator assembles files using a layered approach:

```
Layer 1: POM.xml
  → Spring Boot parent (3.2.0)
  → Dependencies from connector_mapper
  → Plugins (maven-compiler with Lombok)

Layer 2: Main Application Class
  → @SpringBootApplication
  → @EnableScheduling (if schedulers detected)
  → @EnableCaching (if caching detected)

Layer 3: Configuration Classes
  → For each detected connector, generate config class
  → RestTemplateConfig, JmsConfig, KafkaConfig, etc.

Layer 4: Business Classes
  → Controllers (from flow_converter output)
  → Services (extracted business logic)
  → Listeners (JMS, AMQP, Kafka)
  → Schedulers (from scheduler flows)

Layer 5: Exception Handling
  → Custom exception classes
  → GlobalExceptionHandler (@ControllerAdvice)

Layer 6: Resources
  → application.properties (H2 default, with commented prod configs)
  → application-dev.properties
  → application-prod.properties
  → logback-spring.xml

Layer 7: Infrastructure
  → Dockerfile (multi-stage Maven + JRE)
  → docker-compose.yml
  → .gitignore

Layer 8: Tests
  → ApplicationTests.java (context load)
  → Controller tests (@WebMvcTest)
```

### Example Generated Project

For a MuleSoft app with HTTP, Database, and JMS connectors:

```
customer-service/
├── pom.xml                                    # 85 lines
├── Dockerfile                                 # 15 lines
├── docker-compose.yml                         # 25 lines
├── .gitignore                                 # 20 lines
├── src/main/java/com/example/customerservice/
│   ├── CustomerServiceApplication.java        # 12 lines
│   ├── config/
│   │   ├── RestTemplateConfig.java           # 15 lines
│   │   ├── JmsConfig.java                    # 30 lines
│   │   └── SchedulingConfig.java             # 10 lines
│   ├── controller/
│   │   └── CustomerController.java           # 80 lines
│   ├── service/
│   │   └── CustomerService.java              # 60 lines
│   ├── listener/
│   │   └── OrderJmsListener.java             # 35 lines
│   └── exception/
│       ├── ResourceNotFoundException.java     # 12 lines
│       ├── BadRequestException.java          # 12 lines
│       └── GlobalExceptionHandler.java       # 40 lines
├── src/main/resources/
│   ├── application.properties                # 25 lines
│   ├── application-dev.properties            # 10 lines
│   ├── application-prod.properties           # 10 lines
│   └── logback-spring.xml                    # 35 lines
└── src/test/java/com/example/customerservice/
    ├── CustomerServiceApplicationTests.java   # 10 lines
    └── controller/
        └── CustomerControllerTests.java      # 45 lines
```

---

## 7. Quality Assurance Pipeline

```
GENERATED CODE
     ↓
[Import Patching] ← Safety net: add missing Lombok + Spring imports
     ↓
[POM Patching] ← Fix duplicate deps, add missing plugins
     ↓
[Properties Patching] ← Fix driver class references, H2 fallback
     ↓
[LLM Code Review] ← AI reviews for quality, security, best practices
     ↓
[ACR Build] ← Compile with Maven to verify compilation
     ↓
[ACI Deploy] ← Run as container, verify health check
     ↓
[API Comparison] ← Compare with original MuleSoft responses
     ↓
VALIDATED, PRODUCTION-READY CODE
```
