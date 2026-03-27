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
        self.project_name = project_name
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
        files["src/main/resources/application-dev.properties"] = \
            self._generate_profile_properties("dev")
        files["src/main/resources/application-prod.properties"] = \
            self._generate_profile_properties("prod")

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
        controller_test_files = self._generate_controller_tests(spring_files)
        for rel_path, content in controller_test_files.items():
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

        <!-- H2 in-memory database for testing -->
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!-- MySQL connector (uncomment to enable)
        <dependency>
            <groupId>com.mysql</groupId>
            <artifactId>mysql-connector-j</artifactId>
            <scope>runtime</scope>
        </dependency>
        -->

        <!-- PostgreSQL connector (uncomment to enable)
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

        if any(f.get("source", {}).get("type") == "scheduler"
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
        lines = [f"# Migrated from MuleSoft — {self.project_name}",
                 f"spring.application.name={self.project_name}", ""]

        for cfg in parsed_data.get("global_configs", []):
            props = cm.get_spring_config_for_connector(cfg.get("type", ""), cfg)
            if props:
                lines.append(f"# {cfg.get('type', '')} — {cfg.get('name', '')}")
                for k, v in props.items():
                    lines.append(f"{k}={v}")
                lines.append("")

        # Global properties
        for k, v in parsed_data.get("global_properties", {}).items():
            if not k.startswith("_"):
                lines.append(f"{k}={v}")

        lines += ["", "# Logging", "logging.level.root=INFO",
                   f"logging.level.{self.group_id}=DEBUG",
                   "", "# Actuator",
                   "management.endpoints.web.exposure.include=health,info,metrics"]
        return "\n".join(lines) + "\n"

    def _generate_yaml_properties(self, parsed_data, connector_info):
        lines = ["spring:", f"  application:", f"    name: {self.project_name}"]
        for cfg in parsed_data.get("global_configs", []):
            if cfg.get("type") == "http-listener":
                lines += ["", "server:", f"  port: {cfg.get('port', '8081')}"]
            elif cfg.get("type") == "database":
                lines += ["", "  datasource:"]
                if cfg.get("url"):
                    lines.append(f"    url: {cfg['url']}")
                if cfg.get("driver"):
                    lines.append(f"    driver-class-name: {cfg['driver']}")
                if cfg.get("user"):
                    lines.append(f"    username: {cfg['user']}")
                if cfg.get("password"):
                    lines.append(f"    password: {cfg['password']}")
                lines += ["  jpa:", "    hibernate:", "      ddl-auto: none"]
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
                   "      show-details: when-authorized"]

        return "\n".join(lines) + "\n"

    def _generate_profile_properties(self, profile):
        lines = [f"# Profile: {profile}",
                 f"spring.application.name={self.project_name}-{profile}", ""]
        if profile == "dev":
            lines += ["logging.level.root=DEBUG",
                       f"logging.level.{self.group_id}=DEBUG",
                       "spring.jpa.show-sql=true"]
        elif profile == "prod":
            lines += ["logging.level.root=WARN",
                       f"logging.level.{self.group_id}=INFO",
                       "spring.jpa.show-sql=false",
                       "server.error.include-stacktrace=never"]
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
            f"import org.junit.jupiter.api.Test;\n"
            f"import org.springframework.boot.test.context.SpringBootTest;\n"
            f"import static org.junit.jupiter.api.Assertions.assertNotNull;\n\n"
            f"@SpringBootTest\n"
            f"class {app_class}Tests {{\n\n"
            f"    @Test\n"
            f"    void contextLoads() {{\n"
            f"        // Verifies that the Spring application context starts successfully\n"
            f"    }}\n\n"
            f"    @Test\n"
            f"    void mainMethodRuns() {{\n"
            f"        // Smoke test to ensure main() doesn't throw\n"
            f"        {app_class}.main(new String[]{{}});\n"
            f"    }}\n"
            f"}}\n"
        )

    def _generate_controller_tests(self, spring_files):
        """Generate @WebMvcTest test classes for each discovered controller."""
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

            # Find service dependencies: fields annotated or injected
            service_beans = []
            for line in content.splitlines():
                # Match field injection or constructor params that end with Service
                m = re.search(r'\b(\w+Service)\b', line)
                if m and m.group(1) not in service_beans and m.group(1) != "Service":
                    service_beans.append(m.group(1))

            # Find endpoint mappings to generate test methods
            endpoints = []
            for line in content.splitlines():
                gm = re.search(r'@GetMapping\(["\']?(.*?)["\']?\)', line)
                if gm:
                    endpoints.append(("GET", gm.group(1).strip('"').strip("'")))
                pm = re.search(r'@PostMapping\(["\']?(.*?)["\']?\)', line)
                if pm:
                    endpoints.append(("POST", pm.group(1).strip('"').strip("'")))
                rm = re.search(r'@RequestMapping\(["\']?(.*?)["\']?\)', line)
                if rm and "@RestController" in content:
                    endpoints.append(("GET", rm.group(1).strip('"').strip("'")))

            # Extract base path from class-level @RequestMapping
            base_path = ""
            for line in content.splitlines():
                bm = re.search(r'@RequestMapping\(["\']?(.*?)["\']?\)', line)
                if bm:
                    base_path = bm.group(1).strip('"').strip("'")
                    break

            # Build mock bean declarations
            mock_beans = ""
            for svc in service_beans:
                mock_beans += f"    @MockBean\n    private {svc} {svc[0].lower()}{svc[1:]};\n\n"

            # Build test methods
            test_methods = ""
            # Always include a basic GET test
            test_path = base_path if base_path else "/"
            test_methods += (
                f"    @Test\n"
                f"    void shouldReturn200ForGetRequest() throws Exception {{\n"
                f"        mockMvc.perform(get(\"{test_path}\"))\n"
                f"                .andExpect(status().isOk());\n"
                f"    }}\n\n"
            )

            # POST test if any POST endpoints found
            has_post = any(m == "POST" for m, _ in endpoints)
            if has_post:
                post_path = next((p for m, p in endpoints if m == "POST"), base_path or "/")
                test_methods += (
                    f"    @Test\n"
                    f"    void shouldReturn200ForPostRequest() throws Exception {{\n"
                    f"        mockMvc.perform(post(\"{post_path}\")\n"
                    f"                .contentType(MediaType.APPLICATION_JSON)\n"
                    f"                .content(\"{{}}\"))\n"
                    f"                .andExpect(status().isOk());\n"
                    f"    }}\n\n"
                )

            # Error handling test
            test_methods += (
                f"    @Test\n"
                f"    void shouldReturn404ForInvalidPath() throws Exception {{\n"
                f"        mockMvc.perform(get(\"/nonexistent-path-for-test\"))\n"
                f"                .andExpect(status().isNotFound());\n"
                f"    }}\n"
            )

            test_content = (
                f"package {full_package};\n\n"
                f"import org.junit.jupiter.api.Test;\n"
                f"import org.springframework.beans.factory.annotation.Autowired;\n"
                f"import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;\n"
                f"import org.springframework.boot.test.mock.bean.MockBean;\n"
                f"import org.springframework.http.MediaType;\n"
                f"import org.springframework.test.web.servlet.MockMvc;\n\n"
                f"import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;\n"
                f"import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;\n\n"
                f"@WebMvcTest({class_name}.class)\n"
                f"class {test_class_name} {{\n\n"
                f"    @Autowired\n"
                f"    private MockMvc mockMvc;\n\n"
                f"{mock_beans}"
                f"{test_methods}"
                f"}}\n"
            )

            # Place test in same sub-path as the controller
            test_rel_path = rel_path.replace(".java", "Test.java")
            test_files[test_rel_path] = test_content

        return test_files

    def _generate_dockerfile(self):
        return (
            f"FROM eclipse-temurin:{self.java_version}-jdk-alpine AS build\n"
            f"WORKDIR /app\n"
            f"COPY . .\n"
            f"RUN ./mvnw clean package -DskipTests\n\n"
            f"FROM eclipse-temurin:{self.java_version}-jre-alpine\n"
            f"WORKDIR /app\n"
            f"COPY --from=build /app/target/*.jar app.jar\n"
            f"EXPOSE 8080\n"
            f'ENTRYPOINT ["java", "-jar", "app.jar"]\n'
        )

    def _generate_docker_compose(self, connectors):
        services = [
            f"  app:\n"
            f"    build: .\n"
            f"    ports:\n"
            f"      - '8080:8080'\n"
            f"    environment:\n"
            f"      - SPRING_PROFILES_ACTIVE=dev\n"
        ]

        if "database" in connectors:
            services.append(
                "  db:\n"
                "    image: mysql:8\n"
                "    ports:\n"
                "      - '3306:3306'\n"
                "    environment:\n"
                "      MYSQL_ROOT_PASSWORD: root\n"
                "      MYSQL_DATABASE: appdb\n"
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

        return "version: '3.8'\nservices:\n" + "\n".join(services)

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
