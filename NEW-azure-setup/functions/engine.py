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

    # ── Parse and convert each XML file ───────────────────────────
    for filename, xml_content in xml_files.items():
        try:
            # XXE protection
            validate_xml_safe(xml_content)

            parsed = parser.parse(xml_content)
            if parsed is None:
                errors.append(f"File {filename}: parser returned None")
                continue

            all_parsed = parsed

            converter = FlowConverter(dw_converter, mapper)
            conversion_result = converter.convert(parsed, {})

            if isinstance(conversion_result, dict):
                files_dict = conversion_result.get("files", {})
                if not files_dict:
                    for k, v in conversion_result.items():
                        if isinstance(v, str) and ("." in k or "/" in k):
                            files_dict[k] = v
                generated_files.update(files_dict)
                unknown_elements.extend(
                    conversion_result.get("unknown_elements", [])
                )
        except ValueError as exc:
            # XXE or parse error — propagate as validation failure
            raise
        except Exception as exc:
            logger.warning("engine.file_failed: %s — %s", filename, exc)
            errors.append(f"File {filename}: {exc}")

    # ── Generate Spring Boot project skeleton ─────────────────────
    if all_parsed:
        try:
            generator = SpringBootGenerator(
                project_name=artifact_id,
                group_id=group_id,
                java_version=java_version,
            )
            connector_info = mapper.map_connectors(all_parsed)
            project_files = generator.generate(
                generated_files,
                connector_info,
                all_parsed,
            )
            if isinstance(project_files, dict):
                for k, v in project_files.items():
                    if isinstance(v, str):
                        generated_files[k] = v
        except Exception as exc:
            logger.warning("engine.generate_failed: %s", exc)
            errors.append(f"Spring generation: {exc}")

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

    # Map HTTP port
    http_props = mule_config.get("http", {})
    for key, val in http_props.items():
        if "port" in key.lower():
            try:
                # Handle Mule property placeholders like ${http.port}
                port_val = str(val).strip()
                if port_val.isdigit():
                    spring_config["server"]["port"] = int(port_val)
                else:
                    spring_config["server"]["port"] = 8080  # default
            except (ValueError, TypeError):
                spring_config["server"]["port"] = 8080
            break
    if "port" not in spring_config["server"]:
        spring_config["server"]["port"] = 8080

    # Map database config
    db_props = mule_config.get("db", {})
    if db_props:
        datasource: dict[str, Any] = {}
        for key, val in db_props.items():
            key_lower = key.lower()
            val_str = str(val) if val is not None else ""
            if "url" in key_lower or "jdbc" in key_lower:
                datasource["url"] = val_str
            elif "host" in key_lower and "url" not in datasource:
                datasource["_host"] = val_str
            elif "port" in key_lower and "database" in key_lower.replace("port", ""):
                datasource["_db_port"] = val_str
            elif "user" in key_lower:
                datasource["username"] = val_str
            elif "password" in key_lower:
                datasource["password"] = val_str
            elif "database" in key_lower or "schema" in key_lower:
                datasource["_database"] = val_str

        # Build JDBC URL if not explicitly provided
        if "url" not in datasource and "_host" in datasource:
            host = datasource.pop("_host", "localhost")
            port = datasource.pop("_db_port", "3306")
            db_name = datasource.pop("_database", "mydb")
            datasource["url"] = f"jdbc:mysql://{host}:{port}/{db_name}"
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
    llm_enabled = llm_config.get("enabled", False)
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

    # ── Optional LLM enhancement via Azure OpenAI ──────────────────
    if llm_enabled and generated_files:
        try:
            from openai import AzureOpenAI

            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
            api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
            deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT", "gpt-4.1")

            if endpoint and api_key:
                client = AzureOpenAI(
                    azure_endpoint=endpoint,
                    api_key=api_key,
                    api_version="2024-12-01-preview",
                )

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

                for filepath, content in java_files.items():
                    try:
                        response = client.chat.completions.create(
                            model=deployment,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": f"File: {filepath}\n\n```java\n{content}\n```"},
                            ],
                            temperature=0.1,
                            max_tokens=4000,
                        )
                        improved = response.choices[0].message.content or content
                        # Strip markdown code fences if present
                        if improved.startswith("```"):
                            improved = improved.split("\n", 1)[1] if "\n" in improved else improved
                        if improved.endswith("```"):
                            improved = improved.rsplit("```", 1)[0]
                        improved = improved.strip()
                        if improved:
                            generated_files[filepath] = improved

                        total_tokens += (response.usage.total_tokens if response.usage else 0)
                        total_cost_usd += (response.usage.total_tokens or 0) * 0.00001  # ~$0.01/1K tokens

                        agent_trace["agent_results"]["llm_enhancement"]["files"][filepath] = {
                            "status": "success",
                            "tokens": response.usage.total_tokens if response.usage else 0,
                        }
                    except Exception as file_exc:
                        logger.warning("engine.llm_file_enhance_failed: %s %s", filepath, file_exc)
                        agent_trace["agent_results"]["llm_enhancement"]["files"][filepath] = {
                            "status": "error", "error": str(file_exc),
                        }

                logger.info("engine.llm_enhanced: files=%d tokens=%d", len(java_files), total_tokens)
            else:
                errors.append("LLM enhancement: Azure OpenAI not configured")
        except Exception as exc:
            logger.warning("engine.llm_pipeline_failed: %s", exc)
            errors.append(f"LLM enhancement: {exc}")

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
