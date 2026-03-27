import { Status } from "./common";

export type AgentType =
  | "planner"
  | "engine"
  | "coder"
  | "reviewer"
  | "tester"
  | "docs";

export interface AgentTrace {
  id: string;
  migrationId: string;
  agentType: AgentType;
  status: Status;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
  tokensUsed?: number;
  ragContext?: RagContextUsed[];
  prompt?: string;
  response?: string;
  score?: number;
  error?: string;
  metadata?: Record<string, unknown>;
}

export interface RagContextUsed {
  collection: string;
  query: string;
  documentId: string;
  snippet: string;
  score: number;
}

export interface AgentProgress {
  migrationId: string;
  agentType: AgentType;
  status: Status;
  progress: number;
  message: string;
  timestamp: string;
  details?: Record<string, unknown>;
}

export interface PipelineStatus {
  migrationId: string;
  status: Status;
  currentAgent?: AgentType;
  progress: number;
  agents: AgentNodeStatus[];
  startedAt?: string;
  estimatedCompletionAt?: string;
}

export interface AgentNodeStatus {
  agentType: AgentType;
  status: Status;
  progress: number;
  message?: string;
  durationMs?: number;
  tokensUsed?: number;
}

export const AGENT_ORDER: AgentType[] = [
  "planner",
  "engine",
  "coder",
  "reviewer",
  "tester",
  "docs",
];

export const AGENT_LABELS: Record<AgentType, string> = {
  planner: "Planner",
  engine: "Engine",
  coder: "Coder",
  reviewer: "Reviewer",
  tester: "Tester",
  docs: "Docs",
};

export const AGENT_DESCRIPTIONS: Record<AgentType, string> = {
  planner: "Analyzes MuleSoft XML and creates a migration plan",
  engine: "Orchestrates the migration workflow",
  coder: "Generates Spring Boot source code",
  reviewer: "Reviews and improves generated code",
  tester: "Generates test cases",
  docs: "Creates documentation and Swagger specs",
};
