import { useState, useEffect, useRef } from "react";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle,
  XCircle,
  Clock,
  Loader2,
  Brain,
  Cog,
  Code2,
  ShieldCheck,
  TestTube2,
  FileText,
  Zap,
  TrendingUp,
  AlertTriangle,
} from "lucide-react";
import AgentThinking from "./AgentThinking";
import type { AgentType } from "@/types/agent";
import { AGENT_LABELS } from "@/types/agent";

/* ── Types ──────────────────────────────────────────────── */

interface AgentResult {
  status: string;
  tokens?: number;
  error?: string;
  duration_ms?: number;
  files_enhanced?: string[];
  findings?: string[];
}

interface AgentLiveFeedProps {
  agentTrace: {
    status: string;
    agent_results?: Record<string, AgentResult>;
  };
  summary: {
    status: string;
    total_files: number;
    errors: string[];
  };
  totalTokens: number;
  totalCost: number;
  durationMs: number;
  migrationStatus: string; // queued, running, completed, failed
}

/* ── Constants ──────────────────────────────────────────── */

const AGENT_ICON_MAP: Record<string, typeof Brain> = {
  planner: Brain,
  engine: Cog,
  static_engine: Cog,
  coder: Code2,
  ai_coder: Code2,
  reviewer: ShieldCheck,
  tester: TestTube2,
  docs: FileText,
};

const AGENT_DISPLAY_NAMES: Record<string, string> = {
  planner: "Planner Agent",
  engine: "Static Engine",
  static_engine: "Static Engine",
  coder: "AI Coder (GPT-4.1)",
  ai_coder: "AI Coder (GPT-4.1)",
  reviewer: "Code Reviewer",
  tester: "Test Generator",
  docs: "Documentation Generator",
};

const AGENT_THINKING_MESSAGES: Record<string, string> = {
  planner: "Analyzing XML structure",
  engine: "Parsing MuleSoft XML",
  static_engine: "Parsing MuleSoft XML",
  coder: "Enhancing code with AI",
  ai_coder: "Enhancing code with AI",
  reviewer: "Reviewing generated code",
  tester: "Generating test cases",
  docs: "Writing documentation",
};

const AGENT_ORDER = ["planner", "engine", "static_engine", "coder", "ai_coder", "reviewer", "tester", "docs"];

function getAgentSortKey(agentKey: string): number {
  const idx = AGENT_ORDER.indexOf(agentKey);
  return idx >= 0 ? idx : 99;
}

/* ── Sub-components ─────────────────────────────────────── */

function StatusIcon({ status }: { status: string }) {
  switch (status) {
    case "completed":
    case "success":
      return <CheckCircle className="h-4 w-4 text-emerald-500 flex-shrink-0" />;
    case "failed":
    case "error":
      return <XCircle className="h-4 w-4 text-red-500 flex-shrink-0" />;
    case "running":
      return <Loader2 className="h-4 w-4 text-[#0070AD] animate-spin flex-shrink-0" />;
    default:
      return <Clock className="h-4 w-4 text-gray-400 dark:text-gray-600 flex-shrink-0" />;
  }
}

function DurationBadge({ ms }: { ms?: number }) {
  if (ms == null) return null;
  return (
    <span className="ml-auto text-xs font-mono tabular-nums text-gray-400 dark:text-gray-500 flex-shrink-0">
      {(ms / 1000).toFixed(1)}s
    </span>
  );
}

function TreeLine({ isLast, children }: { isLast: boolean; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-0 pl-6">
      <span className="flex-shrink-0 text-gray-300 dark:text-gray-600 font-mono text-xs leading-6 select-none w-4">
        {isLast ? "\u2514\u2500" : "\u251C\u2500"}
      </span>
      <span className="text-sm text-gray-600 dark:text-gray-400 leading-6 min-w-0">
        {children}
      </span>
    </div>
  );
}

function ArrowItem({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-0 pl-10">
      <span className="flex-shrink-0 text-[#0070AD] dark:text-[#12ABDB] font-mono text-xs leading-6 select-none w-5">
        {"\u2192"}{" "}
      </span>
      <span className="text-sm text-[#0070AD] dark:text-[#12ABDB] leading-6 min-w-0">
        {children}
      </span>
    </div>
  );
}

/* ── AgentSection ───────────────────────────────────────── */

function AgentSection({
  agentKey,
  result,
  isRunning,
  defaultExpanded,
}: {
  agentKey: string;
  result: AgentResult;
  isRunning: boolean;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const Icon = AGENT_ICON_MAP[agentKey] || Cog;
  const displayName = AGENT_DISPLAY_NAMES[agentKey] || AGENT_LABELS[agentKey as AgentType] || agentKey;

  const isComplete = result.status === "completed" || result.status === "success";
  const isFailed = result.status === "failed" || result.status === "error";
  const isActive = result.status === "running" || isRunning;

  // Build the detail lines
  const lines: { text: string; type: "normal" | "arrow" | "highlight" }[] = [];

  if (result.findings) {
    result.findings.forEach((f) => {
      if (f.startsWith("->") || f.startsWith("→")) {
        lines.push({ text: f.replace(/^(->|→)\s*/, ""), type: "arrow" });
      } else {
        lines.push({ text: f, type: "normal" });
      }
    });
  }

  if (result.files_enhanced && result.files_enhanced.length > 0) {
    result.files_enhanced.forEach((file) => {
      lines.push({ text: file, type: "normal" });
    });
  }

  if (result.tokens && result.tokens > 0) {
    const cost = ((result.tokens / 1000) * 0.01).toFixed(4);
    lines.push({
      text: `${result.tokens.toLocaleString()} tokens ($${cost})`,
      type: "highlight",
    });
  }

  if (result.error) {
    lines.push({ text: `Error: ${result.error}`, type: "arrow" });
  }

  return (
    <div
      className={`
        rounded-lg border transition-all duration-300
        ${isActive
          ? "border-[#0070AD]/40 bg-[#0070AD]/[0.03] dark:bg-[#0070AD]/[0.06] shadow-sm"
          : isComplete
            ? "border-gray-200 dark:border-white/[0.08] bg-white dark:bg-white/[0.02]"
            : isFailed
              ? "border-red-200 dark:border-red-500/20 bg-red-50/50 dark:bg-red-500/[0.04]"
              : "border-gray-200 dark:border-white/[0.06] bg-gray-50/50 dark:bg-white/[0.01]"
        }
      `}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left group"
      >
        {/* Expand chevron */}
        <span className="text-gray-400 dark:text-gray-600 flex-shrink-0 transition-transform duration-200">
          {expanded ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
        </span>

        {/* Agent icon */}
        <div
          className={`
            flex h-8 w-8 items-center justify-center rounded-lg flex-shrink-0 transition-all duration-200
            ${isActive
              ? "bg-[#0070AD] shadow-lg shadow-[#0070AD]/20"
              : isComplete
                ? "bg-emerald-50 dark:bg-emerald-500/10"
                : isFailed
                  ? "bg-red-50 dark:bg-red-500/10"
                  : "bg-gray-100 dark:bg-white/[0.06]"
            }
          `}
        >
          <Icon
            className={`h-4 w-4 transition-colors
              ${isActive
                ? "text-white"
                : isComplete
                  ? "text-emerald-600 dark:text-emerald-400"
                  : isFailed
                    ? "text-red-500 dark:text-red-400"
                    : "text-gray-400 dark:text-gray-500"
              }
            `}
          />
        </div>

        {/* Name */}
        <span
          className={`text-sm font-semibold flex-1 min-w-0 truncate
            ${isActive
              ? "text-[#0070AD] dark:text-[#12ABDB]"
              : isComplete
                ? "text-[#1B365D] dark:text-gray-200"
                : isFailed
                  ? "text-red-600 dark:text-red-400"
                  : "text-gray-500 dark:text-gray-500"
            }
          `}
        >
          {displayName}
        </span>

        {/* Status + duration */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <StatusIcon status={isActive ? "running" : result.status} />
          <DurationBadge ms={result.duration_ms} />
        </div>
      </button>

      {/* Expanded content with animated reveal */}
      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          expanded ? "max-h-[600px] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="px-4 pb-3 space-y-0">
          {isActive && !lines.length && (
            <div className="pl-6">
              <AgentThinking
                agentName={displayName}
                message={AGENT_THINKING_MESSAGES[agentKey] || "Processing"}
              />
            </div>
          )}

          {lines.map((line, i) => {
            const isLast = i === lines.length - 1;
            if (line.type === "arrow") {
              return (
                <ArrowItem key={i}>
                  {line.text}
                </ArrowItem>
              );
            }
            if (line.type === "highlight") {
              return (
                <TreeLine key={i} isLast={isLast}>
                  <span className="text-[#0070AD] dark:text-[#12ABDB] font-medium">
                    {line.text}
                  </span>
                </TreeLine>
              );
            }
            return (
              <TreeLine key={i} isLast={isLast}>
                {line.text}
              </TreeLine>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ── Main Component ─────────────────────────────────────── */

export default function AgentLiveFeed({
  agentTrace,
  summary,
  totalTokens,
  totalCost,
  durationMs,
  migrationStatus,
}: AgentLiveFeedProps) {
  const feedRef = useRef<HTMLDivElement>(null);
  const isRunning = migrationStatus === "running" || migrationStatus === "queued";
  const isCompleted = migrationStatus === "completed";
  const isFailed = migrationStatus === "failed";

  // Auto-scroll to bottom when new agents appear
  useEffect(() => {
    if (feedRef.current && isRunning) {
      feedRef.current.scrollTo({
        top: feedRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [agentTrace, isRunning]);

  // Sort agent results by pipeline order
  const sortedAgents = agentTrace.agent_results
    ? Object.entries(agentTrace.agent_results).sort(
        ([a], [b]) => getAgentSortKey(a) - getAgentSortKey(b)
      )
    : [];

  // Find currently running agent
  const runningAgentKey = sortedAgents.find(
    ([, r]) => r.status === "running"
  )?.[0];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-200 dark:border-white/[0.06] bg-gradient-to-r from-[#1B365D]/[0.03] to-transparent dark:from-[#0070AD]/[0.06]">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#1B365D] dark:bg-[#0070AD] shadow-lg shadow-[#1B365D]/20 dark:shadow-[#0070AD]/20">
          <Zap className="h-4.5 w-4.5 text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-bold text-[#1B365D] dark:text-white tracking-tight">
            Migration Agent Pipeline
          </h3>
          <p className="text-[11px] text-gray-500 dark:text-gray-500">
            {isRunning
              ? "AI agents are working on your migration..."
              : isCompleted
                ? "All agents completed successfully"
                : isFailed
                  ? "Pipeline encountered an error"
                  : "Waiting to start"}
          </p>
        </div>
        {isRunning && (
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-2 rounded-full bg-[#0070AD] animate-pulse" />
            <span className="text-xs font-medium text-[#0070AD] dark:text-[#12ABDB]">Live</span>
          </div>
        )}
      </div>

      {/* Feed area */}
      <div
        ref={feedRef}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-3"
        style={{ minHeight: 0 }}
      >
        {/* When queued / no agents yet */}
        {sortedAgents.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            {isRunning ? (
              <>
                <div className="relative mb-4">
                  <div className="absolute inset-0 rounded-full bg-[#0070AD]/10 animate-ping" />
                  <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-[#0070AD]/10">
                    <Loader2 className="h-7 w-7 text-[#0070AD] animate-spin" />
                  </div>
                </div>
                <p className="text-sm font-medium text-[#1B365D] dark:text-gray-300">
                  Initializing agent pipeline...
                </p>
                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                  Agents will appear here as they start working
                </p>
              </>
            ) : (
              <>
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-gray-100 dark:bg-white/[0.04] mb-4">
                  <Brain className="h-7 w-7 text-gray-300 dark:text-gray-600" />
                </div>
                <p className="text-sm text-gray-400 dark:text-gray-500">
                  No agent activity yet
                </p>
              </>
            )}
          </div>
        )}

        {/* Agent sections */}
        {sortedAgents.map(([key, result]) => (
          <AgentSection
            key={key}
            agentKey={key}
            result={result}
            isRunning={key === runningAgentKey}
            defaultExpanded={
              key === runningAgentKey ||
              result.status === "failed" ||
              result.status === "error" ||
              isCompleted
            }
          />
        ))}

        {/* Running thinking indicator for the active agent at the bottom */}
        {isRunning && runningAgentKey && (
          <div className="pl-4 pb-2">
            <AgentThinking
              message={AGENT_THINKING_MESSAGES[runningAgentKey] || "Processing"}
            />
          </div>
        )}
      </div>

      {/* Summary footer */}
      {(isCompleted || isFailed) && (
        <div className="border-t border-gray-200 dark:border-white/[0.06] bg-gradient-to-r from-[#1B365D]/[0.02] to-transparent dark:from-white/[0.02]">
          <div className="px-5 py-4">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="h-4 w-4 text-[#1B365D] dark:text-[#0070AD]" />
              <span className="text-xs font-bold text-[#1B365D] dark:text-gray-300 uppercase tracking-wider">
                Summary
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg bg-gray-50 dark:bg-white/[0.03] px-3 py-2">
                <p className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">
                  Files
                </p>
                <p className="text-lg font-bold text-[#1B365D] dark:text-white tabular-nums">
                  {summary.total_files}
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 dark:bg-white/[0.03] px-3 py-2">
                <p className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">
                  Duration
                </p>
                <p className="text-lg font-bold text-[#1B365D] dark:text-white tabular-nums">
                  {(durationMs / 1000).toFixed(1)}s
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 dark:bg-white/[0.03] px-3 py-2">
                <p className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">
                  Tokens
                </p>
                <p className="text-lg font-bold text-[#0070AD] dark:text-[#12ABDB] tabular-nums">
                  {totalTokens > 1000
                    ? `${(totalTokens / 1000).toFixed(1)}K`
                    : totalTokens.toLocaleString()}
                </p>
              </div>
              <div className="rounded-lg bg-gray-50 dark:bg-white/[0.03] px-3 py-2">
                <p className="text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wider">
                  Cost
                </p>
                <p className="text-lg font-bold text-emerald-600 dark:text-emerald-400 tabular-nums">
                  ${totalCost.toFixed(4)}
                </p>
              </div>
            </div>

            {/* Errors */}
            {summary.errors.length > 0 && (
              <div className="mt-3 space-y-1">
                {summary.errors.map((err, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-500/[0.06] px-3 py-2"
                  >
                    <AlertTriangle className="h-3.5 w-3.5 text-red-500 flex-shrink-0 mt-0.5" />
                    <span className="text-xs text-red-600 dark:text-red-400">{err}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
