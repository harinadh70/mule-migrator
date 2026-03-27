import { useMemo } from "react";
import {
  Brain,
  Cog,
  Code2,
  ShieldCheck,
  TestTube2,
  FileText,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
  ChevronRight,
} from "lucide-react";
import type { AgentNodeStatus } from "@/types/agent";
import { AGENT_LABELS, type AgentType } from "@/types/agent";
import type { Status } from "@/types/common";

interface AgentPipelineProps {
  agents: AgentNodeStatus[];
  currentAgent?: AgentType;
  onAgentClick?: (agentType: AgentType) => void;
}

const AGENT_ICONS: Record<AgentType, typeof Brain> = {
  planner: Brain,
  engine: Cog,
  coder: Code2,
  reviewer: ShieldCheck,
  tester: TestTube2,
  docs: FileText,
};

function PillStatus({ status }: { status: Status }) {
  switch (status) {
    case "running":
      return <Loader2 className="h-3 w-3 animate-spin text-white" />;
    case "completed":
      return <CheckCircle className="h-3 w-3 text-white" />;
    case "failed":
      return <XCircle className="h-3 w-3 text-white" />;
    default:
      return <Clock className="h-3 w-3 text-gray-400 dark:text-gray-500" />;
  }
}

function AgentPill({
  agent,
  onClick,
}: {
  agent: AgentNodeStatus;
  onClick?: () => void;
}) {
  const Icon = AGENT_ICONS[agent.agentType] || Cog;
  const label = AGENT_LABELS[agent.agentType] || agent.agentType;
  const isActive = agent.status === "running";
  const isComplete = agent.status === "completed";
  const isFailed = agent.status === "failed";
  const isPending = agent.status === "pending" || agent.status === "queued";

  return (
    <button
      onClick={onClick}
      className={`
        group relative inline-flex items-center gap-1.5 rounded-full px-3 py-1.5
        text-xs font-semibold transition-all duration-200 border whitespace-nowrap
        ${isActive
          ? "bg-[#0070AD] text-white border-[#0070AD] shadow-md shadow-[#0070AD]/25 scale-105"
          : isComplete
            ? "bg-emerald-500 text-white border-emerald-500"
            : isFailed
              ? "bg-red-500 text-white border-red-500"
              : "bg-gray-100 dark:bg-white/[0.04] text-gray-400 dark:text-gray-500 border-gray-200 dark:border-white/[0.08]"
        }
        hover:scale-105
      `}
    >
      {isActive && (
        <span className="absolute inset-0 rounded-full animate-ping bg-[#0070AD]/20 pointer-events-none" />
      )}
      <PillStatus status={agent.status} />
      <span className="relative">{label}</span>
      {isComplete && agent.durationMs != null && (
        <span className="text-[10px] opacity-75 font-mono tabular-nums">
          {(agent.durationMs / 1000).toFixed(1)}s
        </span>
      )}
    </button>
  );
}

function Arrow({ active, completed }: { active: boolean; completed: boolean }) {
  return (
    <ChevronRight
      className={`h-3.5 w-3.5 flex-shrink-0 transition-colors duration-200 ${
        completed
          ? "text-emerald-400 dark:text-emerald-500"
          : active
            ? "text-[#0070AD]"
            : "text-gray-300 dark:text-gray-600"
      }`}
    />
  );
}

export default function AgentPipeline({
  agents,
  onAgentClick,
}: AgentPipelineProps) {
  const agentList: AgentNodeStatus[] = useMemo(() => {
    if (agents.length > 0) return agents;
    return (
      ["planner", "engine", "coder", "reviewer", "tester", "docs"] as AgentType[]
    ).map((agentType) => ({
      agentType,
      status: "pending" as Status,
      progress: 0,
    }));
  }, [agents]);

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      {agentList.map((agent, i) => {
        const prevAgent = i > 0 ? agentList[i - 1] : null;
        const isArrowActive = prevAgent?.status === "running";
        const isArrowCompleted = prevAgent?.status === "completed";

        return (
          <div key={agent.agentType} className="flex items-center gap-1.5">
            {i > 0 && (
              <Arrow active={isArrowActive} completed={isArrowCompleted} />
            )}
            <AgentPill
              agent={agent}
              onClick={() => onAgentClick?.(agent.agentType)}
            />
          </div>
        );
      })}
    </div>
  );
}
