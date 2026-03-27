import { Loader2, CheckCircle, XCircle, Clock, Ban } from "lucide-react";
import type { PipelineStatus } from "@/types/agent";
import { AGENT_LABELS } from "@/types/agent";
import type { Status } from "@/types/common";

interface MigrationProgressProps {
  status: Status;
  pipeline: PipelineStatus | null;
}

export default function MigrationProgress({
  status,
  pipeline,
}: MigrationProgressProps) {
  const progress = status === "completed" ? 100 : status === "failed" ? 100 : (pipeline?.progress ?? 0);

  function getStatusDisplay() {
    switch (status) {
      case "pending":
      case "queued":
        return {
          icon: <Clock className="h-5 w-5 text-gray-400" />,
          label: "Queued",
          color: "text-gray-500",
        };
      case "running":
        return {
          icon: <Loader2 className="h-5 w-5 animate-spin text-blue-500" />,
          label: pipeline?.currentAgent
            ? `Running: ${AGENT_LABELS[pipeline.currentAgent]}`
            : "Running...",
          color: "text-blue-600 dark:text-blue-400",
        };
      case "completed":
        return {
          icon: <CheckCircle className="h-5 w-5 text-green-500" />,
          label: "Migration Complete",
          color: "text-green-600 dark:text-green-400",
        };
      case "failed":
        return {
          icon: <XCircle className="h-5 w-5 text-red-500" />,
          label: "Migration Failed",
          color: "text-red-600 dark:text-red-400",
        };
      case "cancelled":
        return {
          icon: <Ban className="h-5 w-5 text-yellow-500" />,
          label: "Migration Cancelled",
          color: "text-yellow-600 dark:text-yellow-400",
        };
      default:
        return {
          icon: <Clock className="h-5 w-5 text-gray-400" />,
          label: String(status),
          color: "text-gray-500",
        };
    }
  }

  const display = getStatusDisplay();

  function getBarColor() {
    switch (status) {
      case "completed":
        return "bg-green-500";
      case "failed":
        return "bg-red-500";
      case "cancelled":
        return "bg-yellow-500";
      default:
        return "bg-blue-500";
    }
  }

  return (
    <div className="card">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {display.icon}
          <span className={`text-sm font-semibold ${display.color}`}>
            {display.label}
          </span>
        </div>
        <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
          {Math.round(progress)}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${getBarColor()}`}
          style={{ width: `${Math.min(progress, 100)}%` }}
        />
      </div>

      {/* Agent mini-steps */}
      {pipeline && pipeline.agents.length > 0 && (
        <div className="mt-3 flex items-center gap-1">
          {pipeline.agents.map((agent) => {
            let dotColor = "bg-gray-300 dark:bg-gray-600";
            if (agent.status === "completed") dotColor = "bg-green-500";
            else if (agent.status === "running")
              dotColor = "bg-blue-500 animate-pulse";
            else if (agent.status === "failed") dotColor = "bg-red-500";

            return (
              <div key={agent.agentType} className="flex items-center gap-1">
                <div
                  className={`h-2 w-2 rounded-full ${dotColor}`}
                  title={`${AGENT_LABELS[agent.agentType]}: ${agent.status}`}
                />
                <span className="text-[10px] text-gray-400">
                  {AGENT_LABELS[agent.agentType]}
                </span>
                {agent.agentType !== "docs" && (
                  <div className="mx-0.5 h-px w-3 bg-gray-300 dark:bg-gray-600" />
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ETA */}
      {pipeline?.estimatedCompletionAt && status === "running" && (
        <p className="mt-2 text-xs text-gray-400">
          Estimated completion:{" "}
          {new Date(pipeline.estimatedCompletionAt).toLocaleTimeString()}
        </p>
      )}
    </div>
  );
}
