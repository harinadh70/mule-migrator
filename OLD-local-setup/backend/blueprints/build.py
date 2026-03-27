"""
Build & Test blueprint — JAR, WAR, Docker builds with SSE streaming + test execution.
"""
import json
import time
import os
from flask import Blueprint, render_template, request, jsonify, Response, send_file

from services.build_service import (
    check_java, check_docker, check_maven,
    start_build, get_build, get_build_output, cleanup_build,
    DOCKER_PLATFORMS,
)

build_bp = Blueprint('build', __name__)


@build_bp.route('/build')
def build_page():
    return render_template('build.html')


@build_bp.route('/api/build/check-prereqs', methods=['POST'])
def check_prerequisites():
    java = check_java()
    docker = check_docker()
    maven = check_maven()
    return jsonify({
        "success": True,
        "java": java,
        "docker": docker,
        "maven": maven,
        "platforms": {k: v["label"] for k, v in DOCKER_PLATFORMS.items()},
    })


@build_bp.route('/api/build/jar', methods=['POST'])
def build_jar():
    data = request.get_json()
    files = data.get("files", {})
    project_name = data.get("projectName", "migrated-app")
    if not files:
        return jsonify({"error": "No files to build"}), 400
    build_id = start_build(files, build_type="jar", project_name=project_name)
    return jsonify({"success": True, "buildId": build_id})


@build_bp.route('/api/build/war', methods=['POST'])
def build_war():
    data = request.get_json()
    files = data.get("files", {})
    project_name = data.get("projectName", "migrated-app")
    if not files:
        return jsonify({"error": "No files to build"}), 400
    build_id = start_build(files, build_type="war", project_name=project_name)
    return jsonify({"success": True, "buildId": build_id})


@build_bp.route('/api/build/docker', methods=['POST'])
def build_docker():
    data = request.get_json()
    files = data.get("files", {})
    project_name = data.get("projectName", "migrated-app")
    platform = data.get("platform", "linux-amd64")
    if not files:
        return jsonify({"error": "No files to build"}), 400
    build_id = start_build(files, build_type="docker", project_name=project_name, docker_platform=platform)
    return jsonify({"success": True, "buildId": build_id})


@build_bp.route('/api/test/start', methods=['POST'])
def start_tests():
    data = request.get_json()
    files = data.get("files", {})
    project_name = data.get("projectName", "migrated-app")
    if not files:
        return jsonify({"error": "No files to test"}), 400
    build_id = start_build(files, build_type="test", project_name=project_name)
    return jsonify({"success": True, "testId": build_id})


@build_bp.route('/api/build/<build_id>/stream')
def stream_build(build_id):
    """SSE endpoint for streaming build/test output."""
    def generate():
        last_line = 0
        while True:
            info = get_build_output(build_id, from_line=last_line)
            if info is None:
                yield f"data: {json.dumps({'error': 'Build not found'})}\n\n"
                break

            for line in info["lines"]:
                yield f"data: {json.dumps({'line': line})}\n\n"

            last_line = info["total_lines"]

            if info["status"] in ("success", "failed"):
                yield f"data: {json.dumps({'status': info['status'], 'exit_code': info['exit_code'], 'artifact': info.get('artifact_path')})}\n\n"
                break

            time.sleep(0.3)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@build_bp.route('/api/build/<build_id>/artifact')
def download_artifact(build_id):
    build = get_build(build_id)
    if not build:
        return jsonify({"error": "Build not found"}), 404
    artifact = build.get("artifact_path")
    if not artifact or not os.path.exists(artifact):
        return jsonify({"error": "No artifact available"}), 404
    return send_file(artifact, as_attachment=True)


@build_bp.route('/api/build/<build_id>/cleanup', methods=['POST'])
def cleanup(build_id):
    cleanup_build(build_id)
    return jsonify({"success": True})
