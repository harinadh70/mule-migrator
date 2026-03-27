import { Status } from "./common";

export interface BuildJob {
  id: string;
  migrationId: string;
  status: Status;
  buildTool: "maven" | "gradle";
  javaVersion: string;
  logLines: BuildLogLine[];
  exitCode?: number;
  artifactPath?: string;
  error?: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
}

export interface BuildLogLine {
  timestamp: string;
  level: "info" | "warn" | "error" | "debug";
  message: string;
  source?: string;
}

export interface BuildCreate {
  migrationId: string;
  buildTool?: "maven" | "gradle";
  javaVersion?: string;
  skipTests?: boolean;
}

export interface BuildStats {
  totalBuilds: number;
  successfulBuilds: number;
  failedBuilds: number;
  averageDurationMs: number;
  successRate: number;
}
