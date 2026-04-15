"""
Migration Engine — wraps the existing backend.migrator static engine.

Parses MuleSoft XML, converts flows, maps connectors, generates a
complete Spring Boot project.  Returns a dict of {filepath: content}.

This module is imported by the queue-triggered migration worker in
function_app.py.
"""

from __future__ import annotations

import logging
import sys
import os
from pathlib import Path
from typing import Any

import defusedxml.ElementTree as SafeET

logger = logging.getLogger("engine")

# ---------------------------------------------------------------------------
#  Ensure the parent project is on sys.path so that
#  ``backend.migrator.*`` imports resolve correctly.
# ---------------------------------------------------------------------------

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
#  XXE-safe XML pre-validation
# ---------------------------------------------------------------------------

def validate_xml_safe(xml_content: str) -> str:
    """
    Parse the XML with defusedxml to reject external entities, billion-laughs
    attacks, and other XXE vectors.  Returns the content unchanged if safe.
    """
    try:
        SafeET.fromstring(xml_content)
    except SafeET.ParseError as exc:
        raise ValueError(f"Invalid or unsafe XML: {exc}") from exc
    return xml_content


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def run_static_migration(
    xml_files: dict[str, str],
    config: dict[str, Any],
) -> dict[str, Any]:
    """
    Execute the full static migration pipeline.

    Args:
        xml_files: Mapping of filename -> raw MuleSoft XML content.
        config: Dict with ``group_id``, ``artifact_id``, ``java_version``.

    Returns:
        Dict with keys:
          - ``files``:    {relative_path: file_content}
          - ``errors``:   list of non-fatal error strings
          - ``unknown_elements``: list of unrecognised MuleSoft elements
    """
    from backend.migrator.parser import MuleSoftParser
    from backend.migrator.flow_converter import FlowConverter
    from backend.migrator.connector_mapper import ConnectorMapper
    from backend.migrator.dataweave_converter import DataWeaveConverter
    from backend.migrator.spring_generator import SpringBootGenerator

    parser = MuleSoftParser()
    mapper = ConnectorMapper()
    dw_converter = DataWeaveConverter()

    group_id = config.get("group_id", "com.example")
    artifact_id = config.get("artifact_id", "migrated-app")
    java_version = config.get("java_version", "17")

    generated_files: dict[str, str] = {}
    errors: list[str] = []
    unknown_elements: list[str] = []
    all_parsed: dict[str, Any] = {}
    diag: list[str] = []  # diagnostic trace

    diag.append(f"=== Migration Diagnostic ===")
    diag.append(f"xml_files count: {len(xml_files)}")
    diag.append(f"xml_files keys: {list(xml_files.keys())}")
    diag.append(f"config: {config}")

    # ── Parse and convert each XML file ───────────────────────────
    for filename, xml_content in xml_files.items():
        diag.append(f"\n--- Processing: {filename} ---")
        diag.append(f"xml_content length: {len(xml_content)}")
        diag.append(f"xml_content first 200 chars: {xml_content[:200]}")
        try:
            # XXE protection
            validate_xml_safe(xml_content)
            diag.append("XXE validation passed")

            parsed = parser.parse(xml_content)
            if parsed is None:
                errors.append(f"File {filename}: parser returned None")
                diag.append("Parser returned None!")
                continue

            # Diagnostic: what did the parser find?
            diag.append(f"Parser returned keys: {list(parsed.keys())}")
            diag.append(f"  flows: {len(parsed.get('flows', []))}")
            diag.append(f"  sub_flows: {len(parsed.get('sub_flows', []))}")
            diag.append(f"  global_configs: {len(parsed.get('global_configs', []))}")
            diag.append(f"  batch_jobs: {len(parsed.get('batch_jobs', []))}")
            diag.append(f"  error_handlers: {len(parsed.get('error_handlers', []))}")
            for i, flow in enumerate(parsed.get("flows", [])):
                src = flow.get("source")
                diag.append(f"  flow[{i}] name={flow.get('name')!r} "
                            f"source={src.get('type') if isinstance(src, dict) else src!r} "
                            f"processors={len(flow.get('processors', []))}")

            all_parsed = parsed

            converter = FlowConverter(dw_converter, mapper)
            conversion_result = converter.convert(parsed, {})

            diag.append(f"FlowConverter returned type: {type(conversion_result).__name__}")
            if isinstance(conversion_result, dict):
                diag.append(f"FlowConverter keys ({len(conversion_result)}): {list(conversion_result.keys())[:30]}")
                files_dict = conversion_result.get("files", {})
                diag.append(f"conversion_result.get('files'): {len(files_dict)} entries")
                if not files_dict:
                    for k, v in conversion_result.items():
                        if isinstance(v, str) and ("." in k or "/" in k):
                            files_dict[k] = v
                    diag.append(f"After fallback extraction: {len(files_dict)} entries")
                    diag.append(f"Extracted keys: {list(files_dict.keys())[:30]}")
                generated_files.update(files_dict)
                unknown_elements.extend(
                    conversion_result.get("unknown_elements", [])
                )
            else:
                diag.append(f"FlowConverter returned non-dict: {conversion_result!r}")
        except ValueError as exc:
            diag.append(f"ValueError (XXE/parse): {exc}")
            # XXE or parse error — propagate as validation failure
            raise
        except Exception as exc:
            import traceback
            diag.append(f"EXCEPTION: {exc}")
            diag.append(traceback.format_exc())
            logger.warning("engine.file_failed: %s — %s", filename, exc, exc_info=True)
            errors.append(f"File {filename}: {exc}")

    diag.append(f"\n--- After flow conversion ---")
    diag.append(f"generated_files count: {len(generated_files)}")
    diag.append(f"generated_files keys: {list(generated_files.keys())[:30]}")
    diag.append(f"all_parsed truthy: {bool(all_parsed)}")
    if all_parsed:
        diag.append(f"all_parsed keys: {list(all_parsed.keys())}")

    # ── Generate Spring Boot project skeleton ─────────────────────
    if all_parsed:
        try:
            generator = SpringBootGenerator(
                project_name=artifact_id,
                group_id=group_id,
                java_version=java_version,
            )
            connector_info = mapper.map_connectors(all_parsed)
            diag.append(f"connector_info: {connector_info}")
            project_files = generator.generate(
                generated_files,
                connector_info,
                all_parsed,
            )
            diag.append(f"SpringBootGenerator returned type: {type(project_files).__name__}")
            if isinstance(project_files, dict):
                diag.append(f"SpringBootGenerator files ({len(project_files)}): {list(project_files.keys())[:30]}")
                added = 0
                for k, v in project_files.items():
                    if isinstance(v, str):
                        generated_files[k] = v
                        added += 1
                diag.append(f"Added {added} files from SpringBootGenerator")
                # Remove root-level Java files now that they've been
                # remapped under src/main/java/ by the generator
                root_java = [k for k in generated_files
                             if k.endswith(".java") and not k.startswith("src/")
                             and f"src/main/java/{group_id.replace('.', '/')}/{k}" in generated_files]
                for k in root_java:
                    del generated_files[k]
                if root_java:
                    diag.append(f"Removed {len(root_java)} root-level Java duplicates")
            else:
                diag.append(f"SpringBootGenerator returned non-dict: {project_files!r}")
        except Exception as exc:
            import traceback
            diag.append(f"SpringBootGenerator EXCEPTION: {exc}")
            diag.append(traceback.format_exc())
            logger.warning("engine.generate_failed: %s", exc, exc_info=True)
            errors.append(f"Spring generation: {exc}")
            # Fallback: if spring_generator crashed, at least remap
            # flow_converter files to proper package structure
            remapped = {}
            for k, v in list(generated_files.items()):
                if k.endswith(".java") and not k.startswith("src/"):
                    remapped[f"src/main/java/com/example/{k}"] = v
            generated_files.update(remapped)
    else:
        diag.append("SKIPPED SpringBootGenerator: all_parsed is falsy!")

    # ── Include errors as a visible file so user sees what went wrong ─
    if errors:
        error_content = "# Migration Errors\n\n"
        for i, err in enumerate(errors, 1):
            error_content += f"{i}. {err}\n"
        generated_files["MIGRATION-ERRORS.txt"] = error_content

    # ── ALWAYS include diagnostic file ─────────────────────────────
    diag.append(f"\n--- Final state ---")
    diag.append(f"total generated_files: {len(generated_files)}")
    diag.append(f"all keys: {sorted(generated_files.keys())}")
    diag.append(f"errors: {errors}")
    generated_files["MIGRATION-DIAGNOSTIC.txt"] = "\n".join(diag)

    logger.info(
        "engine.complete: files=%d errors=%d unknown=%d",
        len(generated_files), len(errors), len(unknown_elements),
    )

    return {
        "files": generated_files,
        "errors": errors,
        "unknown_elements": unknown_elements,
    }


def _parse_mule_config_yaml(yaml_content: str) -> dict[str, Any]:
    """
    Parse a MuleSoft config.yaml and extract properties useful for
    Spring Boot application.yml generation.

    Returns a dict with structured config sections:
      db      – database connection properties
      http    – HTTP listener properties
      props   – all other key-value properties
    """
    result: dict[str, Any] = {"db": {}, "http": {}, "props": {}}
    if not yaml_content or not yaml_content.strip():
        return result

    try:
        import yaml  # type: ignore[import-untyped]
        data = yaml.safe_load(yaml_content)
    except Exception:
        # Fallback: simple line-based parsing for key: value
        data = {}
        for line in yaml_content.splitlines():
            line = line.strip()
            if ":" in line and not line.startswith("#"):
                key, _, val = line.partition(":")
                data[key.strip()] = val.strip()

    if not isinstance(data, dict):
        return result

    def _flatten(d: dict, prefix: str = "") -> dict:
        out = {}
        for k, v in d.items():
            full = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(_flatten(v, full))
            else:
                out[full] = v
        return out

    flat = _flatten(data)

    # Categorise properties
    db_keywords = ("db", "database", "mysql", "postgres", "oracle", "jdbc",
                   "datasource", "host", "port", "user", "password", "schema", "url")
    http_keywords = ("http", "listener", "port", "host", "basePath")

    for key, val in flat.items():
        key_lower = key.lower()
        if any(kw in key_lower for kw in db_keywords):
            result["db"][key] = val
        elif any(kw in key_lower for kw in http_keywords):
            result["http"][key] = val
        else:
            result["props"][key] = val

    return result


def _generate_application_yml_from_mule_config(
    mule_config: dict[str, Any],
    pom_metadata: dict[str, Any],
    mule_version: str,
) -> str:
    """
    Generate a Spring Boot application.yml from parsed MuleSoft config and
    pom metadata.
    """
    import yaml  # type: ignore[import-untyped]

    spring_config: dict[str, Any] = {
        "spring": {
            "application": {
                "name": pom_metadata.get("artifact_id", "migrated-app"),
            },
        },
        "server": {},
    }

    # Map HTTP port — resolve actual value, skip MuleSoft placeholders
    http_props = mule_config.get("http", {})
    for key, val in http_props.items():
        if "port" in key.lower():
            try:
                port_val = str(val).strip()
                # Skip MuleSoft placeholders like ${http.port}
                if port_val.isdigit():
                    spring_config["server"]["port"] = int(port_val)
                else:
                    spring_config["server"]["port"] = 8081  # default for MuleSoft apps
            except (ValueError, TypeError):
                spring_config["server"]["port"] = 8081
            break
    if "port" not in spring_config["server"]:
        spring_config["server"]["port"] = 8081

    # Map database config — resolve actual values, skip MuleSoft placeholders
    db_props = mule_config.get("db", {})
    if db_props:
        datasource: dict[str, Any] = {}

        def _is_placeholder(v: str) -> bool:
            """Check if value is a MuleSoft placeholder like ${...} or ${secure::...}"""
            return "${" in str(v)

        for key, val in db_props.items():
            key_lower = key.lower()
            val_str = str(val) if val is not None else ""
            if _is_placeholder(val_str):
                continue  # Skip MuleSoft placeholders — they won't resolve in Spring
            if "url" in key_lower or "jdbc" in key_lower:
                datasource["url"] = val_str
            elif "host" in key_lower and "url" not in datasource:
                datasource["_host"] = val_str
            elif "port" in key_lower:
                datasource["_db_port"] = val_str
            elif "user" in key_lower:
                datasource["username"] = val_str
            elif "password" in key_lower:
                datasource["password"] = val_str
            elif "name" in key_lower or "database" in key_lower or "schema" in key_lower:
                datasource["_database"] = val_str

        # Build JDBC URL if not explicitly provided
        if "url" not in datasource and "_host" in datasource:
            host = datasource.pop("_host", "localhost")
            port = datasource.pop("_db_port", "3306")
            db_name = datasource.pop("_database", "mydb")
            datasource["url"] = f"jdbc:mysql://{host}:{port}/{db_name}?useSSL=true&serverTimezone=UTC"
            if not datasource.get("driver-class-name"):
                datasource["driver-class-name"] = "com.mysql.cj.jdbc.Driver"
        else:
            datasource.pop("_host", None)
            datasource.pop("_db_port", None)
            datasource.pop("_database", None)

        if datasource:
            spring_config["spring"]["datasource"] = datasource

    # Map remaining properties
    other_props = mule_config.get("props", {})
    if other_props:
        spring_config["mule-migrated"] = {
            "original-properties": other_props,
        }

    # Add migration metadata as comments via a metadata key
    spring_config["# Migration metadata"] = None
    if mule_version:
        spring_config["migration"] = {
            "source-mule-version": mule_version,
            "group-id": pom_metadata.get("group_id", ""),
        }

    try:
        return yaml.dump(spring_config, default_flow_style=False, sort_keys=False)
    except Exception:
        # Fallback: manual YAML
        lines = [
            f"spring:",
            f"  application:",
            f"    name: {pom_metadata.get('artifact_id', 'migrated-app')}",
            f"server:",
            f"  port: 8080",
        ]
        return "\n".join(lines) + "\n"


def _adapt_java_files_to_spring_package(
    mule_java_files: dict[str, str],
    group_id: str,
    artifact_id: str,
) -> dict[str, str]:
    """
    Take custom Java files from a MuleSoft project and adapt their package
    declarations and paths to a Spring Boot project structure.

    Returns {spring_boot_relative_path: adapted_content}.
    """
    import re

    result: dict[str, str] = {}
    target_base_package = f"{group_id}.{artifact_id}".replace("-", "")
    target_package_path = target_base_package.replace(".", "/")

    for orig_path, content in mule_java_files.items():
        # Extract original class name from the file path
        filename = orig_path.rsplit("/", 1)[-1] if "/" in orig_path else orig_path

        # Determine sub-package from original path (e.g. src/main/java/com/foo/util/X.java -> util)
        # Strip src/main/java/ prefix if present
        rel = orig_path
        if "src/main/java/" in rel:
            rel = rel.split("src/main/java/", 1)[1]

        # Get the directory part (package path)
        if "/" in rel:
            orig_pkg_path = rel.rsplit("/", 1)[0]
            # Try to find a meaningful sub-package (last 1-2 segments)
            segments = orig_pkg_path.split("/")
            # Skip segments that look like the old group/artifact
            sub_pkg_segments = []
            for seg in reversed(segments):
                if seg.lower() in (group_id.split(".")[-1].lower(),
                                   artifact_id.replace("-", "").lower()):
                    break
                sub_pkg_segments.insert(0, seg)
            sub_package = ".".join(sub_pkg_segments) if sub_pkg_segments else "custom"
        else:
            sub_package = "custom"

        full_package = f"{target_base_package}.{sub_package}"
        full_package_path = full_package.replace(".", "/")

        # Update the package declaration in the source
        adapted = re.sub(
            r"^(\s*package\s+)[^;]+;",
            f"\\1{full_package};",
            content,
            count=1,
            flags=re.MULTILINE,
        )

        # Add comment noting migration
        if "// Migrated from MuleSoft" not in adapted:
            adapted = f"// Migrated from MuleSoft project: {orig_path}\n{adapted}"

        spring_path = f"src/main/java/{full_package_path}/{filename}"
        result[spring_path] = adapted

    return result


def _build_raml_context_for_llm(raml_files: dict[str, str]) -> str:
    """
    Build a text summary of RAML files for inclusion in LLM prompts,
    so the LLM can generate better OpenAPI specs and REST controllers.
    """
    if not raml_files:
        return ""

    parts = ["=== RAML API Definitions (from MuleSoft project) ===\n"]
    for name, content in raml_files.items():
        # Truncate very large RAML files
        truncated = content[:8000] if len(content) > 8000 else content
        parts.append(f"--- {name} ---\n{truncated}\n")
    return "\n".join(parts)


def _map_mule_connectors_to_spring_deps(connectors: list[dict]) -> list[str]:
    """
    Map MuleSoft connector artifact IDs to suggested Spring Boot
    dependency strings (groupId:artifactId).
    """
    mapping = {
        "mule-http-connector": "org.springframework.boot:spring-boot-starter-web",
        "mule-db-connector": "org.springframework.boot:spring-boot-starter-jdbc",
        "mule-jms-connector": "org.springframework.boot:spring-boot-starter-activemq",
        "mule-amqp-connector": "org.springframework.boot:spring-boot-starter-amqp",
        "mule-file-connector": "org.springframework:spring-core",
        "mule-ftp-connector": "org.apache.commons:commons-net",
        "mule-sftp-connector": "com.jcraft:jsch",
        "mule-email-connector": "org.springframework.boot:spring-boot-starter-mail",
        "mule-vm-connector": "org.springframework.boot:spring-boot-starter",
        "mule-objectstore-connector": "org.springframework.boot:spring-boot-starter-data-redis",
        "mule-sockets-connector": "org.springframework.boot:spring-boot-starter-websocket",
        "mule-oauth-module": "org.springframework.boot:spring-boot-starter-oauth2-client",
        "mule-apikit-module": "org.springdoc:springdoc-openapi-starter-webmvc-ui",
        "mule-validation-module": "org.springframework.boot:spring-boot-starter-validation",
        "mule-scripting-module": "org.codehaus.groovy:groovy-all",
        "mule-spring-module": "org.springframework.boot:spring-boot-starter",
        "mule-salesforce-connector": "com.force.api:force-partner-api",
    }

    result = set()
    for conn in connectors:
        aid = conn.get("artifactId", "")
        if aid in mapping:
            result.add(mapping[aid])
        else:
            # Add a comment-style suggestion
            result.add(f"# TODO: find Spring equivalent for {aid}")
    return sorted(result)


async def run_migration_pipeline(
    migration_id: str,
    xml_files: dict[str, str],
    config: dict[str, Any],
    llm_config: dict[str, Any] | None = None,
    dataweave_scripts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Full migration pipeline: static engine + optional LLM enhancement.

    This is called from the queue trigger.  The static engine always runs;
    LLM agents are invoked only if ``llm_config.enabled`` is True.

    Enhanced to use extra MuleSoft project files (config.yaml, pom.xml,
    RAML, Java, DataWeave) passed via llm_config for richer output.

    Returns the same shape as ``run_static_migration`` with additional
    ``agent_trace``, ``total_tokens``, and ``total_cost_usd`` keys.
    """
    import time

    start = time.monotonic()
    llm_config = llm_config or {}

    # ── Extract extra MuleSoft context from llm_config ────────────
    mule_config_yaml = llm_config.get("mule_config_yaml", "")
    mule_pom_xml = llm_config.get("mule_pom_xml", "")
    mule_raml = llm_config.get("mule_raml", {})  # {name: content}
    mule_java_files = llm_config.get("mule_java_files", {})  # {name: content}
    mule_global_xml = llm_config.get("mule_global_xml", {})
    mule_log4j2 = llm_config.get("mule_log4j2", "")
    mule_version = llm_config.get("mule_version", "")
    pom_metadata = llm_config.get("pom_metadata", {})
    all_config_files = llm_config.get("all_config_files", {})

    # ── Override config from pom metadata if available ────────────
    if pom_metadata.get("group_id"):
        config["group_id"] = pom_metadata["group_id"]
    if pom_metadata.get("artifact_id"):
        config["artifact_id"] = pom_metadata["artifact_id"]

    # ── Static engine ─────────────────────────────────────────────
    result = run_static_migration(xml_files, config)
    generated_files = result["files"]
    errors = result["errors"]

    agent_trace: dict[str, Any] = {
        "status": "completed",
        "agents_executed": ["static_engine"],
        "agent_results": {
            "static_engine": {
                "status": "success",
                "files_generated": len(generated_files),
                "unknown_elements": len(result["unknown_elements"]),
            }
        },
    }
    total_tokens = 0
    total_cost_usd = 0.0

    # ── Generate application.yml from MuleSoft config ─────────────
    if mule_config_yaml:
        try:
            parsed_config = _parse_mule_config_yaml(mule_config_yaml)
            app_yml = _generate_application_yml_from_mule_config(
                parsed_config, pom_metadata, mule_version,
            )
            if app_yml:
                generated_files["src/main/resources/application.yml"] = app_yml
                agent_trace["agents_executed"].append("config_migration")
                agent_trace["agent_results"]["config_migration"] = {
                    "status": "success",
                    "source": "config.yaml",
                    "db_props_found": len(parsed_config.get("db", {})),
                    "http_props_found": len(parsed_config.get("http", {})),
                    "other_props_found": len(parsed_config.get("props", {})),
                }
                logger.info("engine.config_migrated: db=%d http=%d props=%d",
                            len(parsed_config.get("db", {})),
                            len(parsed_config.get("http", {})),
                            len(parsed_config.get("props", {})))
        except Exception as exc:
            logger.warning("engine.config_migration_failed: %s", exc)
            errors.append(f"Config migration: {exc}")

    # ── Include adapted Java files from MuleSoft project ──────────
    if mule_java_files:
        try:
            adapted = _adapt_java_files_to_spring_package(
                mule_java_files,
                config.get("group_id", "com.example"),
                config.get("artifact_id", "migrated-app"),
            )
            generated_files.update(adapted)
            agent_trace["agents_executed"].append("java_adaptation")
            agent_trace["agent_results"]["java_adaptation"] = {
                "status": "success",
                "files_adapted": len(adapted),
                "original_files": list(mule_java_files.keys()),
            }
            logger.info("engine.java_adapted: %d files", len(adapted))
        except Exception as exc:
            logger.warning("engine.java_adaptation_failed: %s", exc)
            errors.append(f"Java adaptation: {exc}")

    # ── Include DataWeave scripts as reference files ──────────────
    if dataweave_scripts:
        for dw_name, dw_content in dataweave_scripts.items():
            # Place DWL files under a reference directory for the developer
            ref_path = f"src/main/resources/dataweave-reference/{dw_name.rsplit('/', 1)[-1]}"
            generated_files[ref_path] = (
                f"// Original DataWeave script from MuleSoft project: {dw_name}\n"
                f"// TODO: Convert this DataWeave logic to Java/Spring equivalent\n\n"
                f"{dw_content}"
            )
        agent_trace["agents_executed"].append("dataweave_inclusion")
        agent_trace["agent_results"]["dataweave_inclusion"] = {
            "status": "success",
            "scripts_included": len(dataweave_scripts),
        }

    # ── Generate OpenAPI spec from RAML or parsed XML ───────────────
    try:
        from backend.migrator.swagger_generator import (
            generate_from_raml,
            generate_from_parsed_xml,
        )

        openapi_spec = None
        openapi_source = None

        # Also check dataweave_scripts for RAML files (they're often
        # included as reference files but not in mule_raml for JSON endpoint)
        effective_raml = dict(mule_raml) if mule_raml else {}
        if not effective_raml and dataweave_scripts:
            for dw_name, dw_content in dataweave_scripts.items():
                if dw_name.lower().endswith(".raml"):
                    # Strip the "// Original DataWeave..." header if present
                    content = dw_content
                    if content.startswith("//"):
                        lines = content.split("\n")
                        while lines and lines[0].startswith("//"):
                            lines.pop(0)
                        content = "\n".join(lines).lstrip()
                    effective_raml[dw_name] = content

        # Prefer RAML-based generation (more accurate API definition)
        if effective_raml:
            # Find the main RAML file (typically the one with the API title)
            main_raml_content = None
            main_raml_name = None
            for rname, rcontent in effective_raml.items():
                rname_lower = rname.lower()
                # Pick the root .raml file (not a fragment/type/trait)
                if rname_lower.endswith(".raml"):
                    if main_raml_content is None or "title" in rcontent[:500]:
                        main_raml_content = rcontent
                        main_raml_name = rname
            if main_raml_content:
                try:
                    openapi_spec = generate_from_raml(main_raml_content)
                    openapi_source = f"raml:{main_raml_name}"
                    logger.info("engine.openapi_from_raml: %s paths=%d",
                                main_raml_name,
                                len(openapi_spec.get("paths", {})))
                except Exception as raml_exc:
                    logger.warning("engine.openapi_from_raml_failed: %s", raml_exc)

        # Fallback: generate from parsed XML flows
        if openapi_spec is None and all_parsed:
            openapi_spec = generate_from_parsed_xml(
                all_parsed,
                config.get("artifact_id", "migrated-app"),
            )
            openapi_source = "parsed_xml"
            logger.info("engine.openapi_from_xml: paths=%d",
                        len(openapi_spec.get("paths", {})))

        if openapi_spec and openapi_spec.get("paths"):
            import json as _json
            generated_files["openapi.json"] = _json.dumps(openapi_spec, indent=2)
            agent_trace["agents_executed"].append("openapi_generation")
            agent_trace["agent_results"]["openapi_generation"] = {
                "status": "success",
                "source": openapi_source,
                "endpoints": sum(
                    len(methods) for methods in openapi_spec["paths"].values()
                ),
                "paths": len(openapi_spec["paths"]),
            }
    except Exception as exc:
        logger.warning("engine.openapi_generation_failed: %s", exc)
        errors.append(f"OpenAPI generation: {exc}")

    # ── Map MuleSoft connectors to Spring Boot dependencies ───────
    spring_deps_suggestions: list[str] = []
    if pom_metadata.get("connectors"):
        spring_deps_suggestions = _map_mule_connectors_to_spring_deps(
            pom_metadata["connectors"]
        )
        if spring_deps_suggestions:
            # Add a migration-notes.md with dependency mapping
            dep_lines = "\n".join(f"  - {d}" for d in spring_deps_suggestions)
            conn_lines = "\n".join(
                f"  - {c['artifactId']} ({c.get('version', 'N/A')})"
                for c in pom_metadata["connectors"]
            )
            generated_files["MIGRATION-NOTES.md"] = (
                f"# MuleSoft to Spring Boot Migration Notes\n\n"
                f"## Source Project\n"
                f"- **Group ID:** {pom_metadata.get('group_id', 'N/A')}\n"
                f"- **Artifact ID:** {pom_metadata.get('artifact_id', 'N/A')}\n"
                f"- **Version:** {pom_metadata.get('version', 'N/A')}\n"
                f"- **Mule Version:** {mule_version or 'N/A'}\n\n"
                f"## MuleSoft Connectors Detected\n{conn_lines}\n\n"
                f"## Suggested Spring Boot Dependencies\n{dep_lines}\n\n"
                f"## DataWeave Scripts ({len(dataweave_scripts or {})})\n"
                f"DataWeave scripts have been placed in "
                f"`src/main/resources/dataweave-reference/` for manual conversion.\n\n"
                f"## Custom Java Files ({len(mule_java_files)})\n"
                f"Custom Java files have been adapted to the Spring Boot package "
                f"structure. Review them for any MuleSoft-specific API usage.\n"
            )

    # ── RAG context retrieval ─────────────────────────────────────
    rag_context = ""
    # Check both llm_config from frontend/DB AND ENABLE_LLM env var as fallback
    llm_enabled = llm_config.get("enabled", False)
    if not llm_enabled:
        env_llm = os.getenv("ENABLE_LLM", "").lower()
        if env_llm in ("true", "1", "yes"):
            llm_enabled = True
            logger.info("engine.llm_enabled_via_env: ENABLE_LLM=%s (llm_config.enabled was %s)",
                        env_llm, llm_config.get("enabled"))
    logger.info("engine.llm_config_check: enabled=%s provider=%s model=%s config_keys=%s",
                llm_enabled, llm_config.get("provider"), llm_config.get("model"),
                list(llm_config.keys()) if isinstance(llm_config, dict) else type(llm_config).__name__)
    if llm_enabled and generated_files:
        try:
            from rag_service import get_migration_context

            # Combine all XML content to detect patterns
            combined_xml = "\n".join(xml_files.values())
            rag_context = await get_migration_context(combined_xml, top_k=5)
            if rag_context:
                logger.info(
                    "engine.rag_context_retrieved: chars=%d", len(rag_context),
                )
                agent_trace["agents_executed"].append("rag_retrieval")
                agent_trace["agent_results"]["rag_retrieval"] = {
                    "status": "success",
                    "context_length": len(rag_context),
                }
        except Exception as exc:
            logger.warning("engine.rag_retrieval_failed: %s", exc)
            # Non-fatal — continue without RAG context

    # ── Optional LLM enhancement via GitHub Copilot or Azure OpenAI ─
    if llm_enabled and generated_files:
        try:
            from openai import OpenAI

            github_token = os.getenv("GITHUB_TOKEN", "")
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
            azure_key = os.getenv("AZURE_OPENAI_API_KEY", "")

            logger.info("engine.llm_credentials: github_token=%s azure_endpoint=%s azure_key=%s",
                        "SET" if github_token else "EMPTY",
                        "SET" if azure_endpoint else "EMPTY",
                        "SET" if azure_key else "EMPTY")

            client = None
            deployment = "gpt-4.1"
            provider_name = "none"

            # Allow frontend to specify model via llm_config
            requested_model = llm_config.get("model", "")
            requested_provider = llm_config.get("provider", "")

            # Primary: Azure OpenAI (higher rate limits, no daily cap)
            # Fallback: GitHub Copilot Models API (50 req/day limit)
            if azure_endpoint and azure_key and requested_provider != "github_copilot":
                from openai import AzureOpenAI
                client = AzureOpenAI(
                    azure_endpoint=azure_endpoint,
                    api_key=azure_key,
                    api_version="2024-12-01-preview",
                )
                # IMPORTANT: Azure OpenAI uses custom deployment names (e.g. "gpt-41")
                # which differ from the model name ("gpt-4.1"). Always use the env var.
                deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-41")
                provider_name = "azure_openai"
                logger.info("engine.llm_provider: azure_openai deployment=%s (requested_model=%s)",
                            deployment, requested_model)
            elif github_token:
                # Fallback: GitHub Copilot (Models API) — 50 req/day limit
                # GitHub uses standard model names like "gpt-4.1"
                client = OpenAI(
                    base_url="https://models.inference.ai.azure.com",
                    api_key=github_token,
                )
                deployment = requested_model or os.getenv("GITHUB_COPILOT_MODEL", "gpt-4.1")
                provider_name = "github_copilot"
                logger.info("engine.llm_provider: github_copilot model=%s (fallback)", deployment)

            if client:

                # Build the system prompt with RAG context and extra MuleSoft context
                rag_section = ""
                if rag_context:
                    rag_section = (
                        "\n\nHere are relevant migration patterns from our "
                        "knowledge base:\n\n"
                        f"{rag_context}\n\n"
                        "Use these patterns as reference when improving the code."
                    )

                # Build extra context from MuleSoft project files
                extra_context_parts = []
                if mule_config_yaml:
                    extra_context_parts.append(
                        f"=== MuleSoft config.yaml ===\n{mule_config_yaml[:4000]}"
                    )
                if mule_pom_xml:
                    extra_context_parts.append(
                        f"=== MuleSoft pom.xml (dependencies) ===\n{mule_pom_xml[:6000]}"
                    )
                raml_context = _build_raml_context_for_llm(mule_raml)
                if raml_context:
                    extra_context_parts.append(raml_context)
                if dataweave_scripts:
                    dw_summary = "\n".join(
                        f"--- {n} ---\n{c[:2000]}"
                        for n, c in list(dataweave_scripts.items())[:5]
                    )
                    extra_context_parts.append(
                        f"=== DataWeave Scripts ===\n{dw_summary}"
                    )
                if mule_global_xml:
                    gxml_summary = "\n".join(
                        f"--- {n} ---\n{c[:3000]}"
                        for n, c in list(mule_global_xml.items())[:3]
                    )
                    extra_context_parts.append(
                        f"=== MuleSoft Global XML Configs ===\n{gxml_summary}"
                    )

                extra_context = ""
                if extra_context_parts:
                    extra_context = (
                        "\n\nHere is additional context from the original "
                        "MuleSoft project. Use this to generate more accurate "
                        "Spring Boot code:\n\n"
                        + "\n\n".join(extra_context_parts)
                    )

                system_prompt = (
                    "You are an expert Java Spring Boot developer specializing "
                    "in MuleSoft to Spring Boot migrations."
                    f"{rag_section}"
                    f"{extra_context}\n\n"
                    "Review and improve the following generated Java code. "
                    "Fix any syntax errors, add missing imports, improve "
                    "naming conventions, and ensure best practices. "
                    "If RAML API definitions are provided, ensure REST "
                    "controllers match the API specification. "
                    "If DataWeave scripts are provided, add TODO comments "
                    "showing how the transformation logic should be "
                    "implemented in Java. "
                    "Return ONLY the improved Java code, no explanations."
                )

                # Enhance each Java file with LLM review
                java_files = {k: v for k, v in generated_files.items() if k.endswith(".java")}
                agent_trace["agents_executed"].append("llm_enhancement")
                agent_trace["agent_results"]["llm_enhancement"] = {"files": {}}

                # Max ~6000 tokens ≈ ~24000 chars of Java code (leaves room for system prompt)
                _MAX_FILE_CHARS = 20000
                _MAX_RETRIES = 2
                _files_enhanced = 0
                _files_skipped = 0
                _rate_limited = False

                for filepath, content in java_files.items():
                    # Skip if we've been rate-limited (don't burn remaining quota)
                    if _rate_limited:
                        agent_trace["agent_results"]["llm_enhancement"]["files"][filepath] = {
                            "status": "skipped", "reason": "rate_limited",
                        }
                        _files_skipped += 1
                        continue

                    # Truncate very large files to avoid 413 errors
                    file_content = content
                    truncated = False
                    if len(file_content) > _MAX_FILE_CHARS:
                        file_content = file_content[:_MAX_FILE_CHARS]
                        truncated = True
                        logger.info("engine.llm_file_truncated: %s (%d -> %d chars)",
                                    filepath, len(content), _MAX_FILE_CHARS)

                    try:
                        response = None
                        last_exc = None
                        for attempt in range(_MAX_RETRIES + 1):
                            try:
                                response = client.chat.completions.create(
                                    model=deployment,
                                    messages=[
                                        {"role": "system", "content": system_prompt},
                                        {"role": "user", "content": f"File: {filepath}\n\n```java\n{file_content}\n```"},
                                    ],
                                    temperature=0.1,
                                    max_tokens=4096,
                                )
                                break  # Success
                            except Exception as retry_exc:
                                last_exc = retry_exc
                                err_str = str(retry_exc)
                                # Rate limit — stop trying all files
                                if "429" in err_str or "RateLimitReached" in err_str:
                                    if "86400" in err_str or "UserByModelByDay" in err_str:
                                        # Daily limit hit — no point retrying
                                        _rate_limited = True
                                        logger.warning("engine.llm_daily_rate_limit: %s", err_str[:200])
                                        break
                                    # Per-minute limit — wait and retry
                                    if attempt < _MAX_RETRIES:
                                        import time as _time
                                        wait = min(30, 10 * (attempt + 1))
                                        logger.info("engine.llm_rate_limit_retry: attempt %d, wait %ds", attempt + 1, wait)
                                        _time.sleep(wait)
                                        continue
                                # Token limit — try with smaller content
                                if "413" in err_str or "tokens_limit" in err_str:
                                    if not truncated and len(file_content) > 8000:
                                        file_content = file_content[:8000]
                                        truncated = True
                                        logger.info("engine.llm_file_shrink: %s -> 8000 chars", filepath)
                                        continue
                                break  # Other error — don't retry

                        if _rate_limited:
                            agent_trace["agent_results"]["llm_enhancement"]["files"][filepath] = {
                                "status": "skipped", "reason": "daily_rate_limit",
                            }
                            _files_skipped += 1
                            continue

                        if response is None:
                            raise last_exc or RuntimeError("No response from LLM")

                        improved = response.choices[0].message.content or content
                        # Strip markdown code fences if present
                        if improved.startswith("```"):
                            improved = improved.split("\n", 1)[1] if "\n" in improved else improved
                        if improved.endswith("```"):
                            improved = improved.rsplit("```", 1)[0]
                        improved = improved.strip()
                        if improved:
                            generated_files[filepath] = improved
                            _files_enhanced += 1

                        total_tokens += (response.usage.total_tokens if response.usage else 0)
                        total_cost_usd += (response.usage.total_tokens or 0) * 0.00001

                        agent_trace["agent_results"]["llm_enhancement"]["files"][filepath] = {
                            "status": "success",
                            "tokens": response.usage.total_tokens if response.usage else 0,
                            "truncated": truncated,
                        }
                    except Exception as file_exc:
                        logger.warning("engine.llm_file_enhance_failed: %s %s", filepath, file_exc)
                        agent_trace["agent_results"]["llm_enhancement"]["files"][filepath] = {
                            "status": "error", "error": str(file_exc)[:200],
                        }

                logger.info("engine.llm_enhanced: provider=%s total=%d enhanced=%d skipped=%d tokens=%d",
                            provider_name, len(java_files), _files_enhanced, _files_skipped, total_tokens)
            else:
                logger.error("engine.llm_no_provider: GITHUB_TOKEN=%s AZURE_OPENAI_ENDPOINT=%s AZURE_OPENAI_API_KEY=%s",
                             "SET" if github_token else "EMPTY",
                             "SET" if azure_endpoint else "EMPTY",
                             "SET" if azure_key else "EMPTY")
                errors.append("LLM enhancement: No AI provider configured. Set GITHUB_TOKEN or AZURE_OPENAI_ENDPOINT+AZURE_OPENAI_API_KEY in Function App settings.")
        except Exception as exc:
            logger.error("engine.llm_pipeline_failed: %s", exc, exc_info=True)
            errors.append(f"LLM enhancement failed: {exc}")

    duration_ms = int((time.monotonic() - start) * 1000)

    return {
        "files": generated_files,
        "errors": errors,
        "unknown_elements": result["unknown_elements"],
        "agent_trace": agent_trace,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost_usd,
        "duration_ms": duration_ms,
    }
