"""
GitHub Service — push generated Spring Boot files to a GitHub repository.

Uses PyGithub with the user's Personal Access Token (stored in Key Vault
or passed per-request).
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Any, Optional

from github import Github, GithubException, InputGitTreeElement

logger = logging.getLogger("github_service")


# ---------------------------------------------------------------------------
#  PAT retrieval
# ---------------------------------------------------------------------------

async def _get_pat_from_keyvault(secret_name: str = "github-pat") -> Optional[str]:
    """Attempt to retrieve the GitHub PAT from Azure Key Vault."""
    key_vault_uri = os.getenv("KEY_VAULT_URI", "")
    if not key_vault_uri:
        return None
    try:
        from azure.identity.aio import DefaultAzureCredential
        from azure.keyvault.secrets.aio import SecretClient

        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=key_vault_uri, credential=credential)
        try:
            secret = await client.get_secret(secret_name)
            return secret.value
        finally:
            await client.close()
            await credential.close()
    except Exception as exc:
        logger.warning("keyvault.github_pat_failed: %s", exc)
        return None


def _get_github_client(pat: str) -> Github:
    """Create an authenticated GitHub client."""
    return Github(pat)


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

async def push_to_github(
    files: dict[str, str],
    repo_name: str,
    branch: str = "main",
    commit_message: str = "feat: add migrated Spring Boot project",
    pat: Optional[str] = None,
    base_path: str = "",
) -> dict[str, Any]:
    """
    Push generated files to a GitHub repository.

    Args:
        files:          {relative_path: content} mapping.
        repo_name:      Full repo name, e.g. ``owner/repo``.
        branch:         Target branch name.
        commit_message: Git commit message.
        pat:            GitHub Personal Access Token.  Falls back to
                        Key Vault secret ``github-pat``.
        base_path:      Optional subdirectory prefix inside the repo.

    Returns:
        Dict with ``commit_sha``, ``commit_url``, ``files_pushed``.

    Raises:
        ValueError: If no PAT is available or the repo is not accessible.
        GithubException: On GitHub API errors.
    """
    # Resolve PAT
    if not pat:
        pat = await _get_pat_from_keyvault()
    if not pat:
        pat = os.getenv("GITHUB_PAT", "")
    if not pat:
        raise ValueError(
            "No GitHub PAT provided and Key Vault lookup failed. "
            "Pass a PAT in the request body or store one in Key Vault."
        )

    g = _get_github_client(pat)

    try:
        repo = g.get_repo(repo_name)
    except GithubException as exc:
        raise ValueError(f"Cannot access repository '{repo_name}': {exc}") from exc

    # Get or create the target branch
    try:
        ref = repo.get_git_ref(f"heads/{branch}")
        base_sha = ref.object.sha
    except GithubException:
        # Branch doesn't exist — create from default branch
        default_branch = repo.default_branch
        default_ref = repo.get_git_ref(f"heads/{default_branch}")
        base_sha = default_ref.object.sha
        repo.create_git_ref(f"refs/heads/{branch}", base_sha)
        ref = repo.get_git_ref(f"heads/{branch}")

    # Build the Git tree
    tree_elements = []
    for rel_path, content in files.items():
        full_path = f"{base_path}/{rel_path}" if base_path else rel_path
        # Normalise path separators
        full_path = full_path.replace("\\", "/").lstrip("/")

        tree_elements.append(
            InputGitTreeElement(
                path=full_path,
                mode="100644",
                type="blob",
                content=content,
            )
        )

    if not tree_elements:
        raise ValueError("No files to push.")

    # Create tree and commit
    base_tree = repo.get_git_tree(base_sha)
    new_tree = repo.create_git_tree(tree_elements, base_tree)
    parent_commit = repo.get_git_commit(base_sha)
    new_commit = repo.create_git_commit(
        message=commit_message,
        tree=new_tree,
        parents=[parent_commit],
    )

    # Update branch ref
    ref.edit(sha=new_commit.sha)

    result = {
        "commit_sha": new_commit.sha,
        "commit_url": f"https://github.com/{repo_name}/commit/{new_commit.sha}",
        "branch": branch,
        "repo": repo_name,
        "files_pushed": len(tree_elements),
    }

    logger.info(
        "github.pushed: repo=%s branch=%s files=%d sha=%s",
        repo_name, branch, len(tree_elements), new_commit.sha[:8],
    )
    return result
