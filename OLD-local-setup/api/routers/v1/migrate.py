"""
V1 Legacy migration endpoints — backward-compatible with the original Flask API.

Wraps the synchronous backend migration engine (parser, flow_converter,
spring_generator) in async FastAPI handlers so existing frontend clients
continue to work without modification.

Routes:
  POST  /migrate          → Synchronous migration (returns generated files)
  POST  /validate         → Validate generated code via LLM
  POST  /generate-swagger → Generate OpenAPI spec from MuleSoft XML
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from api.exceptions import ValidationError

router = APIRouter()

# Shared thread pool for blocking backend calls
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="v1-migrate")


# ── Request Schemas ───────────────────────────────────────────────────


class V1MigrateRequest(BaseModel):
    """Payload matching the legacy Flask /api/migrate endpoint."""

    muleXmlFiles: Optional[list[dict[str, Any]]] = Field(
        default=None, description="List of XML files [{name, content}].",
    )
    muleXml: Optional[str] = Field(
        default=None, description="Single MuleSoft XML content string.",
    )
    dataweaveScripts: Optional[dict[str, Any]] = Field(
        default=None, description="DataWeave scripts {name: content}.",
    )
    projectName: str = Field(default="migrated-app", description="Output project name.")
    groupId: str = Field(default="com.example", description="Maven group ID.")
    javaVersion: str = Field(default="17", description="Target Java version.")
    llmConfig: Optional[dict[str, Any]] = Field(
        default=None, description="LLM provider configuration.",
    )


class V1ValidateRequest(BaseModel):
    """Payload for the legacy /api/validate endpoint."""

    files: dict[str, str] = Field(..., description="Generated files to validate.")
    summary: Optional[dict[str, Any]] = Field(default=None, description="Migration summary.")
    llmConfig: dict[str, Any] = Field(..., description="LLM config with provider, model, apiKey.")


class V1SwaggerRequest(BaseModel):
    """Payload for the legacy /api/generate-swagger endpoint."""

    xmlContent: Optional[str] = Field(default=None, description="MuleSoft XML content.")
    ramlContent: Optional[str] = Field(default=None, description="RAML content (alternative).")
    projectName: str = Field(default="migrated-app", description="Project name for the spec title.")


# ── Helper ────────────────────────────────────────────────────────────


async def _run_sync(fn, *args, **kwargs) -> Any:
    """Run a blocking function in the thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: fn(*args, **kwargs))


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post(
    "/migrate",
    summary="Synchronous migration (legacy)",
    description=(
        "Perform a synchronous MuleSoft-to-SpringBoot migration. "
        "This endpoint mirrors the original Flask /api/migrate behavior. "
        "For async migration with progress tracking, use POST /api/v2/migrations."
    ),
)
async def migrate(body: V1MigrateRequest) -> JSONResponse:
    """
    Synchronous migration endpoint.

    Parses MuleSoft XML, converts flows, generates Spring Boot project
    files, and optionally runs LLM validation -- all in a single request.
    """
    xml_files = body.muleXmlFiles or []
    single_xml = body.muleXml or ""

    if not xml_files and single_xml.strip():
        xml_files = [{"name": "main.xml", "content": single_xml}]

    if not xml_files:
        raise ValidationError(
            detail="MuleSoft XML content is required.",
            errors=[{"field": "muleXmlFiles", "message": "No XML files provided."}],
        )

    def _do_migration() -> dict[str, Any]:
        from backend.migrator.parser import MuleSoftParser
        from backend.migrator.flow_converter import FlowConverter
        from backend.migrator.dataweave_converter import DataWeaveConverter
        from backend.migrator.connector_mapper import ConnectorMapper
        from backend.migrator.spring_generator import SpringBootGenerator
        from backend.migrator.llm_validator import validate_code
        from backend.migrator.llm_agent import AgentContext
        from backend.utils import merge_parsed_results, split_comment_separated_xml

        llm_config = body.llmConfig or {}
        llm_enabled = llm_config.get("enabled", False)
        llm_provider = llm_config.get("provider", "")

        agent_context = AgentContext(
            enabled=llm_enabled and bool(llm_provider),
            llm_config=llm_config if llm_enabled else {},
        )

        parser = MuleSoftParser()
        parsed_list: list[dict] = []
        file_names: list[str] = []

        for xml_file in xml_files:
            content = xml_file.get("content", "").strip()
            name = xml_file.get("name", "unknown.xml")
            if not content:
                continue

            if "<!-- File:" in content:
                segments = split_comment_separated_xml(content)
                for seg_name, seg_content in segments:
                    try:
                        parsed_list.append(parser.parse(seg_content, agent_context=agent_context))
                        file_names.append(seg_name)
                    except Exception as e:
                        parsed_list.append({
                            "warnings": [f"Error parsing {seg_name}: {str(e)}"],
                            "global_configs": [], "flows": [], "sub_flows": [],
                            "error_handlers": [], "global_properties": {},
                            "connectors": set(), "batch_jobs": [],
                            "apikit_configs": [], "secure_properties": [],
                            "tls_contexts": [], "caching_strategies": [],
                        })
                        file_names.append(seg_name)
            else:
                try:
                    parsed_list.append(parser.parse(content, agent_context=agent_context))
                    file_names.append(name)
                except Exception as e:
                    return {"error": f"Error parsing {name}: {str(e)}"}

        if not parsed_list:
            return {"error": "No valid XML content found"}

        parsed = parsed_list[0] if len(parsed_list) == 1 else merge_parsed_results(parsed_list)

        dw_converter = DataWeaveConverter()
        converted_dw = {}
        for dw_name, script in (body.dataweaveScripts or {}).items():
            converted_dw[dw_name] = dw_converter.convert(script, agent_context=agent_context)

        connector_mapper = ConnectorMapper()
        connector_info = connector_mapper.map_connectors(parsed, agent_context=agent_context)

        flow_converter = FlowConverter(dw_converter, connector_mapper)
        spring_files = flow_converter.convert(parsed, converted_dw, agent_context=agent_context)

        generator = SpringBootGenerator(
            project_name=body.projectName,
            group_id=body.groupId,
            java_version=body.javaVersion,
        )
        project_files = generator.generate(spring_files, connector_info, parsed)

        ai_summary = agent_context.to_summary()
        summary = {
            "flowsConverted": len(parsed.get("flows", [])),
            "subFlowsConverted": len(parsed.get("sub_flows", [])),
            "connectorsFound": list(connector_info.get("connectors", set())),
            "dataweaveScriptsConverted": len(converted_dw),
            "dependencies": connector_info.get("dependencies", []),
            "warnings": parsed.get("warnings", []) + flow_converter.warnings,
            "xmlFilesProcessed": len(file_names),
            "xmlFileNames": file_names,
            **ai_summary,
        }

        response_data: dict[str, Any] = {
            "success": True,
            "files": project_files,
            "summary": summary,
        }

        # Optional LLM validation
        if llm_enabled and llm_provider:
            try:
                validation = validate_code(
                    provider_name=llm_provider,
                    api_key=llm_config.get("apiKey", ""),
                    model=llm_config.get("model", ""),
                    files=project_files,
                    summary=summary,
                    base_url=llm_config.get("baseUrl", ""),
                )
                response_data["llmValidation"] = validation
            except Exception as e:
                response_data["llmValidation"] = {
                    "overallScore": 0,
                    "summary": f"LLM validation failed: {str(e)}",
                    "issues": [{
                        "severity": "warning", "file": "", "line": "",
                        "message": str(e),
                        "suggestion": "Check your API key and model configuration.",
                    }],
                    "improvements": [], "missingItems": [],
                    "securityIssues": [], "bestPractices": [],
                }

        return response_data

    try:
        result = await _run_sync(_do_migration)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )

    if "error" in result and "success" not in result:
        return JSONResponse(status_code=400, content=result)

    return JSONResponse(content=result)


@router.post(
    "/validate",
    summary="Validate generated code (legacy)",
    description="Run LLM validation on generated Spring Boot files.",
)
async def validate(body: V1ValidateRequest) -> JSONResponse:
    """Validate generated code via the configured LLM provider."""
    llm_config = body.llmConfig
    provider = llm_config.get("provider", "")
    if not provider:
        raise ValidationError(detail="LLM provider is required.")
    if not body.files:
        raise ValidationError(detail="No files to validate.")

    def _do_validate() -> dict[str, Any]:
        from backend.migrator.llm_validator import validate_code

        result = validate_code(
            provider_name=provider,
            api_key=llm_config.get("apiKey", ""),
            model=llm_config.get("model", ""),
            files=body.files,
            summary=body.summary or {},
            base_url=llm_config.get("baseUrl", ""),
        )
        return {"success": True, "validation": result}

    try:
        result = await _run_sync(_do_validate)
        return JSONResponse(content=result)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )


@router.post(
    "/generate-swagger",
    summary="Generate OpenAPI spec (legacy)",
    description="Generate an OpenAPI specification from MuleSoft XML or RAML content.",
)
async def generate_swagger(body: V1SwaggerRequest) -> JSONResponse:
    """Generate OpenAPI spec from MuleSoft XML or RAML."""
    xml_content = body.xmlContent or ""
    raml_content = body.ramlContent or ""

    if not xml_content.strip() and not raml_content.strip():
        raise ValidationError(detail="Either xmlContent or ramlContent is required.")

    def _do_generate() -> dict[str, Any]:
        if raml_content.strip():
            from backend.migrator.swagger_generator import generate_from_raml

            spec = generate_from_raml(raml_content)
            return {"success": True, "spec": spec}
        else:
            from backend.migrator.parser import MuleSoftParser
            from backend.migrator.swagger_generator import generate_from_parsed_xml
            from backend.migrator.llm_agent import AgentContext

            parser = MuleSoftParser()
            parsed = parser.parse(xml_content, agent_context=AgentContext(enabled=False))
            spec = generate_from_parsed_xml(parsed, body.projectName)
            return {"success": True, "spec": spec}

    try:
        result = await _run_sync(_do_generate)
        return JSONResponse(content=result)
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )
