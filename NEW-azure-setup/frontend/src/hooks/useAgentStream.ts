import { useEffect } from "react";
import { useWebSocket } from "./useWebSocket";
import { useMigrationStore } from "@/store/migration";
import type { AgentProgress, PipelineStatus } from "@/types/agent";

export function useAgentStream(migrationId: string | undefined) {
  const { on, send } = useWebSocket({
    path: `/ws/migrations/${migrationId}/stream`,
    autoConnect: !!migrationId,
  });

  const {
    setPipelineStatus,
    updateAgentTrace,
    setCurrentMigration,
  } = useMigrationStore();

  useEffect(() => {
    if (!migrationId) return;

    const unsubProgress = on("agent_progress", (data) => {
      const progress = data as AgentProgress;
      updateAgentTrace({
        id: `${migrationId}-${progress.agentType}`,
        migrationId,
        agentType: progress.agentType,
        status: progress.status,
        startedAt: progress.timestamp,
      });
    });

    const unsubPipeline = on("pipeline_status", (data) => {
      const status = data as PipelineStatus;
      setPipelineStatus(status);
    });

    const unsubComplete = on("migration_complete", (data) => {
      const migration = data as Parameters<
        typeof setCurrentMigration
      >[0];
      setCurrentMigration(migration);
    });

    const unsubError = on("migration_error", (data) => {
      const error = data as { message: string };
      useMigrationStore.getState().setError(error.message);
    });

    send("subscribe", { migrationId });

    return () => {
      unsubProgress();
      unsubPipeline();
      unsubComplete();
      unsubError();
    };
  }, [
    migrationId,
    on,
    send,
    setPipelineStatus,
    updateAgentTrace,
    setCurrentMigration,
  ]);
}
