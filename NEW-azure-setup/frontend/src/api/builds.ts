import apiClient from "./client";
import type { BuildJob, BuildCreate } from "@/types/build";

export async function createBuild(data: BuildCreate): Promise<BuildJob> {
  const response = await apiClient.post<BuildJob>(
    `/migrations/${data.migrationId}/builds`,
    data
  );
  return response.data;
}

export async function getBuild(id: string): Promise<BuildJob> {
  const response = await apiClient.get<BuildJob>(`/builds/${id}`);
  return response.data;
}

export async function getBuildsForMigration(
  migrationId: string
): Promise<BuildJob[]> {
  const response = await apiClient.get<{ builds: BuildJob[] }>(
    `/migrations/${migrationId}/builds`
  );
  return response.data.builds || [];
}

export async function cancelBuild(id: string): Promise<BuildJob> {
  const response = await apiClient.post<BuildJob>(`/builds/${id}/cancel`);
  return response.data;
}
