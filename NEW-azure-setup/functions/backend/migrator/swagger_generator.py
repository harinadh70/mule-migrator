"""
Swagger/OpenAPI 3.0 Generator

Generates OpenAPI 3.0 specifications from:
  1. Parsed MuleSoft XML data (flows → endpoints)
  2. RAML content (YAML-based API spec → OpenAPI)
"""
import re
import yaml
import json


def generate_from_parsed_xml(parsed_data, project_name="migrated-app"):
    """Generate an OpenAPI 3.0 spec from parsed MuleSoft XML data.

    Extracts HTTP listener flows and converts them to OpenAPI paths.
    """
    flows = parsed_data.get("flows", [])

    # Extract server info from HTTP listener config if available
    server_url = _extract_server_url(parsed_data)

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": _to_title(project_name) + " API",
            "description": "Auto-generated OpenAPI specification from MuleSoft migration",
            "version": "1.0.0",
            "contact": {"name": "API Team"},
        },
        "servers": [{"url": server_url, "description": "Local development"}],
        "paths": {},
        "components": {
            "schemas": {},
            "securitySchemes": {},
        },
        "tags": [],
    }

    tag_set = set()

    for flow in flows:
        source = flow.get("source", {})
        source_type = source.get("type", "")

        # Only process HTTP listener flows
        if source_type not in ("http-listener", "http:listener"):
            continue

        path = source.get("path", "/")
        method = source.get("method", "GET").lower()
        flow_name = flow.get("name", "unknown")
        processors = flow.get("processors", [])

        # Normalize path: convert MuleSoft {param} style to OpenAPI
        openapi_path = _normalize_path(path)

        # Extract tag from flow name
        tag = _extract_tag(flow_name)
        tag_set.add(tag)

        # Derive a clean entity name from the flow for schema naming
        entity_name = _extract_entity_name(flow_name)
        response_schema_name = _to_pascal_case(flow_name) + "Response"

        # Build operation
        operation = {
            "summary": _flow_name_to_summary(flow_name),
            "operationId": _to_camel_case(flow_name),
            "tags": [tag],
            "responses": {
                "200": {
                    "description": "Successful response",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": f"#/components/schemas/{response_schema_name}"}
                        }
                    }
                },
                "400": {
                    "description": "Bad request",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                },
                "404": {
                    "description": "Resource not found",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                },
                "500": {
                    "description": "Internal server error",
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                        }
                    }
                },
            }
        }

        # Build the success response schema
        spec["components"]["schemas"][response_schema_name] = {
            "type": "object",
            "properties": {
                "status": {"type": "string", "example": "success"},
                "message": {"type": "string", "example": "Operation completed successfully"},
                "data": {"type": "object", "additionalProperties": True},
            },
        }

        # Add path parameters
        path_params = re.findall(r'\{(\w+)\}', openapi_path)
        if path_params:
            operation["parameters"] = []
            for param in path_params:
                operation["parameters"].append({
                    "name": param,
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                    "description": f"The {param} identifier",
                })

        # Add query parameters for GET
        if method == "get":
            if "parameters" not in operation:
                operation["parameters"] = []

            # Extract query param names from set-variable processors referencing queryParams
            extracted_params = _extract_query_params_from_processors(processors)
            for ep in extracted_params:
                operation["parameters"].append({
                    "name": ep,
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": f"Query parameter: {ep}",
                })

            # Add common pagination parameters for GET endpoints
            flow_lower = flow_name.lower()
            operation["parameters"].extend([
                {
                    "name": "page",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 0},
                    "description": "Page number (zero-based)",
                },
                {
                    "name": "size",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 20},
                    "description": "Number of items per page",
                },
                {
                    "name": "sort",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Sort criteria (e.g. 'name,asc')",
                },
            ])

            # Add a search/query parameter for search-like endpoints
            if any(kw in flow_lower for kw in ("search", "filter", "find", "list", "get-all", "getall", "get_all")):
                operation["parameters"].append({
                    "name": "q",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Search query string",
                })

        # Add request body for POST/PUT/PATCH
        if method in ("post", "put", "patch"):
            schema_name = _to_pascal_case(flow_name) + "Request"
            operation["requestBody"] = {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": {"$ref": f"#/components/schemas/{schema_name}"}
                    }
                }
            }
            # Build a meaningful request schema from flow analysis
            request_properties = _build_request_properties(flow_name, processors, entity_name)
            spec["components"]["schemas"][schema_name] = {
                "type": "object",
                "properties": request_properties,
                "additionalProperties": True,
            }

        # Add to paths
        if openapi_path not in spec["paths"]:
            spec["paths"][openapi_path] = {}
        spec["paths"][openapi_path][method] = operation

    # Build tags
    spec["tags"] = [{"name": t, "description": f"{t} operations"} for t in sorted(tag_set)]

    # Add common error response schema
    spec["components"]["schemas"]["ErrorResponse"] = {
        "type": "object",
        "properties": {
            "error": {"type": "string", "description": "Error type or code"},
            "message": {"type": "string", "description": "Human-readable error message"},
            "timestamp": {"type": "string", "format": "date-time", "description": "When the error occurred"},
        },
        "required": ["error", "message", "timestamp"],
    }

    # Keep backward-compatible Error schema
    spec["components"]["schemas"]["Error"] = {
        "type": "object",
        "properties": {
            "code": {"type": "integer"},
            "message": {"type": "string"},
        },
        "required": ["code", "message"],
    }

    return spec


def generate_from_raml(raml_content):
    """Convert RAML content to OpenAPI 3.0 spec.

    Supports RAML 1.0 and basic RAML 0.8 constructs:
      - Resource paths with methods
      - Types/schemas
      - Query parameters
      - URI parameters
      - Descriptions and examples
    """
    # Remove RAML version header for YAML parsing
    clean = re.sub(r'^#%RAML\s+[\d.]+\s*\n', '', raml_content.strip())
    try:
        raml = yaml.safe_load(clean)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse RAML: {e}")

    if not isinstance(raml, dict):
        raise ValueError("Invalid RAML: expected a mapping at the root level")

    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": raml.get("title", "API"),
            "description": raml.get("description", "Converted from RAML"),
            "version": str(raml.get("version", "1.0.0")),
        },
        "servers": [],
        "paths": {},
        "components": {"schemas": {}},
        "tags": [],
    }

    # Base URI
    base_uri = raml.get("baseUri", "")
    if base_uri:
        # Replace RAML {version} placeholder
        base_uri = base_uri.replace("{version}", str(raml.get("version", "v1")))
        spec["servers"].append({"url": base_uri, "description": "Base URI from RAML"})
    else:
        spec["servers"].append({"url": "http://localhost:8080"})

    # Convert types / schemas
    types = raml.get("types", raml.get("schemas", {}))
    if isinstance(types, dict):
        for type_name, type_def in types.items():
            spec["components"]["schemas"][type_name] = _raml_type_to_schema(type_def)
    elif isinstance(types, list):
        for item in types:
            if isinstance(item, dict):
                for type_name, type_def in item.items():
                    spec["components"]["schemas"][type_name] = _raml_type_to_schema(type_def)

    # Convert resources (top-level keys starting with /)
    tag_set = set()
    for key, value in raml.items():
        if isinstance(key, str) and key.startswith('/') and isinstance(value, dict):
            _convert_raml_resource(key, value, spec["paths"], spec["components"]["schemas"], tag_set)

    spec["tags"] = [{"name": t, "description": f"{t} operations"} for t in sorted(tag_set)]

    return spec


def _convert_raml_resource(path, resource, paths, schemas, tag_set, parent_params=None):
    """Recursively convert a RAML resource to OpenAPI paths."""
    http_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
    uri_params = resource.get("uriParameters", {})
    all_params = dict(parent_params or {})
    all_params.update(uri_params)

    openapi_path = _normalize_path(path)
    tag = _extract_tag_from_path(openapi_path)
    tag_set.add(tag)

    for method in http_methods:
        if method not in resource:
            continue

        method_def = resource[method]
        if not isinstance(method_def, dict):
            method_def = {}

        operation = {
            "summary": method_def.get("description", f"{method.upper()} {path}"),
            "operationId": _path_to_operation_id(method, path),
            "tags": [tag],
            "responses": {},
        }

        # Parameters
        params = []
        path_params = re.findall(r'\{(\w+)\}', openapi_path)
        for p in path_params:
            p_def = all_params.get(p, {})
            params.append({
                "name": p,
                "in": "path",
                "required": True,
                "schema": {"type": _raml_type_str(p_def.get("type", "string"))},
                "description": p_def.get("description", ""),
            })

        query_params = method_def.get("queryParameters", {})
        if isinstance(query_params, dict):
            for qp_name, qp_def in query_params.items():
                if not isinstance(qp_def, dict):
                    qp_def = {"type": "string"}
                params.append({
                    "name": qp_name,
                    "in": "query",
                    "required": qp_def.get("required", False),
                    "schema": {"type": _raml_type_str(qp_def.get("type", "string"))},
                    "description": qp_def.get("description", ""),
                })

        if params:
            operation["parameters"] = params

        # Request body
        body = method_def.get("body", {})
        if body and method in ("post", "put", "patch"):
            content = {}
            for mime, mime_def in body.items():
                if not isinstance(mime_def, dict):
                    mime_def = {}
                schema_ref = mime_def.get("type", mime_def.get("schema", "object"))
                if isinstance(schema_ref, str) and schema_ref in schemas:
                    content[mime] = {"schema": {"$ref": f"#/components/schemas/{schema_ref}"}}
                else:
                    content[mime] = {"schema": {"type": "object"}}
            if content:
                operation["requestBody"] = {"required": True, "content": content}

        # Responses
        responses = method_def.get("responses", {})
        if responses and isinstance(responses, dict):
            for status, resp_def in responses.items():
                status_str = str(status)
                if not isinstance(resp_def, dict):
                    resp_def = {}
                resp = {"description": resp_def.get("description", f"Status {status_str}")}
                resp_body = resp_def.get("body", {})
                if resp_body and isinstance(resp_body, dict):
                    resp_content = {}
                    for mime, mime_def in resp_body.items():
                        if not isinstance(mime_def, dict):
                            mime_def = {}
                        type_ref = mime_def.get("type", mime_def.get("schema", "object"))
                        if isinstance(type_ref, str) and type_ref in schemas:
                            resp_content[mime] = {"schema": {"$ref": f"#/components/schemas/{type_ref}"}}
                        else:
                            resp_content[mime] = {"schema": {"type": "object"}}
                    if resp_content:
                        resp["content"] = resp_content
                operation["responses"][status_str] = resp
        else:
            operation["responses"]["200"] = {"description": "Successful response"}

        if openapi_path not in paths:
            paths[openapi_path] = {}
        paths[openapi_path][method] = operation

    # Nested resources
    for key, value in resource.items():
        if isinstance(key, str) and key.startswith('/') and isinstance(value, dict):
            _convert_raml_resource(path + key, value, paths, schemas, tag_set, all_params)


def _raml_type_to_schema(type_def):
    """Convert a RAML type definition to an OpenAPI schema."""
    if isinstance(type_def, str):
        return {"type": _raml_type_str(type_def)}

    if not isinstance(type_def, dict):
        return {"type": "object"}

    schema = {}
    raml_type = type_def.get("type", "object")

    if raml_type == "object" or "properties" in type_def:
        schema["type"] = "object"
        props = type_def.get("properties", {})
        if isinstance(props, dict):
            schema["properties"] = {}
            required = []
            for prop_name, prop_def in props.items():
                clean_name = prop_name.rstrip("?")
                is_required = not prop_name.endswith("?") and (
                    isinstance(prop_def, dict) and prop_def.get("required", True)
                )
                if is_required:
                    required.append(clean_name)
                schema["properties"][clean_name] = _raml_type_to_schema(prop_def)
            if required:
                schema["required"] = required
    elif raml_type == "array" or "items" in type_def:
        schema["type"] = "array"
        items = type_def.get("items", "object")
        schema["items"] = _raml_type_to_schema(items)
    else:
        schema["type"] = _raml_type_str(raml_type)

    if "description" in type_def:
        schema["description"] = type_def["description"]
    if "enum" in type_def:
        schema["enum"] = type_def["enum"]
    if "example" in type_def:
        schema["example"] = type_def["example"]

    return schema


def _raml_type_str(t):
    """Map RAML type strings to OpenAPI type strings."""
    mapping = {
        "string": "string",
        "number": "number",
        "integer": "integer",
        "boolean": "boolean",
        "date-only": "string",
        "time-only": "string",
        "datetime-only": "string",
        "datetime": "string",
        "file": "string",
        "nil": "string",
        "any": "object",
        "object": "object",
        "array": "array",
    }
    if isinstance(t, str):
        t_lower = t.lower().strip()
        if t_lower.endswith("[]"):
            return "array"
        return mapping.get(t_lower, "string")
    return "object"


# ── XML flow analysis helpers ───────────────────────────────────

def _extract_server_url(parsed_data):
    """Extract server URL from HTTP listener config in parsed data."""
    # Check for global configurations / connector configs
    configs = parsed_data.get("configurations", parsed_data.get("connectors", []))
    if isinstance(configs, list):
        for cfg in configs:
            if not isinstance(cfg, dict):
                continue
            cfg_type = cfg.get("type", "")
            if "http" in cfg_type.lower() and "listener" in cfg_type.lower():
                host = cfg.get("host", cfg.get("attributes", {}).get("host", ""))
                port = cfg.get("port", cfg.get("attributes", {}).get("port", ""))
                if host and port:
                    return f"http://{host}:{port}"
                elif port:
                    return f"http://localhost:{port}"
    elif isinstance(configs, dict):
        for key, cfg in configs.items():
            if not isinstance(cfg, dict):
                continue
            if "http" in key.lower() and "listener" in key.lower():
                host = cfg.get("host", "localhost")
                port = cfg.get("port", "8080")
                return f"http://{host}:{port}"

    # Check for a top-level http config
    http_config = parsed_data.get("httpListenerConfig", parsed_data.get("http_listener_config", {}))
    if isinstance(http_config, dict) and http_config:
        host = http_config.get("host", "localhost")
        port = http_config.get("port", "8080")
        return f"http://{host}:{port}"

    return "http://localhost:8080"


def _extract_query_params_from_processors(processors):
    """Extract query parameter names from flow processors that reference attributes.queryParams."""
    params = []
    if not isinstance(processors, list):
        return params
    for proc in processors:
        if not isinstance(proc, dict):
            continue
        # Look at set-variable processors
        proc_type = proc.get("type", "")
        if proc_type in ("set-variable", "set_variable", "ee:set-variable"):
            value = proc.get("value", proc.get("expression", ""))
            if isinstance(value, str) and "queryParams" in value:
                # Try to extract param name from patterns like:
                #   attributes.queryParams.paramName
                #   attributes.queryParams['paramName']
                #   attributes.queryParams["paramName"]
                matches = re.findall(r'queryParams\s*[\.\[]\s*[\'"]?(\w+)[\'"]?\s*\]?', value)
                params.extend(matches)
        # Also check transform/dataweave processors
        if proc_type in ("transform", "ee:transform", "dataweave"):
            body = proc.get("body", proc.get("code", proc.get("expression", "")))
            if isinstance(body, str) and "queryParams" in body:
                matches = re.findall(r'queryParams\s*[\.\[]\s*[\'"]?(\w+)[\'"]?\s*\]?', body)
                params.extend(matches)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for p in params:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def _extract_entity_name(flow_name):
    """Try to extract an entity name from the flow name (e.g. 'create-user' -> 'user')."""
    lower = flow_name.lower()
    # Remove common action prefixes
    for prefix in ("create", "update", "delete", "get", "find", "list", "search", "add", "remove", "fetch", "save", "post", "put", "patch"):
        pattern = r'^' + prefix + r'[-_\s]+'
        stripped = re.sub(pattern, '', lower)
        if stripped != lower:
            # Clean up and return the entity part
            return re.sub(r'[-_\s]+', '', stripped).capitalize()
    # Fallback: use the last meaningful part
    parts = re.split(r'[-_:\s]+', flow_name)
    return parts[-1].capitalize() if parts else "Entity"


def _build_request_properties(flow_name, processors, entity_name):
    """Build request body properties by analyzing flow name and processors."""
    properties = {}

    # Check processors for payload hints (set-payload, transform)
    payload_fields = _extract_payload_fields_from_processors(processors)
    if payload_fields:
        for field_name, field_type in payload_fields.items():
            properties[field_name] = {"type": field_type}
        return properties

    # Generate entity-appropriate fields based on flow/entity name
    lower_entity = entity_name.lower()
    lower_flow = flow_name.lower()

    # Common entity fields
    if any(kw in lower_entity or kw in lower_flow for kw in ("user", "account", "profile", "person", "employee", "customer")):
        properties = {
            "name": {"type": "string", "description": f"{entity_name} name"},
            "email": {"type": "string", "format": "email", "description": f"{entity_name} email address"},
        }
    elif any(kw in lower_entity or kw in lower_flow for kw in ("order", "purchase", "transaction")):
        properties = {
            "amount": {"type": "number", "description": "Order amount"},
            "currency": {"type": "string", "description": "Currency code (e.g. USD)"},
            "items": {"type": "array", "items": {"type": "object"}, "description": "Order line items"},
        }
    elif any(kw in lower_entity or kw in lower_flow for kw in ("product", "item", "catalog")):
        properties = {
            "name": {"type": "string", "description": "Product name"},
            "description": {"type": "string", "description": "Product description"},
            "price": {"type": "number", "description": "Product price"},
        }
    else:
        # Generic fallback with the entity as context
        properties = {
            "name": {"type": "string", "description": f"{entity_name} name"},
            "description": {"type": "string", "description": f"{entity_name} description"},
        }

    return properties


def _extract_payload_fields_from_processors(processors):
    """Try to extract field names from set-payload or transform processors."""
    fields = {}
    if not isinstance(processors, list):
        return fields
    for proc in processors:
        if not isinstance(proc, dict):
            continue
        proc_type = proc.get("type", "")
        if proc_type in ("set-payload", "set_payload", "transform", "ee:transform", "dataweave"):
            body = proc.get("value", proc.get("body", proc.get("code", proc.get("expression", ""))))
            if not isinstance(body, str):
                continue
            # Look for JSON-like key patterns: "fieldName": or fieldName:
            json_keys = re.findall(r'["\'](\w+)["\']\s*:', body)
            dw_keys = re.findall(r'(\w+)\s*:', body)
            all_keys = json_keys or dw_keys
            for key in all_keys:
                # Skip common non-field keys
                if key.lower() in ("type", "class", "content", "output", "application", "json", "java", "payload"):
                    continue
                fields[key] = "string"
    return fields


# ── Helpers ─────────────────────────────────────────────────────

def _normalize_path(path):
    """Normalize MuleSoft path to OpenAPI path format."""
    # Already in {param} format — just clean up
    path = path.strip()
    if not path.startswith('/'):
        path = '/' + path
    # Replace :param with {param} style
    path = re.sub(r':(\w+)', r'{\1}', path)
    return path


def _to_title(s):
    return re.sub(r'[-_]+', ' ', s).title()


def _to_camel_case(s):
    parts = re.split(r'[-_\s]+', s)
    return parts[0].lower() + ''.join(p.capitalize() for p in parts[1:])


def _to_pascal_case(s):
    return ''.join(p.capitalize() for p in re.split(r'[-_\s]+', s))


def _flow_name_to_summary(name):
    return re.sub(r'[-_]+', ' ', name).strip().capitalize()


def _extract_tag(flow_name):
    parts = re.split(r'[-_:\s]+', flow_name)
    return parts[0].capitalize() if parts else "Default"


def _extract_tag_from_path(path):
    parts = [p for p in path.split('/') if p and not p.startswith('{')]
    return parts[0].capitalize() if parts else "Default"


def _path_to_operation_id(method, path):
    clean = re.sub(r'[{}]', '', path)
    parts = [p for p in clean.split('/') if p]
    name = method + '_' + '_'.join(parts)
    return re.sub(r'[^a-zA-Z0-9_]', '', name)
