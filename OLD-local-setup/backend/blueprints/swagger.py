"""
Swagger blueprint — OpenAPI generation from RAML or MuleSoft XML.
"""
import json
import yaml
from flask import Blueprint, render_template, request, jsonify, Response

from migrator.swagger_generator import generate_from_parsed_xml, generate_from_raml
from migrator.parser import MuleSoftParser
from migrator.llm_agent import AgentContext

swagger_bp = Blueprint('swagger', __name__)


@swagger_bp.route('/swagger')
def swagger_page():
    return render_template('swagger.html')


@swagger_bp.route('/api/swagger/from-xml', methods=['POST'])
def swagger_from_xml():
    """Generate OpenAPI from MuleSoft XML."""
    data = request.get_json()
    xml_content = data.get("xmlContent", "")
    project_name = data.get("projectName", "migrated-app")

    if not xml_content.strip():
        return jsonify({"error": "XML content is required"}), 400

    try:
        parser = MuleSoftParser()
        parsed = parser.parse(xml_content, agent_context=AgentContext(enabled=False))
        spec = generate_from_parsed_xml(parsed, project_name)
        return jsonify({"success": True, "spec": spec})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@swagger_bp.route('/api/swagger/from-raml', methods=['POST'])
def swagger_from_raml():
    """Generate OpenAPI from RAML content."""
    data = request.get_json()
    raml_content = data.get("ramlContent", "")

    if not raml_content.strip():
        return jsonify({"error": "RAML content is required"}), 400

    try:
        spec = generate_from_raml(raml_content)
        return jsonify({"success": True, "spec": spec})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@swagger_bp.route('/api/swagger/from-migration', methods=['POST'])
def swagger_from_migration():
    """Generate OpenAPI from stored migration result (parsed data).

    Accepts multiple data shapes:
      1. { parsedData: { flows: [...], configurations: [...] } }  — direct parsed output
      2. { parsedData: { summary: { flows: [...] } } }           — wrapped in summary
      3. { summary: { flows: [...] } }                           — summary at top level
      4. { parsedData: { endpoints: [...] } }                    — endpoints list (converted to flows)
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON body provided"}), 400

    parsed_data = data.get("parsedData", {})
    project_name = data.get("projectName", "migrated-app")

    # Normalise: accept various shapes and unify into {flows: [...]}
    if not parsed_data:
        # Try top-level summary
        parsed_data = data.get("summary", {})

    if not parsed_data:
        return jsonify({"error": "No parsed data provided"}), 400

    # If parsedData wraps a summary object that holds the flows, unwrap it
    if "flows" not in parsed_data and "summary" in parsed_data:
        inner = parsed_data["summary"]
        if isinstance(inner, dict) and "flows" in inner:
            # Merge inner summary into parsed_data, keeping other top-level keys
            merged = dict(parsed_data)
            merged.update(inner)
            parsed_data = merged

    # Support an "endpoints" list as an alternative to "flows"
    if "flows" not in parsed_data and "endpoints" in parsed_data:
        endpoints = parsed_data["endpoints"]
        if isinstance(endpoints, list):
            # Convert endpoint objects into the flow shape the generator expects
            flows = []
            for ep in endpoints:
                if not isinstance(ep, dict):
                    continue
                flow = {
                    "name": ep.get("name", ep.get("operationId", "unknown")),
                    "source": {
                        "type": "http-listener",
                        "path": ep.get("path", ep.get("uri", "/")),
                        "method": ep.get("method", "GET"),
                    },
                    "processors": ep.get("processors", []),
                }
                flows.append(flow)
            parsed_data["flows"] = flows

    try:
        spec = generate_from_parsed_xml(parsed_data, project_name)
        return jsonify({"success": True, "spec": spec})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@swagger_bp.route('/api/swagger/download', methods=['POST'])
def swagger_download():
    """Download OpenAPI spec as YAML or JSON."""
    data = request.get_json()
    spec = data.get("spec", {})
    fmt = data.get("format", "yaml")

    if fmt == "json":
        content = json.dumps(spec, indent=2)
        mime = "application/json"
        filename = "openapi.json"
    else:
        content = yaml.dump(spec, default_flow_style=False, sort_keys=False, allow_unicode=True)
        mime = "text/yaml"
        filename = "openapi.yaml"

    return Response(
        content,
        mimetype=mime,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
