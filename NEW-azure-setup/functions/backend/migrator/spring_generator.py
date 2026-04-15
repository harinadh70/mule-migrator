"""
Spring Boot Project Generator – Produces a complete, runnable Spring Boot project.

Generates:
  - pom.xml with all required dependencies
  - Main application class with correct annotations
  - application.properties / application.yml (multi-profile)
  - Config classes: Scheduling, JMS, AMQP, Kafka, RestTemplate, WebClient,
                    Redis/Cache, Security/OAuth2, Async, Batch, SFTP, CORS
  - Exception classes
  - .gitignore, test class, Dockerfile, docker-compose.yml
"""
import re


class SpringBootGenerator:
    def __init__(self, project_name="migrated-app", group_id="com.example",
                 java_version="17"):
        # Sanitize project_name for Maven artifactId (no spaces, special chars)
        import re as _re
        self.project_name = _re.sub(r"[^a-zA-Z0-9._-]", "-", project_name).strip("-")
        if not self.project_name:
            self.project_name = "migrated-app"
        self.group_id = group_id
        self.java_version = java_version
        self.package_path = group_id.replace(".", "/")

    # ══════════════════════════════════════════════════════════════════════
    #  MAIN ENTRY
    # ══════════════════════════════════════════════════════════════════════
    def generate(self, spring_files: dict, connector_info: dict,
                 parsed_data: dict) -> dict:
        files = {}

        # ── pom.xml ───────────────────────────────────────────────────
        files["pom.xml"] = self._generate_pom(connector_info)

        # ── Main Application class ────────────────────────────────────
        app_class = self._to_class_name(self.project_name) + "Application"
        files[f"src/main/java/{self.package_path}/{app_class}.java"] = \
            self._generate_main_app(app_class, parsed_data, connector_info)

        # ── application.properties & yml ──────────────────────────────
        files["src/main/resources/application.properties"] = \
            self._generate_properties(parsed_data, connector_info)
        files["src/main/resources/application.yml"] = \
            self._generate_yaml_properties(parsed_data, connector_info)
        for profile in ("dev", "sit", "uat", "preprod", "prod"):
            files[f"src/main/resources/application-{profile}.properties"] = \
                self._generate_profile_properties(profile, parsed_data)

        # ── logback-spring.xml ──────────────────────────────────────────
        files["src/main/resources/logback-spring.xml"] = \
            self._generate_logback_config()

        # ── Generated Java source files ───────────────────────────────
        for rel_path, content in spring_files.items():
            content = content.replace(
                "package com.example.",
                f"package {self.group_id}.",
            )
            content = content.replace(
                "package com.example;",
                f"package {self.group_id};",
            )
            # Add OpenAPI annotations to controller classes
            if "@RestController" in content or "@Controller" in content:
                content = self._add_openapi_annotations(content, rel_path)
            files[f"src/main/java/{self.package_path}/{rel_path}"] = content

        connectors = connector_info.get("connectors", set())

        # ── Config classes ────────────────────────────────────────────
        has_scheduling = any("scheduler" in k for k in spring_files)
        has_jms = "jms" in connectors
        has_amqp = "amqp" in connectors
        has_kafka = "kafka" in connectors
        has_rest_template = any("RestTemplate" in v for v in spring_files.values())
        has_webclient = any("WebClient" in v for v in spring_files.values())
        has_redis = "redis" in connectors or "objectstore" in connectors
        has_oauth = "oauth" in connectors
        has_async = any("CompletableFuture.runAsync" in v for v in spring_files.values())
        has_batch = "batch" in connectors or parsed_data.get("batch_jobs")
        has_sftp = "sftp" in connectors
        has_ftp = "ftp" in connectors
        has_cache = any("@Cacheable" in v or "cache" in v.lower() for v in spring_files.values())
        has_email = "email" in connectors
        has_s3 = "s3" in connectors
        has_sqs = "sqs" in connectors
        has_mongo = "mongo" in connectors
        has_salesforce = "salesforce" in connectors
        has_ws = "ws" in connectors or "wsc" in connectors

        cfg_path = f"src/main/java/{self.package_path}/config"

        if has_scheduling:
            files[f"{cfg_path}/SchedulingConfig.java"] = self._gen_scheduling_config()
        if has_jms:
            files[f"{cfg_path}/JmsConfig.java"] = self._gen_jms_config()
        if has_amqp:
            files[f"{cfg_path}/AmqpConfig.java"] = self._gen_amqp_config()
        if has_kafka:
            files[f"{cfg_path}/KafkaConfig.java"] = self._gen_kafka_config()
        if has_rest_template:
            files[f"{cfg_path}/RestTemplateConfig.java"] = self._gen_rest_template_config()
        if has_webclient:
            files[f"{cfg_path}/WebClientConfig.java"] = self._gen_webclient_config(parsed_data)
        if has_redis or has_cache:
            files[f"{cfg_path}/CacheConfig.java"] = self._gen_cache_config()
        if has_oauth:
            files[f"{cfg_path}/SecurityConfig.java"] = self._gen_security_config()
        if has_async:
            files[f"{cfg_path}/AsyncConfig.java"] = self._gen_async_config()
        if has_batch:
            files[f"{cfg_path}/BatchConfig.java"] = self._gen_batch_config()
        if has_sftp:
            files[f"{cfg_path}/SftpConfig.java"] = self._gen_sftp_config()
        if has_ftp:
            files[f"{cfg_path}/FtpConfig.java"] = self._gen_ftp_config()
        if has_s3:
            files[f"{cfg_path}/AwsS3Config.java"] = self._gen_s3_config()
        if has_sqs:
            files[f"{cfg_path}/AwsSqsConfig.java"] = self._gen_sqs_config()
        if has_ws:
            files[f"{cfg_path}/WebServiceConfig.java"] = self._gen_ws_config()

        # CORS config always helpful for API projects
        files[f"{cfg_path}/CorsConfig.java"] = self._gen_cors_config()

        # ── Exception classes ─────────────────────────────────────────
        exc_path = f"src/main/java/{self.package_path}/exception"
        for exc in ("ResourceNotFoundException", "BadRequestException",
                     "UnauthorizedException", "ServiceUnavailableException",
                     "TooManyRequestsException"):
            files[f"{exc_path}/{exc}.java"] = self._gen_exception_class(exc)

        # ── Utility classes ───────────────────────────────────────────
        files[f"src/main/java/{self.package_path}/util/JsonUtil.java"] = self._gen_json_util()

        # ── .gitignore ────────────────────────────────────────────────
        files[".gitignore"] = self._generate_gitignore()

        # ── Test classes ───────────────────────────────────────────────
        files[f"src/test/java/{self.package_path}/{app_class}Tests.java"] = \
            self._generate_test_class(app_class)

        # Controller unit tests (@WebMvcTest)
        controller_test_files = self._generate_controller_tests(spring_files)
        for rel_path, content in controller_test_files.items():
            files[f"src/test/java/{self.package_path}/{rel_path}"] = content

        # Controller integration tests (@SpringBootTest)
        integration_test_files = self._generate_integration_tests(spring_files)
        for rel_path, content in integration_test_files.items():
            files[f"src/test/java/{self.package_path}/{rel_path}"] = content

        # ── Dockerfile ────────────────────────────────────────────────
        files["Dockerfile"] = self._generate_dockerfile()

        # ── docker-compose.yml ────────────────────────────────────────
        files["docker-compose.yml"] = self._generate_docker_compose(connectors)

        return files

    # ══════════════════════════════════════════════════════════════════════
    #  POM.XML
    # ══════════════════════════════════════════════════════════════════════
    def _generate_pom(self, connector_info):
        deps = connector_info.get("dependencies", [])
        dep_xml = ""
        for d in deps:
            scope = d.get("scope", "")
            scope_xml = f"\n            <scope>{scope}</scope>" if scope else ""
            dep_xml += f"""
        <dependency>
            <groupId>{d['groupId']}</groupId>
            <artifactId>{d['artifactId']}</artifactId>{scope_xml}
        </dependency>"""

        # ── Additional dependencies for a complete, runnable project ───
        dep_xml += """

        <!-- Lombok for @Slf4j, @RequiredArgsConstructor etc. -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>

        <!-- OpenAPI / Swagger UI -->
        <dependency>
            <groupId>org.springdoc</groupId>
            <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
            <version>2.3.0</version>
        </dependency>

        <!-- Actuator for health checks and monitoring -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>

        <!-- Spring Boot Test -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>

        <!-- H2 in-memory database (for unit/integration tests only) -->
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>test</scope>
        </dependency>

        <!-- MySQL connector (enabled — detected from MuleSoft config) -->
        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!-- PostgreSQL connector (uncomment if needed)
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        -->"""

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
        <relativePath/>
    </parent>

    <groupId>{self.group_id}</groupId>
    <artifactId>{self.project_name}</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <name>{self.project_name}</name>
    <description>Migrated from MuleSoft to Spring Boot</description>

    <properties>
        <java.version>{self.java_version}</java.version>
    </properties>

    <dependencies>{dep_xml}
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <configuration>
                    <annotationProcessorPaths>
                        <path>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </path>
                    </annotationProcessorPaths>
                </configuration>
            </plugin>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
                <configuration>
                    <excludes>
                        <exclude>
                            <groupId>org.projectlombok</groupId>
                            <artifactId>lombok</artifactId>
                        </exclude>
                    </excludes>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>
"""

    # ══════════════════════════════════════════════════════════════════════
    #  MAIN APPLICATION CLASS
    # ══════════════════════════════════════════════════════════════════════
    def _generate_main_app(self, app_class, parsed_data, connector_info):
        connectors = connector_info.get("connectors", set())
        annotations = [
            f'@OpenAPIDefinition(\n'
            f'    info = @Info(title = "{self.project_name} API", version = "1.0",\n'
            f'                description = "Migrated from MuleSoft"),\n'
            f'    servers = @Server(url = "http://localhost:8080")\n'
            f')',
            "@SpringBootApplication",
        ]
        imports = [
            "org.springframework.boot.SpringApplication",
            "org.springframework.boot.autoconfigure.SpringBootApplication",
            "io.swagger.v3.oas.annotations.OpenAPIDefinition",
            "io.swagger.v3.oas.annotations.info.Info",
            "io.swagger.v3.oas.annotations.servers.Server",
        ]

        if any((f.get("source") or {}).get("type") == "scheduler"
               for f in parsed_data.get("flows", [])):
            annotations.append("@EnableScheduling")
            imports.append("org.springframework.scheduling.annotation.EnableScheduling")

        if "jms" in connectors:
            annotations.append("@EnableJms")
            imports.append("org.springframework.jms.annotation.EnableJms")

        if "batch" in connectors or parsed_data.get("batch_jobs"):
            imports.append("org.springframework.batch.core.configuration.annotation.EnableBatchProcessing")

        if any("CompletableFuture.runAsync" in str(v)
               for v in parsed_data.get("flows", [])):
            annotations.append("@EnableAsync")
            imports.append("org.springframework.scheduling.annotation.EnableAsync")

        if "objectstore" in connectors or "redis" in connectors:
            annotations.append("@EnableCaching")
            imports.append("org.springframework.cache.annotation.EnableCaching")

        import_lines = "\n".join(f"import {i};" for i in sorted(imports))
        anno_lines   = "\n".join(annotations)

        return (
            f"package {self.group_id};\n\n"
            f"{import_lines}\n\n"
            f"{anno_lines}\n"
            f"public class {app_class} {{\n\n"
            f"    public static void main(String[] args) {{\n"
            f"        SpringApplication.run({app_class}.class, args);\n"
            f"    }}\n"
            f"}}\n"
        )

    # ══════════════════════════════════════════════════════════════════════
    #  PROPERTIES
    # ══════════════════════════════════════════════════════════════════════
    def _generate_properties(self, parsed_data, connector_info):
        from backend.migrator.connector_mapper import ConnectorMapper
        cm = ConnectorMapper()

        # Determine server port from MuleSoft config (resolve actual values)
        server_port = "8081"
        for cfg in parsed_data.get("global_configs", []):
            if cfg.get("type") == "http-listener":
                port_val = str(cfg.get("port", "8081"))
                # Strip MuleSoft placeholders like ${http.port}
                if "${" not in port_val and port_val.isdigit():
                    server_port = port_val
                break

        lines = [
            f"# ========================================",
            f"# {self.project_name} - Spring Boot",
            f"# Migrated from MuleSoft",
            f"# ========================================",
            f"# Use profiles: -Dspring.profiles.active=dev|sit|uat|preprod|prod",
            f"",
            f"spring.application.name={self.project_name}",
            f"",
            f"# Server port (from original MuleSoft config)",
            f"server.port={server_port}",
            f"",
        ]

        has_db = False
        self._db_configs = []   # Store for profile generation
        self._server_port = server_port  # Store for Dockerfile/docker-compose
        for cfg in parsed_data.get("global_configs", []):
            props = cm.get_spring_config_for_connector(cfg.get("type", ""), cfg)
            if props:
                if cfg.get("type") == "database":
                    has_db = True
                    self._db_configs.append(cfg)
                elif cfg.get("type") != "http-listener":
                    lines.append(f"# {cfg.get('type', '')} — {cfg.get('name', '')}")
                    for k, v in props.items():
                        v_str = str(v)
                        if "${" not in v_str:
                            lines.append(f"{k}={v_str}")
                        else:
                            lines.append(f"# {k}={v_str}  # TODO: set actual value")
                    lines.append("")

        # Database config — use real DB from MuleSoft config as default
        if has_db and self._db_configs:
            cfg = self._db_configs[0]
            db_url = str(cfg.get("url", ""))
            db_driver = str(cfg.get("driver", ""))
            db_user = str(cfg.get("user", ""))
            db_password = str(cfg.get("password", ""))
            db_host = str(cfg.get("host", ""))
            db_port = str(cfg.get("port", "3306"))
            db_name = str(cfg.get("database", ""))

            # Build JDBC URL if needed
            if not db_url and db_host and "${" not in db_host:
                if "postgres" in db_driver.lower():
                    db_url = f"jdbc:postgresql://{db_host}:{db_port}/{db_name}?sslmode=require"
                    db_driver = db_driver or "org.postgresql.Driver"
                elif "sqlserver" in db_driver.lower() or "mssql" in db_driver.lower():
                    db_url = f"jdbc:sqlserver://{db_host}:{db_port};databaseName={db_name};encrypt=true"
                    db_driver = db_driver or "com.microsoft.sqlserver.jdbc.SQLServerDriver"
                else:
                    db_url = f"jdbc:mysql://{db_host}:{db_port}/{db_name}?useSSL=true&requireSSL=true&serverTimezone=UTC&allowPublicKeyRetrieval=true"
                    db_driver = db_driver or "com.mysql.cj.jdbc.Driver"

            # Determine dialect
            dialect = "org.hibernate.dialect.MySQLDialect"
            if "postgres" in (db_driver + db_url).lower():
                dialect = "org.hibernate.dialect.PostgreSQLDialect"
            elif "sqlserver" in (db_driver + db_url).lower() or "mssql" in (db_driver + db_url).lower():
                dialect = "org.hibernate.dialect.SQLServerDialect"

            # If we have real resolvable values, use them as default
            has_real_url = db_url and "${" not in db_url
            has_real_user = db_user and "${" not in db_user
            has_real_password = db_password and "${" not in db_password

            if has_real_url:
                lines += [
                    f"# Database — same connection as original MuleSoft app ({cfg.get('name', '')})",
                    f"spring.datasource.url={db_url}",
                    f"spring.datasource.driver-class-name={db_driver}",
                ]
                if has_real_user:
                    lines.append(f"spring.datasource.username={db_user}")
                else:
                    lines.append(f"spring.datasource.username=${{DB_USERNAME:admin}}")
                if has_real_password:
                    lines.append(f"spring.datasource.password={db_password}")
                else:
                    lines.append(f"spring.datasource.password=${{DB_PASSWORD}}")
                lines += [
                    f"spring.jpa.database-platform={dialect}",
                    f"spring.jpa.hibernate.ddl-auto=none",
                    f"spring.jpa.show-sql=true",
                    "",
                ]
            else:
                # MuleSoft config had placeholders — use env vars
                lines += [
                    f"# Database ({cfg.get('name', '')})",
                    f"# Original MuleSoft config used placeholders — set via environment variables",
                    f"spring.datasource.url=${{DB_URL:jdbc:mysql://localhost:3306/appdb}}",
                    f"spring.datasource.driver-class-name={db_driver or 'com.mysql.cj.jdbc.Driver'}",
                    f"spring.datasource.username=${{DB_USERNAME:admin}}",
                    f"spring.datasource.password=${{DB_PASSWORD:changeme}}",
                    f"spring.jpa.database-platform={dialect}",
                    f"spring.jpa.hibernate.ddl-auto=none",
                    f"spring.jpa.show-sql=true",
                    "",
                ]

        # Global properties (skip MuleSoft-only placeholders)
        for k, v in parsed_data.get("global_properties", {}).items():
            if not k.startswith("_") and "${" not in str(v):
                lines.append(f"{k}={v}")

        lines += [
            "", "# Logging", "logging.level.root=INFO",
            f"logging.level.{self.group_id}=DEBUG",
            "", "# Actuator",
            "management.endpoints.web.exposure.include=health,info,metrics",
            "management.endpoint.health.show-details=always",
            "", "# Swagger / OpenAPI",
            "springdoc.swagger-ui.path=/swagger-ui.html",
            "springdoc.api-docs.path=/v3/api-docs",
        ]
        return "\n".join(lines) + "\n"

    def _generate_yaml_properties(self, parsed_data, connector_info):
        """Generate application.yml with resolved values (no MuleSoft placeholders)."""
        # Resolve server port
        server_port = "8081"
        for cfg in parsed_data.get("global_configs", []):
            if cfg.get("type") == "http-listener":
                port_val = str(cfg.get("port", "8081"))
                if "${" not in port_val and port_val.isdigit():
                    server_port = port_val
                break

        lines = [
            "# ========================================",
            f"# {self.project_name} - Spring Boot",
            "# Migrated from MuleSoft",
            "# ========================================",
            "# Profile-specific configs in application-{profile}.properties override these",
            "",
            "spring:",
            "  application:",
            f"    name: {self.project_name}",
            "  profiles:",
            "    active: ${SPRING_PROFILES_ACTIVE:}",
            "",
            "server:",
            f"  port: {server_port}",
        ]

        # Note: DB config goes in profile-specific .properties files, not here
        # This YAML only has shared/default settings

        lines += ["", "logging:", "  level:", "    root: INFO",
                   f"    {self.group_id}: DEBUG"]

        # ── Springdoc / Swagger UI ─────────────────────────────────────
        lines += ["", "springdoc:",
                   "  swagger-ui:",
                   "    path: /swagger-ui.html",
                   "  api-docs:",
                   "    path: /v3/api-docs"]

        # ── Actuator / Management ──────────────────────────────────────
        lines += ["", "management:",
                   "  endpoints:",
                   "    web:",
                   "      exposure:",
                   "        include: health,info,metrics",
                   "  endpoint:",
                   "    health:",
                   "      show-details: always"]

        return "\n".join(lines) + "\n"

    def _generate_profile_properties(self, profile, parsed_data=None):
        """Generate profile-specific properties with actual DB config."""
        lines = [
            f"# ========================================",
            f"# {profile.upper()} Environment — {self.project_name}",
            f"# ========================================",
            f"",
            f"spring.application.name={self.project_name}-{profile}",
            "",
        ]

        # Include actual database configuration from MuleSoft parsed data
        db_configs = getattr(self, "_db_configs", [])
        if db_configs:
            cfg = db_configs[0]  # Primary database
            db_url = cfg.get("url", "")
            db_driver = cfg.get("driver", "")
            db_user = cfg.get("user", "")
            db_password = cfg.get("password", "")
            db_host = cfg.get("host", "localhost")
            db_port = cfg.get("port", "3306")
            db_name = cfg.get("database", "appdb")

            # Resolve MuleSoft placeholders to concrete values
            def _resolve(val):
                val = str(val) if val else ""
                return "" if "${" in val else val

            r_url = _resolve(db_url)
            r_driver = _resolve(db_driver)
            r_user = _resolve(db_user)
            r_password = _resolve(db_password)
            r_host = _resolve(db_host)
            r_port = _resolve(db_port) or "3306"
            r_name = _resolve(db_name) or "appdb"

            # Build JDBC URL if not explicitly set
            if not r_url and r_host:
                # Detect driver type for URL format
                if "postgres" in (r_driver or "").lower():
                    r_url = f"jdbc:postgresql://{r_host}:{r_port}/{r_name}?sslmode=require"
                elif "sqlserver" in (r_driver or "").lower() or "mssql" in (r_driver or "").lower():
                    r_url = f"jdbc:sqlserver://{r_host}:{r_port};databaseName={r_name};encrypt=true"
                else:
                    r_url = f"jdbc:mysql://{r_host}:{r_port}/{r_name}?useSSL=true&requireSSL=true&serverTimezone=UTC&allowPublicKeyRetrieval=true"

            # Determine dialect
            dialect = "org.hibernate.dialect.MySQLDialect"
            if "postgres" in (r_driver or r_url).lower():
                dialect = "org.hibernate.dialect.PostgreSQLDialect"
                r_driver = r_driver or "org.postgresql.Driver"
            elif "sqlserver" in (r_driver or r_url).lower() or "mssql" in (r_driver or r_url).lower():
                dialect = "org.hibernate.dialect.SQLServerDialect"
                r_driver = r_driver or "com.microsoft.sqlserver.jdbc.SQLServerDriver"
            else:
                r_driver = r_driver or "com.mysql.cj.jdbc.Driver"

            if profile == "dev" and r_url:
                lines += [
                    f"# Database ({cfg.get('name', 'primary')})",
                    f"spring.datasource.url={r_url}",
                    f"spring.datasource.driver-class-name={r_driver}",
                    f"spring.datasource.username={r_user or 'admin'}",
                    f"spring.datasource.password={r_password or 'changeme'}",
                    f"spring.jpa.database-platform={dialect}",
                    f"spring.jpa.hibernate.ddl-auto=none",
                    f"spring.jpa.show-sql=true",
                    "",
                ]
            elif profile == "prod":
                # Prod uses env vars for secrets
                prod_url = r_url.replace("-dev", "-prod").replace("_dev", "_prod") if r_url else ""
                lines += [
                    f"# Database ({cfg.get('name', 'primary')})",
                    f"spring.datasource.url={prod_url or '${DB_URL}'}",
                    f"spring.datasource.driver-class-name={r_driver}",
                    f"spring.datasource.username=${{DB_USERNAME}}",
                    f"spring.datasource.password=${{DB_PASSWORD}}",
                    f"spring.jpa.database-platform={dialect}",
                    f"spring.jpa.hibernate.ddl-auto=none",
                    f"spring.jpa.show-sql=false",
                    "",
                ]
            else:
                # SIT / UAT / PreProd — use env vars for passwords
                env_url = r_url
                for env in ["dev", "sit", "uat", "preprod"]:
                    env_url = env_url.replace(f"-{env}", f"-{profile}").replace(f"_{env}", f"_{profile}")
                lines += [
                    f"# Database ({cfg.get('name', 'primary')})",
                    f"spring.datasource.url={env_url}",
                    f"spring.datasource.driver-class-name={r_driver}",
                    f"spring.datasource.username=${{DB_USERNAME:{r_user or 'admin'}}}",
                    f"spring.datasource.password=${{DB_PASSWORD}}",
                    f"spring.jpa.database-platform={dialect}",
                    f"spring.jpa.hibernate.ddl-auto=none",
                    "",
                ]

            # No H2 at runtime — real database is used (H2 is test-scope only)

        # Profile-specific logging
        if profile == "dev":
            lines += [
                "# Logging",
                "logging.level.root=INFO",
                f"logging.level.{self.group_id}=DEBUG",
                "spring.jpa.show-sql=true",
            ]
        elif profile == "prod":
            lines += [
                "# Logging",
                "logging.level.root=WARN",
                f"logging.level.{self.group_id}=INFO",
                "spring.jpa.show-sql=false",
                "server.error.include-stacktrace=never",
            ]
        else:
            lines += [
                "# Logging",
                "logging.level.root=INFO",
                f"logging.level.{self.group_id}=INFO",
            ]

        return "\n".join(lines) + "\n"

    def _generate_logback_config(self):
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration>

    <!-- ── Console appender with colored output ──────────────────────── -->
    <appender name="CONSOLE" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%clr(%d{{yyyy-MM-dd HH:mm:ss.SSS}}){{faint}} %clr(%5p) %clr(${{PID:- }}){{magenta}} %clr(---){{faint}} %clr([%15.15t]){{faint}} %clr(%-40.40logger{{39}}){{cyan}} %clr(:){{faint}} %m%n%wEx</pattern>
        </encoder>
    </appender>

    <!-- ── File appender with rolling policy ─────────────────────────── -->
    <appender name="FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>logs/{self.project_name}.log</file>
        <rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
            <fileNamePattern>logs/{self.project_name}.%d{{yyyy-MM-dd}}.%i.log.gz</fileNamePattern>
            <maxFileSize>10MB</maxFileSize>
            <maxHistory>30</maxHistory>
            <totalSizeCap>500MB</totalSizeCap>
        </rollingPolicy>
        <encoder>
            <pattern>%d{{yyyy-MM-dd HH:mm:ss.SSS}} %5p ${{PID:- }} --- [%15.15t] %-40.40logger{{39}} : %m%n%wEx</pattern>
        </encoder>
    </appender>

    <!-- ── Dev profile: DEBUG level, console only ────────────────────── -->
    <springProfile name="dev">
        <logger name="{self.group_id}" level="DEBUG"/>
        <root level="DEBUG">
            <appender-ref ref="CONSOLE"/>
        </root>
    </springProfile>

    <!-- ── Prod profile: INFO level, file + console ──────────────────── -->
    <springProfile name="prod">
        <logger name="{self.group_id}" level="INFO"/>
        <root level="INFO">
            <appender-ref ref="CONSOLE"/>
            <appender-ref ref="FILE"/>
        </root>
    </springProfile>

    <!-- ── Default (no profile): INFO level, console only ────────────── -->
    <springProfile name="default">
        <logger name="{self.group_id}" level="DEBUG"/>
        <root level="INFO">
            <appender-ref ref="CONSOLE"/>
        </root>
    </springProfile>

</configuration>
"""

    # ══════════════════════════════════════════════════════════════════════
    #  H2 SCHEMA & SAMPLE DATA (for out-of-the-box local development)
    # ══════════════════════════════════════════════════════════════════════
    def _generate_h2_schema(self, parsed_data):
        """Generate schema-h2.sql by inspecting DB queries in the converted code."""
        # Extract table names from SQL queries in flows
        tables = set()
        for flow in parsed_data.get("flows", []):
            for step in flow.get("steps", []):
                sql = step.get("sql", "") or step.get("query", "")
                if sql:
                    # Extract table names from FROM/INTO/UPDATE/JOIN
                    import re as _re
                    for match in _re.findall(
                        r'(?:FROM|INTO|UPDATE|JOIN)\s+(\w+)', sql, _re.IGNORECASE
                    ):
                        if match.lower() not in ("select", "where", "set", "values"):
                            tables.add(match)

        lines = [
            "-- ========================================",
            "-- H2 Schema (auto-generated from MuleSoft migration)",
            "-- Creates tables for local development with H2",
            "-- ========================================",
            "",
        ]

        if tables:
            for table in sorted(tables):
                lines += [
                    f"CREATE TABLE IF NOT EXISTS {table} (",
                    f"    id INT AUTO_INCREMENT PRIMARY KEY,",
                    f"    -- TODO: Add columns based on your MuleSoft queries",
                    f"    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                    f");",
                    "",
                ]
        else:
            # Provide a useful default schema with common insurance patterns
            lines += [
                "-- Default schema (customize based on your domain)",
                "CREATE TABLE IF NOT EXISTS policies (",
                "    policy_id INT AUTO_INCREMENT PRIMARY KEY,",
                "    policy_number VARCHAR(50) NOT NULL,",
                "    holder_name VARCHAR(200) NOT NULL,",
                "    holder_email VARCHAR(200),",
                "    policy_type VARCHAR(50),",
                "    coverage_amount DECIMAL(15, 2),",
                "    premium DECIMAL(15, 2),",
                "    status VARCHAR(20) DEFAULT 'ACTIVE',",
                "    effective_date DATE,",
                "    expiration_date DATE,",
                "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                ");",
                "",
                "CREATE TABLE IF NOT EXISTS claims (",
                "    claim_id INT AUTO_INCREMENT PRIMARY KEY,",
                "    claim_number VARCHAR(50) NOT NULL,",
                "    policy_id INT,",
                "    claimant_name VARCHAR(200),",
                "    claim_type VARCHAR(50),",
                "    description TEXT,",
                "    claim_amount DECIMAL(15, 2),",
                "    approved_amount DECIMAL(15, 2),",
                "    status VARCHAR(20) DEFAULT 'SUBMITTED',",
                "    filed_date DATE,",
                "    resolved_date DATE,",
                "    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
                ");",
                "",
            ]

        return "\n".join(lines)

    def _generate_h2_sample_data(self, parsed_data):
        """Generate data-h2.sql with sample data for local development."""
        return (
            "-- ========================================\n"
            "-- Sample data for H2 (local development)\n"
            "-- ========================================\n"
            "\n"
            "-- Add INSERT statements here for test data\n"
            "-- Example:\n"
            "-- INSERT INTO policies (policy_number, holder_name, holder_email, policy_type, coverage_amount, premium, status, effective_date, expiration_date)\n"
            "-- VALUES ('POL-2024-001', 'John Smith', 'john@email.com', 'AUTO', 50000.00, 1200.00, 'ACTIVE', '2024-01-01', '2025-01-01');\n"
        )

    # ══════════════════════════════════════════════════════════════════════
    #  CONFIG CLASSES
    # ══════════════════════════════════════════════════════════════════════
    def _cfg(self, name, body, extra_imports=None):
        imp = extra_imports or []
        imp_lines = "\n".join(f"import {i};" for i in imp)
        return (
            f"package {self.group_id}.config;\n\n"
            f"import org.springframework.context.annotation.Configuration;\n"
            f"import org.springframework.context.annotation.Bean;\n"
            f"{imp_lines}\n\n"
            f"@Configuration\n"
            f"public class {name} {{\n\n"
            f"{body}\n"
            f"}}\n"
        )

    def _gen_scheduling_config(self):
        return self._cfg("SchedulingConfig",
            '    // Scheduling is enabled via @EnableScheduling on the main app class',
            ["org.springframework.scheduling.annotation.EnableScheduling"])

    def _gen_jms_config(self):
        return self._cfg("JmsConfig", '    // JMS is enabled via @EnableJms on the main app class',
            ["org.springframework.jms.annotation.EnableJms"])

    def _gen_amqp_config(self):
        return self._cfg("AmqpConfig",
            '    // AMQP (RabbitMQ) auto-configured by Spring Boot\n'
            '    // Configure exchanges, queues and bindings here as needed',
            ["org.springframework.amqp.rabbit.annotation.EnableRabbit"])

    def _gen_kafka_config(self):
        return self._cfg("KafkaConfig",
            '    // Kafka auto-configured by Spring Boot\n'
            '    // Customise consumer/producer factories here if needed',
            ["org.springframework.kafka.annotation.EnableKafka"])

    def _gen_rest_template_config(self):
        return self._cfg("RestTemplateConfig",
            '    @Bean\n'
            '    public org.springframework.web.client.RestTemplate restTemplate() {\n'
            '        return new org.springframework.web.client.RestTemplate();\n'
            '    }',
            ["org.springframework.web.client.RestTemplate"])

    def _gen_webclient_config(self, parsed_data):
        beans = []
        beans.append(
            '    @Bean\n'
            '    public org.springframework.web.reactive.function.client.WebClient.Builder webClientBuilder() {\n'
            '        return org.springframework.web.reactive.function.client.WebClient.builder();\n'
            '    }'
        )
        # Create named WebClient beans for each HTTP request config
        for cfg in parsed_data.get("global_configs", []):
            if cfg.get("type") == "http-request":
                bean_name = self._to_bean_name(cfg.get("name", "external"))
                host = cfg.get("host", "localhost")
                port = cfg.get("port", "80")
                proto = cfg.get("protocol", "HTTP").lower()
                base = cfg.get("basePath", "/")
                url = f"{proto}://{host}:{port}{base}"
                beans.append(
                    f'\n    @Bean("{bean_name}WebClient")\n'
                    f'    public org.springframework.web.reactive.function.client.WebClient {bean_name}WebClient(\n'
                    f'            org.springframework.web.reactive.function.client.WebClient.Builder builder) {{\n'
                    f'        return builder.baseUrl("{url}").build();\n'
                    f'    }}'
                )
        return self._cfg("WebClientConfig", "\n".join(beans),
            ["org.springframework.web.reactive.function.client.WebClient"])

    def _gen_cache_config(self):
        return self._cfg("CacheConfig",
            '    // Caching enabled via @EnableCaching on the main app class\n'
            '    // Uses Redis as the cache store (configure in application.properties)\n'
            '    // Use @Cacheable, @CacheEvict, @CachePut on service methods',
            ["org.springframework.cache.annotation.EnableCaching"])

    def _gen_security_config(self):
        return self._cfg("SecurityConfig",
            '    @Bean\n'
            '    public org.springframework.security.web.SecurityFilterChain filterChain(\n'
            '            org.springframework.security.config.annotation.web.builders.HttpSecurity http) throws Exception {\n'
            '        http\n'
            '            .csrf(csrf -> csrf.disable())\n'
            '            .authorizeHttpRequests(auth -> auth\n'
            '                .requestMatchers("/actuator/**").permitAll()\n'
            '                .anyRequest().authenticated()\n'
            '            )\n'
            '            .oauth2ResourceServer(oauth2 -> oauth2.jwt(jwt -> {}));\n'
            '        return http.build();\n'
            '    }',
            ["org.springframework.security.config.annotation.web.builders.HttpSecurity",
             "org.springframework.security.web.SecurityFilterChain"])

    def _gen_async_config(self):
        return self._cfg("AsyncConfig",
            '    @Bean\n'
            '    public java.util.concurrent.Executor taskExecutor() {\n'
            '        org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor executor =\n'
            '            new org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor();\n'
            '        executor.setCorePoolSize(4);\n'
            '        executor.setMaxPoolSize(8);\n'
            '        executor.setQueueCapacity(100);\n'
            '        executor.setThreadNamePrefix("async-");\n'
            '        executor.initialize();\n'
            '        return executor;\n'
            '    }',
            ["org.springframework.scheduling.annotation.EnableAsync",
             "org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor"])

    def _gen_batch_config(self):
        return self._cfg("BatchConfig",
            '    // Spring Batch auto-configured\n'
            '    // Job definitions are in the batch/ package',
            [])

    def _gen_sftp_config(self):
        return self._cfg("SftpConfig",
            '    @Bean\n'
            '    public org.springframework.integration.sftp.session.DefaultSftpSessionFactory sftpSessionFactory() {\n'
            '        var factory = new org.springframework.integration.sftp.session.DefaultSftpSessionFactory();\n'
            '        factory.setHost("${sftp.host}");\n'
            '        factory.setPort(Integer.parseInt("${sftp.port:22}"));\n'
            '        factory.setUser("${sftp.username}");\n'
            '        factory.setPassword("${sftp.password}");\n'
            '        factory.setAllowUnknownKeys(true);\n'
            '        return factory;\n'
            '    }\n\n'
            '    @Bean\n'
            '    public org.springframework.integration.sftp.session.SftpRemoteFileTemplate sftpTemplate() {\n'
            '        return new org.springframework.integration.sftp.session.SftpRemoteFileTemplate(sftpSessionFactory());\n'
            '    }',
            ["org.springframework.beans.factory.annotation.Value"])

    def _gen_ftp_config(self):
        return self._cfg("FtpConfig",
            '    // Configure FTP session factory and template here',
            [])

    def _gen_s3_config(self):
        return self._cfg("AwsS3Config",
            '    @Bean\n'
            '    public software.amazon.awssdk.services.s3.S3Client s3Client() {\n'
            '        return software.amazon.awssdk.services.s3.S3Client.builder()\n'
            '            .region(software.amazon.awssdk.regions.Region.US_EAST_1)\n'
            '            .build();\n'
            '    }',
            ["software.amazon.awssdk.services.s3.S3Client",
             "software.amazon.awssdk.regions.Region"])

    def _gen_sqs_config(self):
        return self._cfg("AwsSqsConfig",
            '    @Bean\n'
            '    public software.amazon.awssdk.services.sqs.SqsClient sqsClient() {\n'
            '        return software.amazon.awssdk.services.sqs.SqsClient.builder()\n'
            '            .region(software.amazon.awssdk.regions.Region.US_EAST_1)\n'
            '            .build();\n'
            '    }',
            ["software.amazon.awssdk.services.sqs.SqsClient",
             "software.amazon.awssdk.regions.Region"])

    def _gen_ws_config(self):
        return self._cfg("WebServiceConfig",
            '    @Bean\n'
            '    public org.springframework.ws.client.core.WebServiceTemplate webServiceTemplate() {\n'
            '        return new org.springframework.ws.client.core.WebServiceTemplate();\n'
            '    }',
            ["org.springframework.ws.client.core.WebServiceTemplate"])

    def _gen_cors_config(self):
        return self._cfg("CorsConfig",
            '    @Bean\n'
            '    public org.springframework.web.servlet.config.annotation.WebMvcConfigurer corsConfigurer() {\n'
            '        return new org.springframework.web.servlet.config.annotation.WebMvcConfigurer() {\n'
            '            @Override\n'
            '            public void addCorsMappings(org.springframework.web.servlet.config.annotation.CorsRegistry registry) {\n'
            '                registry.addMapping("/**")\n'
            '                    .allowedOrigins("*")\n'
            '                    .allowedMethods("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS")\n'
            '                    .allowedHeaders("*");\n'
            '            }\n'
            '        };\n'
            '    }',
            [])

    # ══════════════════════════════════════════════════════════════════════
    #  EXCEPTION CLASSES
    # ══════════════════════════════════════════════════════════════════════
    def _gen_exception_class(self, name):
        status_map = {
            "ResourceNotFoundException": "HttpStatus.NOT_FOUND",
            "BadRequestException": "HttpStatus.BAD_REQUEST",
            "UnauthorizedException": "HttpStatus.UNAUTHORIZED",
            "ServiceUnavailableException": "HttpStatus.SERVICE_UNAVAILABLE",
            "TooManyRequestsException": "HttpStatus.TOO_MANY_REQUESTS",
        }
        status = status_map.get(name, "HttpStatus.INTERNAL_SERVER_ERROR")
        return (
            f"package {self.group_id}.exception;\n\n"
            f"import org.springframework.http.HttpStatus;\n"
            f"import org.springframework.web.bind.annotation.ResponseStatus;\n\n"
            f"@ResponseStatus({status})\n"
            f"public class {name} extends RuntimeException {{\n\n"
            f"    public {name}(String message) {{\n"
            f"        super(message);\n"
            f"    }}\n\n"
            f"    public {name}(String message, Throwable cause) {{\n"
            f"        super(message, cause);\n"
            f"    }}\n"
            f"}}\n"
        )

    # ══════════════════════════════════════════════════════════════════════
    #  UTILITY CLASSES
    # ══════════════════════════════════════════════════════════════════════
    def _gen_json_util(self):
        return (
            f"package {self.group_id}.util;\n\n"
            f"import com.fasterxml.jackson.databind.ObjectMapper;\n"
            f"import com.fasterxml.jackson.core.type.TypeReference;\n"
            f"import java.util.Map;\n\n"
            f"public class JsonUtil {{\n\n"
            f"    private static final ObjectMapper MAPPER = new ObjectMapper();\n\n"
            f"    public static String toJson(Object obj) {{\n"
            f"        try {{ return MAPPER.writeValueAsString(obj); }}\n"
            f"        catch (Exception e) {{ throw new RuntimeException(e); }}\n"
            f"    }}\n\n"
            f"    public static Map<String, Object> fromJson(String json) {{\n"
            f"        try {{ return MAPPER.readValue(json, new TypeReference<>() {{}}); }}\n"
            f"        catch (Exception e) {{ throw new RuntimeException(e); }}\n"
            f"    }}\n\n"
            f"    public static <T> T fromJson(String json, Class<T> clazz) {{\n"
            f"        try {{ return MAPPER.readValue(json, clazz); }}\n"
            f"        catch (Exception e) {{ throw new RuntimeException(e); }}\n"
            f"    }}\n"
            f"}}\n"
        )

    # ══════════════════════════════════════════════════════════════════════
    #  INFRASTRUCTURE FILES
    # ══════════════════════════════════════════════════════════════════════
    def _generate_gitignore(self):
        return """HELP.md
target/
!.mvn/wrapper/maven-wrapper.jar
!**/src/main/**/target/
!**/src/test/**/target/

### STS ###
.apt_generated
.classpath
.factorypath
.project
.settings
.springBeans
.sts4-cache

### IntelliJ IDEA ###
.idea
*.iws
*.iml
*.ipr

### NetBeans ###
/nbproject/private/
/nbbuild/
/dist/
/nbdist/
/.nb-gradle/
build/
!**/src/main/**/build/
!**/src/test/**/build/

### VS Code ###
.vscode/

### Mac ###
.DS_Store
"""

    def _generate_test_class(self, app_class):
        return (
            f"package {self.group_id};\n\n"
            f"import org.junit.jupiter.api.DisplayName;\n"
            f"import org.junit.jupiter.api.Test;\n"
            f"import org.springframework.beans.factory.annotation.Autowired;\n"
            f"import org.springframework.boot.test.context.SpringBootTest;\n"
            f"import org.springframework.context.ApplicationContext;\n\n"
            f"import static org.junit.jupiter.api.Assertions.assertNotNull;\n"
            f"import static org.junit.jupiter.api.Assertions.assertTrue;\n\n"
            f"@SpringBootTest\n"
            f"@DisplayName(\"{app_class} - Application Context Tests\")\n"
            f"class {app_class}Tests {{\n\n"
            f"    @Autowired\n"
            f"    private ApplicationContext applicationContext;\n\n"
            f"    @Test\n"
            f"    @DisplayName(\"Application context should load successfully\")\n"
            f"    void contextLoads() {{\n"
            f"        // Verifies that the Spring application context starts without errors\n"
            f"        assertNotNull(applicationContext, \"Application context should not be null\");\n"
            f"    }}\n\n"
            f"    @Test\n"
            f"    @DisplayName(\"Application context should contain expected beans\")\n"
            f"    void contextContainsBeans() {{\n"
            f"        assertTrue(applicationContext.getBeanDefinitionCount() > 0,\n"
            f"                \"Application context should contain bean definitions\");\n"
            f"    }}\n\n"
            f"    @Test\n"
            f"    @DisplayName(\"Main method should run without throwing\")\n"
            f"    void mainMethodRuns() {{\n"
            f"        // Smoke test to ensure main() doesn't throw\n"
            f"        {app_class}.main(new String[]{{}});\n"
            f"    }}\n"
            f"}}\n"
        )

    def _generate_controller_tests(self, spring_files):
        """Generate comprehensive @WebMvcTest test classes for each controller."""
        test_files = {}
        for rel_path, content in spring_files.items():
            if "@RestController" not in content and "@Controller" not in content:
                continue

            # Extract class name from file path
            class_name = rel_path.rsplit("/", 1)[-1].replace(".java", "")
            test_class_name = f"{class_name}Test"

            # Determine the sub-package from the relative path
            if "/" in rel_path:
                sub_package = rel_path.rsplit("/", 1)[0].replace("/", ".")
                full_package = f"{self.group_id}.{sub_package}"
            else:
                full_package = self.group_id

            # ── Detect dependencies to mock ──────────────────────────
            service_beans = []
            has_jdbc = False
            has_rest_template = False
            has_webclient = False
            for line in content.splitlines():
                if "JdbcTemplate" in line:
                    has_jdbc = True
                if "RestTemplate" in line:
                    has_rest_template = True
                if "WebClient" in line:
                    has_webclient = True
                m = re.search(r'\b(\w+Service)\b', line)
                if m and m.group(1) not in service_beans and m.group(1) != "Service":
                    service_beans.append(m.group(1))

            # ── Extract base path from class-level @RequestMapping ───
            base_path = ""
            lines_list = content.splitlines()
            for i, line in enumerate(lines_list):
                stripped = line.strip()
                # Only match class-level @RequestMapping (right before class declaration)
                if stripped.startswith("@RequestMapping"):
                    # Check if next non-annotation line is the class declaration
                    for j in range(i + 1, min(i + 5, len(lines_list))):
                        if "class " in lines_list[j]:
                            bm = re.search(
                                r'@RequestMapping\(\s*(?:value\s*=\s*)?["\']?(.*?)["\']?\s*\)',
                                stripped)
                            if bm:
                                base_path = bm.group(1).strip('"').strip("'")
                            break

            # ── Parse all endpoint methods with full details ─────────
            endpoints = self._parse_controller_endpoints(content, base_path)

            # ── Build imports ────────────────────────────────────────
            imports = set()
            imports.add("org.junit.jupiter.api.DisplayName")
            imports.add("org.junit.jupiter.api.Test")
            imports.add("org.springframework.beans.factory.annotation.Autowired")
            imports.add("org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest")
            imports.add("org.springframework.boot.test.mock.bean.MockBean")
            imports.add("org.springframework.http.MediaType")
            imports.add("org.springframework.test.web.servlet.MockMvc")

            static_imports = set()
            static_imports.add("org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*")
            static_imports.add("org.springframework.test.web.servlet.result.MockMvcResultMatchers.*")

            needs_mockito = has_jdbc or service_beans or has_rest_template
            if needs_mockito:
                static_imports.add("org.mockito.Mockito.when")
                static_imports.add("org.mockito.ArgumentMatchers.any")
                static_imports.add("org.mockito.ArgumentMatchers.anyString")
                static_imports.add("org.mockito.ArgumentMatchers.eq")

            if has_jdbc:
                imports.add("org.springframework.jdbc.core.JdbcTemplate")
                imports.add("java.util.List")
                imports.add("java.util.Map")
                imports.add("java.util.Collections")

            if has_rest_template:
                imports.add("org.springframework.web.client.RestTemplate")

            if has_webclient:
                imports.add("org.springframework.web.reactive.function.client.WebClient")

            # ── Build imports string ─────────────────────────────────
            import_str = ""
            for imp in sorted(imports):
                import_str += f"import {imp};\n"
            import_str += "\n"
            for imp in sorted(static_imports):
                import_str += f"import static {imp};\n"

            # ── Build mock bean declarations ─────────────────────────
            mock_beans = ""
            if has_jdbc:
                mock_beans += "    @MockBean\n    private JdbcTemplate jdbcTemplate;\n\n"
            if has_rest_template:
                mock_beans += "    @MockBean\n    private RestTemplate restTemplate;\n\n"
            if has_webclient:
                mock_beans += "    @MockBean\n    private WebClient webClient;\n\n"
            for svc in service_beans:
                bean_name = svc[0].lower() + svc[1:]
                mock_beans += f"    @MockBean\n    private {svc} {bean_name};\n\n"

            # ── Build test methods ───────────────────────────────────
            test_methods = self._build_controller_test_methods(
                endpoints, has_jdbc, has_rest_template, service_beans, base_path)

            test_content = (
                f"package {full_package};\n\n"
                f"{import_str}\n"
                f"@WebMvcTest({class_name}.class)\n"
                f"@DisplayName(\"{class_name} - Unit Tests\")\n"
                f"class {test_class_name} {{\n\n"
                f"    @Autowired\n"
                f"    private MockMvc mockMvc;\n\n"
                f"{mock_beans}"
                f"{test_methods}"
                f"}}\n"
            )

            test_rel_path = rel_path.replace(".java", "Test.java")
            test_files[test_rel_path] = test_content

        return test_files

    def _parse_controller_endpoints(self, content, base_path):
        """Parse controller source to extract detailed endpoint information."""
        endpoints = []
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            # Match mapping annotations
            mapping_match = re.search(
                r'@(Get|Post|Put|Delete|Patch)Mapping'
                r'(?:\(\s*(?:value\s*=\s*)?["\']?(.*?)["\']?\s*\))?',
                line)

            if not mapping_match:
                i += 1
                continue

            http_method = mapping_match.group(1).upper()
            path_suffix = mapping_match.group(2) or ""
            path_suffix = path_suffix.strip('"').strip("'")
            full_path = base_path.rstrip("/") + "/" + path_suffix.lstrip("/") \
                if path_suffix else base_path
            full_path = full_path if full_path else "/"
            # Normalize double slashes
            full_path = re.sub(r'//+', '/', full_path)

            # Look ahead at the method signature to extract details
            has_request_body = False
            has_path_variable = False
            has_request_param = False
            path_var_names = []
            request_param_names = []
            method_name = ""

            # Scan forward for the method declaration (up to 10 lines)
            for j in range(i + 1, min(i + 10, len(lines))):
                method_line = lines[j]
                if "@RequestBody" in method_line:
                    has_request_body = True
                if "@PathVariable" in method_line:
                    has_path_variable = True
                    pv = re.findall(
                        r'@PathVariable(?:\(["\']?(\w+)["\']?\))?\s+\w+\s+(\w+)',
                        method_line)
                    for grp in pv:
                        path_var_names.append(grp[1] if grp[1] else grp[0])
                if "@RequestParam" in method_line:
                    has_request_param = True
                    rp = re.findall(
                        r'@RequestParam(?:\([^)]*\))?\s+\w+\s+(\w+)',
                        method_line)
                    request_param_names.extend(rp)
                # Detect method name
                mn = re.search(
                    r'(?:public|private|protected)?\s*\w+(?:<[^>]+>)?\s+(\w+)\s*\(',
                    method_line)
                if mn:
                    method_name = mn.group(1)
                    break

            # Detect path variables from the path pattern (e.g., {id})
            path_vars_in_url = re.findall(r'\{(\w+)\}', full_path)
            if path_vars_in_url:
                has_path_variable = True
                if not path_var_names:
                    path_var_names = path_vars_in_url

            # Detect DB operations in the method body
            uses_db_select = False
            uses_db_insert = False
            uses_db_update = False
            uses_db_delete = False
            if method_name:
                in_method = False
                brace_depth = 0
                for j in range(i, min(i + 80, len(lines))):
                    ml = lines[j]
                    if method_name in ml and "(" in ml:
                        in_method = True
                    if in_method:
                        brace_depth += ml.count("{") - ml.count("}")
                        if "queryForList" in ml or "queryForMap" in ml or "query(" in ml:
                            uses_db_select = True
                        if "update(" in ml and "jdbcTemplate" in ml:
                            if http_method in ("POST", "PUT", "PATCH"):
                                if http_method == "POST":
                                    uses_db_insert = True
                                else:
                                    uses_db_update = True
                            else:
                                uses_db_delete = True
                        if brace_depth <= 0 and in_method and j > i + 1:
                            break

            endpoints.append({
                "method": http_method,
                "path": full_path,
                "method_name": method_name,
                "has_request_body": has_request_body,
                "has_path_variable": has_path_variable,
                "has_request_param": has_request_param,
                "path_var_names": path_var_names,
                "request_param_names": request_param_names,
                "uses_db_select": uses_db_select,
                "uses_db_insert": uses_db_insert,
                "uses_db_update": uses_db_update,
                "uses_db_delete": uses_db_delete,
            })
            i += 1

        return endpoints

    def _build_controller_test_methods(self, endpoints, has_jdbc,
                                       has_rest_template, service_beans,
                                       base_path):
        """Build comprehensive test methods for each controller endpoint."""
        methods = ""
        seen_names = set()

        for ep in endpoints:
            http_method = ep["method"]
            path = ep["path"]
            method_name = ep["method_name"] or http_method.lower()
            display_method = http_method
            # Create a clean test name
            test_base = self._to_test_name(method_name)

            # ── Build the test path (replace path variables with sample values) ──
            test_path = re.sub(r'\{(\w+)\}', lambda m: self._sample_path_value(m.group(1)), path)

            # ── Determine the MockMvc method name ────────────────────
            mvc_method = http_method.lower()
            if mvc_method == "delete":
                mvc_method = "delete"

            # ─────────────────────────────────────────────────────────
            # HAPPY PATH TEST
            # ─────────────────────────────────────────────────────────
            happy_name = self._unique_name(f"test{test_base}_ReturnsOk", seen_names)
            methods += f"    @Test\n"
            methods += f"    @DisplayName(\"{display_method} {path} - should return 200 OK\")\n"
            methods += f"    void {happy_name}() throws Exception {{\n"

            # Add mock setup if DB is used
            if has_jdbc and ep.get("uses_db_select"):
                sql_table = self._guess_table_from_path(path)
                methods += (
                    f"        // Given\n"
                    f"        when(jdbcTemplate.queryForList(anyString()))\n"
                    f"                .thenReturn(List.of(Map.of(\"id\", 1, \"name\", \"test\")));\n\n"
                )
            elif has_jdbc and (ep.get("uses_db_insert") or ep.get("uses_db_update") or ep.get("uses_db_delete")):
                methods += (
                    f"        // Given\n"
                    f"        when(jdbcTemplate.update(anyString(), any(Object[].class)))\n"
                    f"                .thenReturn(1);\n\n"
                )

            # Build the MockMvc perform chain
            methods += f"        // When & Then\n"
            if http_method in ("POST", "PUT", "PATCH") and ep["has_request_body"]:
                sample_body = self._sample_json_body(path)
                methods += (
                    f"        mockMvc.perform({mvc_method}(\"{test_path}\")\n"
                    f"                .contentType(MediaType.APPLICATION_JSON)\n"
                    f"                .content(\"{self._escape_java(sample_body)}\"))\n"
                )
            elif ep["has_request_param"]:
                param_chain = ""
                for pname in ep["request_param_names"]:
                    param_chain += f"\n                .param(\"{pname}\", \"testValue\")"
                methods += (
                    f"        mockMvc.perform({mvc_method}(\"{test_path}\")"
                    f"{param_chain})\n"
                )
            else:
                methods += f"        mockMvc.perform({mvc_method}(\"{test_path}\"))\n"

            # Response expectations
            if http_method == "GET" and not ep["has_path_variable"]:
                methods += (
                    f"                .andExpect(status().isOk())\n"
                    f"                .andExpect(content().contentType(MediaType.APPLICATION_JSON));\n"
                )
            else:
                methods += f"                .andExpect(status().isOk());\n"
            methods += f"    }}\n\n"

            # ─────────────────────────────────────────────────────────
            # GET list endpoint - verify JSON array response
            # ─────────────────────────────────────────────────────────
            if http_method == "GET" and not ep["has_path_variable"]:
                array_name = self._unique_name(f"test{test_base}_ReturnsJsonArray", seen_names)
                methods += f"    @Test\n"
                methods += f"    @DisplayName(\"{display_method} {path} - should return JSON array\")\n"
                methods += f"    void {array_name}() throws Exception {{\n"
                if has_jdbc:
                    methods += (
                        f"        // Given\n"
                        f"        when(jdbcTemplate.queryForList(anyString()))\n"
                        f"                .thenReturn(List.of(\n"
                        f"                        Map.of(\"id\", 1, \"name\", \"Alice\"),\n"
                        f"                        Map.of(\"id\", 2, \"name\", \"Bob\")));\n\n"
                    )
                methods += (
                    f"        // When & Then\n"
                    f"        mockMvc.perform(get(\"{test_path}\"))\n"
                    f"                .andExpect(status().isOk())\n"
                    f"                .andExpect(jsonPath(\"$\").isArray());\n"
                    f"    }}\n\n"
                )

            # ─────────────────────────────────────────────────────────
            # GET list endpoint - verify empty list
            # ─────────────────────────────────────────────────────────
            if http_method == "GET" and not ep["has_path_variable"] and has_jdbc:
                empty_name = self._unique_name(f"test{test_base}_ReturnsEmptyList", seen_names)
                methods += f"    @Test\n"
                methods += f"    @DisplayName(\"{display_method} {path} - should return empty list when no data\")\n"
                methods += f"    void {empty_name}() throws Exception {{\n"
                methods += (
                    f"        // Given\n"
                    f"        when(jdbcTemplate.queryForList(anyString()))\n"
                    f"                .thenReturn(Collections.emptyList());\n\n"
                    f"        // When & Then\n"
                    f"        mockMvc.perform(get(\"{test_path}\"))\n"
                    f"                .andExpect(status().isOk())\n"
                    f"                .andExpect(jsonPath(\"$\").isEmpty());\n"
                    f"    }}\n\n"
                )

            # ─────────────────────────────────────────────────────────
            # POST/PUT/PATCH - empty body → 400
            # ─────────────────────────────────────────────────────────
            if http_method in ("POST", "PUT", "PATCH") and ep["has_request_body"]:
                empty_name = self._unique_name(f"test{test_base}_EmptyBody_Returns400", seen_names)
                methods += f"    @Test\n"
                methods += f"    @DisplayName(\"{display_method} {path} - should return 400 with empty body\")\n"
                methods += f"    void {empty_name}() throws Exception {{\n"
                methods += (
                    f"        mockMvc.perform({mvc_method}(\"{test_path}\")\n"
                    f"                .contentType(MediaType.APPLICATION_JSON)\n"
                    f"                .content(\"{{}}\"))\n"
                    f"                .andExpect(status().isBadRequest());\n"
                    f"    }}\n\n"
                )

            # ─────────────────────────────────────────────────────────
            # POST/PUT/PATCH - invalid JSON → 400
            # ─────────────────────────────────────────────────────────
            if http_method in ("POST", "PUT", "PATCH") and ep["has_request_body"]:
                invalid_name = self._unique_name(f"test{test_base}_InvalidJson_Returns400", seen_names)
                methods += f"    @Test\n"
                methods += f"    @DisplayName(\"{display_method} {path} - should return 400 with invalid JSON\")\n"
                methods += f"    void {invalid_name}() throws Exception {{\n"
                methods += (
                    f"        mockMvc.perform({mvc_method}(\"{test_path}\")\n"
                    f"                .contentType(MediaType.APPLICATION_JSON)\n"
                    f"                .content(\"{{invalid json}}\"))\n"
                    f"                .andExpect(status().isBadRequest());\n"
                    f"    }}\n\n"
                )

            # ─────────────────────────────────────────────────────────
            # POST/PUT/PATCH - missing content type → 415
            # ─────────────────────────────────────────────────────────
            if http_method in ("POST", "PUT", "PATCH") and ep["has_request_body"]:
                no_ct_name = self._unique_name(f"test{test_base}_MissingContentType_Returns415", seen_names)
                methods += f"    @Test\n"
                methods += f"    @DisplayName(\"{display_method} {path} - should return 415 without content type\")\n"
                methods += f"    void {no_ct_name}() throws Exception {{\n"
                methods += (
                    f"        mockMvc.perform({mvc_method}(\"{test_path}\")\n"
                    f"                .content(\"{{\\\"name\\\":\\\"test\\\"}}\"))\n"
                    f"                .andExpect(status().isUnsupportedMediaType());\n"
                    f"    }}\n\n"
                )

            # ─────────────────────────────────────────────────────────
            # GET by ID - not found → 404
            # ─────────────────────────────────────────────────────────
            if http_method == "GET" and ep["has_path_variable"]:
                not_found_name = self._unique_name(f"test{test_base}_NotFound_Returns404", seen_names)
                not_found_path = re.sub(r'\{(\w+)\}', "99999", path)
                methods += f"    @Test\n"
                methods += f"    @DisplayName(\"{display_method} {path} - should return 404 when not found\")\n"
                methods += f"    void {not_found_name}() throws Exception {{\n"
                if has_jdbc:
                    methods += (
                        f"        // Given - empty result for non-existent ID\n"
                        f"        when(jdbcTemplate.queryForList(anyString(), any(Object[].class)))\n"
                        f"                .thenReturn(Collections.emptyList());\n\n"
                    )
                methods += (
                    f"        // When & Then\n"
                    f"        mockMvc.perform(get(\"{not_found_path}\"))\n"
                    f"                .andExpect(status().isNotFound());\n"
                    f"    }}\n\n"
                )

            # ─────────────────────────────────────────────────────────
            # DELETE by ID - happy path
            # ─────────────────────────────────────────────────────────
            if http_method == "DELETE" and ep["has_path_variable"]:
                del_nf_name = self._unique_name(f"test{test_base}_NotFound_Returns404", seen_names)
                not_found_path = re.sub(r'\{(\w+)\}', "99999", path)
                methods += f"    @Test\n"
                methods += f"    @DisplayName(\"{display_method} {path} - should return 404 for non-existent resource\")\n"
                methods += f"    void {del_nf_name}() throws Exception {{\n"
                if has_jdbc:
                    methods += (
                        f"        // Given - no rows affected\n"
                        f"        when(jdbcTemplate.update(anyString(), any(Object[].class)))\n"
                        f"                .thenReturn(0);\n\n"
                    )
                methods += (
                    f"        mockMvc.perform(delete(\"{not_found_path}\"))\n"
                    f"                .andExpect(status().isNotFound());\n"
                    f"    }}\n\n"
                )

        # ── Always add a 404 test for unknown path ───────────────
        unknown_name = self._unique_name("testUnknownPath_Returns404", seen_names)
        methods += (
            f"    @Test\n"
            f"    @DisplayName(\"Unknown path - should return 404\")\n"
            f"    void {unknown_name}() throws Exception {{\n"
            f"        mockMvc.perform(get(\"/nonexistent-path-for-test\"))\n"
            f"                .andExpect(status().isNotFound());\n"
            f"    }}\n"
        )

        return methods

    def _generate_integration_tests(self, spring_files):
        """Generate @SpringBootTest integration test classes for each controller."""
        test_files = {}
        for rel_path, content in spring_files.items():
            if "@RestController" not in content and "@Controller" not in content:
                continue

            class_name = rel_path.rsplit("/", 1)[-1].replace(".java", "")
            test_class_name = f"{class_name}IntegrationTest"

            if "/" in rel_path:
                sub_package = rel_path.rsplit("/", 1)[0].replace("/", ".")
                full_package = f"{self.group_id}.{sub_package}"
            else:
                full_package = self.group_id

            # Extract base path
            base_path = ""
            for line in content.splitlines():
                bm = re.search(
                    r'@RequestMapping\(\s*(?:value\s*=\s*)?["\']?(.*?)["\']?\s*\)',
                    line)
                if bm:
                    candidate = bm.group(1).strip('"').strip("'")
                    # Check this is class-level (next non-annotation line is class)
                    idx = content.splitlines().index(line)
                    remaining = content.splitlines()[idx + 1:idx + 5]
                    if any("class " in r for r in remaining):
                        base_path = candidate
                        break

            # Parse endpoints
            endpoints = self._parse_controller_endpoints(content, base_path)

            # Separate by HTTP method for CRUD flow test
            gets = [e for e in endpoints if e["method"] == "GET"]
            posts = [e for e in endpoints if e["method"] == "POST"]
            puts = [e for e in endpoints if e["method"] == "PUT"]
            deletes = [e for e in endpoints if e["method"] == "DELETE"]

            test_methods = ""

            # ── Individual endpoint integration tests ────────────────
            seen_names = set()
            for ep in endpoints:
                path = ep["path"]
                test_path = re.sub(
                    r'\{(\w+)\}',
                    lambda m: self._sample_path_value(m.group(1)),
                    path)
                mvc_method = ep["method"].lower()
                test_base = self._to_test_name(ep["method_name"] or ep["method"].lower())
                tname = self._unique_name(
                    f"testIntegration{test_base}_ReturnsSuccess", seen_names)

                test_methods += f"    @Test\n"
                test_methods += (
                    f"    @DisplayName(\"Integration: {ep['method']} {path}"
                    f" - should return success\")\n"
                )
                test_methods += f"    void {tname}() throws Exception {{\n"

                if ep["method"] in ("POST", "PUT", "PATCH") and ep["has_request_body"]:
                    sample_body = self._sample_json_body(path)
                    test_methods += (
                        f"        mockMvc.perform({mvc_method}(\"{test_path}\")\n"
                        f"                .contentType(MediaType.APPLICATION_JSON)\n"
                        f"                .content(\"{self._escape_java(sample_body)}\"))\n"
                        f"                .andExpect(status().isOk());\n"
                    )
                elif ep["has_request_param"]:
                    param_chain = ""
                    for pname in ep["request_param_names"]:
                        param_chain += f"\n                .param(\"{pname}\", \"testValue\")"
                    test_methods += (
                        f"        mockMvc.perform({mvc_method}(\"{test_path}\")"
                        f"{param_chain})\n"
                        f"                .andExpect(status().isOk());\n"
                    )
                else:
                    test_methods += (
                        f"        mockMvc.perform({mvc_method}(\"{test_path}\"))\n"
                        f"                .andExpect(status().isOk());\n"
                    )
                test_methods += f"    }}\n\n"

            # ── Full CRUD flow test (only if we have POST + GET) ─────
            if posts and gets:
                test_methods += (
                    f"    @Test\n"
                    f"    @DisplayName(\"Integration: Full CRUD flow\")\n"
                    f"    void testFullCrudFlow() throws Exception {{\n"
                )

                # Create (POST)
                post_ep = posts[0]
                post_path = re.sub(
                    r'\{(\w+)\}',
                    lambda m: self._sample_path_value(m.group(1)),
                    post_ep["path"])
                sample_body = self._sample_json_body(post_ep["path"])
                test_methods += (
                    f"        // Create\n"
                    f"        mockMvc.perform(post(\"{post_path}\")\n"
                    f"                .contentType(MediaType.APPLICATION_JSON)\n"
                    f"                .content(\"{self._escape_java(sample_body)}\"))\n"
                    f"                .andExpect(status().isOk());\n\n"
                )

                # Read (GET)
                get_ep = gets[0]
                get_path = re.sub(
                    r'\{(\w+)\}',
                    lambda m: self._sample_path_value(m.group(1)),
                    get_ep["path"])
                test_methods += (
                    f"        // Read\n"
                    f"        mockMvc.perform(get(\"{get_path}\"))\n"
                    f"                .andExpect(status().isOk());\n"
                )

                # Update (PUT) if available
                if puts:
                    put_ep = puts[0]
                    put_path = re.sub(
                        r'\{(\w+)\}',
                        lambda m: self._sample_path_value(m.group(1)),
                        put_ep["path"])
                    update_body = self._sample_json_body(put_ep["path"])
                    test_methods += (
                        f"\n        // Update\n"
                        f"        mockMvc.perform(put(\"{put_path}\")\n"
                        f"                .contentType(MediaType.APPLICATION_JSON)\n"
                        f"                .content(\"{self._escape_java(update_body)}\"))\n"
                        f"                .andExpect(status().isOk());\n"
                    )

                # Delete (DELETE) if available
                if deletes:
                    del_ep = deletes[0]
                    del_path = re.sub(
                        r'\{(\w+)\}',
                        lambda m: self._sample_path_value(m.group(1)),
                        del_ep["path"])
                    test_methods += (
                        f"\n        // Delete\n"
                        f"        mockMvc.perform(delete(\"{del_path}\"))\n"
                        f"                .andExpect(status().isOk());\n"
                    )

                test_methods += f"    }}\n\n"

            # ── Concurrent requests test ─────────────────────────────
            if gets:
                get_ep = gets[0]
                get_path = re.sub(
                    r'\{(\w+)\}',
                    lambda m: self._sample_path_value(m.group(1)),
                    get_ep["path"])
                test_methods += (
                    f"    @Test\n"
                    f"    @DisplayName(\"Integration: Concurrent GET requests\")\n"
                    f"    void testConcurrentGetRequests() throws Exception {{\n"
                    f"        // Verify endpoint handles multiple rapid requests\n"
                    f"        for (int i = 0; i < 5; i++) {{\n"
                    f"            mockMvc.perform(get(\"{get_path}\"))\n"
                    f"                    .andExpect(status().isOk());\n"
                    f"        }}\n"
                    f"    }}\n"
                )

            test_content = (
                f"package {full_package};\n\n"
                f"import org.junit.jupiter.api.DisplayName;\n"
                f"import org.junit.jupiter.api.Test;\n"
                f"import org.springframework.beans.factory.annotation.Autowired;\n"
                f"import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;\n"
                f"import org.springframework.boot.test.context.SpringBootTest;\n"
                f"import org.springframework.http.MediaType;\n"
                f"import org.springframework.test.web.servlet.MockMvc;\n\n"
                f"import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;\n"
                f"import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;\n\n"
                f"@SpringBootTest\n"
                f"@AutoConfigureMockMvc\n"
                f"@DisplayName(\"{class_name} - Integration Tests\")\n"
                f"class {test_class_name} {{\n\n"
                f"    @Autowired\n"
                f"    private MockMvc mockMvc;\n\n"
                f"{test_methods}"
                f"}}\n"
            )

            int_test_rel_path = rel_path.replace(".java", "IntegrationTest.java")
            test_files[int_test_rel_path] = test_content

        return test_files

    # ── Test generation helper methods ───────────────────────────────
    def _to_test_name(self, method_name):
        """Convert a method name to a PascalCase test name fragment."""
        if not method_name:
            return "Endpoint"
        return method_name[0].upper() + method_name[1:]

    def _unique_name(self, name, seen):
        """Ensure test method names are unique by appending a counter."""
        original = name
        counter = 2
        while name in seen:
            name = f"{original}{counter}"
            counter += 1
        seen.add(name)
        return name

    def _sample_path_value(self, var_name):
        """Return a sample value for a path variable based on its name."""
        lower = var_name.lower()
        if lower == "id" or lower.endswith("id"):
            return "1"
        if lower == "name" or lower.endswith("name"):
            return "test"
        if lower == "status":
            return "active"
        return "test"

    def _sample_json_body(self, path):
        """Generate a plausible JSON body based on the endpoint path."""
        # Extract the resource name from the path (last segment before any {id})
        segments = [s for s in path.split("/") if s and not s.startswith("{")]
        resource = segments[-1] if segments else "item"
        # Singularize a rough approximation
        if resource.endswith("s") and len(resource) > 3:
            singular = resource[:-1]
        else:
            singular = resource

        # Common field patterns based on resource name
        common_fields = {
            "user": '{"name":"John Doe","email":"john@example.com"}',
            "order": '{"product":"Widget","quantity":1,"price":9.99}',
            "product": '{"name":"Widget","price":9.99,"category":"General"}',
            "customer": '{"name":"Jane Doe","email":"jane@example.com","phone":"555-0100"}',
            "account": '{"name":"Test Account","type":"standard"}',
            "item": '{"name":"Test Item","description":"A test item"}',
            "employee": '{"name":"John Smith","department":"Engineering","email":"john@company.com"}',
            "payment": '{"amount":100.00,"currency":"USD","method":"credit_card"}',
            "message": '{"subject":"Test","body":"Hello World","recipient":"user@example.com"}',
        }

        return common_fields.get(
            singular.lower(),
            f'{{"name":"test {singular}","description":"Test {singular} description"}}')

    def _guess_table_from_path(self, path):
        """Guess a DB table name from the URL path."""
        segments = [s for s in path.split("/") if s and not s.startswith("{")]
        return segments[-1] if segments else "items"

    def _escape_java(self, text):
        """Escape a string for use inside a Java string literal."""
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _generate_dockerfile(self):
        port = getattr(self, "_server_port", "8081")
        return (
            f"FROM maven:3.9-eclipse-temurin-{self.java_version} AS build\n"
            f"WORKDIR /app\n"
            f"COPY pom.xml .\n"
            f"RUN mvn dependency:go-offline -B\n"
            f"COPY src ./src\n"
            f"RUN mvn clean package -Dmaven.test.skip=true -B\n\n"
            f"FROM eclipse-temurin:{self.java_version}-jre-alpine\n"
            f"WORKDIR /app\n"
            f"COPY --from=build /app/target/*.jar app.jar\n"
            f"EXPOSE {port}\n"
            f"ENV SPRING_PROFILES_ACTIVE=dev\n"
            f'ENTRYPOINT ["java", "-jar", "app.jar"]\n'
        )

    def _generate_docker_compose(self, connectors):
        port = getattr(self, "_server_port", "8081")
        db_name = "appdb"
        db_user = "admin"
        db_password = "changeme"
        db_configs = getattr(self, "_db_configs", [])
        if db_configs:
            cfg = db_configs[0]
            dn = str(cfg.get("database", "appdb"))
            du = str(cfg.get("user", "admin"))
            dp = str(cfg.get("password", "changeme"))
            if "${" not in dn:
                db_name = dn
            if "${" not in du:
                db_user = du
            if "${" not in dp:
                db_password = dp

        services = [
            f"  app:\n"
            f"    build: .\n"
            f"    ports:\n"
            f"      - '{port}:{port}'\n"
            f"    environment:\n"
            f"      - SPRING_PROFILES_ACTIVE=dev\n"
            f"    depends_on:\n"
            f"      - db\n"
        ]

        if "database" in connectors:
            services.append(
                f"  db:\n"
                f"    image: mysql:8\n"
                f"    ports:\n"
                f"      - '3306:3306'\n"
                f"    environment:\n"
                f"      MYSQL_ROOT_PASSWORD: root\n"
                f"      MYSQL_DATABASE: {db_name}\n"
                f"      MYSQL_USER: {db_user}\n"
                f"      MYSQL_PASSWORD: {db_password}\n"
                f"    volumes:\n"
                f"      - mysql_data:/var/lib/mysql\n"
            )

        if "jms" in connectors:
            services.append(
                "  activemq:\n"
                "    image: apache/activemq-artemis:latest\n"
                "    ports:\n"
                "      - '61616:61616'\n"
                "      - '8161:8161'\n"
            )

        if "amqp" in connectors:
            services.append(
                "  rabbitmq:\n"
                "    image: rabbitmq:3-management\n"
                "    ports:\n"
                "      - '5672:5672'\n"
                "      - '15672:15672'\n"
            )

        if "kafka" in connectors:
            services.append(
                "  kafka:\n"
                "    image: confluentinc/cp-kafka:7.5.0\n"
                "    ports:\n"
                "      - '9092:9092'\n"
                "    environment:\n"
                "      KAFKA_BROKER_ID: 1\n"
                "      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181\n"
                "      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092\n"
                "  zookeeper:\n"
                "    image: confluentinc/cp-zookeeper:7.5.0\n"
                "    ports:\n"
                "      - '2181:2181'\n"
                "    environment:\n"
                "      ZOOKEEPER_CLIENT_PORT: 2181\n"
            )

        if "redis" in connectors or "objectstore" in connectors:
            services.append(
                "  redis:\n"
                "    image: redis:7-alpine\n"
                "    ports:\n"
                "      - '6379:6379'\n"
            )

        if "mongo" in connectors:
            services.append(
                "  mongodb:\n"
                "    image: mongo:7\n"
                "    ports:\n"
                "      - '27017:27017'\n"
            )

        if "elasticsearch" in connectors:
            services.append(
                "  elasticsearch:\n"
                "    image: elasticsearch:8.11.0\n"
                "    ports:\n"
                "      - '9200:9200'\n"
                "    environment:\n"
                "      - discovery.type=single-node\n"
            )

        compose = "version: '3.8'\nservices:\n" + "\n".join(services)
        # Add volumes section if database is used
        if "database" in connectors:
            compose += "\nvolumes:\n  mysql_data:\n"
        return compose

    # ══════════════════════════════════════════════════════════════════════
    #  OPENAPI ANNOTATION INJECTION
    # ══════════════════════════════════════════════════════════════════════
    def _add_openapi_annotations(self, content, rel_path):
        """Inject OpenAPI/Swagger annotations into controller source code."""
        # Derive a tag name from the file name
        class_name = rel_path.rsplit("/", 1)[-1].replace(".java", "")
        tag_name = re.sub(r'Controller$', '', class_name)
        tag_name = re.sub(r'([a-z])([A-Z])', r'\1 \2', tag_name)  # CamelCase -> spaced

        # Add OpenAPI imports after existing imports
        openapi_imports = (
            "import io.swagger.v3.oas.annotations.Operation;\n"
            "import io.swagger.v3.oas.annotations.responses.ApiResponse;\n"
            "import io.swagger.v3.oas.annotations.tags.Tag;\n"
        )

        # Find the last import line and insert after it
        lines = content.split("\n")
        last_import_idx = -1
        for i, line in enumerate(lines):
            if line.startswith("import "):
                last_import_idx = i
        if last_import_idx >= 0:
            lines.insert(last_import_idx + 1, openapi_imports.rstrip())
        content = "\n".join(lines)

        # Add @Tag annotation before @RestController or @Controller
        content = content.replace(
            "@RestController",
            f'@Tag(name = "{tag_name}", description = "{tag_name} operations")\n@RestController',
            1,
        )
        if "@Controller" in content and "@RestController" not in content:
            content = content.replace(
                "@Controller",
                f'@Tag(name = "{tag_name}", description = "{tag_name} operations")\n@Controller',
                1,
            )

        # Add @Operation and @ApiResponse to endpoint methods
        for mapping in ("@GetMapping", "@PostMapping", "@PutMapping",
                        "@DeleteMapping", "@PatchMapping"):
            http_method = mapping.replace("@", "").replace("Mapping", "").upper()
            # Find each occurrence and prepend @Operation
            pattern = re.compile(rf'(\s+)({re.escape(mapping)}\(.*?\))', re.DOTALL)
            def _add_operation(m):
                indent = m.group(1)
                original = m.group(2)
                return (
                    f'{indent}@Operation(summary = "{http_method} operation")\n'
                    f'{indent}@ApiResponse(responseCode = "200", description = "Success")\n'
                    f'{indent}{original}'
                )
            content = pattern.sub(_add_operation, content)

        return content

    # ── Helpers ───────────────────────────────────────────────────────────
    def _to_class_name(self, name):
        name = re.sub(r"[^a-zA-Z0-9]", " ", name)
        return "".join(w.capitalize() for w in name.split())

    def _to_bean_name(self, name):
        name = name.replace("-", "_").replace(" ", "_")
        parts = name.split("_")
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

    def _to_property_name(self, name):
        name = re.sub(r"[^a-zA-Z0-9]", "-", name).lower()
        return re.sub(r"-+", "-", name).strip("-")
