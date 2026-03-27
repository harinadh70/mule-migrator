import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Clock,
  Coins,
  Star,
  Database,
  MessageSquare,
  AlertCircle,
} from "lucide-react";
import type { AgentTrace } from "@/types/agent";
import { AGENT_LABELS, AGENT_DESCRIPTIONS, type AgentType } from "@/types/agent";
import type { Status } from "@/types/common";

interface AgentDetailProps {
  trace: AgentTrace;
}

function StatusDot({ status }: { status: Status }) {
  const colors: Record<string, string> = {
    pending: "bg-gray-400",
    queued: "bg-gray-400",
    running: "bg-blue-500 animate-pulse",
    completed: "bg-green-500",
    failed: "bg-red-500",
    cancelled: "bg-yellow-500",
  };

  return (
    <span className={`inline-block h-2.5 w-2.5 rounded-full ${colors[status]}`} />
  );
}

export default function AgentDetail({ trace }: AgentDetailProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-lg border border-gray-200 bg-white transition-all dark:border-gray-700 dark:bg-gray-800">
      {/* Header - always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <div className="flex items-center gap-3">
          <StatusDot status={trace.status} />
          <div>
            <h4 className="font-medium text-gray-900 dark:text-white">
              {AGENT_LABELS[trace.agentType as AgentType]}
            </h4>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {AGENT_DESCRIPTIONS[trace.agentType as AgentType]}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {trace.durationMs != null && (
            <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
              <Clock className="h-3.5 w-3.5" />
              {(trace.durationMs / 1000).toFixed(1)}s
            </span>
          )}
          {trace.tokensUsed != null && (
            <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
              <Coins className="h-3.5 w-3.5" />
              {trace.tokensUsed.toLocaleString()}
            </span>
          )}
          {trace.score != null && (
            <span className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
              <Star className="h-3.5 w-3.5" />
              {trace.score.toFixed(2)}
            </span>
          )}
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-gray-400" />
          ) : (
            <ChevronDown className="h-4 w-4 text-gray-400" />
          )}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="space-y-4 border-t border-gray-200 p-4 dark:border-gray-700">
          {/* Error */}
          {trace.error && (
            <div className="flex items-start gap-2 rounded-lg bg-red-50 p-3 dark:bg-red-900/20">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-red-500" />
              <pre className="whitespace-pre-wrap text-sm text-red-700 dark:text-red-300">
                {trace.error}
              </pre>
            </div>
          )}

          {/* RAG Context */}
          {trace.ragContext && trace.ragContext.length > 0 && (
            <div>
              <h5 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-gray-700 dark:text-gray-300">
                <Database className="h-4 w-4" />
                RAG Context ({trace.ragContext.length} sources)
              </h5>
              <div className="space-y-2">
                {trace.ragContext.map((ctx, idx) => (
                  <div
                    key={idx}
                    className="rounded-lg bg-gray-50 p-3 dark:bg-gray-700/50"
                  >
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-xs font-medium text-brand-600 dark:text-brand-400">
                        {ctx.collection}
                      </span>
                      <span className="text-xs text-gray-400">
                        Score: {ctx.score.toFixed(3)}
                      </span>
                    </div>
                    <p className="line-clamp-3 text-xs text-gray-600 dark:text-gray-300">
                      {ctx.snippet}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Prompt */}
          {trace.prompt && (
            <div>
              <h5 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-gray-700 dark:text-gray-300">
                <MessageSquare className="h-4 w-4" />
                Prompt
              </h5>
              <pre className="max-h-48 overflow-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-300">
                {trace.prompt}
              </pre>
            </div>
          )}

          {/* Response */}
          {trace.response && (
            <div>
              <h5 className="mb-2 text-sm font-medium text-gray-700 dark:text-gray-300">
                Response
              </h5>
              <pre className="max-h-48 overflow-auto rounded-lg bg-gray-900 p-3 text-xs text-gray-300">
                {trace.response}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
