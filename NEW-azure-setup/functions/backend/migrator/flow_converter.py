"""
Flow Converter – Converts ALL MuleSoft flow types to Spring Boot code.

Supported sources : HTTP listener, Scheduler, JMS, AMQP, Kafka, VM, File,
                    SFTP, FTP, Email, Salesforce, SQS, Anypoint MQ
Supported processors:
  Core       : logger, set-payload, set-variable, remove-variable, choice,
               scatter-gather, for-each, parallel-for-each, try,
               until-successful, first-successful, round-robin, async,
               flow-ref, raise-error, parse-template,
               idempotent-message-validator
  HTTP       : request
  Database   : select, insert, update, delete, stored-procedure, bulk-insert
  JMS/AMQP   : publish, consume
  Kafka      : publish, consume
  VM         : publish, consume
  File/SFTP  : read, write, list, delete, move, copy, rename
  Email      : send, list
  Object Store: store, retrieve, remove, contains
  Web Service: consume (SOAP)
  Salesforce : query, create, update, upsert, delete
  AWS S3     : put-object, get-object, delete-object, list-objects
  AWS SQS    : send-message, receive-messages, delete-message
  Cache      : cache scope
  Validation : is-not-null, is-not-empty, is-email, is-url, matches-regex,
               is-true, is-false, validate-size
  Transformers: object-to-json, json-to-object, object-to-string
"""
import re


class FlowConverter:
    def __init__(self, dw_converter, connector_mapper):
        self.dw_converter = dw_converter
        self.connector_mapper = connector_mapper
        self.warnings = []
        self._sub_flow_map = {}

    # ══════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ══════════════════════════════════════════════════════════════════════
    def convert(self, parsed_data: dict, converted_dw: dict,
                agent_context=None) -> dict:
        files = {}
        self._agent_ctx = agent_context
        self._sub_flow_map = {
            sf["name"]: sf for sf in parsed_data.get("sub_flows", [])
        }

        # Categorise flows by source type
        http_flows = []
        scheduler_flows = []
        jms_flows = []
        amqp_flows = []
        kafka_flows = []
        vm_flows = []
        file_flows = []
        email_flows = []
        salesforce_flows = []
        sqs_flows = []
        other_flows = []
        apikit_flows = []           # APIkit-routed flows (no source)

        # ── Detect APIkit pattern ─────────────────────────────────────
        # APIkit flows have names like "get:\policies:insurance-api-router"
        # They have no source (source=None) and are children of an
        # APIkit router.  Detect the router config name from apikit_configs
        # or from the main flow's apikit:router processor.
        apikit_router_configs = set()
        for cfg in parsed_data.get("apikit_configs", []):
            apikit_router_configs.add(cfg.get("name", ""))
        # Also detect from flows whose processors include apikit:router
        for flow in parsed_data.get("flows", []):
            for proc in flow.get("processors", []):
                if proc.get("type") in ("apikit:router", "apikit-router"):
                    ref = proc.get("attributes", {}).get("config-ref", "")
                    if ref:
                        apikit_router_configs.add(ref)

        _APIKIT_NAME_RE = re.compile(
            r'^(get|post|put|patch|delete|head|options):'  # HTTP method
            r'\\(.+?)'                                     # path
            r'(?::application\\[a-z]+)?'                   # optional content-type
            r':(.+)$'                                      # router config
        )

        for flow in parsed_data.get("flows", []):
            source = flow.get("source")
            if not source:
                # Check if this is an APIkit flow by name pattern
                m = _APIKIT_NAME_RE.match(flow.get("name", ""))
                if m:
                    apikit_flows.append(flow)
                else:
                    other_flows.append(flow)
            elif source["type"] == "http-listener":
                http_flows.append(flow)
            elif source["type"] == "scheduler":
                scheduler_flows.append(flow)
            elif source["type"].startswith("jms"):
                jms_flows.append(flow)
            elif source["type"].startswith("amqp"):
                amqp_flows.append(flow)
            elif source["type"].startswith("kafka"):
                kafka_flows.append(flow)
            elif source["type"].startswith("vm"):
                vm_flows.append(flow)
            elif source["type"] in ("file-listener", "sftp-listener", "ftp-listener"):
                file_flows.append(flow)
            elif source["type"].startswith("email"):
                email_flows.append(flow)
            elif source["type"].startswith("salesforce"):
                salesforce_flows.append(flow)
            elif source["type"].startswith("sqs"):
                sqs_flows.append(flow)
            else:
                other_flows.append(flow)

        # ── Generate code per category ────────────────────────────────

        # APIkit flows → proper REST controller with individual endpoints
        if apikit_flows:
            ctrl_files = self._generate_apikit_controller(
                apikit_flows, http_flows, parsed_data)
            files.update(ctrl_files)
            # Remove the main flow from http_flows so it doesn't generate
            # a duplicate catch-all controller
            http_flows = [f for f in http_flows
                          if not any(p.get("type") in ("apikit:router", "apikit-router")
                                     for p in f.get("processors", []))]

        if http_flows:
            controllers = self._group_flows_by_config(http_flows)
            for cfg_name, flows in controllers.items():
                cls = self._to_class_name(cfg_name) + "Controller"
                files[f"controller/{cls}.java"] = self._generate_controller(
                    cls, flows, parsed_data)

        if scheduler_flows:
            files["scheduler/ScheduledTasks.java"] = self._generate_scheduler(
                scheduler_flows, parsed_data)

        if jms_flows:
            files["listener/JmsMessageListener.java"] = self._generate_jms_listener(
                jms_flows, parsed_data)

        if amqp_flows:
            files["listener/AmqpMessageListener.java"] = self._generate_amqp_listener(
                amqp_flows, parsed_data)

        if kafka_flows:
            files["listener/KafkaMessageListener.java"] = self._generate_kafka_listener(
                kafka_flows, parsed_data)

        if vm_flows:
            files["listener/VmEventListener.java"] = self._generate_vm_listener(
                vm_flows, parsed_data)

        if file_flows:
            files["listener/FileWatcherService.java"] = self._generate_file_watcher(
                file_flows, parsed_data)

        if email_flows:
            files["listener/EmailListener.java"] = self._generate_email_listener(
                email_flows, parsed_data)

        if salesforce_flows:
            files["listener/SalesforceEventListener.java"] = self._generate_salesforce_listener(
                salesforce_flows, parsed_data)

        if sqs_flows:
            files["listener/SqsMessageListener.java"] = self._generate_sqs_listener(
                sqs_flows, parsed_data)

        # Sub-flows → service classes
        if parsed_data.get("sub_flows"):
            services = self._generate_services(parsed_data["sub_flows"], parsed_data)
            for name, content in services.items():
                files[f"service/{name}.java"] = content

        # Standalone flows → services
        for flow in other_flows:
            cls = self._to_class_name(flow["name"]) + "Service"
            files[f"service/{cls}.java"] = self._generate_service_from_flow(
                cls, flow, parsed_data)

        # Batch jobs
        for job in parsed_data.get("batch_jobs", []):
            cls = self._to_class_name(job["name"]) + "BatchConfig"
            files[f"batch/{cls}.java"] = self._generate_batch_job(cls, job, parsed_data)

        # Global error handler + exception classes
        error_handlers = parsed_data.get("error_handlers", [])
        has_flow_errors = any(
            f.get("error_handler") for f in parsed_data.get("flows", []))
        if error_handlers or has_flow_errors:
            files["exception/GlobalExceptionHandler.java"] = \
                self._generate_exception_handler(error_handlers, parsed_data)
        # Always generate exception classes (used by GlobalExceptionHandler and service code)
        files["exception/ResourceNotFoundException.java"] = (
            'package com.example.exception;\n\n'
            'public class ResourceNotFoundException extends RuntimeException {\n'
            '    public ResourceNotFoundException(String message) {\n'
            '        super(message);\n'
            '    }\n'
            '    public ResourceNotFoundException(String message, Throwable cause) {\n'
            '        super(message, cause);\n'
            '    }\n'
            '}\n'
        )
        files["exception/BadRequestException.java"] = (
            'package com.example.exception;\n\n'
            'public class BadRequestException extends RuntimeException {\n'
            '    public BadRequestException(String message) {\n'
            '        super(message);\n'
            '    }\n'
            '    public BadRequestException(String message, Throwable cause) {\n'
            '        super(message, cause);\n'
            '    }\n'
            '}\n'
        )

        return files

    # ══════════════════════════════════════════════════════════════════════
    #  PROCESSOR CONVERSION  –  the core engine
    # ══════════════════════════════════════════════════════════════════════
    def _convert_processors(self, processors, parsed_data, indent=2):
        lines = []
        imports = set()
        service_deps = set()
        px = "    " * indent

        for proc in processors:
            tag   = proc.get("tag", "")
            ns    = proc.get("namespace", "")
            attrs = proc.get("attributes", {})

            # ── logger ────────────────────────────────────────────
            if tag == "logger":
                level = attrs.get("level", "INFO").lower()
                if level not in ("trace", "debug", "info", "warn", "error"):
                    level = "info"
                msg   = attrs.get("message", "")
                cat   = attrs.get("category", "")
                if cat:
                    lines.append(f'{px}// Category: {cat}')
                # Sanitize MuleSoft expressions to safe log strings
                safe_msg = re.sub(r"#\[([^\]]+)\]", r"{}", msg)
                safe_msg = self._escape_java(safe_msg)
                lines.append(f'{px}log.{level}("{safe_msg}");')

            # ── set-payload ───────────────────────────────────────
            elif tag == "set-payload":
                value = attrs.get("value", "")
                mime  = attrs.get("mimeType", "")
                if value.strip() == "#[payload]":
                    # payload = payload is a no-op, skip it
                    pass
                elif value.startswith("#["):
                    java_expr = self.dw_converter.convert_inline_expression(value)
                    # Avoid generating broken code
                    if any(p in java_expr for p in ["request.", "attributes.", "vars."]):
                        lines.append(f'{px}// TODO: Convert MuleSoft expression: {value}')
                    else:
                        lines.append(f"{px}payload = {java_expr};")
                else:
                    lines.append(f'{px}payload = "{self._escape_java(value)}";')
                if mime:
                    lines.append(f'{px}// MIME type: {mime}')

            # ── set-variable ──────────────────────────────────────
            elif tag == "set-variable":
                var_name = attrs.get("variableName", "var")
                value = attrs.get("value", "")
                if value.startswith("#["):
                    java_expr = self.dw_converter.convert_inline_expression(value)
                    lines.append(f"{px}Object {var_name} = {java_expr};")
                else:
                    lines.append(f'{px}Object {var_name} = "{self._escape_java(value)}";')

            # ── remove-variable ───────────────────────────────────
            elif tag == "remove-variable":
                var_name = attrs.get("variableName", "")
                lines.append(f"{px}{var_name} = null;")

            # ── ee:transform (DataWeave) ──────────────────────────
            elif tag == "transform" and ns == "ee":
                dw_script = proc.get("dataweave", "")
                if dw_script:
                    result = self.dw_converter.convert(dw_script)
                    imports.update(result.get("imports", []))
                    java_code = result.get("java_code", "").strip()
                    # Skip no-op transforms (just "payload")
                    if java_code and java_code != "payload":
                        # Validate the converted code is actually Java, not
                        # leftover DataWeave.  Common DW-syntax leaks:
                        _dw_leak = (
                            " map {" in java_code or
                            " map\n" in java_code or
                            re.search(r"^\s*\w+:\s+\w+\.get\(", java_code, re.MULTILINE) or
                            re.search(r"^\s*\{\s*success:", java_code, re.MULTILINE) or
                            "format:" in java_code or
                            " filter {" in java_code or
                            # DW object literal: { key: value, ... } in Java context
                            re.search(r'\.put\(\s*"[^"]+"\s*,\s*\{', java_code) or
                            # DW-style field access: p.field_name without .get()
                            re.search(r'\b[a-z]\w*\.[a-z_]+\s*[,})]', java_code) or
                            # DW reduce/map/filter operators
                            " reduce " in java_code or
                            # DW sizeOf function
                            "sizeOf(" in java_code or
                            # DW ternary with 'if' keyword: value if condition
                            re.search(r'\w+\s+if\s+\w+', java_code) or
                            # DW 'as' type coercion
                            re.search(r'\bas\s+(String|Number|Date)', java_code)
                        )
                        if _dw_leak:
                            # Wrap raw DW as a TODO comment instead of
                            # emitting broken Java
                            lines.append(f"{px}// TODO: Convert the following DataWeave transform to Java")
                            for dw_line in dw_script.strip().split("\n"):
                                lines.append(f"{px}// DW: {dw_line}")
                            lines.append(f"{px}Map<String, Object> transformed = new LinkedHashMap<>();")
                            lines.append(f"{px}// Populate 'transformed' map from the DataWeave logic above")
                            imports.add("java.util.LinkedHashMap")
                            imports.add("java.util.Map")
                        else:
                            # Comprehensively rename "result" variable to "transformed"
                            # to avoid conflicts with other variables in scope
                            java_code = re.sub(r'\bresult\b', 'transformed', java_code)
                            for dw_line in java_code.split("\n"):
                                lines.append(f"{px}{dw_line}")
                        # Update payload to transformed result
                        lines.append(f"{px}payload = transformed;")
                    if result.get("warnings"):
                        for w in result["warnings"]:
                            lines.append(f"{px}// WARNING: {w}")
                else:
                    lines.append(f"{px}// TODO: Convert DataWeave transform")

            # ── choice (if/else router) ───────────────────────────
            elif tag == "choice":
                choice_lines, ci = self._convert_choice(proc, parsed_data, indent)
                lines.extend(choice_lines)
                imports.update(ci)

            # ── scatter-gather (parallel execution) ───────────────
            elif tag == "scatter-gather":
                imports.add("java.util.concurrent.CompletableFuture")
                imports.add("java.util.List")
                lines.append(f"{px}// Scatter-Gather: parallel execution")
                routes = [c for c in proc.get("children", []) if c.get("tag") == "route"]
                for i, route in enumerate(routes):
                    lines.append(
                        f"{px}CompletableFuture<Object> future{i} = CompletableFuture.supplyAsync(() -> {{")
                    cl, ci, cd = self._convert_processors(
                        route.get("children", []), parsed_data, indent + 1)
                    lines.extend(cl)
                    imports.update(ci)
                    service_deps.update(cd)
                    lines.append(f"{px}    return payload;")
                    lines.append(f"{px}}});")
                futures = ", ".join(f"future{i}" for i in range(len(routes)))
                lines.append(f"{px}CompletableFuture.allOf({futures}).join();")
                lines.append(f"{px}List<Object> scatterResults = List.of({', '.join(f'future{i}.join()' for i in range(len(routes)))});")

            # ── for-each ──────────────────────────────────────────
            elif tag in ("foreach", "for-each"):
                collection = attrs.get("collection", proc.get("collection", "#[payload]"))
                batch_size = attrs.get("batchSize", proc.get("batchSize", ""))
                java_coll = self.dw_converter.convert_inline_expression(collection)
                imports.add("java.util.List")
                if batch_size:
                    lines.append(f"{px}// Batch size: {batch_size}")
                lines.append(f"{px}for (Object item : (List<?>) {java_coll}) {{")
                cl, ci, cd = self._convert_processors(
                    proc.get("children", []), parsed_data, indent + 1)
                lines.extend(cl)
                imports.update(ci)
                service_deps.update(cd)
                lines.append(f"{px}}}")

            # ── parallel-for-each ─────────────────────────────────
            elif tag == "parallel-for-each":
                collection = attrs.get("collection", proc.get("collection", "#[payload]"))
                java_coll = self.dw_converter.convert_inline_expression(collection)
                imports.update(["java.util.List", "java.util.stream.Collectors",
                                "java.util.concurrent.CompletableFuture"])
                max_conc = attrs.get("maxConcurrency", proc.get("maxConcurrency", ""))
                if max_conc:
                    lines.append(f"{px}// Max concurrency: {max_conc}")
                lines.append(f"{px}List<CompletableFuture<Object>> parallelTasks = ((List<?>) {java_coll}).stream()")
                lines.append(f"{px}    .map(item -> CompletableFuture.supplyAsync(() -> {{")
                cl, ci, cd = self._convert_processors(
                    proc.get("children", []), parsed_data, indent + 2)
                lines.extend(cl)
                imports.update(ci)
                service_deps.update(cd)
                lines.append(f"{px}        return item;")
                lines.append(f"{px}    }}))")
                lines.append(f"{px}    .collect(Collectors.toList());")
                lines.append(f"{px}CompletableFuture.allOf(parallelTasks.toArray(new CompletableFuture[0])).join();")

            # ── try (try-catch) ───────────────────────────────────
            elif tag == "try":
                main_children = [c for c in proc.get("children", [])
                                 if c.get("tag") != "error-handler"]
                err_children  = [c for c in proc.get("children", [])
                                 if c.get("tag") == "error-handler"]
                lines.append(f"{px}try {{")
                cl, ci, cd = self._convert_processors(main_children, parsed_data, indent + 1)
                lines.extend(cl)
                imports.update(ci)
                service_deps.update(cd)

                if err_children:
                    for eh in err_children:
                        for handler in eh.get("children", []):
                            h_tag = handler.get("tag", "")
                            h_type = handler.get("attributes", {}).get("type", "ANY")
                            exc_class = self.connector_mapper.get_exception_class(h_type)
                            lines.append(f"{px}}} catch ({exc_class} e) {{")
                            lines.append(f'{px}    log.error("{h_type}: {{}}", e.getMessage(), e);')
                            cl2, ci2, cd2 = self._convert_processors(
                                handler.get("children", []), parsed_data, indent + 1)
                            lines.extend(cl2)
                            imports.update(ci2)
                            service_deps.update(cd2)
                else:
                    lines.append(f"{px}}} catch (Exception e) {{")
                    lines.append(f'{px}    log.error("Error: {{}}", e.getMessage(), e);')
                lines.append(f"{px}}}")

            # ── until-successful (@Retryable) ─────────────────────
            elif tag == "until-successful":
                max_retries = attrs.get("maxRetries", proc.get("maxRetries", "5"))
                millis = attrs.get("millisBetweenRetries",
                                   proc.get("millisBetweenRetries", "60000"))
                imports.add("org.springframework.retry.annotation.Retryable")
                imports.add("org.springframework.retry.annotation.Backoff")
                lines.append(f"{px}// until-successful: maxRetries={max_retries}, interval={millis}ms")
                lines.append(f"{px}// Migrated as @Retryable on a separate service method")
                lines.append(f"{px}// @Retryable(maxAttempts = {max_retries}, backoff = @Backoff(delay = {millis}))")
                cl, ci, cd = self._convert_processors(
                    proc.get("children", []), parsed_data, indent)
                lines.extend(cl)
                imports.update(ci)
                service_deps.update(cd)

            # ── first-successful (fallback chain) ─────────────────
            elif tag == "first-successful":
                lines.append(f"{px}// first-successful: try routes until one succeeds")
                lines.append(f"{px}Object firstSuccessResult = null;")
                routes = [c for c in proc.get("children", []) if c.get("tag") == "route"]
                for i, route in enumerate(routes):
                    lines.append(f"{px}if (firstSuccessResult == null) {{")
                    lines.append(f"{px}    try {{")
                    cl, ci, cd = self._convert_processors(
                        route.get("children", []), parsed_data, indent + 2)
                    lines.extend(cl)
                    imports.update(ci)
                    service_deps.update(cd)
                    lines.append(f"{px}        firstSuccessResult = payload;")
                    lines.append(f"{px}    }} catch (Exception e{i}) {{")
                    lines.append(f'{px}        log.warn("Route {i} failed: {{}}", e{i}.getMessage());')
                    lines.append(f"{px}    }}")
                    lines.append(f"{px}}}")

            # ── round-robin ───────────────────────────────────────
            elif tag == "round-robin":
                imports.add("java.util.concurrent.atomic.AtomicInteger")
                routes = [c for c in proc.get("children", []) if c.get("tag") == "route"]
                lines.append(f"{px}// round-robin: rotate between {len(routes)} routes")
                lines.append(f"{px}int routeIndex = roundRobinCounter.getAndIncrement() % {len(routes)};")
                lines.append(f"{px}switch (routeIndex) {{")
                for i, route in enumerate(routes):
                    lines.append(f"{px}    case {i}:")
                    cl, ci, cd = self._convert_processors(
                        route.get("children", []), parsed_data, indent + 2)
                    lines.extend(cl)
                    imports.update(ci)
                    service_deps.update(cd)
                    lines.append(f"{px}        break;")
                lines.append(f"{px}}}")

            # ── async ─────────────────────────────────────────────
            elif tag == "async":
                imports.add("java.util.concurrent.CompletableFuture")
                lines.append(f"{px}CompletableFuture.runAsync(() -> {{")
                cl, ci, cd = self._convert_processors(
                    proc.get("children", []), parsed_data, indent + 1)
                lines.extend(cl)
                imports.update(ci)
                service_deps.update(cd)
                lines.append(f"{px}}});")

            # ── flow-ref ──────────────────────────────────────────
            elif tag == "flow-ref":
                ref_name = attrs.get("name", "")
                method = self._to_method_name(ref_name)
                # Derive service class from prefix (same grouping as _generate_services)
                if ":" in ref_name:
                    svc_prefix = ref_name.split(":")[0]
                else:
                    _parts = re.split(r"[-_\s]", ref_name)
                    svc_prefix = _parts[0] if _parts else "Common"
                svc_name = self._to_class_name(svc_prefix) + "Service"
                svc_var  = self._to_variable_name(svc_name)
                service_deps.add((svc_name, svc_var))
                lines.append(f"{px}Object payload = {svc_var}.{method}();")

            # ── raise-error ───────────────────────────────────────
            elif tag == "raise-error":
                err_type = attrs.get("type", "APP:ERROR")
                desc = attrs.get("description", "An error occurred")
                desc = self._convert_dw_in_string(desc)
                exc_class = self.connector_mapper.get_exception_class(err_type)
                lines.append(f'{px}throw new {exc_class}("{desc}");')

            # ── parse-template ────────────────────────────────────
            elif tag == "parse-template":
                location = attrs.get("location", proc.get("location", ""))
                lines.append(f'{px}// parse-template: {location}')
                lines.append(f'{px}// Use Thymeleaf or FreeMarker to render template')
                lines.append(f'{px}String templateContent = new String(getClass().getResourceAsStream("/{location}").readAllBytes());')
                imports.add("java.io.IOException")

            # ── idempotent-message-validator ───────────────────────
            elif tag == "idempotent-message-validator":
                id_expr = attrs.get("idExpression", proc.get("idExpression", ""))
                lines.append(f"{px}// Idempotent check — use Redis or DB to track message IDs")
                lines.append(f'{px}String messageId = String.valueOf({self.dw_converter.convert_inline_expression(id_expr) if id_expr else "payload.hashCode()"});')
                lines.append(f'{px}if (idempotencyStore.containsKey(messageId)) {{')
                lines.append(f'{px}    log.info("Duplicate message detected: {{}}", messageId);')
                lines.append(f'{px}    return;')
                lines.append(f'{px}}}')
                lines.append(f'{px}idempotencyStore.put(messageId, true);')

            # ── HTTP request ──────────────────────────────────────
            elif tag == "request" and ns == "http":
                self._convert_http_request(proc, attrs, lines, imports, service_deps, px)

            # ── Database operations ───────────────────────────────
            elif tag == "select" and ns == "db":
                self._convert_db_select(proc, attrs, lines, imports, service_deps, px)
            elif tag == "insert" and ns == "db":
                self._convert_db_write(proc, attrs, lines, imports, service_deps, px, "insert")
            elif tag == "update" and ns == "db":
                self._convert_db_write(proc, attrs, lines, imports, service_deps, px, "update")
            elif tag == "delete" and ns == "db":
                self._convert_db_write(proc, attrs, lines, imports, service_deps, px, "delete")
            elif tag == "stored-procedure" and ns == "db":
                self._convert_db_stored_proc(proc, attrs, lines, imports, service_deps, px)
            elif tag == "bulk-insert" and ns == "db":
                self._convert_db_bulk_insert(proc, attrs, lines, imports, service_deps, px)

            # ── JMS publish / consume ─────────────────────────────
            elif tag == "publish" and ns == "jms":
                dest = attrs.get("destination", "")
                imports.add("org.springframework.jms.core.JmsTemplate")
                service_deps.add(("JmsTemplate", "jmsTemplate"))
                lines.append(f'{px}jmsTemplate.convertAndSend("{dest}", payload);')
            elif tag == "consume" and ns == "jms":
                dest = attrs.get("destination", "")
                imports.add("org.springframework.jms.core.JmsTemplate")
                service_deps.add(("JmsTemplate", "jmsTemplate"))
                lines.append(f'{px}Object message = jmsTemplate.receiveAndConvert("{dest}");')

            # ── AMQP publish / consume ────────────────────────────
            elif tag == "publish" and ns == "amqp":
                exchange = attrs.get("exchangeName", "")
                routing  = attrs.get("routingKey", "")
                imports.add("org.springframework.amqp.rabbit.core.RabbitTemplate")
                service_deps.add(("RabbitTemplate", "rabbitTemplate"))
                lines.append(f'{px}rabbitTemplate.convertAndSend("{exchange}", "{routing}", payload);')
            elif tag == "consume" and ns == "amqp":
                queue = attrs.get("queueName", "")
                imports.add("org.springframework.amqp.rabbit.core.RabbitTemplate")
                service_deps.add(("RabbitTemplate", "rabbitTemplate"))
                lines.append(f'{px}Object message = rabbitTemplate.receiveAndConvert("{queue}");')

            # ── Kafka publish / consume ───────────────────────────
            elif tag in ("publish", "publish-message") and ns == "kafka":
                topic = attrs.get("topic", "")
                imports.add("org.springframework.kafka.core.KafkaTemplate")
                service_deps.add(("KafkaTemplate<String, Object>", "kafkaTemplate"))
                lines.append(f'{px}kafkaTemplate.send("{topic}", payload);')
            elif tag in ("consume", "consumer") and ns == "kafka":
                topic = attrs.get("topic", "")
                lines.append(f'{px}// Kafka consume from "{topic}" — use @KafkaListener instead')

            # ── VM publish / consume ──────────────────────────────
            elif tag == "publish" and ns == "vm":
                queue = attrs.get("queueName", "")
                imports.add("org.springframework.context.ApplicationEventPublisher")
                service_deps.add(("ApplicationEventPublisher", "eventPublisher"))
                lines.append(f'{px}// VM publish to queue "{queue}" → Spring Event')
                lines.append(f'{px}eventPublisher.publishEvent(payload);')
            elif tag == "consume" and ns == "vm":
                queue = attrs.get("queueName", "")
                lines.append(f'{px}// VM consume from "{queue}" → use @EventListener')

            # ── File operations ───────────────────────────────────
            elif ns == "file" and tag in ("read", "write", "list", "delete", "move", "copy", "rename"):
                self._convert_file_op(tag, attrs, lines, imports, px)
            elif ns == "sftp" and tag in ("read", "write", "list", "delete", "move", "copy"):
                self._convert_sftp_op(tag, attrs, lines, imports, service_deps, px)
            elif ns == "ftp" and tag in ("read", "write", "list", "delete", "move", "copy"):
                self._convert_ftp_op(tag, attrs, lines, imports, px)

            # ── Email send ────────────────────────────────────────
            elif ns == "email" and tag in ("send", "send-email"):
                self._convert_email_send(attrs, lines, imports, service_deps, px)

            # ── Object Store ──────────────────────────────────────
            elif ns == "os" and tag in ("store", "retrieve", "remove", "contains"):
                self._convert_objectstore_op(tag, attrs, lines, imports, service_deps, px)

            # ── Web Service Consumer (SOAP) ───────────────────────
            elif ns in ("wsc", "ws") and tag == "consume":
                self._convert_soap_consume(attrs, lines, imports, service_deps, px)

            # ── Salesforce operations ─────────────────────────────
            elif ns == "salesforce":
                self._convert_salesforce_op(tag, attrs, lines, imports, service_deps, px)

            # ── AWS S3 operations ─────────────────────────────────
            elif ns == "s3":
                self._convert_s3_op(tag, attrs, lines, imports, service_deps, px)

            # ── AWS SQS operations ────────────────────────────────
            elif ns == "sqs":
                self._convert_sqs_op(tag, attrs, lines, imports, service_deps, px)

            # ── Validation ────────────────────────────────────────
            elif ns == "validation":
                self._convert_validation(tag, attrs, lines, imports, px)

            # ── Cache scope ───────────────────────────────────────
            elif tag in ("cache", "cached"):
                lines.append(f"{px}// Cache scope → use @Cacheable on service method")
                cl, ci, cd = self._convert_processors(
                    proc.get("children", []), parsed_data, indent)
                lines.extend(cl)
                imports.update(ci)
                service_deps.update(cd)

            # ── JSON transformers ─────────────────────────────────
            elif tag in ("object-to-json-transformer", "object-to-json"):
                imports.add("com.fasterxml.jackson.databind.ObjectMapper")
                lines.append(f"{px}ObjectMapper mapper = new ObjectMapper();")
                lines.append(f"{px}String jsonPayload = mapper.writeValueAsString(payload);")

            elif tag in ("json-to-object-transformer", "json-to-object"):
                imports.update(["com.fasterxml.jackson.databind.ObjectMapper",
                                "com.fasterxml.jackson.core.type.TypeReference"])
                lines.append(f"{px}ObjectMapper mapper = new ObjectMapper();")
                lines.append(f"{px}Map<String, Object> payload = mapper.readValue(")
                lines.append(f"{px}    jsonPayload, new TypeReference<Map<String, Object>>() {{}});")

            elif tag == "object-to-string-transformer":
                lines.append(f"{px}String payload = String.valueOf(payload);")

            # ── Unknown processor — attempt smart conversion ─────
            else:
                ai_code = self._handle_unknown_processor(
                    ns, tag, proc, px)
                lines.append(ai_code)

        return lines, imports, service_deps

    def _handle_unknown_processor(self, ns, tag, proc, px):
        """Attempt smart conversion for an unrecognised processor; fall back to TODO."""
        element_label = f"{ns}:{tag}" if ns else tag
        attrs = proc.get("attributes", {})
        todo = f"{px}// TODO: Migrate {element_label} — attrs={attrs}"

        if not self._agent_ctx:
            self.warnings.append(
                f"Unmigrated processor: {element_label}. "
                f"Enable LLM-assisted conversion for auto-migration.")
            return todo

        from .llm_agent import convert_unknown_element

        # Build minimal XML representation for the converter
        xml_repr = f"<{element_label}"
        for k, v in attrs.items():
            xml_repr += f' {k}="{v}"'
        xml_repr += "/>"

        converted = convert_unknown_element(
            self._agent_ctx, element_label, xml_repr)
        if converted:
            indented = "\n".join(
                f"{px}{line}" for line in converted.split("\n"))
            return f"{px}// Converted from {element_label}\n{indented}"

        self.warnings.append(f"Unmigrated processor: {element_label}")
        return todo

    # ══════════════════════════════════════════════════════════════════════
    #  SPECIFIC PROCESSOR CONVERTERS
    # ══════════════════════════════════════════════════════════════════════

    # ── Choice (if/else router) ───────────────────────────────────────────
    def _convert_choice(self, choice_proc, parsed_data, indent):
        lines = []
        imports = set()
        service_deps = set()
        px = "    " * indent
        first = True

        for child in choice_proc.get("children", []):
            tag = child.get("tag", "")
            if tag == "when":
                expression = child.get("attributes", {}).get("expression", "")
                java_expr = self.dw_converter.convert_inline_expression(expression)
                keyword = "if" if first else "} else if"
                lines.append(f"{px}{keyword} ({java_expr}) {{")
                first = False
                cl, ci, cd = self._convert_processors(
                    child.get("children", []), parsed_data, indent + 1)
                lines.extend(cl)
                imports.update(ci)
                service_deps.update(cd)
            elif tag == "otherwise":
                lines.append(f"{px}}} else {{")
                cl, ci, cd = self._convert_processors(
                    child.get("children", []), parsed_data, indent + 1)
                lines.extend(cl)
                imports.update(ci)
                service_deps.update(cd)

        if not first:
            lines.append(f"{px}}}")

        return lines, imports

    # ── HTTP Request ──────────────────────────────────────────────────────
    def _convert_http_request(self, proc, attrs, lines, imports, deps, px):
        method = attrs.get("method", "GET")
        path   = attrs.get("path", "/")
        cfg    = attrs.get("config-ref", "")
        # Use config-ref to build a bean name for the WebClient
        bean_name = self._to_variable_name(cfg) + "WebClient" if cfg else "webClient"
        imports.update(["org.springframework.web.reactive.function.client.WebClient",
                        "org.springframework.http.HttpMethod"])
        deps.add(("WebClient", bean_name))
        lines.append(f'{px}// HTTP Request → {method} {path} (config: {cfg})')
        lines.append(f'{px}String response = {bean_name}')
        lines.append(f'{px}    .method(HttpMethod.{method})')
        lines.append(f'{px}    .uri("{path}")')
        lines.append(f'{px}    .retrieve()')
        lines.append(f'{px}    .bodyToMono(String.class)')
        lines.append(f'{px}    .block();')
        lines.append(f'{px}payload = response;')

    # ── Database Select ───────────────────────────────────────────────────
    def _db_bean_name(self, attrs):
        """Derive JdbcTemplate bean name from config-ref for multi-datasource support."""
        cfg = attrs.get("config-ref", "")
        if cfg:
            return self._to_variable_name(cfg) + "JdbcTemplate"
        return "jdbcTemplate"

    def _convert_db_select(self, proc, attrs, lines, imports, deps, px):
        sql = self._extract_sql(proc)
        imports.add("org.springframework.jdbc.core.JdbcTemplate")
        imports.add("java.util.List")
        imports.add("java.util.Map")
        jdbc_bean = self._db_bean_name(attrs)
        deps.add(("JdbcTemplate", jdbc_bean))
        params = self._extract_db_params(proc)
        # Escape multiline SQL into a single Java string
        sql_escaped = sql.strip().replace("\n", " ").replace("  ", " ")
        lines.append(f'{px}List<Map<String, Object>> queryResult = {jdbc_bean}.queryForList(')
        if params:
            lines.append(f'{px}    "{sql_escaped}",')
            lines.append(f'{px}    {params}')
        else:
            lines.append(f'{px}    "{sql_escaped}"')
        lines.append(f'{px});')
        lines.append(f'{px}payload = queryResult;')

    # ── Database Write (insert/update/delete) ─────────────────────────────
    def _convert_db_write(self, proc, attrs, lines, imports, deps, px, op):
        sql = self._extract_sql(proc)
        imports.add("org.springframework.jdbc.core.JdbcTemplate")
        jdbc_bean = self._db_bean_name(attrs)
        deps.add(("JdbcTemplate", jdbc_bean))
        params = self._extract_db_params(proc)
        # Escape multiline SQL into a single Java string
        sql_escaped = sql.strip().replace("\n", " ").replace("  ", " ")
        lines.append(f'{px}int rowsAffected = {jdbc_bean}.update(')
        if params:
            lines.append(f'{px}    "{sql_escaped}",')
            lines.append(f'{px}    {params}')
        else:
            lines.append(f'{px}    "{sql_escaped}"')
        lines.append(f'{px});')
        lines.append(f'{px}log.info("{op}: {{}} rows affected", rowsAffected);')
        lines.append(f'{px}payload = Map.of("rowsAffected", rowsAffected);')

    # ── Database Stored Procedure ─────────────────────────────────────────
    def _convert_db_stored_proc(self, proc, attrs, lines, imports, deps, px):
        imports.update(["org.springframework.jdbc.core.JdbcTemplate",
                        "org.springframework.jdbc.core.simple.SimpleJdbcCall"])
        jdbc_bean = self._db_bean_name(attrs)
        deps.add(("JdbcTemplate", jdbc_bean))
        proc_name = attrs.get("storedProcedureName", self._extract_sql(proc))
        lines.append(f'{px}SimpleJdbcCall jdbcCall = new SimpleJdbcCall({jdbc_bean})')
        lines.append(f'{px}    .withProcedureName("{proc_name}");')
        lines.append(f'{px}Map<String, Object> result = jdbcCall.execute();')

    # ── Database Bulk Insert ──────────────────────────────────────────────
    def _convert_db_bulk_insert(self, proc, attrs, lines, imports, deps, px):
        sql = self._extract_sql(proc)
        imports.update(["org.springframework.jdbc.core.JdbcTemplate",
                        "java.util.List", "java.util.Map"])
        jdbc_bean = self._db_bean_name(attrs)
        deps.add(("JdbcTemplate", jdbc_bean))
        lines.append(f'{px}// Bulk insert')
        lines.append(f'{px}List<Object[]> batchArgs = new java.util.ArrayList<>();')
        lines.append(f'{px}for (Object item : (List<?>) payload) {{')
        lines.append(f'{px}    batchArgs.add(new Object[]{{item}});')
        lines.append(f'{px}}}')
        lines.append(f'{px}int[] results = {jdbc_bean}.batchUpdate("{sql}", batchArgs);')

    # ── File operations ───────────────────────────────────────────────────
    def _convert_file_op(self, tag, attrs, lines, imports, px):
        imports.update(["java.nio.file.Files", "java.nio.file.Paths", "java.nio.file.Path"])
        path = attrs.get("path", "")
        if tag == "read":
            lines.append(f'{px}String fileContent = Files.readString(Paths.get("{path}"));')
            lines.append(f'{px}Object payload = fileContent;')
        elif tag == "write":
            lines.append(f'{px}Files.writeString(Paths.get("{path}"), String.valueOf(payload));')
        elif tag == "list":
            directory = attrs.get("directoryPath", path)
            lines.append(f'{px}List<Path> fileList = Files.list(Paths.get("{directory}")).collect(Collectors.toList());')
            imports.add("java.util.stream.Collectors")
        elif tag == "delete":
            lines.append(f'{px}Files.deleteIfExists(Paths.get("{path}"));')
        elif tag == "move":
            target = attrs.get("renameTo", attrs.get("targetPath", ""))
            lines.append(f'{px}Files.move(Paths.get("{path}"), Paths.get("{target}"));')
        elif tag == "copy":
            target = attrs.get("targetPath", "")
            lines.append(f'{px}Files.copy(Paths.get("{path}"), Paths.get("{target}"));')
        elif tag == "rename":
            new_name = attrs.get("to", "")
            lines.append(f'{px}Files.move(Paths.get("{path}"), Paths.get("{path}").resolveSibling("{new_name}"));')

    # ── SFTP operations ───────────────────────────────────────────────────
    def _convert_sftp_op(self, tag, attrs, lines, imports, deps, px):
        imports.add("org.springframework.integration.sftp.session.SftpRemoteFileTemplate")
        deps.add(("SftpRemoteFileTemplate", "sftpTemplate"))
        path = attrs.get("path", "")
        if tag == "read":
            lines.append(f'{px}// SFTP read')
            lines.append(f'{px}byte[] content = sftpTemplate.get("{path}", stream -> stream.readAllBytes());')
            lines.append(f'{px}Object payload = new String(content);')
        elif tag == "write":
            lines.append(f'{px}sftpTemplate.send(new ByteArrayInputStream(payload.toString().getBytes()), "{path}");')
            imports.add("java.io.ByteArrayInputStream")
        elif tag == "list":
            directory = attrs.get("directoryPath", path)
            lines.append(f'{px}String[] fileNames = sftpTemplate.list("{directory}");')
        elif tag == "delete":
            lines.append(f'{px}sftpTemplate.remove("{path}");')
        elif tag == "move":
            target = attrs.get("renameTo", attrs.get("targetPath", ""))
            lines.append(f'{px}sftpTemplate.rename("{path}", "{target}");')

    # ── FTP operations ────────────────────────────────────────────────────
    def _convert_ftp_op(self, tag, attrs, lines, imports, px):
        imports.add("org.springframework.integration.ftp.session.FtpRemoteFileTemplate")
        path = attrs.get("path", "")
        lines.append(f'{px}// FTP {tag}: {path}')
        lines.append(f'{px}// Use FtpRemoteFileTemplate for FTP operations')

    # ── Email send ────────────────────────────────────────────────────────
    def _convert_email_send(self, attrs, lines, imports, deps, px):
        imports.update(["org.springframework.mail.javamail.JavaMailSender",
                        "org.springframework.mail.SimpleMailMessage"])
        deps.add(("JavaMailSender", "mailSender"))
        to_addr = attrs.get("toAddresses", attrs.get("to", ""))
        subject = attrs.get("subject", "")
        lines.append(f'{px}SimpleMailMessage email = new SimpleMailMessage();')
        lines.append(f'{px}email.setTo("{to_addr}");')
        lines.append(f'{px}email.setSubject("{subject}");')
        lines.append(f'{px}email.setText(String.valueOf(payload));')
        lines.append(f'{px}mailSender.send(email);')

    # ── Object Store ──────────────────────────────────────────────────────
    def _convert_objectstore_op(self, tag, attrs, lines, imports, deps, px):
        imports.add("org.springframework.data.redis.core.RedisTemplate")
        deps.add(("RedisTemplate<String, Object>", "redisTemplate"))
        key = attrs.get("key", "")
        key_java = self.dw_converter.convert_inline_expression(key) if key.startswith("#[") else f'"{key}"'
        if tag == "store":
            lines.append(f'{px}redisTemplate.opsForValue().set({key_java}, payload);')
        elif tag == "retrieve":
            lines.append(f'{px}Object storedValue = redisTemplate.opsForValue().get({key_java});')
        elif tag == "remove":
            lines.append(f'{px}redisTemplate.delete({key_java});')
        elif tag == "contains":
            lines.append(f'{px}boolean exists = Boolean.TRUE.equals(redisTemplate.hasKey({key_java}));')

    # ── SOAP Web Service Consumer ─────────────────────────────────────────
    def _convert_soap_consume(self, attrs, lines, imports, deps, px):
        operation = attrs.get("operation", "")
        imports.add("org.springframework.ws.client.core.WebServiceTemplate")
        deps.add(("WebServiceTemplate", "webServiceTemplate"))
        lines.append(f'{px}// SOAP call: operation="{operation}"')
        lines.append(f'{px}Object soapResponse = webServiceTemplate.marshalSendAndReceive(payload);')

    # ── Salesforce ────────────────────────────────────────────────────────
    def _convert_salesforce_op(self, tag, attrs, lines, imports, deps, px):
        imports.add("org.springframework.web.reactive.function.client.WebClient")
        deps.add(("WebClient", "salesforceClient"))
        obj_type = attrs.get("type", attrs.get("objectType", ""))
        if tag == "query":
            query = attrs.get("query", "")
            lines.append(f'{px}// Salesforce SOQL query')
            lines.append(f'{px}String sfResponse = salesforceClient.get()')
            lines.append(f'{px}    .uri("/services/data/v58.0/query?q=" + java.net.URLEncoder.encode("{query}", "UTF-8"))')
            lines.append(f'{px}    .retrieve().bodyToMono(String.class).block();')
            lines.append(f'{px}Object payload = sfResponse;')
        elif tag == "create":
            lines.append(f'{px}// Salesforce create {obj_type}')
            lines.append(f'{px}String sfResponse = salesforceClient.post()')
            lines.append(f'{px}    .uri("/services/data/v58.0/sobjects/{obj_type}")')
            lines.append(f'{px}    .bodyValue(payload)')
            lines.append(f'{px}    .retrieve().bodyToMono(String.class).block();')
        elif tag in ("update", "upsert"):
            lines.append(f'{px}// Salesforce {tag} {obj_type}')
            lines.append(f'{px}salesforceClient.patch()')
            lines.append(f'{px}    .uri("/services/data/v58.0/sobjects/{obj_type}/{{id}}")')
            lines.append(f'{px}    .bodyValue(payload)')
            lines.append(f'{px}    .retrieve().bodyToMono(String.class).block();')
        elif tag == "delete":
            lines.append(f'{px}// Salesforce delete {obj_type}')
            lines.append(f'{px}salesforceClient.delete()')
            lines.append(f'{px}    .uri("/services/data/v58.0/sobjects/{obj_type}/{{id}}")')
            lines.append(f'{px}    .retrieve().bodyToMono(Void.class).block();')
        else:
            ai_code = self._handle_unknown_processor(
                "salesforce", tag, {"attributes": attrs}, px)
            lines.append(ai_code)

    # ── AWS S3 ────────────────────────────────────────────────────────────
    def _convert_s3_op(self, tag, attrs, lines, imports, deps, px):
        imports.add("software.amazon.awssdk.services.s3.S3Client")
        deps.add(("S3Client", "s3Client"))
        bucket = attrs.get("bucketName", "")
        key = attrs.get("key", attrs.get("objectKey", ""))
        if tag in ("put-object", "putObject"):
            lines.append(f'{px}s3Client.putObject(b -> b.bucket("{bucket}").key("{key}"),')
            lines.append(f'{px}    software.amazon.awssdk.core.sync.RequestBody.fromString(String.valueOf(payload)));')
        elif tag in ("get-object", "getObject"):
            lines.append(f'{px}var s3Response = s3Client.getObjectAsBytes(b -> b.bucket("{bucket}").key("{key}"));')
            lines.append(f'{px}Object payload = s3Response.asUtf8String();')
        elif tag in ("delete-object", "deleteObject"):
            lines.append(f'{px}s3Client.deleteObject(b -> b.bucket("{bucket}").key("{key}"));')
        elif tag in ("list-objects", "listObjects"):
            lines.append(f'{px}var objects = s3Client.listObjects(b -> b.bucket("{bucket}"));')
        else:
            ai_code = self._handle_unknown_processor(
                "s3", tag, {"attributes": attrs}, px)
            lines.append(ai_code)

    # ── AWS SQS ───────────────────────────────────────────────────────────
    def _convert_sqs_op(self, tag, attrs, lines, imports, deps, px):
        imports.add("software.amazon.awssdk.services.sqs.SqsClient")
        deps.add(("SqsClient", "sqsClient"))
        queue_url = attrs.get("queueUrl", "")
        if tag in ("send-message", "sendMessage"):
            lines.append(f'{px}sqsClient.sendMessage(b -> b.queueUrl("{queue_url}").messageBody(String.valueOf(payload)));')
        elif tag in ("receive-messages", "receiveMessages"):
            lines.append(f'{px}var messages = sqsClient.receiveMessage(b -> b.queueUrl("{queue_url}").maxNumberOfMessages(10));')
        elif tag in ("delete-message", "deleteMessage"):
            receipt = attrs.get("receiptHandle", "")
            lines.append(f'{px}sqsClient.deleteMessage(b -> b.queueUrl("{queue_url}").receiptHandle("{receipt}"));')
        else:
            ai_code = self._handle_unknown_processor(
                "sqs", tag, {"attributes": attrs}, px)
            lines.append(ai_code)

    # ── Validation ────────────────────────────────────────────────────────
    def _convert_validation(self, tag, attrs, lines, imports, px):
        value = attrs.get("value", attrs.get("expression", ""))
        java_val = self.dw_converter.convert_inline_expression(value) if value else "payload"
        msg = attrs.get("message", f"Validation failed: {tag}")

        if tag in ("is-not-null", "isNotNull"):
            lines.append(f'{px}if ({java_val} == null) throw new IllegalArgumentException("{msg}");')
        elif tag in ("is-not-empty", "isNotEmpty"):
            lines.append(f'{px}if ({java_val} == null || String.valueOf({java_val}).isEmpty()) throw new IllegalArgumentException("{msg}");')
        elif tag in ("is-email", "isEmail"):
            lines.append(f'{px}if (!String.valueOf({java_val}).matches("^[A-Za-z0-9+_.-]+@(.+)$")) throw new IllegalArgumentException("{msg}");')
        elif tag in ("is-url", "isUrl"):
            lines.append(f'{px}try {{ new java.net.URL(String.valueOf({java_val})); }} catch (Exception e) {{ throw new IllegalArgumentException("{msg}"); }}')
        elif tag in ("matches-regex", "matchesRegex"):
            regex = attrs.get("regex", ".*")
            lines.append(f'{px}if (!String.valueOf({java_val}).matches("{regex}")) throw new IllegalArgumentException("{msg}");')
        elif tag in ("is-true", "isTrue"):
            lines.append(f'{px}if (!Boolean.parseBoolean(String.valueOf({java_val}))) throw new IllegalArgumentException("{msg}");')
        elif tag in ("is-false", "isFalse"):
            lines.append(f'{px}if (Boolean.parseBoolean(String.valueOf({java_val}))) throw new IllegalArgumentException("{msg}");')
        elif tag in ("validate-size", "validateSize"):
            min_val = attrs.get("min", "0")
            max_val = attrs.get("max", "2147483647")
            lines.append(f'{px}int size = String.valueOf({java_val}).length();')
            lines.append(f'{px}if (size < {min_val} || size > {max_val}) throw new IllegalArgumentException("{msg}");')
        else:
            ai_code = self._handle_unknown_processor(
                "validation", tag, {"attributes": attrs}, px)
            lines.append(ai_code)

    # ══════════════════════════════════════════════════════════════════════
    #  LISTENER / CONTROLLER GENERATORS
    # ══════════════════════════════════════════════════════════════════════

    def _group_flows_by_config(self, flows):
        groups = {}
        for flow in flows:
            cfg = flow["source"].get("config_ref", "default")
            groups.setdefault(cfg, []).append(flow)
        return groups

    # ── REST Controller ───────────────────────────────────────────────────
    def _generate_controller(self, class_name, flows, parsed_data):
        imports = {"org.springframework.web.bind.annotation.*",
                   "org.springframework.http.ResponseEntity",
                   "org.springframework.http.HttpStatus",
                   "lombok.extern.slf4j.Slf4j",
                   "lombok.RequiredArgsConstructor",
                   "java.util.*"}
        methods = []
        service_deps = set()

        for flow in flows:
            source = flow["source"]
            path   = source.get("path", "/")
            method = source.get("method", "GET")
            method_name = self._to_method_name(flow["name"])
            annotation = self.connector_mapper.get_http_annotation(method)
            path_vars = re.findall(r"\{(\w+)\}", path)
            params = self._build_method_params(flow, path_vars)
            body_lines, extra_imports, deps = self._convert_processors(
                flow["processors"], parsed_data)
            imports.update(extra_imports)
            service_deps.update(deps)
            methods.append(self._format_method(annotation, path, method_name, params, body_lines, flow))

        base_path = ""
        if flows:
            cfg_ref = flows[0]["source"].get("config_ref", "")
            for cfg in parsed_data.get("global_configs", []):
                if cfg.get("name") == cfg_ref and cfg.get("type") == "http-listener":
                    base_path = cfg.get("basePath", "")

        return self._format_controller_class(class_name, base_path, imports, service_deps, methods)

    # ── APIkit Router → REST Controller ────────────────────────────────────
    _APIKIT_NAME_PATTERN = re.compile(
        r'^(get|post|put|patch|delete|head|options):'  # HTTP method
        r'\\(.+?)'                                     # path
        r'(?::application\\[a-z]+)?'                   # optional content-type
        r':(.+)$'                                      # router config
    )

    @staticmethod
    def _apikit_path_to_spring(raw_path: str) -> str:
        """Convert APIkit path ``\\policies\\(policyId)`` → ``/policies/{policyId}``."""
        path = raw_path.replace("\\", "/")
        path = re.sub(r"\((\w+)\)", r"{\1}", path)
        if not path.startswith("/"):
            path = "/" + path
        return path

    def _generate_apikit_controller(self, apikit_flows, http_flows, parsed_data):
        """Generate a proper REST controller from APIkit-routed flows.

        Each APIkit flow name encodes its HTTP method and path:
            ``get:\\policies\\(policyId):insurance-api-router``
        This method parses those names and generates individual @GetMapping,
        @PostMapping, etc. endpoints in a single controller class.
        """
        files = {}
        imports = {
            "org.springframework.web.bind.annotation.*",
            "org.springframework.http.ResponseEntity",
            "org.springframework.http.HttpStatus",
            "lombok.extern.slf4j.Slf4j",
            "lombok.RequiredArgsConstructor",
            "java.util.*",
        }
        methods = []
        service_deps = set()

        # Find the base path from the main flow's HTTP listener (e.g. /api/v1)
        base_path = ""
        for flow in http_flows:
            for proc in flow.get("processors", []):
                if proc.get("type") in ("apikit:router", "apikit-router"):
                    source = flow.get("source") or {}
                    raw_bp = source.get("path", "")
                    # Strip wildcard suffix like /api/v1/* → /api/v1
                    base_path = re.sub(r"/?\*$", "", raw_bp)
                    break
            if base_path:
                break

        # Also try to extract base path from HTTP listener config
        if not base_path:
            for flow in http_flows:
                source = flow.get("source") or {}
                cfg_ref = source.get("config_ref", "")
                for cfg in parsed_data.get("global_configs", []):
                    if cfg.get("name") == cfg_ref and cfg.get("type") == "http-listener":
                        bp = cfg.get("basePath", "")
                        if bp:
                            base_path = bp
                            break
                if base_path:
                    break

        # Determine controller class name from router config
        router_config = ""
        for flow in apikit_flows:
            m = self._APIKIT_NAME_PATTERN.match(flow.get("name", ""))
            if m:
                router_config = m.group(3)
                break
        class_name = self._to_class_name(router_config or "api") + "Controller"
        tag_name = self._to_class_name(router_config or "api")

        for flow in apikit_flows:
            m = self._APIKIT_NAME_PATTERN.match(flow.get("name", ""))
            if not m:
                continue
            http_method = m.group(1).upper()    # GET, POST, PUT, etc.
            raw_path = m.group(2)               # \policies\(policyId)
            spring_path = self._apikit_path_to_spring(raw_path)

            # Build annotation
            annotation = self.connector_mapper.get_http_annotation(http_method)

            # Extract path variables from spring_path
            path_vars = re.findall(r"\{(\w+)\}", spring_path)

            # Build method name from path + method
            clean = re.sub(r"[^a-zA-Z0-9]", " ", raw_path).split()
            method_name = http_method.lower() + "".join(w.capitalize() for w in clean)

            # Build params: path vars + request body for POST/PUT/PATCH
            params = []
            for var in path_vars:
                params.append(f'@PathVariable String {var}')
            if http_method in ("POST", "PUT", "PATCH"):
                params.append("@RequestBody Map<String, Object> requestBody")
            params_str = ", ".join(params)

            # Convert processors (the actual flow body)
            body_lines, extra_imports, deps = self._convert_processors(
                flow["processors"], parsed_data)
            imports.update(extra_imports)
            service_deps.update(deps)

            # Build payload init
            if http_method in ("POST", "PUT", "PATCH"):
                payload_init = "        Object payload = requestBody;"
            else:
                payload_init = "        Object payload = null;"

            # Build the method
            body = "\n".join(body_lines)
            escaped_name = flow["name"].replace("\\", "\\\\")
            method_code = (
                f'    @{annotation}("{spring_path}")\n'
                f'    public ResponseEntity<?> {method_name}({params_str}) {{\n'
                f'        log.info("Handling request: {escaped_name}");\n'
                f'{payload_init}\n'
                f'{body}\n'
                f'        return ResponseEntity.ok(payload);\n'
                f'    }}'
            )
            methods.append(method_code)

        # Format the controller class
        dep_fields = self._format_service_deps(service_deps)
        imports.add("lombok.extern.slf4j.Slf4j")
        imports.add("lombok.RequiredArgsConstructor")
        import_lines = "\n".join(f"import {i};" for i in sorted(imports))
        bp_anno = f'@RequestMapping("{base_path}")\n' if base_path else ""
        tag_anno = f'@Tag(name = "{tag_name}", description = "{tag_name} operations")\n'

        # Add Swagger annotations
        imports.add("io.swagger.v3.oas.annotations.tags.Tag")
        import_lines = "\n".join(f"import {i};" for i in sorted(imports))

        controller_code = (
            f"package com.example.controller;\n\n"
            f"{import_lines}\n\n"
            f"@Slf4j\n@RequiredArgsConstructor\n"
            f"{tag_anno}"
            f"@RestController\n{bp_anno}"
            f"public class {class_name} {{\n\n"
            f"{dep_fields}\n\n"
            + "\n\n".join(methods) + "\n"
            f"}}\n"
        )

        files[f"controller/{class_name}.java"] = controller_code
        return files

    # ── Scheduler ─────────────────────────────────────────────────────────
    def _generate_scheduler(self, flows, parsed_data):
        imports = {"org.springframework.scheduling.annotation.Scheduled",
                   "org.springframework.stereotype.Component",
                   }
        methods = []
        service_deps = set()

        for flow in flows:
            mn = self._to_method_name(flow["name"])
            body_lines, ei, deps = self._convert_processors(flow["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            sched_anno = self._extract_schedule_annotation(flow)
            methods.append(
                f'    {sched_anno}\n'
                f'    public void {mn}() {{\n'
                f'        log.info("Running scheduled task: {flow["name"]}");\n'
                + "\n".join(body_lines) + "\n"
                f'    }}'
            )

        return self._format_component_class("ScheduledTasks", "com.example.scheduler",
                                            imports, service_deps, methods)

    # ── JMS Listener ──────────────────────────────────────────────────────
    def _generate_jms_listener(self, flows, parsed_data):
        imports = {"org.springframework.jms.annotation.JmsListener",
                   "org.springframework.stereotype.Component",
                   }
        methods = []
        service_deps = set()
        for flow in flows:
            mn = self._to_method_name(flow["name"])
            dest = flow.get("source", {}).get("destination", "default-queue")
            body_lines, ei, deps = self._convert_processors(flow["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            methods.append(
                f'    @JmsListener(destination = "{dest}")\n'
                f'    public void {mn}(String message) {{\n'
                f'        log.info("Received JMS message from {dest}");\n'
                f'        Object payload = message;\n'
                + "\n".join(body_lines) + "\n"
                f'    }}'
            )
        return self._format_component_class("JmsMessageListener", "com.example.listener",
                                            imports, service_deps, methods)

    # ── AMQP Listener ─────────────────────────────────────────────────────
    def _generate_amqp_listener(self, flows, parsed_data):
        imports = {"org.springframework.amqp.rabbit.annotation.RabbitListener",
                   "org.springframework.stereotype.Component",
                   }
        methods = []
        service_deps = set()
        for flow in flows:
            mn = self._to_method_name(flow["name"])
            queue = flow.get("source", {}).get("queueName", "default-queue")
            body_lines, ei, deps = self._convert_processors(flow["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            methods.append(
                f'    @RabbitListener(queues = "{queue}")\n'
                f'    public void {mn}(String message) {{\n'
                f'        log.info("Received AMQP message from {queue}");\n'
                f'        Object payload = message;\n'
                + "\n".join(body_lines) + "\n"
                f'    }}'
            )
        return self._format_component_class("AmqpMessageListener", "com.example.listener",
                                            imports, service_deps, methods)

    # ── Kafka Listener ────────────────────────────────────────────────────
    def _generate_kafka_listener(self, flows, parsed_data):
        imports = {"org.springframework.kafka.annotation.KafkaListener",
                   "org.springframework.stereotype.Component",
                   }
        methods = []
        service_deps = set()
        for flow in flows:
            mn = self._to_method_name(flow["name"])
            topic = flow.get("source", {}).get("topic", "default-topic")
            body_lines, ei, deps = self._convert_processors(flow["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            methods.append(
                f'    @KafkaListener(topics = "{topic}")\n'
                f'    public void {mn}(String message) {{\n'
                f'        log.info("Received Kafka message from {topic}");\n'
                f'        Object payload = message;\n'
                + "\n".join(body_lines) + "\n"
                f'    }}'
            )
        return self._format_component_class("KafkaMessageListener", "com.example.listener",
                                            imports, service_deps, methods)

    # ── VM Listener (Spring Event) ────────────────────────────────────────
    def _generate_vm_listener(self, flows, parsed_data):
        imports = {"org.springframework.context.event.EventListener",
                   "org.springframework.stereotype.Component",
                   }
        methods = []
        service_deps = set()
        for flow in flows:
            mn = self._to_method_name(flow["name"])
            queue = flow.get("source", {}).get("queueName", "")
            body_lines, ei, deps = self._convert_processors(flow["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            methods.append(
                f'    @EventListener\n'
                f'    public void {mn}(Object event) {{\n'
                f'        log.info("Received VM event (queue: {queue})");\n'
                f'        Object payload = event;\n'
                + "\n".join(body_lines) + "\n"
                f'    }}'
            )
        return self._format_component_class("VmEventListener", "com.example.listener",
                                            imports, service_deps, methods)

    # ── File Watcher ──────────────────────────────────────────────────────
    def _generate_file_watcher(self, flows, parsed_data):
        imports = {"org.springframework.scheduling.annotation.Scheduled",
                   "org.springframework.stereotype.Component",
                   
                   "java.nio.file.*", "java.io.IOException"}
        methods = []
        service_deps = set()
        for flow in flows:
            mn = self._to_method_name(flow["name"])
            directory = flow.get("source", {}).get("directory", "/tmp")
            body_lines, ei, deps = self._convert_processors(flow["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            methods.append(
                f'    @Scheduled(fixedDelay = 10000)\n'
                f'    public void {mn}() throws IOException {{\n'
                f'        log.info("Watching directory: {directory}");\n'
                f'        Files.list(Paths.get("{directory}")).forEach(file -> {{\n'
                f'            Object payload = file;\n'
                + "\n".join(body_lines) + "\n"
                f'        }});\n'
                f'    }}'
            )
        return self._format_component_class("FileWatcherService", "com.example.listener",
                                            imports, service_deps, methods)

    # ── Email Listener ────────────────────────────────────────────────────
    def _generate_email_listener(self, flows, parsed_data):
        imports = {"org.springframework.scheduling.annotation.Scheduled",
                   "org.springframework.stereotype.Component",
                   }
        methods = []
        service_deps = set()
        for flow in flows:
            mn = self._to_method_name(flow["name"])
            body_lines, ei, deps = self._convert_processors(flow["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            methods.append(
                f'    @Scheduled(fixedDelay = 60000)\n'
                f'    public void {mn}() {{\n'
                f'        log.info("Checking for new emails...");\n'
                f'        // Use JavaMail to fetch new emails\n'
                + "\n".join(body_lines) + "\n"
                f'    }}'
            )
        return self._format_component_class("EmailListener", "com.example.listener",
                                            imports, service_deps, methods)

    # ── Salesforce Event Listener ─────────────────────────────────────────
    def _generate_salesforce_listener(self, flows, parsed_data):
        imports = {"org.springframework.scheduling.annotation.Scheduled",
                   "org.springframework.stereotype.Component",
                   }
        methods = []
        service_deps = set()
        for flow in flows:
            mn = self._to_method_name(flow["name"])
            body_lines, ei, deps = self._convert_processors(flow["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            methods.append(
                f'    @Scheduled(fixedDelay = 30000)\n'
                f'    public void {mn}() {{\n'
                f'        log.info("Polling Salesforce events...");\n'
                + "\n".join(body_lines) + "\n"
                f'    }}'
            )
        return self._format_component_class("SalesforceEventListener", "com.example.listener",
                                            imports, service_deps, methods)

    # ── SQS Listener ──────────────────────────────────────────────────────
    def _generate_sqs_listener(self, flows, parsed_data):
        imports = {"org.springframework.scheduling.annotation.Scheduled",
                   "org.springframework.stereotype.Component",
                   
                   "software.amazon.awssdk.services.sqs.SqsClient"}
        methods = []
        service_deps = set()
        service_deps.add(("SqsClient", "sqsClient"))
        for flow in flows:
            mn = self._to_method_name(flow["name"])
            queue_url = flow.get("source", {}).get("queueUrl", "")
            body_lines, ei, deps = self._convert_processors(flow["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            methods.append(
                f'    @Scheduled(fixedDelay = 5000)\n'
                f'    public void {mn}() {{\n'
                f'        log.info("Polling SQS: {queue_url}");\n'
                f'        var messages = sqsClient.receiveMessage(b -> b.queueUrl("{queue_url}"));\n'
                f'        messages.messages().forEach(msg -> {{\n'
                f'            Object payload = msg.body();\n'
                + "\n".join(body_lines) + "\n"
                f'        }});\n'
                f'    }}'
            )
        return self._format_component_class("SqsMessageListener", "com.example.listener",
                                            imports, service_deps, methods)

    # ── Batch Job ─────────────────────────────────────────────────────────
    def _generate_batch_job(self, class_name, job, parsed_data):
        imports = {
            "org.springframework.batch.core.*",
            "org.springframework.batch.core.configuration.annotation.*",
            "org.springframework.batch.core.step.tasklet.*",
            "org.springframework.batch.repeat.RepeatStatus",
            "org.springframework.context.annotation.Bean",
            "org.springframework.context.annotation.Configuration",
            "lombok.extern.slf4j.Slf4j",
            "lombok.RequiredArgsConstructor",
        }
        service_deps = set()
        step_beans = []
        for i, step in enumerate(job.get("steps", [])):
            step_name = self._to_method_name(step["name"] or f"step{i}")
            body_lines, ei, deps = self._convert_processors(step["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            step_beans.append(
                f'    @Bean\n'
                f'    public Step {step_name}(JobRepository jobRepository, PlatformTransactionManager txManager) {{\n'
                f'        return new StepBuilder("{step["name"]}", jobRepository)\n'
                f'            .tasklet((contribution, chunkContext) -> {{\n'
                f'                log.info("Executing batch step: {step["name"]}");\n'
                + "\n".join(body_lines) + "\n"
                f'                return RepeatStatus.FINISHED;\n'
                f'            }}, txManager)\n'
                f'            .build();\n'
                f'    }}'
            )

        step_refs = ", ".join(
            self._to_method_name(s["name"] or f"step{i}") + "(jobRepository, txManager)"
            for i, s in enumerate(job.get("steps", []))
        )

        dep_fields = self._format_service_deps(service_deps)
        import_lines = "\n".join(f"import {i};" for i in sorted(imports))

        return (
            f"package com.example.batch;\n\n"
            f"{import_lines}\n\n"
            f"@Slf4j\n"
            f"@Configuration\n"
            f"@RequiredArgsConstructor\n"
            f"public class {class_name} {{\n\n"
            f"{dep_fields}\n\n"
            + "\n\n".join(step_beans) + "\n\n"
            f'    @Bean\n'
            f'    public Job {self._to_method_name(job["name"])}(JobRepository jobRepository, PlatformTransactionManager txManager) {{\n'
            f'        return new JobBuilder("{job["name"]}", jobRepository)\n'
            f'            .start({self._to_method_name(job["steps"][0]["name"] if job["steps"] else "step0")}(jobRepository, txManager))\n'
            f'            .build();\n'
            f'    }}\n'
            f"}}\n"
        )

    # ══════════════════════════════════════════════════════════════════════
    #  SERVICE & EXCEPTION GENERATORS
    # ══════════════════════════════════════════════════════════════════════

    def _generate_services(self, sub_flows, parsed_data):
        groups = {}
        for sf in sub_flows:
            name = sf["name"]
            if ":" in name:
                prefix = name.split(":")[0]
            else:
                parts = re.split(r"[-_\s]", name)
                prefix = parts[0] if parts else "Common"
            groups.setdefault(prefix, []).append(sf)

        services = {}
        for prefix, flows in groups.items():
            cls = self._to_class_name(prefix) + "Service"
            services[cls] = self._generate_service_class(cls, flows, parsed_data)
        return services

    def _generate_service_class(self, class_name, sub_flows, parsed_data):
        imports = {"org.springframework.stereotype.Service",
                   "lombok.extern.slf4j.Slf4j",
                   "lombok.RequiredArgsConstructor",
                   "java.util.*"}
        methods = []
        service_deps = set()
        for sf in sub_flows:
            mn = self._to_method_name(sf["name"])
            body_lines, ei, deps = self._convert_processors(sf["processors"], parsed_data)
            imports.update(ei)
            service_deps.update(deps)
            methods.append(
                f'    public Object {mn}() {{\n'
                f'        log.info("Executing: {sf["name"].replace(chr(92), chr(92)*2)}");\n'
                f'        Object payload = null;\n'
                + "\n".join(body_lines) + "\n"
                f'        return payload;\n'
                f'    }}'
            )
        dep_fields = self._format_service_deps(service_deps)
        import_lines = "\n".join(f"import {i};" for i in sorted(imports))
        return (
            f"package com.example.service;\n\n"
            f"{import_lines}\n\n"
            f"@Slf4j\n@Service\n@RequiredArgsConstructor\n"
            f"public class {class_name} {{\n\n"
            f"{dep_fields}\n\n"
            + "\n\n".join(methods) + "\n"
            f"}}\n"
        )

    def _generate_service_from_flow(self, class_name, flow, parsed_data):
        imports = {"org.springframework.stereotype.Service",
                   "lombok.extern.slf4j.Slf4j",
                   "lombok.RequiredArgsConstructor",
                   "java.util.*"}
        mn = self._to_method_name(flow["name"])
        body_lines, ei, deps = self._convert_processors(flow["processors"], parsed_data)
        imports.update(ei)
        dep_fields = self._format_service_deps(deps)
        import_lines = "\n".join(f"import {i};" for i in sorted(imports))

        # Build method params from flow source (path vars, request body)
        source = flow.get("source") or {}
        path = source.get("path", "")
        method = source.get("method", "GET").upper()
        path_vars = re.findall(r"\{(\w+)\}", path)
        param_parts = []
        for var in path_vars:
            param_parts.append(f"String {var}")
        if method in ("POST", "PUT", "PATCH"):
            param_parts.append("Map<String, Object> requestBody")
        params_str = ", ".join(param_parts)

        # Determine payload initialization
        if method in ("POST", "PUT", "PATCH"):
            payload_init = '        Object payload = requestBody;'
        else:
            payload_init = '        Object payload = null;'

        return (
            f"package com.example.service;\n\n"
            f"{import_lines}\n\n"
            f"@Slf4j\n@Service\n@RequiredArgsConstructor\n"
            f"public class {class_name} {{\n\n"
            f"{dep_fields}\n\n"
            f'    public Object {mn}({params_str}) {{\n'
            f'        log.info("Executing flow: {flow["name"].replace(chr(92), chr(92)*2)}");\n'
            f'{payload_init}\n'
            + "\n".join(body_lines) + "\n"
            f'        return payload;\n'
            f'    }}\n'
            f"}}\n"
        )

    def _generate_exception_handler(self, error_handlers, parsed_data):
        return (
            'package com.example.exception;\n\n'
            'import org.springframework.http.HttpStatus;\n'
            'import org.springframework.http.ResponseEntity;\n'
            'import org.springframework.web.bind.annotation.ControllerAdvice;\n'
            'import org.springframework.web.bind.annotation.ExceptionHandler;\n'
            'import java.util.Map;\n'
            'import java.util.LinkedHashMap;\n\n'
            '@ControllerAdvice\n'
            'public class GlobalExceptionHandler {\n\n'
            '    private static final org.slf4j.Logger log = org.slf4j.LoggerFactory.getLogger(GlobalExceptionHandler.class);\n\n'
            '    @ExceptionHandler(ResourceNotFoundException.class)\n'
            '    public ResponseEntity<Map<String, Object>> handleNotFound(ResourceNotFoundException e) {\n'
            '        log.error("Not found: {}", e.getMessage());\n'
            '        return buildError(HttpStatus.NOT_FOUND, e.getMessage());\n'
            '    }\n\n'
            '    @ExceptionHandler(BadRequestException.class)\n'
            '    public ResponseEntity<Map<String, Object>> handleBadRequest(BadRequestException e) {\n'
            '        log.error("Bad request: {}", e.getMessage());\n'
            '        return buildError(HttpStatus.BAD_REQUEST, e.getMessage());\n'
            '    }\n\n'
            '    @ExceptionHandler(IllegalArgumentException.class)\n'
            '    public ResponseEntity<Map<String, Object>> handleValidation(IllegalArgumentException e) {\n'
            '        log.error("Validation error: {}", e.getMessage());\n'
            '        return buildError(HttpStatus.BAD_REQUEST, e.getMessage());\n'
            '    }\n\n'
            '    @ExceptionHandler(SecurityException.class)\n'
            '    public ResponseEntity<Map<String, Object>> handleSecurity(SecurityException e) {\n'
            '        log.error("Security error: {}", e.getMessage());\n'
            '        return buildError(HttpStatus.FORBIDDEN, e.getMessage());\n'
            '    }\n\n'
            '    @ExceptionHandler(java.util.concurrent.TimeoutException.class)\n'
            '    public ResponseEntity<Map<String, Object>> handleTimeout(java.util.concurrent.TimeoutException e) {\n'
            '        log.error("Timeout: {}", e.getMessage());\n'
            '        return buildError(HttpStatus.GATEWAY_TIMEOUT, e.getMessage());\n'
            '    }\n\n'
            '    @ExceptionHandler(RuntimeException.class)\n'
            '    public ResponseEntity<Map<String, Object>> handleRuntime(RuntimeException e) {\n'
            '        log.error("Runtime error: {}", e.getMessage(), e);\n'
            '        return buildError(HttpStatus.INTERNAL_SERVER_ERROR, e.getMessage());\n'
            '    }\n\n'
            '    @ExceptionHandler(Exception.class)\n'
            '    public ResponseEntity<Map<String, Object>> handleGeneric(Exception e) {\n'
            '        log.error("Unexpected error: {}", e.getMessage(), e);\n'
            '        return buildError(HttpStatus.INTERNAL_SERVER_ERROR, "An unexpected error occurred");\n'
            '    }\n\n'
            '    private ResponseEntity<Map<String, Object>> buildError(HttpStatus status, String message) {\n'
            '        Map<String, Object> body = new LinkedHashMap<>();\n'
            '        body.put("status", status.value());\n'
            '        body.put("error", status.getReasonPhrase());\n'
            '        body.put("message", message);\n'
            '        body.put("timestamp", java.time.LocalDateTime.now().toString());\n'
            '        return ResponseEntity.status(status).body(body);\n'
            '    }\n'
            '}\n'
        )

    # ══════════════════════════════════════════════════════════════════════
    #  FORMATTING HELPERS
    # ══════════════════════════════════════════════════════════════════════

    def _format_method(self, annotation, path, method_name, params, body_lines, flow):
        body = "\n".join(body_lines)
        # Determine initial payload based on HTTP method
        source_method = flow.get("source", {}).get("method", "GET").upper()
        if source_method in ("POST", "PUT", "PATCH"):
            payload_init = "        Object payload = requestBody;"
        else:
            payload_init = "        Object payload = null;"
        return (
            f'    @{annotation}("{path}")\n'
            f'    public ResponseEntity<?> {method_name}({params}) {{\n'
            f'        log.info("Handling request: {flow["name"].replace(chr(92), chr(92)*2)}");\n'
            f'{payload_init}\n'
            f'{body}\n'
            f'        return ResponseEntity.ok(payload);\n'
            f'    }}'
        )

    def _format_controller_class(self, class_name, base_path, imports, service_deps, methods):
        dep_fields = self._format_service_deps(service_deps)
        # Ensure Lombok imports are present for @Slf4j and @RequiredArgsConstructor
        imports.add("lombok.extern.slf4j.Slf4j")
        imports.add("lombok.RequiredArgsConstructor")
        import_lines = "\n".join(f"import {i};" for i in sorted(imports))
        bp = f'@RequestMapping("{base_path}")\n' if base_path else ""
        return (
            f"package com.example.controller;\n\n"
            f"{import_lines}\n\n"
            f"@Slf4j\n@RequiredArgsConstructor\n@RestController\n{bp}"
            f"public class {class_name} {{\n\n"
            f"{dep_fields}\n\n"
            + "\n\n".join(methods) + "\n"
            f"}}\n"
        )

    def _format_component_class(self, class_name, package, imports, service_deps, methods):
        dep_fields = self._format_service_deps(service_deps)
        imports.add("lombok.extern.slf4j.Slf4j")
        imports.add("lombok.RequiredArgsConstructor")
        import_lines = "\n".join(f"import {i};" for i in sorted(imports))
        return (
            f"package {package};\n\n"
            f"{import_lines}\n\n"
            f"@Slf4j\n@RequiredArgsConstructor\n@Component\n"
            f"public class {class_name} {{\n\n"
            f"{dep_fields}\n\n"
            + "\n\n".join(methods) + "\n"
            f"}}\n"
        )

    def _generate_constructor(self, class_name, service_deps):
        if not service_deps:
            return ""
        params = ", ".join(f"{cls} {var}" for cls, var in sorted(service_deps))
        assignments = "\n".join(f"        this.{var} = {var};" for _, var in sorted(service_deps))
        return (
            f"    public {class_name}({params}) {{\n"
            f"{assignments}\n"
            f"    }}\n"
        )

    def _format_service_deps(self, service_deps):
        if not service_deps:
            return ""
        return "\n".join(
            f"    private final {cls} {var};"
            for cls, var in sorted(service_deps)
        )

    def _build_method_params(self, flow, path_vars):
        params = []
        for var in path_vars:
            params.append(f'@PathVariable String {var}')
        for proc in flow["processors"]:
            if "queryParams" in str(proc.get("attributes", {})):
                params.append("@RequestParam Map<String, String> queryParams")
                break
        source_method = flow.get("source", {}).get("method", "GET")
        if source_method.upper() in ("POST", "PUT", "PATCH"):
            params.append("@RequestBody Map<String, Object> requestBody")
        return ", ".join(params)

    def _extract_schedule_annotation(self, flow):
        source = flow.get("source", {})
        for child in source.get("children", []):
            if child.get("tag") == "scheduling-strategy":
                for inner in child.get("children", []):
                    if inner.get("tag") == "fixed-frequency":
                        freq = inner.get("attributes", {}).get("frequency", "60000")
                        return f"@Scheduled(fixedRate = {freq})"
                    elif inner.get("tag") == "cron":
                        cron_expr = inner.get("attributes", {}).get("expression", "0 0 * * * *")
                        return f'@Scheduled(cron = "{cron_expr}")'
        return "@Scheduled(fixedRate = 60000)"

    # ── SQL helpers ───────────────────────────────────────────────────────
    def _extract_sql(self, proc):
        for child in proc.get("children", []):
            if child.get("tag") in ("sql", "parameterized-query"):
                text = child.get("text", "")
                if text:
                    return self._convert_sql_params(text)
                for inner in child.get("children", []):
                    if inner.get("text"):
                        return self._convert_sql_params(inner["text"])
        return proc.get("attributes", {}).get("sql", "SELECT 1")

    def _convert_sql_params(self, sql):
        sql = re.sub(r":(\w+)", "?", sql)
        # Normalize MySQL-specific functions to ANSI SQL equivalents
        sql = re.sub(r'\bCURDATE\(\)', 'CURRENT_DATE', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bNOW\(\)', 'CURRENT_TIMESTAMP', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bIFNULL\(', 'COALESCE(', sql, flags=re.IGNORECASE)
        sql = re.sub(r'\bLIMIT\s+(\d+)\s*,\s*(\d+)', r'LIMIT \2 OFFSET \1', sql, flags=re.IGNORECASE)
        return sql

    def _extract_db_params(self, proc):
        params = []
        for child in proc.get("children", []):
            if child.get("tag") == "input-parameters":
                text = child.get("text", "")
                if text:
                    # Extract parameter names from DataWeave map like {name: $.name, email: $.email}
                    pairs = re.findall(r"(\w+)\s*:\s*([^,}\]]+)", text)
                    for name, value in pairs:
                        value = value.strip()
                        # Convert to safe Java — use requestBody.get("name") pattern
                        if "." in value and any(value.startswith(p) for p in ("vars.", "$.", "payload.")):
                            # Extract field name from last segment
                            field = value.split(".")[-1].strip()
                            params.append(f'requestBody.get("{field}")')
                        else:
                            try:
                                java = self.dw_converter.convert_inline_expression(value)
                                # Ensure it's safe Java
                                if any(c in java for c in [",}", "]", "vars."]):
                                    params.append(f'requestBody.get("{name}")')
                                else:
                                    params.append(java)
                            except Exception:
                                params.append(f'requestBody.get("{name}")')
        return ", ".join(params) if params else ""

    # ── String / naming helpers ───────────────────────────────────────────
    def _convert_dw_in_string(self, text):
        """Convert MuleSoft #[...] expressions in strings to safe Java.

        Attempts to convert to Java; falls back to a placeholder comment
        if the conversion would produce uncompilable code.
        """
        def repl(m):
            expr = m.group(1)
            try:
                java = self.dw_converter.convert_inline_expression(f"#[{expr}]")
                # If the result contains unresolvable references, use placeholder
                unsafe_patterns = ["request.", "message.", "attributes.", "vars.", "flow."]
                if any(p in java for p in unsafe_patterns):
                    return "/* " + expr + " */"
                return '" + ' + java + ' + "'
            except Exception:
                return "/* " + expr + " */"
        return re.sub(r"#\[([^\]]+)\]", repl, text)

    def _escape_java(self, text):
        return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

    def _to_class_name(self, name):
        name = re.sub(r"[^a-zA-Z0-9]", " ", name)
        return "".join(w.capitalize() for w in name.split())

    def _to_method_name(self, name):
        name = re.sub(r"[^a-zA-Z0-9]", " ", name)
        parts = name.split()
        if not parts:
            return "process"
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])

    def _to_variable_name(self, class_name):
        if not class_name:
            return "service"
        # Convert hyphens, dots, underscores to camelCase
        # e.g. "claims-db-config" → "claimsDbConfig"
        #      "my_service.name"  → "myServiceName"
        import re as _re
        parts = _re.split(r'[-._]+', class_name)
        if not parts:
            return "service"
        result = parts[0][0].lower() + parts[0][1:] if parts[0] else ""
        for p in parts[1:]:
            if p:
                result += p[0].upper() + p[1:]
        # Strip any remaining non-Java-identifier characters
        result = _re.sub(r'[^a-zA-Z0-9]', '', result)
        return result or "service"
