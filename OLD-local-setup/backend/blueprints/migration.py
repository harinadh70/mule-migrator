"""
Migration blueprint — Main migration tool, validation, download, DataWeave conversion.
"""
import io
import logging
import zipfile
from flask import Blueprint, render_template, request, jsonify, send_file, Response

from migrator.parser import MuleSoftParser
from migrator.flow_converter import FlowConverter
from migrator.dataweave_converter import DataWeaveConverter
from migrator.connector_mapper import ConnectorMapper
from migrator.spring_generator import SpringBootGenerator
from migrator.llm_validator import get_available_providers, validate_code
from migrator.llm_agent import AgentContext
from utils import merge_parsed_results, split_comment_separated_xml

migration_bp = Blueprint('migration', __name__)


@migration_bp.route('/migrate')
def migrate_page():
    return render_template('migration.html')


@migration_bp.route('/api/llm/providers', methods=['GET'])
def llm_providers():
    return jsonify(get_available_providers())


@migration_bp.route('/api/migrate', methods=['POST'])
def migrate():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    xml_files = data.get("muleXmlFiles", [])
    single_xml = data.get("muleXml", "")

    if not xml_files and single_xml.strip():
        xml_files = [{"name": "main.xml", "content": single_xml}]

    if not xml_files:
        return jsonify({"error": "MuleSoft XML content is required"}), 400

    dataweave_scripts = data.get("dataweaveScripts", {})
    project_name = data.get("projectName", "migrated-app")
    group_id = data.get("groupId", "com.example")
    java_version = data.get("javaVersion", "17")

    llm_config = data.get("llmConfig", {})
    llm_enabled = llm_config.get("enabled", False)
    llm_provider = llm_config.get("provider", "")
    llm_model = llm_config.get("model", "")
    llm_api_key = llm_config.get("apiKey", "")
    llm_base_url = llm_config.get("baseUrl", "")

    try:
        agent_context = AgentContext(
            enabled=llm_enabled and bool(llm_provider),
            llm_config={
                "provider": llm_provider,
                "apiKey": llm_api_key,
                "model": llm_model,
                "baseUrl": llm_base_url,
            } if llm_enabled else {},
        )

        parser = MuleSoftParser()
        parsed_list = []
        file_names = []

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
                    return jsonify({"error": f"Error parsing {name}: {str(e)}"}), 400

        if not parsed_list:
            return jsonify({"error": "No valid XML content found"}), 400

        parsed = parsed_list[0] if len(parsed_list) == 1 else merge_parsed_results(parsed_list)

        dw_converter = DataWeaveConverter()
        converted_dw = {}
        for name, script in dataweave_scripts.items():
            converted_dw[name] = dw_converter.convert(script, agent_context=agent_context)

        connector_mapper = ConnectorMapper()
        connector_info = connector_mapper.map_connectors(parsed, agent_context=agent_context)

        flow_converter = FlowConverter(dw_converter, connector_mapper)
        spring_files = flow_converter.convert(parsed, converted_dw, agent_context=agent_context)

        generator = SpringBootGenerator(
            project_name=project_name,
            group_id=group_id,
            java_version=java_version,
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

        response_data = {
            "success": True,
            "files": project_files,
            "summary": summary,
        }

        if llm_enabled and llm_provider:
            try:
                validation = validate_code(
                    provider_name=llm_provider,
                    api_key=llm_api_key,
                    model=llm_model,
                    files=project_files,
                    summary=summary,
                    base_url=llm_base_url,
                )
                response_data["llmValidation"] = validation
            except Exception as e:
                response_data["llmValidation"] = {
                    "overallScore": 0,
                    "summary": f"LLM validation failed: {str(e)}",
                    "issues": [{
                        "severity": "warning", "file": "", "line": "",
                        "message": str(e),
                        "suggestion": "Check your API key and model configuration."
                    }],
                    "improvements": [], "missingItems": [],
                    "securityIssues": [], "bestPractices": [],
                }

        return jsonify(response_data)

    except Exception as e:
        logging.getLogger("migrator").exception("Migration failed")
        return jsonify({"error": str(e)}), 500


@migration_bp.route('/api/validate', methods=['POST'])
def validate_endpoint():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    files = data.get("files", {})
    summary = data.get("summary", {})
    llm_config = data.get("llmConfig", {})

    provider = llm_config.get("provider", "")
    model = llm_config.get("model", "")
    api_key = llm_config.get("apiKey", "")
    base_url = llm_config.get("baseUrl", "")

    if not provider:
        return jsonify({"error": "LLM provider is required"}), 400
    if not files:
        return jsonify({"error": "No files to validate"}), 400

    try:
        result = validate_code(
            provider_name=provider,
            api_key=api_key,
            model=model,
            files=files,
            summary=summary,
            base_url=base_url,
        )
        return jsonify({"success": True, "validation": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@migration_bp.route('/api/migrate/download', methods=['POST'])
def download_project():
    data = request.get_json()
    files = data.get("files", {})
    project_name = data.get("projectName", "migrated-app")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath, content in files.items():
            zf.writestr(f"{project_name}/{filepath}", content)

    buffer.seek(0)
    return send_file(
        buffer,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{project_name}.zip",
    )


@migration_bp.route('/api/convert/dataweave', methods=['POST'])
def convert_dataweave():
    data = request.get_json()
    script = data.get("script", "")
    if not script.strip():
        return jsonify({"error": "DataWeave script is required"}), 400

    try:
        converter = DataWeaveConverter()
        result = converter.convert(script)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
