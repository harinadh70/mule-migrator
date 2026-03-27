"""
GitHub API service — wraps PyGithub for repository operations.

Supports:
  - Listing user/org repos
  - Creating repositories
  - Pushing files via Git Data API (no local git needed)
  - Branch management
"""
import base64
from github import Github, GithubException, InputGitTreeElement


class GitHubService:
    """Stateless service — token passed per request, never stored."""

    def __init__(self, token):
        self._gh = Github(token)
        self._user = None

    @property
    def user(self):
        if self._user is None:
            self._user = self._gh.get_user()
        return self._user

    def get_user_info(self):
        u = self.user
        return {
            "login": u.login,
            "name": u.name,
            "avatar_url": u.avatar_url,
            "public_repos": u.public_repos,
            "private_repos": u.owned_private_repos,
        }

    def list_orgs(self):
        orgs = self.user.get_orgs()
        return [{"login": o.login, "avatar_url": o.avatar_url, "description": o.description or ""} for o in orgs]

    def list_repos(self, org=None, sort="updated"):
        if org:
            org_obj = self._gh.get_organization(org)
            repos = org_obj.get_repos(sort=sort)
        else:
            repos = self.user.get_repos(sort=sort)

        result = []
        for r in repos[:50]:  # Limit to 50
            result.append({
                "full_name": r.full_name,
                "name": r.name,
                "private": r.private,
                "description": r.description or "",
                "default_branch": r.default_branch,
                "html_url": r.html_url,
                "language": r.language or "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
                "stargazers_count": r.stargazers_count,
            })
        return result

    def list_branches(self, owner, repo):
        repo_obj = self._gh.get_repo(f"{owner}/{repo}")
        branches = repo_obj.get_branches()
        return [{"name": b.name, "sha": b.commit.sha} for b in branches]

    def create_repo(self, name, description="", private=True, org=None):
        if org:
            org_obj = self._gh.get_organization(org)
            repo = org_obj.create_repo(
                name=name, description=description, private=private,
                auto_init=True,
            )
        else:
            repo = self.user.create_repo(
                name=name, description=description, private=private,
                auto_init=True,
            )
        return {
            "full_name": repo.full_name,
            "html_url": repo.html_url,
            "default_branch": repo.default_branch,
        }

    def push_files(self, owner, repo_name, files, branch=None, commit_message="Migration: push generated Spring Boot project"):
        """Push multiple files to a repo using the Git Data API.

        Args:
            owner: repo owner (user or org)
            repo_name: repository name
            files: dict of {filepath: content}
            branch: target branch (defaults to repo default branch)
            commit_message: commit message
        """
        repo = self._gh.get_repo(f"{owner}/{repo_name}")
        if not branch:
            branch = repo.default_branch

        # Get the reference for the branch
        ref = repo.get_git_ref(f"heads/{branch}")
        base_sha = ref.object.sha

        # Get the base tree
        base_tree = repo.get_git_tree(base_sha)

        # Build tree elements
        tree_elements = []
        for filepath, content in files.items():
            blob = repo.create_git_blob(content, "utf-8")
            tree_elements.append(InputGitTreeElement(
                path=filepath,
                mode="100644",
                type="blob",
                sha=blob.sha,
            ))

        # Create the new tree
        new_tree = repo.create_git_tree(tree_elements, base_tree)

        # Create the commit
        parent = repo.get_git_commit(base_sha)
        new_commit = repo.create_git_commit(commit_message, new_tree, [parent])

        # Update the reference
        ref.edit(new_commit.sha)

        return {
            "sha": new_commit.sha,
            "message": commit_message,
            "html_url": f"{repo.html_url}/commit/{new_commit.sha}",
            "files_pushed": len(files),
        }

    def create_branch(self, owner, repo_name, branch_name, from_branch=None):
        repo = self._gh.get_repo(f"{owner}/{repo_name}")
        if not from_branch:
            from_branch = repo.default_branch

        source = repo.get_git_ref(f"heads/{from_branch}")
        repo.create_git_ref(f"refs/heads/{branch_name}", source.object.sha)

        return {"name": branch_name, "sha": source.object.sha}
