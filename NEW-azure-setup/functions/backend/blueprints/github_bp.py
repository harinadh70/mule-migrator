"""
GitHub blueprint — Connect repos, push code, manage branches.
"""
from flask import Blueprint, render_template, request, jsonify
from github import GithubException

github_bp = Blueprint('github', __name__)


def _get_service():
    """Create GitHubService from the request's Authorization header or body."""
    from services.github_service import GitHubService

    token = request.headers.get("X-GitHub-Token", "")
    if not token:
        data = request.get_json(silent=True) or {}
        token = data.get("token", "")
    if not token:
        return None
    return GitHubService(token)


@github_bp.route('/github')
def github_page():
    return render_template('github.html')


@github_bp.route('/api/github/connect', methods=['POST'])
def github_connect():
    svc = _get_service()
    if not svc:
        return jsonify({"error": "GitHub token is required"}), 400
    try:
        info = svc.get_user_info()
        return jsonify({"success": True, "user": info})
    except GithubException as e:
        return jsonify({"error": f"Authentication failed: {e.data.get('message', str(e))}"}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@github_bp.route('/api/github/orgs', methods=['GET'])
def github_orgs():
    svc = _get_service()
    if not svc:
        return jsonify({"error": "GitHub token is required"}), 400
    try:
        orgs = svc.list_orgs()
        return jsonify({"success": True, "orgs": orgs})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@github_bp.route('/api/github/repos', methods=['GET'])
def github_repos():
    svc = _get_service()
    if not svc:
        return jsonify({"error": "GitHub token is required"}), 400
    try:
        org = request.args.get("org", "")
        repos = svc.list_repos(org=org or None)
        return jsonify({"success": True, "repos": repos})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@github_bp.route('/api/github/repos/create', methods=['POST'])
def github_create_repo():
    svc = _get_service()
    if not svc:
        return jsonify({"error": "GitHub token is required"}), 400
    data = request.get_json()
    name = data.get("name", "")
    if not name:
        return jsonify({"error": "Repository name is required"}), 400
    try:
        result = svc.create_repo(
            name=name,
            description=data.get("description", ""),
            private=data.get("private", True),
            org=data.get("org") or None,
        )
        return jsonify({"success": True, "repo": result})
    except GithubException as e:
        msg = e.data.get("message", str(e)) if hasattr(e, 'data') else str(e)
        return jsonify({"error": msg}), 422
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@github_bp.route('/api/github/repos/<owner>/<repo>/branches', methods=['GET'])
def github_branches(owner, repo):
    svc = _get_service()
    if not svc:
        return jsonify({"error": "GitHub token is required"}), 400
    try:
        branches = svc.list_branches(owner, repo)
        return jsonify({"success": True, "branches": branches})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@github_bp.route('/api/github/repos/<owner>/<repo>/branches/create', methods=['POST'])
def github_create_branch(owner, repo):
    svc = _get_service()
    if not svc:
        return jsonify({"error": "GitHub token is required"}), 400
    data = request.get_json()
    branch_name = data.get("branchName", "")
    if not branch_name:
        return jsonify({"error": "Branch name is required"}), 400
    try:
        result = svc.create_branch(owner, repo, branch_name, data.get("fromBranch"))
        return jsonify({"success": True, "branch": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@github_bp.route('/api/github/push', methods=['POST'])
def github_push():
    svc = _get_service()
    if not svc:
        return jsonify({"error": "GitHub token is required"}), 400
    data = request.get_json()
    owner = data.get("owner", "")
    repo = data.get("repo", "")
    files = data.get("files", {})
    branch = data.get("branch", "")
    message = data.get("message", "Migration: push generated Spring Boot project")

    if not owner or not repo:
        return jsonify({"error": "Owner and repo are required"}), 400
    if not files:
        return jsonify({"error": "No files to push"}), 400

    try:
        result = svc.push_files(owner, repo, files, branch=branch or None, commit_message=message)
        return jsonify({"success": True, "commit": result})
    except GithubException as e:
        msg = e.data.get("message", str(e)) if hasattr(e, 'data') else str(e)
        return jsonify({"error": msg}), 422
    except Exception as e:
        return jsonify({"error": str(e)}), 500
