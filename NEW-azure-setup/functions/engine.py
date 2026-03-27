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

    Returns the same shape as ``run_static_migration`` with additional
    ``agent_trace``, ``total_tokens``, and ``total_cost_usd`` keys.
    """
    import time

    start = time.monotonic()

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

    # ── RAG context retrieval ─────────────────────────────────────
    rag_context = ""
    llm_enabled = (llm_config or {}).get("enabled", False)
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

                # Build the system prompt with RAG context
                rag_section = ""
                if rag_context:
                    rag_section = (
                        "\n\nHere are relevant migration patterns from our "
                        "knowledge base:\n\n"
                        f"{rag_context}\n\n"
                        "Use these patterns as reference when improving the code."
                    )

                system_prompt = (
                    "You are an expert Java Spring Boot developer."
                    f"{rag_section}\n\n"
                    "Review and improve the following generated Java code. "
                    "Fix any syntax errors, add missing imports, improve "
                    "naming conventions, and ensure best practices. "
                    "Return ONLY the improved Java code, no explanations."
                )

                # Enhance each Java file with LLM review
                java_files = {k: v for k, v in generated_files.items() if k.endswith(".java")}
                agent_trace = {"status": "completed", "agent_results": {}}

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

                        agent_trace["agent_results"][filepath] = {
                            "status": "success",
                            "tokens": response.usage.total_tokens if response.usage else 0,
                        }
                    except Exception as file_exc:
                        logger.warning("engine.llm_file_enhance_failed: %s %s", filepath, file_exc)
                        agent_trace["agent_results"][filepath] = {"status": "error", "error": str(file_exc)}

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
