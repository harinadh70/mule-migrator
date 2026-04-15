"""
Connector Mapper – Maps ALL MuleSoft connectors to Spring Boot equivalents.
Covers 30+ connectors, error types, HTTP methods, and Spring config generation.
"""


# ══════════════════════════════════════════════════════════════════════════════
#  Dependency map:  MuleSoft connector → list of Maven coordinates
# ══════════════════════════════════════════════════════════════════════════════
CONNECTOR_DEPENDENCY_MAP = {
    # ── HTTP / Web ────────────────────────────────────────────────────────
    "http": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-web"},
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-webflux"},
    ],
    # ── Database ──────────────────────────────────────────────────────────
    "database": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-data-jpa"},
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-jdbc"},
    ],
    # ── JMS ───────────────────────────────────────────────────────────────
    "jms": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-activemq"},
    ],
    # ── AMQP (RabbitMQ) ──────────────────────────────────────────────────
    "amqp": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-amqp"},
    ],
    # ── Kafka ─────────────────────────────────────────────────────────────
    "kafka": [
        {"groupId": "org.springframework.kafka", "artifactId": "spring-kafka"},
    ],
    # ── VM  (Spring Events / in-memory) ──────────────────────────────────
    "vm": [],
    # ── File (java.nio) ──────────────────────────────────────────────────
    "file": [],
    # ── SFTP ──────────────────────────────────────────────────────────────
    "sftp": [
        {"groupId": "org.springframework.integration", "artifactId": "spring-integration-sftp"},
    ],
    # ── FTP ───────────────────────────────────────────────────────────────
    "ftp": [
        {"groupId": "org.springframework.integration", "artifactId": "spring-integration-ftp"},
    ],
    # ── Email ─────────────────────────────────────────────────────────────
    "email": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-mail"},
    ],
    # ── Web Service Consumer (SOAP) ──────────────────────────────────────
    "ws": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-web-services"},
        {"groupId": "org.springframework.ws", "artifactId": "spring-ws-core"},
    ],
    "wsc": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-web-services"},
        {"groupId": "org.springframework.ws", "artifactId": "spring-ws-core"},
    ],
    # ── Object Store → Redis / Cache ─────────────────────────────────────
    "objectstore": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-data-redis"},
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-cache"},
    ],
    # ── Batch ─────────────────────────────────────────────────────────────
    "batch": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-batch"},
    ],
    # ── Validation ────────────────────────────────────────────────────────
    "validation": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-validation"},
    ],
    # ── Salesforce ────────────────────────────────────────────────────────
    "salesforce": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-web"},
        # Salesforce REST API via RestTemplate / WebClient
    ],
    # ── AWS S3 ────────────────────────────────────────────────────────────
    "s3": [
        {"groupId": "software.amazon.awssdk", "artifactId": "s3"},
        {"groupId": "software.amazon.awssdk", "artifactId": "sts"},
    ],
    # ── AWS SQS ───────────────────────────────────────────────────────────
    "sqs": [
        {"groupId": "software.amazon.awssdk", "artifactId": "sqs"},
        {"groupId": "io.awspring.cloud", "artifactId": "spring-cloud-aws-messaging"},
    ],
    # ── AWS SNS ───────────────────────────────────────────────────────────
    "sns": [
        {"groupId": "software.amazon.awssdk", "artifactId": "sns"},
    ],
    # ── MongoDB ───────────────────────────────────────────────────────────
    "mongo": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-data-mongodb"},
    ],
    # ── Redis ─────────────────────────────────────────────────────────────
    "redis": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-data-redis"},
    ],
    # ── Elasticsearch ─────────────────────────────────────────────────────
    "elasticsearch": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-data-elasticsearch"},
    ],
    # ── Anypoint MQ → Spring JMS / AMQP ──────────────────────────────────
    "anypoint-mq": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-amqp"},
    ],
    # ── OAuth / Security ──────────────────────────────────────────────────
    "oauth": [
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-security"},
        {"groupId": "org.springframework.boot", "artifactId": "spring-boot-starter-oauth2-client"},
    ],
    # ── Azure Blob Storage ──────────────────────────────────────────────────
    "azure-blob": [
        {"groupId": "com.azure", "artifactId": "azure-storage-blob"},
        {"groupId": "com.azure", "artifactId": "azure-identity"},
    ],
    # ── Azure File Share ──────────────────────────────────────────────────
    "azure-file": [
        {"groupId": "com.azure", "artifactId": "azure-storage-file-share"},
        {"groupId": "com.azure", "artifactId": "azure-identity"},
    ],
    # ── Azure Service Bus ─────────────────────────────────────────────────
    "azure-service-bus": [
        {"groupId": "com.azure.spring", "artifactId": "spring-cloud-azure-starter-servicebus"},
    ],
    # ── Azure Cosmos DB ───────────────────────────────────────────────────
    "azure-cosmos": [
        {"groupId": "com.azure.spring", "artifactId": "spring-cloud-azure-starter-data-cosmos"},
    ],
    # ── Azure Key Vault ───────────────────────────────────────────────────
    "azure-keyvault": [
        {"groupId": "com.azure.spring", "artifactId": "spring-cloud-azure-starter-keyvault"},
    ],
    # ── APIkit → handled by Spring Web ────────────────────────────────────
    "apikit": [],
    # ── EE core (DataWeave transforms) ────────────────────────────────────
    "ee": [],
    # ── Scripting ─────────────────────────────────────────────────────────
    "scripting": [],
}


# ══════════════════════════════════════════════════════════════════════════════
#  HTTP method → Spring annotation
# ══════════════════════════════════════════════════════════════════════════════
HTTP_METHOD_MAP = {
    "GET":     "GetMapping",
    "POST":    "PostMapping",
    "PUT":     "PutMapping",
    "DELETE":  "DeleteMapping",
    "PATCH":   "PatchMapping",
    "HEAD":    "GetMapping",
    "OPTIONS": "RequestMapping",
}


# ══════════════════════════════════════════════════════════════════════════════
#  MuleSoft error type → Java exception class
# ══════════════════════════════════════════════════════════════════════════════
ERROR_TYPE_MAP = {
    # HTTP
    "HTTP:NOT_FOUND":              "ResourceNotFoundException",
    "HTTP:BAD_REQUEST":            "BadRequestException",
    "HTTP:UNAUTHORIZED":           "UnauthorizedException",
    "HTTP:FORBIDDEN":              "AccessDeniedException",
    "HTTP:METHOD_NOT_ALLOWED":     "MethodNotAllowedException",
    "HTTP:NOT_ACCEPTABLE":         "NotAcceptableException",
    "HTTP:UNSUPPORTED_MEDIA_TYPE": "UnsupportedMediaTypeException",
    "HTTP:TOO_MANY_REQUESTS":      "TooManyRequestsException",
    "HTTP:INTERNAL_SERVER_ERROR":  "InternalServerErrorException",
    "HTTP:SERVICE_UNAVAILABLE":    "ServiceUnavailableException",
    "HTTP:TIMEOUT":                "java.util.concurrent.TimeoutException",
    "HTTP:CONNECTIVITY":           "java.net.ConnectException",
    "HTTP:PARSING":                "HttpMessageNotReadableException",
    "HTTP:SECURITY":               "SecurityException",
    "HTTP:CLIENT_SECURITY":        "SecurityException",
    "HTTP:RETRY_EXHAUSTED":        "RetryExhaustedException",

    # Database
    "DB:CONNECTIVITY":             "org.springframework.jdbc.CannotGetJdbcConnectionException",
    "DB:BAD_SQL_SYNTAX":           "org.springframework.jdbc.BadSqlGrammarException",
    "DB:QUERY_EXECUTION":          "org.springframework.dao.DataAccessException",
    "DB:INVALID_DATABASE":         "org.springframework.dao.DataAccessException",
    "DB:INVALID_INPUT":            "IllegalArgumentException",

    # JMS
    "JMS:CONNECTIVITY":            "org.springframework.jms.JmsException",
    "JMS:CONSUMING":               "org.springframework.jms.JmsException",
    "JMS:PUBLISHING":              "org.springframework.jms.JmsException",
    "JMS:TIMEOUT":                 "java.util.concurrent.TimeoutException",
    "JMS:ACK":                     "javax.jms.JMSException",

    # File / FTP / SFTP
    "FILE:FILE_NOT_FOUND":         "java.io.FileNotFoundException",
    "FILE:ILLEGAL_PATH":           "java.nio.file.InvalidPathException",
    "FILE:ACCESS_DENIED":          "java.nio.file.AccessDeniedException",
    "FILE:CONNECTIVITY":           "java.io.IOException",
    "SFTP:CONNECTIVITY":           "java.io.IOException",
    "SFTP:FILE_NOT_FOUND":         "java.io.FileNotFoundException",
    "FTP:CONNECTIVITY":            "java.io.IOException",

    # Validation
    "VALIDATION:INVALID_BOOLEAN":  "IllegalArgumentException",
    "VALIDATION:INVALID_NUMBER":   "NumberFormatException",
    "VALIDATION:INVALID_EMAIL":    "IllegalArgumentException",
    "VALIDATION:INVALID_URL":      "IllegalArgumentException",
    "VALIDATION:INVALID_SIZE":     "IllegalArgumentException",
    "VALIDATION:NULL":             "NullPointerException",
    "VALIDATION:NOT_NULL":         "IllegalArgumentException",
    "VALIDATION:BLANK_STRING":     "IllegalArgumentException",
    "VALIDATION:NOT_BLANK_STRING": "IllegalArgumentException",
    "VALIDATION:EMPTY_COLLECTION": "IllegalArgumentException",
    "VALIDATION:NOT_EMPTY_COLLECTION": "IllegalArgumentException",

    # Expression / Transformation
    "EXPRESSION":                  "RuntimeException",
    "TRANSFORMATION":              "org.springframework.core.convert.ConversionException",

    # Mule core
    "MULE:EXPRESSION":             "RuntimeException",
    "MULE:SECURITY":               "SecurityException",
    "MULE:RETRY_EXHAUSTED":        "RuntimeException",
    "MULE:ROUTING":                "RuntimeException",
    "MULE:CONNECTIVITY":           "java.net.ConnectException",
    "MULE:TIMEOUT":                "java.util.concurrent.TimeoutException",
    "MULE:DUPLICATE_MESSAGE":      "RuntimeException",

    # AMQP
    "AMQP:CONNECTIVITY":           "org.springframework.amqp.AmqpException",
    "AMQP:PUBLISHING":             "org.springframework.amqp.AmqpException",

    # Kafka
    "KAFKA:CONNECTIVITY":          "org.springframework.kafka.KafkaException",

    # Salesforce
    "SALESFORCE:CONNECTIVITY":     "RuntimeException",
    "SALESFORCE:INVALID_SESSION":  "SecurityException",

    # AWS
    "S3:CONNECTIVITY":             "software.amazon.awssdk.core.exception.SdkException",
    "SQS:CONNECTIVITY":            "software.amazon.awssdk.core.exception.SdkException",

    # Catch-all
    "ANY":                         "Exception",
}


# ══════════════════════════════════════════════════════════════════════════════
#  Processor tag → Spring equivalent (display hint)
# ══════════════════════════════════════════════════════════════════════════════
PROCESSOR_MAP = {
    "logger":                      'log.{}("{}")',
    "set-payload":                 "// Set response body",
    "set-variable":                "// Set variable",
    "remove-variable":             "// Remove variable",
    "choice":                      "if/else",
    "scatter-gather":              "CompletableFuture.allOf()",
    "for-each":                    "for loop / stream",
    "parallel-for-each":           "parallelStream / CompletableFuture",
    "flow-ref":                    "method call / @Autowired service",
    "raise-error":                 "throw new Exception()",
    "try":                         "try-catch",
    "until-successful":            "@Retryable / RetryTemplate",
    "first-successful":            "fallback chain",
    "round-robin":                 "load-balancer rotation",
    "async":                       "@Async / CompletableFuture",
    "parse-template":              "Thymeleaf / template engine",
    "idempotent-message-validator":"idempotency check (Redis / DB)",
    "batch:job":                   "Spring Batch Job",
    "batch:step":                  "Spring Batch Step",
    "cache":                       "@Cacheable",
}


class ConnectorMapper:
    def __init__(self):
        self.warnings = []

    def map_connectors(self, parsed_data: dict, agent_context=None) -> dict:
        """Map detected MuleSoft connectors to Spring Boot dependencies.

        Args:
            parsed_data: Output from MuleSoftParser.parse().
            agent_context: Optional AgentContext for LLM-based fallback on unknown connectors.
        """
        self._agent_ctx = agent_context
        connectors = parsed_data.get("connectors", set())
        dependencies = []
        seen = set()

        # Ensure HTTP starter when listeners exist
        has_http = any(
            f.get("source", {}).get("type") == "http-listener"
            for f in parsed_data.get("flows", [])
            if f.get("source")
        )
        if has_http or "http" in connectors:
            connectors.add("http")

        # Batch jobs detected
        if parsed_data.get("batch_jobs"):
            connectors.add("batch")

        # OAuth detected
        if parsed_data.get("secure_properties") or any(
            c.get("authentication") for c in parsed_data.get("global_configs", [])
            if c.get("type") == "http-request"
        ):
            connectors.add("oauth")

        for connector in connectors:
            deps = CONNECTOR_DEPENDENCY_MAP.get(connector, [])
            if not deps and connector not in CONNECTOR_DEPENDENCY_MAP:
                # Unknown connector — try LLM-assisted fallback
                if self._agent_ctx:
                    from .llm_agent import suggest_connector_mapping
                    suggestion = suggest_connector_mapping(
                        self._agent_ctx, connector)
                    if suggestion and suggestion.get("maven_dependencies"):
                        deps = suggestion["maven_dependencies"]
                        self.warnings.append(
                            f"Connector '{connector}' mapped via LLM: "
                            f"{suggestion.get('notes', '')}")
                    else:
                        self.warnings.append(
                            f"Unknown connector '{connector}' — LLM could not map. "
                            f"Add dependencies manually.")
                else:
                    self.warnings.append(
                        f"Unknown connector '{connector}' — no Spring dependency mapped. "
                        f"Enable LLM-assisted conversion for auto-suggestions.")
            for dep in deps:
                key = f"{dep['groupId']}:{dep['artifactId']}"
                if key not in seen:
                    seen.add(key)
                    dependencies.append(dep)

        # ── Common dependencies always included ───────────────────────
        common = [
            {"groupId": "org.springframework.boot",
             "artifactId": "spring-boot-starter"},
            {"groupId": "org.springframework.boot",
             "artifactId": "spring-boot-starter-actuator"},
            {"groupId": "org.springframework.boot",
             "artifactId": "spring-boot-starter-test", "scope": "test"},
            {"groupId": "org.projectlombok",
             "artifactId": "lombok"},  # Handled by spring_generator with <optional>true</optional>
        ]
        for dep in common:
            key = f"{dep['groupId']}:{dep['artifactId']}"
            if key not in seen:
                seen.add(key)
                dependencies.append(dep)

        # Jackson for JSON
        if "ee" in connectors or "http" in connectors:
            key = "com.fasterxml.jackson.core:jackson-databind"
            if key not in seen:
                seen.add(key)
                dependencies.append({
                    "groupId": "com.fasterxml.jackson.core",
                    "artifactId": "jackson-databind",
                })

        # Retry support if until-successful is used
        if self._uses_until_successful(parsed_data):
            key = "org.springframework.retry:spring-retry"
            if key not in seen:
                seen.add(key)
                dependencies.append({
                    "groupId": "org.springframework.retry",
                    "artifactId": "spring-retry",
                })
                dependencies.append({
                    "groupId": "org.springframework",
                    "artifactId": "spring-aspects",
                })

        return {
            "connectors": connectors,
            "dependencies": dependencies,
            "warnings": self.warnings,
        }

    # ── HTTP annotation helper ────────────────────────────────────────────
    def get_http_annotation(self, method: str) -> str:
        method = method.upper().strip() if method else "GET"
        if "," in method:
            methods = [m.strip() for m in method.split(",")]
            method_enums = ", ".join(f"RequestMethod.{m}" for m in methods)
            return f'RequestMapping(method = {{{method_enums}}})'
        return HTTP_METHOD_MAP.get(method, "RequestMapping")

    # ── Exception class helper ────────────────────────────────────────────
    def get_exception_class(self, mule_error_type: str) -> str:
        return ERROR_TYPE_MAP.get(mule_error_type, "RuntimeException")

    # ── Spring config properties for a connector config ───────────────────
    def get_spring_config_for_connector(self, connector_type: str, config: dict) -> dict:
        props = {}

        if connector_type == "http-listener":
            props["server.port"] = config.get("port", "8081")
            if config.get("tls"):
                props["server.ssl.enabled"] = "true"

        elif connector_type == "http-request":
            name = self._to_property_name(config.get("name", ""))
            host = config.get("host", "localhost")
            proto = config.get("protocol", "HTTP").lower()
            default_port = "443" if proto == "https" else "80"
            port = config.get("port", default_port)
            base = config.get("basePath", "/")
            # Don't include port in URL if it's the default for the protocol
            if (proto == "https" and str(port) == "443") or (proto == "http" and str(port) == "80"):
                props[f"external.api.{name}.url"] = f"{proto}://{host}{base}"
            else:
                props[f"external.api.{name}.url"] = f"{proto}://{host}:{port}{base}"
            if config.get("authentication"):
                auth = config["authentication"]
                props[f"external.api.{name}.auth.type"] = auth.get("type", "")
                if auth.get("username"):
                    props[f"external.api.{name}.auth.username"] = auth["username"]
                if auth.get("clientId"):
                    props[f"external.api.{name}.auth.client-id"] = auth["clientId"]

        elif connector_type == "database":
            if config.get("url"):
                props["spring.datasource.url"] = config["url"]
            if config.get("driver"):
                props["spring.datasource.driver-class-name"] = config["driver"]
            if config.get("user"):
                props["spring.datasource.username"] = config["user"]
            if config.get("password"):
                props["spring.datasource.password"] = config["password"]
            props["spring.jpa.hibernate.ddl-auto"] = "none"
            props["spring.jpa.show-sql"] = "true"

        elif connector_type == "jms":
            props["spring.activemq.broker-url"] = "tcp://localhost:61616"
            props["spring.activemq.user"] = "admin"
            props["spring.activemq.password"] = "admin"

        elif connector_type == "amqp":
            props["spring.rabbitmq.host"] = "localhost"
            props["spring.rabbitmq.port"] = "5672"
            props["spring.rabbitmq.username"] = "guest"
            props["spring.rabbitmq.password"] = "guest"

        elif connector_type.startswith("kafka"):
            props["spring.kafka.bootstrap-servers"] = "localhost:9092"
            props["spring.kafka.consumer.group-id"] = "migrated-app-group"
            props["spring.kafka.consumer.auto-offset-reset"] = "earliest"

        elif connector_type == "email-smtp":
            props["spring.mail.host"] = "smtp.example.com"
            props["spring.mail.port"] = "587"
            props["spring.mail.username"] = ""
            props["spring.mail.password"] = ""
            props["spring.mail.properties.mail.smtp.auth"] = "true"
            props["spring.mail.properties.mail.smtp.starttls.enable"] = "true"

        elif connector_type in ("email-imap", "email-pop3"):
            props["spring.mail.host"] = "imap.example.com"
            props["spring.mail.port"] = "993"

        elif connector_type == "sftp":
            props["sftp.host"] = "localhost"
            props["sftp.port"] = "22"
            props["sftp.username"] = ""
            props["sftp.password"] = ""
            props["sftp.remote-directory"] = "/"

        elif connector_type == "ftp":
            props["ftp.host"] = "localhost"
            props["ftp.port"] = "21"
            props["ftp.username"] = ""
            props["ftp.password"] = ""

        elif connector_type == "objectstore":
            props["spring.data.redis.host"] = "localhost"
            props["spring.data.redis.port"] = "6379"

        elif connector_type == "redis":
            props["spring.data.redis.host"] = "localhost"
            props["spring.data.redis.port"] = "6379"

        elif connector_type == "mongo":
            props["spring.data.mongodb.uri"] = "mongodb://localhost:27017/mydb"

        elif connector_type == "elasticsearch":
            props["spring.elasticsearch.uris"] = "http://localhost:9200"

        elif connector_type == "s3":
            props["aws.s3.region"] = "us-east-1"
            props["aws.s3.bucket"] = ""

        elif connector_type == "sqs":
            props["aws.sqs.region"] = "us-east-1"
            props["aws.sqs.queue-url"] = ""

        elif connector_type == "salesforce":
            props["salesforce.instance-url"] = "https://login.salesforce.com"
            props["salesforce.client-id"] = ""
            props["salesforce.client-secret"] = ""
            props["salesforce.username"] = ""
            props["salesforce.password"] = ""

        elif connector_type in ("azure-blob", "azure-file"):
            props["azure.storage.account-name"] = config.get("accountName", "${AZURE_STORAGE_ACCOUNT}")
            props["azure.storage.account-key"] = "${AZURE_STORAGE_KEY}"
            if config.get("containerName"):
                props["azure.storage.container"] = config["containerName"]
            if config.get("shareName"):
                props["azure.storage.share-name"] = config["shareName"]

        elif connector_type == "azure-service-bus":
            props["spring.cloud.azure.servicebus.connection-string"] = "${AZURE_SERVICEBUS_CONNECTION_STRING}"
            props["spring.cloud.azure.servicebus.namespace"] = config.get("namespace", "")

        elif connector_type == "azure-cosmos":
            props["spring.cloud.azure.cosmos.endpoint"] = config.get("endpoint", "${AZURE_COSMOS_ENDPOINT}")
            props["spring.cloud.azure.cosmos.key"] = "${AZURE_COSMOS_KEY}"
            props["spring.cloud.azure.cosmos.database"] = config.get("database", "")

        elif connector_type == "azure-keyvault":
            props["spring.cloud.azure.keyvault.secret.property-sources[0].endpoint"] = config.get("vaultUrl", "${AZURE_KEYVAULT_URL}")

        return props

    # ── Internal helpers ──────────────────────────────────────────────────
    def _uses_until_successful(self, parsed_data: dict) -> bool:
        for flow in parsed_data.get("flows", []) + parsed_data.get("sub_flows", []):
            for proc in flow.get("processors", []):
                if proc.get("tag") == "until-successful":
                    return True
        return False

    def _to_property_name(self, name: str) -> str:
        import re
        name = re.sub(r"[^a-zA-Z0-9]", "-", name).lower()
        return re.sub(r"-+", "-", name).strip("-")

    def _to_bean_name(self, name: str) -> str:
        name = name.replace("-", "_").replace(" ", "_")
        parts = name.split("_")
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
