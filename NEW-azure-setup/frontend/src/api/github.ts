import apiClient from "./client";

export interface GitHubRepo {
  id: number;
  name: string;
  fullName: string;
  htmlUrl: string;
  description?: string;
  private: boolean;
  defaultBranch: string;
}

export interface PushRequest {
  migrationId: string;
  repoName: string;
  commitMessage: string;
  isPrivate: boolean;
  branch?: string;
  createRepo?: boolean;
  token?: string;
}

export interface PushResponse {
  success: boolean;
  repoUrl: string;
  commitSha: string;
  branch: string;
  filesPushed: number;
}

export async function pushToGithub(data: PushRequest): Promise<PushResponse> {
  const { token } = data;
  const body = {
    migration_id: data.migrationId,
    repo_name: data.repoName,
    commit_message: data.commitMessage,
    is_private: data.isPrivate,
    branch: data.branch || "main",
    create_repo: data.createRepo ?? true,
  };
  const response = await apiClient.post<PushResponse>("/github/push", body, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  return response.data;
}

export async function listRepos(): Promise<GitHubRepo[]> {
  const response = await apiClient.get<GitHubRepo[]>("/github/repos");
  return response.data;
}

export async function createRepo(data: {
  name: string;
  description?: string;
  isPrivate: boolean;
}): Promise<GitHubRepo> {
  const response = await apiClient.post<GitHubRepo>("/github/repos", data);
  return response.data;
}

export async function getGitHubStatus(): Promise<{
  connected: boolean;
  username?: string;
  avatarUrl?: string;
}> {
  const response = await apiClient.get("/github/status");
  return response.data;
}
