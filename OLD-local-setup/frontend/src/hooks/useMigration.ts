import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createMigration,
  getMigration,
  listMigrations,
  cancelMigration,
  deleteMigration,
  getMigrationFiles,
  getMigrationStats,
  getAgentTraces,
} from "@/api/migrations";
import type { MigrationCreate } from "@/types/migration";

export function useMigrationList(params?: {
  page?: number;
  pageSize?: number;
  status?: string;
  search?: string;
}) {
  return useQuery({
    queryKey: ["migrations", params],
    queryFn: () => listMigrations(params),
    refetchInterval: 10_000,
  });
}

export function useMigrationDetail(id: string | undefined) {
  return useQuery({
    queryKey: ["migration", id],
    queryFn: () => getMigration(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "pending" ? 3000 : false;
    },
  });
}

export function useMigrationFiles(migrationId: string | undefined) {
  return useQuery({
    queryKey: ["migrationFiles", migrationId],
    queryFn: () => getMigrationFiles(migrationId!),
    enabled: !!migrationId,
  });
}

export function useMigrationStats() {
  return useQuery({
    queryKey: ["migrationStats"],
    queryFn: getMigrationStats,
    refetchInterval: 30_000,
  });
}

export function useAgentTraces(migrationId: string | undefined) {
  return useQuery({
    queryKey: ["agentTraces", migrationId],
    queryFn: () => getAgentTraces(migrationId!),
    enabled: !!migrationId,
    refetchInterval: (query) => {
      const traces = query.state.data;
      const allDone = traces?.every(
        (t) => t.status === "completed" || t.status === "failed"
      );
      return allDone ? false : 3000;
    },
  });
}

export function useCreateMigration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: MigrationCreate) => createMigration(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["migrations"] });
      queryClient.invalidateQueries({ queryKey: ["migrationStats"] });
    },
  });
}

export function useCancelMigration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => cancelMigration(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: ["migration", id] });
      queryClient.invalidateQueries({ queryKey: ["migrations"] });
    },
  });
}

export function useDeleteMigration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => deleteMigration(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["migrations"] });
      queryClient.invalidateQueries({ queryKey: ["migrationStats"] });
    },
  });
}
