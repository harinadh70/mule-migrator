"""
MuleSoft XML Parser - Comprehensive parser for ALL Mule 4 configuration components.
Covers: Core processors, all connectors, APIkit, Batch, Error handling, Secure properties.
Fallback: Unknown configs/sources can be sent to an LLM for conversion when enabled.
"""
import re
from lxml import etree


# ── Complete MuleSoft Namespace Registry ──────────────────────────────────────
NAMESPACES = {
    # Core
    "mule":   "http://www.mulesoft.org/schema/mule/core",
    "ee":     "http://www.mulesoft.org/schema/mule/ee/core",

    # Connectivity
    "http":   "http://www.mulesoft.org/schema/mule/http",
    "sockets":"http://www.mulesoft.org/schema/mule/sockets",
    "tls":    "http://www.mulesoft.org/schema/mule/tls",

    # Database
    "db":     "http://www.mulesoft.org/schema/mule/db",

    # Messaging
    "jms":    "http://www.mulesoft.org/schema/mule/jms",
    "amqp":   "http://www.mulesoft.org/schema/mule/amqp",
    "vm":     "http://www.mulesoft.org/schema/mule/vm",
    "kafka":  "http://www.mulesoft.org/schema/mule/kafka",
    "anypoint-mq": "http://www.mulesoft.org/schema/mule/anypoint-mq",

    # File
    "file":   "http://www.mulesoft.org/schema/mule/file",
    "sftp":   "http://www.mulesoft.org/schema/mule/sftp",
    "ftp":    "http://www.mulesoft.org/schema/mule/ftp",

    # Email
    "email":  "http://www.mulesoft.org/schema/mule/email",

    # API
    "apikit": "http://www.mulesoft.org/schema/mule/mule-apikit",

    # Web Services
    "ws":     "http://www.mulesoft.org/schema/mule/ws",
    "wsc":    "http://www.mulesoft.org/schema/mule/wsc",

    # Object Store / Cache
    "os":     "http://www.mulesoft.org/schema/mule/os",

    # Batch
    "batch":  "http://www.mulesoft.org/schema/mule/batch",

    # Validation
    "validation": "http://www.mulesoft.org/schema/mule/validation",

    # Scripting
    "scripting": "http://www.mulesoft.org/schema/mule/scripting",

    # Data formats
    "json":   "http://www.mulesoft.org/schema/mule/json",
    "xml-module": "http://www.mulesoft.org/schema/mule/xml-module",

    # Security / OAuth
    "oauth":  "http://www.mulesoft.org/schema/mule/oauth",
    "oauth2-provider": "http://www.mulesoft.org/schema/mule/oauth2-provider",
    "spring-security": "http://www.mulesoft.org/schema/mule/spring-security",
    "secure-properties": "http://www.mulesoft.org/schema/mule/secure-properties",

    # Cloud connectors
    "salesforce": "http://www.mulesoft.org/schema/mule/salesforce",
    "s3":     "http://www.mulesoft.org/schema/mule/s3",
    "sqs":    "http://www.mulesoft.org/schema/mule/sqs",
    "sns":    "http://www.mulesoft.org/schema/mule/sns",

    # NoSQL
    "mongo":  "http://www.mulesoft.org/schema/mule/mongo",
    "redis":  "http://www.mulesoft.org/schema/mule/redis",
    "elasticsearch": "http://www.mulesoft.org/schema/mule/elasticsearch",

    # Spring module
    "spring": "http://www.mulesoft.org/schema/mule/spring",
}

# All recognised core processor tags
CORE_PROCESSOR_TAGS = {
    "logger", "set-payload", "set-variable", "remove-variable",
    "choice", "scatter-gather", "for-each", "parallel-for-each",
    "try", "until-successful", "first-successful", "round-robin",
    "async", "flow-ref", "raise-error", "parse-template",
    "foreach", "set-attributes", "remove-attributes",
    "object-to-json-transformer", "json-to-object-transformer",
    "object-to-string-transformer", "idempotent-message-validator",
}

# Source (inbound) tags that start a flow
SOURCE_TAGS = {
    "listener",      # http:listener
    "scheduler",     # mule:scheduler
    "subscriber",    # jms:subscriber / amqp:subscriber
    "listener",      # kafka:listener / file:listener / ftp:listener / sftp:listener
    "on-new-file",   # file:listener alias
    "on-new-or-updated-file",
    "on-new-email",  # email source
    "on-updated-object", # salesforce
    "on-new-object",
}


class MuleSoftParser:
    """Parses MuleSoft 4 XML configuration into a structured dictionary."""

    def __init__(self):
        self.warnings = []

    # ── Public API ────────────────────────────────────────────────────────
    def parse(self, xml_content: str, agent_context=None) -> dict:
        """Main entry point – returns structured representation of the Mule app.

        Args:
            xml_content: Raw MuleSoft XML string.
            agent_context: Optional AgentContext for LLM-powered fallback on
                           unknown configs and sources.
        """
        xml_content = xml_content.strip()
        if not xml_content.startswith("<?xml"):
            xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_content

        try:
            root = etree.fromstring(xml_content.encode("utf-8"))
        except etree.XMLSyntaxError as e:
            raise ValueError(f"Invalid XML: {e}")

        self._agent_ctx = agent_context
        ns_map = self._build_ns_map(root)

        return {
            "global_configs":     self._parse_global_configs(root, ns_map),
            "flows":              self._parse_flows(root, ns_map),
            "sub_flows":          self._parse_sub_flows(root, ns_map),
            "error_handlers":     self._parse_error_handlers(root, ns_map),
            "global_properties":  self._parse_global_properties(root, ns_map),
            "connectors":         self._detect_connectors(root, ns_map),
            "batch_jobs":         self._parse_batch_jobs(root, ns_map),
            "apikit_configs":     self._parse_apikit(root, ns_map),
            "secure_properties":  self._parse_secure_properties(root, ns_map),
            "tls_contexts":       self._parse_tls_contexts(root, ns_map),
            "caching_strategies": self._parse_caching_strategies(root, ns_map),
            "warnings":           self.warnings,
        }

    # ── Namespace handling ────────────────────────────────────────────────
    def _build_ns_map(self, root):
        ns_map = {}
        for prefix, uri in root.nsmap.items():
            if prefix:
                ns_map[prefix] = uri
        for prefix, uri in NAMESPACES.items():
            if prefix not in ns_map:
                ns_map[prefix] = uri
        return ns_map

    # ── Global Configurations ─────────────────────────────────────────────
    def _parse_global_configs(self, root, ns_map):
        configs = []
        for elem in root:
            if not self._is_element(elem):
                continue  # skip Comment / PI nodes
            tag = self._local_tag(elem)
            ns  = self._get_ns_prefix(elem, ns_map)

            # HTTP Listener config
            if tag == "listener-config" and ns in ("http", ""):
                config = self._make_http_listener_config(elem, ns_map)
                if config:
                    configs.append(config)

            # HTTP Request config
            elif tag == "request-config" and ns in ("http", ""):
                configs.append(self._make_http_request_config(elem, ns_map))

            # Database config
            elif tag == "config" and ns == "db":
                configs.append(self._make_db_config(elem, ns_map))

            # JMS config
            elif tag == "config" and ns == "jms":
                configs.append({"type": "jms", "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # AMQP config
            elif tag == "config" and ns == "amqp":
                configs.append({"type": "amqp", "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # Kafka config
            elif tag in ("consumer-config", "producer-config") and ns == "kafka":
                configs.append({"type": f"kafka-{tag.split('-')[0]}",
                                "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # VM config
            elif tag == "config" and ns == "vm":
                configs.append({"type": "vm", "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # File / SFTP / FTP config
            elif tag == "config" and ns in ("file", "sftp", "ftp"):
                configs.append({"type": ns, "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # Email config
            elif tag in ("imap-config", "pop3-config", "smtp-config") and ns == "email":
                configs.append({"type": f"email-{tag.replace('-config', '')}",
                                "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # Object Store config
            elif tag == "config" and ns == "os":
                configs.append({"type": "objectstore", "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # Web Service Consumer config
            elif tag == "config" and ns in ("wsc", "ws"):
                configs.append({"type": "wsc", "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # Salesforce config
            elif tag == "config" and ns == "salesforce":
                configs.append({"type": "salesforce", "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # AWS S3 config
            elif tag == "config" and ns == "s3":
                configs.append({"type": "s3", "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # AWS SQS config
            elif tag == "config" and ns == "sqs":
                configs.append({"type": "sqs", "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # Redis config
            elif tag == "config" and ns == "redis":
                configs.append({"type": "redis", "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # MongoDB config
            elif tag == "config" and ns == "mongo":
                configs.append({"type": "mongo", "name": elem.get("name", ""),
                                "attributes": dict(elem.attrib),
                                "children": self._parse_children(elem)})

            # APIkit config
            elif tag == "config" and ns == "apikit":
                configs.append({"type": "apikit", "name": elem.get("name", ""),
                                "raml": elem.get("raml", elem.get("api", "")),
                                "attributes": dict(elem.attrib)})

            # ── Unknown config — try LLM fallback ─────────────────
            elif ns and tag in ("config", "listener-config", "request-config",
                                "consumer-config", "producer-config"):
                element_label = f"{ns}:{tag}"
                raw_xml = etree.tostring(elem, encoding="unicode", pretty_print=True)
                if self._agent_ctx:
                    from .llm_agent import convert_unknown_source
                    ai_result = convert_unknown_source(
                        self._agent_ctx, element_label, raw_xml)
                    if ai_result:
                        configs.append({
                            "type": ai_result.get("type", ns),
                            "name": elem.get("name", ""),
                            "attributes": dict(elem.attrib),
                            "children": self._parse_children(elem),
                            "auto_converted": True,
                            "fallback_config": ai_result,
                        })
                    else:
                        self.warnings.append(
                            f"Unknown config '{element_label}' — LLM could not convert. "
                            f"Check your provider or API key.")
                else:
                    self.warnings.append(
                        f"Unknown config '{element_label}' skipped. "
                        f"Enable LLM-assisted conversion for auto-migration.")

        return configs

    def _make_http_listener_config(self, elem, ns_map):
        http_ns = ns_map.get("http", "")
        config = {
            "type": "http-listener",
            "name": elem.get("name", ""),
            "host": elem.get("host", "0.0.0.0"),
            "port": elem.get("port", "8081"),
            "basePath": elem.get("basePath", "/"),
            "attributes": dict(elem.attrib),
        }
        # Check for TLS context
        for child in elem:
            if not self._is_element(child):
                continue
            ct = self._local_tag(child)
            if ct == "listener-connection":
                config["host"] = child.get("host", config["host"])
                config["port"] = child.get("port", config["port"])
                config["protocol"] = child.get("protocol", "HTTP")
            elif "tls" in ct.lower():
                config["tls"] = True
        return config

    def _make_http_request_config(self, elem, ns_map):
        config = {
            "type": "http-request",
            "name": elem.get("name", ""),
            "host": "", "port": "", "basePath": "/", "protocol": "HTTP",
            "attributes": dict(elem.attrib),
            "authentication": None,
        }
        for child in elem:
            if not self._is_element(child):
                continue
            ct = self._local_tag(child)
            if "connection" in ct:
                config["host"] = child.get("host", "")
                config["port"] = child.get("port", "")
                config["basePath"] = child.get("basePath", "/")
                config["protocol"] = child.get("protocol", "HTTP")
                # Check for auth
                for auth_child in child:
                    if not self._is_element(auth_child):
                        continue
                    auth_tag = self._local_tag(auth_child)
                    if "authentication" in auth_tag or "oauth" in auth_tag.lower():
                        config["authentication"] = {
                            "type": auth_tag,
                            "attributes": dict(auth_child.attrib),
                        }
        return config

    def _make_db_config(self, elem, ns_map):
        config = {
            "type": "database",
            "name": elem.get("name", ""),
            "url": "", "driver": "", "user": "", "password": "",
            "connection_type": "",
            "attributes": dict(elem.attrib),
        }
        for child in elem:
            if not self._is_element(child):
                continue
            ct = self._local_tag(child)
            if "connection" in ct:
                config["connection_type"] = ct  # my-sql-connection, oracle-connection, etc.
                config["url"] = child.get("url", "")
                config["driver"] = child.get("driverClassName", "")
                config["user"] = child.get("user", "")
                config["password"] = child.get("password", "")
                # MySQL-specific
                if "my-sql" in ct:
                    host = child.get("host", "localhost")
                    port = child.get("port", "3306")
                    database = child.get("database", "")
                    if not config["url"] and database:
                        config["url"] = f"jdbc:mysql://{host}:{port}/{database}"
                        config["driver"] = "com.mysql.cj.jdbc.Driver"
                    config["user"] = child.get("user", config["user"])
                    config["password"] = child.get("password", config["password"])
                # Oracle-specific
                elif "oracle" in ct:
                    host = child.get("host", "localhost")
                    port = child.get("port", "1521")
                    instance = child.get("instance", child.get("serviceName", ""))
                    if not config["url"] and instance:
                        config["url"] = f"jdbc:oracle:thin:@{host}:{port}:{instance}"
                        config["driver"] = "oracle.jdbc.OracleDriver"
                # PostgreSQL
                elif "postgre" in ct.lower():
                    host = child.get("host", "localhost")
                    port = child.get("port", "5432")
                    database = child.get("database", "")
                    if not config["url"] and database:
                        config["url"] = f"jdbc:postgresql://{host}:{port}/{database}"
                        config["driver"] = "org.postgresql.Driver"
                # MS SQL Server
                elif "mssql" in ct.lower() or "sqlserver" in ct.lower():
                    host = child.get("host", "localhost")
                    port = child.get("port", "1433")
                    database = child.get("databaseName", child.get("database", ""))
                    if not config["url"] and database:
                        config["url"] = f"jdbc:sqlserver://{host}:{port};databaseName={database}"
                        config["driver"] = "com.microsoft.sqlserver.jdbc.SQLServerDriver"
        return config

    # ── Flows ─────────────────────────────────────────────────────────────
    def _parse_flows(self, root, ns_map):
        flows = []
        mule_ns = ns_map.get("mule", "http://www.mulesoft.org/schema/mule/core")
        seen_names = set()

        for flow in root.findall(f"{{{mule_ns}}}flow"):
            name = flow.get("name", "")
            if name not in seen_names:
                seen_names.add(name)
                flows.append(self._parse_flow_element(flow, ns_map))

        # Also try without namespace prefix
        for flow in root.findall("flow"):
            name = flow.get("name", "")
            if name not in seen_names:
                seen_names.add(name)
                flows.append(self._parse_flow_element(flow, ns_map))

        return flows

    def _parse_sub_flows(self, root, ns_map):
        sub_flows = []
        mule_ns = ns_map.get("mule", "http://www.mulesoft.org/schema/mule/core")
        seen_names = set()

        for sf in root.findall(f"{{{mule_ns}}}sub-flow"):
            name = sf.get("name", "")
            if name not in seen_names:
                seen_names.add(name)
                sub_flows.append(self._parse_flow_element(sf, ns_map, is_sub_flow=True))

        for sf in root.findall("sub-flow"):
            name = sf.get("name", "")
            if name not in seen_names:
                seen_names.add(name)
                sub_flows.append(self._parse_flow_element(sf, ns_map, is_sub_flow=True))

        return sub_flows

    def _parse_flow_element(self, flow_elem, ns_map, is_sub_flow=False):
        flow_data = {
            "name": flow_elem.get("name", ""),
            "is_sub_flow": is_sub_flow,
            "source": None,
            "processors": [],
            "error_handler": None,
            "initialState": flow_elem.get("initialState", "started"),
            "maxConcurrency": flow_elem.get("maxConcurrency", ""),
        }

        for child in flow_elem:
            if not self._is_element(child):
                continue  # skip Comment / PI nodes
            tag = self._local_tag(child)
            ns  = self._get_ns_prefix(child, ns_map)
            processor = self._parse_processor(child, tag, ns, ns_map)

            # ── Source detection ──────────────────────────────────
            if not is_sub_flow and flow_data["source"] is None:
                source = self._try_parse_source(child, tag, ns, ns_map)
                if source:
                    flow_data["source"] = source
                    continue

            # ── Error handler ─────────────────────────────────────
            if tag == "error-handler":
                flow_data["error_handler"] = self._parse_error_handler_element(child, ns_map)
                continue

            flow_data["processors"].append(processor)

        return flow_data

    def _try_parse_source(self, elem, tag, ns, ns_map):
        """Detect and parse flow source (inbound endpoint)."""
        attrs = dict(elem.attrib)

        # HTTP Listener
        if tag == "listener" and ns in ("http", ""):
            return {
                "type": "http-listener",
                "path": attrs.get("path", "/"),
                "method": attrs.get("method", attrs.get("allowedMethods", "GET")),
                "config_ref": attrs.get("config-ref", ""),
                "responseStreaming": attrs.get("responseStreamingMode", ""),
                "attributes": attrs,
            }

        # Scheduler
        if tag == "scheduler":
            return {
                "type": "scheduler",
                "attributes": attrs,
                "children": self._parse_children(elem),
            }

        # JMS subscriber / listener
        if tag in ("subscriber", "listener") and ns == "jms":
            return {
                "type": "jms-listener",
                "destination": attrs.get("destination", ""),
                "config_ref": attrs.get("config-ref", ""),
                "ackMode": attrs.get("ackMode", "AUTO"),
                "attributes": attrs,
            }

        # AMQP listener
        if tag in ("subscriber", "listener") and ns == "amqp":
            return {
                "type": "amqp-listener",
                "queueName": attrs.get("queueName", attrs.get("destination", "")),
                "config_ref": attrs.get("config-ref", ""),
                "attributes": attrs,
            }

        # Kafka consumer / listener
        if tag in ("consumer", "message-listener", "listener") and ns == "kafka":
            return {
                "type": "kafka-listener",
                "topic": attrs.get("topic", ""),
                "config_ref": attrs.get("config-ref", ""),
                "attributes": attrs,
            }

        # VM listener
        if tag == "listener" and ns == "vm":
            return {
                "type": "vm-listener",
                "queueName": attrs.get("queueName", ""),
                "config_ref": attrs.get("config-ref", ""),
                "attributes": attrs,
            }

        # File listener
        if tag in ("listener", "on-new-file", "on-new-or-updated-file") and ns == "file":
            return {
                "type": "file-listener",
                "directory": attrs.get("directory", ""),
                "config_ref": attrs.get("config-ref", ""),
                "attributes": attrs,
            }

        # SFTP listener
        if tag in ("listener", "on-new-file") and ns == "sftp":
            return {
                "type": "sftp-listener",
                "directory": attrs.get("directory", ""),
                "config_ref": attrs.get("config-ref", ""),
                "attributes": attrs,
            }

        # FTP listener
        if tag in ("listener", "on-new-file") and ns == "ftp":
            return {
                "type": "ftp-listener",
                "directory": attrs.get("directory", ""),
                "config_ref": attrs.get("config-ref", ""),
                "attributes": attrs,
            }

        # Email listener
        if tag in ("listener-imap", "listener-pop3", "on-new-email") and ns == "email":
            return {
                "type": "email-listener",
                "config_ref": attrs.get("config-ref", ""),
                "attributes": attrs,
            }

        # Salesforce streaming
        if tag in ("on-new-object", "on-updated-object", "subscribe-topic",
                    "subscribe-channel") and ns == "salesforce":
            return {
                "type": f"salesforce-{tag}",
                "config_ref": attrs.get("config-ref", ""),
                "attributes": attrs,
            }

        # AWS SQS listener
        if tag in ("receivemessages", "listener") and ns == "sqs":
            return {
                "type": "sqs-listener",
                "queueUrl": attrs.get("queueUrl", ""),
                "config_ref": attrs.get("config-ref", ""),
                "attributes": attrs,
            }

        # Anypoint MQ subscriber
        if tag in ("subscriber", "listener") and ns == "anypoint-mq":
            return {
                "type": "anypoint-mq-listener",
                "destination": attrs.get("destination", ""),
                "config_ref": attrs.get("config-ref", ""),
                "attributes": attrs,
            }

        # ── Unknown source — try LLM fallback ─────────────────
        if ns and tag in SOURCE_TAGS:
            element_label = f"{ns}:{tag}"
            raw_xml = etree.tostring(elem, encoding="unicode", pretty_print=True)
            if self._agent_ctx:
                from .llm_agent import convert_unknown_source
                ai_result = convert_unknown_source(
                    self._agent_ctx, element_label, raw_xml)
                if ai_result:
                    return {
                        "type": ai_result.get("type", f"{ns}-{tag}"),
                        "config_ref": attrs.get("config-ref", ""),
                        "attributes": attrs,
                        "auto_converted": True,
                        "fallback_config": ai_result,
                    }
                else:
                    self.warnings.append(
                        f"Unknown source '{element_label}' — LLM could not convert.")
            else:
                self.warnings.append(
                    f"Unknown source '{element_label}' skipped. "
                    f"Enable LLM-assisted conversion for auto-migration.")

        return None

    # ── Processor parsing ─────────────────────────────────────────────────
    def _parse_processor(self, elem, tag, ns, ns_map):
        processor = {
            "type": f"{ns}:{tag}" if ns else tag,
            "tag": tag,
            "namespace": ns,
            "attributes": dict(elem.attrib),
            "children": [],
            "text": (elem.text or "").strip(),
        }

        # Recursively parse children
        for child in elem:
            if not self._is_element(child):
                continue  # skip Comment / PI nodes
            child_tag = self._local_tag(child)
            child_ns  = self._get_ns_prefix(child, ns_map)
            processor["children"].append(
                self._parse_processor(child, child_tag, child_ns, ns_map)
            )

        # ── Extract DataWeave from ee:transform ───────────────
        if tag == "transform" and ns == "ee":
            self._extract_transform_dw(elem, processor)

        # ── Inline DW expressions ─────────────────────────────
        if tag == "set-payload":
            value = elem.get("value", "")
            if value.startswith("#[") or "payload" in value.lower():
                processor["expression"] = value

        if tag == "set-variable":
            processor["variable_name"] = elem.get("variableName", "")
            processor["value"] = elem.get("value", "")

        if tag == "set-attributes":
            processor["attributes_map"] = elem.get("value", "")

        # ── Until-successful specifics ────────────────────────
        if tag == "until-successful":
            processor["maxRetries"] = elem.get("maxRetries", "5")
            processor["millisBetweenRetries"] = elem.get("millisBetweenRetries", "60000")

        # ── Async specifics ───────────────────────────────────
        if tag == "async":
            processor["maxConcurrency"] = elem.get("maxConcurrency", "")

        # ── For-each specifics ────────────────────────────────
        if tag in ("foreach", "for-each"):
            processor["collection"] = elem.get("collection", "#[payload]")
            processor["batchSize"] = elem.get("batchSize", "")

        # ── Parallel-for-each specifics ───────────────────────
        if tag == "parallel-for-each":
            processor["collection"] = elem.get("collection", "#[payload]")
            processor["maxConcurrency"] = elem.get("maxConcurrency", "")
            processor["timeout"] = elem.get("timeout", "")

        # ── Idempotent validator ──────────────────────────────
        if tag == "idempotent-message-validator":
            processor["idExpression"] = elem.get("idExpression", "")
            processor["valueExpression"] = elem.get("valueExpression", "")
            processor["objectStore"] = elem.get("objectStore-ref", "")

        # ── Parse-template ────────────────────────────────────
        if tag == "parse-template":
            processor["location"] = elem.get("location", "")

        return processor

    def _extract_transform_dw(self, elem, processor):
        """Extract all DataWeave scripts from an ee:transform block."""
        dw_parts = {}
        for child in elem.iter():
            child_tag = self._local_tag(child)
            if child_tag in ("set-payload", "set-variable", "message"):
                dw_text = ""
                target = child_tag
                var_name = child.get("variableName", "")
                for inner in child.iter():
                    if inner.text and inner.text.strip():
                        dw_text += inner.text.strip()
                if not dw_text and child.text:
                    dw_text = child.text.strip()
                if dw_text:
                    key = var_name if var_name else target
                    dw_parts[key] = dw_text

        # For backward compat, set top-level dataweave to the first found
        if dw_parts:
            first_key = list(dw_parts.keys())[0]
            processor["dataweave"] = dw_parts[first_key]
            processor["dw_target"] = first_key
            processor["dw_all_parts"] = dw_parts

    # ── Error Handlers ────────────────────────────────────────────────────
    def _parse_error_handlers(self, root, ns_map):
        handlers = []
        mule_ns = ns_map.get("mule", "http://www.mulesoft.org/schema/mule/core")
        for eh in root.findall(f"{{{mule_ns}}}error-handler"):
            # Only global error handlers (direct children of root)
            if eh.getparent() is root:
                handlers.append(self._parse_error_handler_element(eh, ns_map))
        return handlers

    def _parse_error_handler_element(self, eh_elem, ns_map):
        handler = {
            "name": eh_elem.get("name", ""),
            "ref": eh_elem.get("ref", ""),
            "on_error_propagate": [],
            "on_error_continue": [],
        }
        for child in eh_elem:
            if not self._is_element(child):
                continue
            tag = self._local_tag(child)
            entry = {
                "type": child.get("type", "ANY"),
                "when": child.get("when", ""),
                "logException": child.get("logException", "true"),
                "enableNotifications": child.get("enableNotifications", "true"),
                "processors": [],
            }
            for proc_child in child:
                if not self._is_element(proc_child):
                    continue
                proc_tag = self._local_tag(proc_child)
                proc_ns  = self._get_ns_prefix(proc_child, ns_map)
                entry["processors"].append(
                    self._parse_processor(proc_child, proc_tag, proc_ns, ns_map)
                )
            if tag == "on-error-propagate":
                handler["on_error_propagate"].append(entry)
            elif tag == "on-error-continue":
                handler["on_error_continue"].append(entry)
        return handler

    # ── Global Properties ─────────────────────────────────────────────────
    def _parse_global_properties(self, root, ns_map):
        props = {}
        for elem in root.iter():
            if not self._is_element(elem):
                continue
            tag = self._local_tag(elem)
            if tag == "global-property":
                props[elem.get("name", "")] = elem.get("value", "")
            elif tag == "configuration-properties":
                props["_config_file"] = elem.get("file", "")
            elif tag == "secure-properties":
                props["_secure_config_file"] = elem.get("file", "")
                props["_secure_key"] = elem.get("key", "")
        return props

    # ── Connector Detection ───────────────────────────────────────────────
    def _detect_connectors(self, root, ns_map):
        connectors = set()
        connector_keywords = {
            "http": ["http"],
            "database": ["db", "database"],
            "jms": ["jms"],
            "amqp": ["amqp"],
            "kafka": ["kafka"],
            "file": ["file"],
            "sftp": ["sftp"],
            "ftp": ["ftp"],
            "email": ["email"],
            "vm": ["vm"],
            "objectstore": ["os", "object-store"],
            "batch": ["batch"],
            "validation": ["validation"],
            "ee": ["ee/core"],
            "scripting": ["scripting"],
            "ws": ["/ws/", "/wsc/"],
            "salesforce": ["salesforce"],
            "s3": ["/s3"],
            "sqs": ["/sqs"],
            "sns": ["/sns"],
            "mongo": ["mongo"],
            "redis": ["redis"],
            "elasticsearch": ["elasticsearch"],
            "apikit": ["apikit"],
            "oauth": ["oauth"],
            "anypoint-mq": ["anypoint-mq"],
        }
        for elem in root.iter():
            if not self._is_element(elem):
                continue
            ns_uri = self._get_ns_uri(elem)
            if ns_uri:
                for connector, keywords in connector_keywords.items():
                    if any(kw in ns_uri for kw in keywords):
                        connectors.add(connector)
        return connectors

    # ── Batch Jobs ────────────────────────────────────────────────────────
    def _parse_batch_jobs(self, root, ns_map):
        jobs = []
        for elem in root.iter():
            if not self._is_element(elem):
                continue
            tag = self._local_tag(elem)
            if tag == "job" or (tag == "batch-job"):
                job = {
                    "name": elem.get("name", ""),
                    "maxFailedRecords": elem.get("maxFailedRecords", "-1"),
                    "steps": [],
                    "on_complete": [],
                }
                for child in elem:
                    if not self._is_element(child):
                        continue
                    child_tag = self._local_tag(child)
                    if child_tag in ("step", "batch-step"):
                        step = {
                            "name": child.get("name", ""),
                            "acceptExpression": child.get("acceptExpression", ""),
                            "acceptPolicy": child.get("acceptPolicy", "NO_FAILURES"),
                            "processors": [],
                        }
                        for proc in child:
                            if not self._is_element(proc):
                                continue
                            pt = self._local_tag(proc)
                            pn = self._get_ns_prefix(proc, ns_map)
                            step["processors"].append(
                                self._parse_processor(proc, pt, pn, ns_map)
                            )
                        job["steps"].append(step)
                    elif child_tag in ("on-complete", "batch-on-complete"):
                        for proc in child:
                            if not self._is_element(proc):
                                continue
                            pt = self._local_tag(proc)
                            pn = self._get_ns_prefix(proc, ns_map)
                            job["on_complete"].append(
                                self._parse_processor(proc, pt, pn, ns_map)
                            )
                jobs.append(job)
        return jobs

    # ── APIkit ────────────────────────────────────────────────────────────
    def _parse_apikit(self, root, ns_map):
        configs = []
        for elem in root.iter():
            if not self._is_element(elem):
                continue
            tag = self._local_tag(elem)
            ns  = self._get_ns_prefix(elem, ns_map)
            if tag == "config" and ns == "apikit":
                configs.append({
                    "name": elem.get("name", ""),
                    "raml": elem.get("raml", elem.get("api", "")),
                    "outboundHeadersMapName": elem.get("outboundHeadersMapName", ""),
                    "httpStatusVarName": elem.get("httpStatusVarName", ""),
                    "attributes": dict(elem.attrib),
                })
            elif tag == "router" and ns == "apikit":
                configs.append({
                    "name": "apikit-router",
                    "type": "router",
                    "config_ref": elem.get("config-ref", ""),
                    "attributes": dict(elem.attrib),
                })
        return configs

    # ── Secure Properties ─────────────────────────────────────────────────
    def _parse_secure_properties(self, root, ns_map):
        secure = []
        for elem in root.iter():
            if not self._is_element(elem):
                continue
            tag = self._local_tag(elem)
            if tag == "config" and "secure-properties" in self._get_ns_uri(elem):
                secure.append({
                    "file": elem.get("file", ""),
                    "key": elem.get("key", ""),
                    "algorithm": "",
                    "mode": "",
                })
                for child in elem:
                    if not self._is_element(child):
                        continue
                    ct = self._local_tag(child)
                    if "encrypt" in ct:
                        secure[-1]["algorithm"] = child.get("algorithm", "AES")
                        secure[-1]["mode"] = child.get("mode", "CBC")
        return secure

    # ── TLS Contexts ──────────────────────────────────────────────────────
    def _parse_tls_contexts(self, root, ns_map):
        contexts = []
        for elem in root.iter():
            if not self._is_element(elem):
                continue
            tag = self._local_tag(elem)
            if tag == "context" and "tls" in self._get_ns_uri(elem):
                ctx = {
                    "name": elem.get("name", ""),
                    "keyStore": {},
                    "trustStore": {},
                }
                for child in elem:
                    if not self._is_element(child):
                        continue
                    ct = self._local_tag(child)
                    if ct == "key-store":
                        ctx["keyStore"] = dict(child.attrib)
                    elif ct == "trust-store":
                        ctx["trustStore"] = dict(child.attrib)
                contexts.append(ctx)
        return contexts

    # ── Caching Strategies ────────────────────────────────────────────────
    def _parse_caching_strategies(self, root, ns_map):
        strategies = []
        for elem in root.iter():
            if not self._is_element(elem):
                continue
            tag = self._local_tag(elem)
            if tag in ("caching-strategy", "cache"):
                strategy = {
                    "name": elem.get("name", ""),
                    "keyExpression": elem.get("keyGenerationExpression", ""),
                    "attributes": dict(elem.attrib),
                    "children": self._parse_children(elem),
                }
                strategies.append(strategy)
        return strategies

    # ── Utility methods ───────────────────────────────────────────────────
    def _parse_children(self, elem):
        children = []
        for child in elem:
            if not self._is_element(child):
                continue
            children.append({
                "tag": self._local_tag(child),
                "attributes": dict(child.attrib),
                "text": (child.text or "").strip(),
                "children": self._parse_children(child),
            })
        return children

    @staticmethod
    def _is_element(elem):
        """Return True if *elem* is a real XML element (not a Comment / PI)."""
        return isinstance(elem.tag, str)

    def _local_tag(self, elem):
        tag = elem.tag
        if not isinstance(tag, str):
            return ""  # Comment / ProcessingInstruction node
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        return tag

    def _get_ns_prefix(self, elem, ns_map):
        tag = elem.tag
        if not isinstance(tag, str):
            return ""
        if "}" in tag:
            uri = tag.split("}")[0].strip("{")
            for prefix, ns_uri in ns_map.items():
                if ns_uri == uri:
                    return prefix
            for prefix, ns_uri in NAMESPACES.items():
                if ns_uri == uri:
                    return prefix
        return ""

    def _get_ns_uri(self, elem):
        tag = elem.tag
        if not isinstance(tag, str):
            return ""
        if "}" in tag:
            return tag.split("}")[0].strip("{")
        return ""
