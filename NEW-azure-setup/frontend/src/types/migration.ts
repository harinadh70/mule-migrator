import { Status } from "./common";

export interface MigrationJob {
  id: string;
  name: string;
  status: Status;
  sourceXml: string;
  sourceType: MuleSourceType;
  targetFramework: TargetFramework;
  config: MigrationConfig;
  files: MigrationFile[];
  agentTraces: string[];
  summary?: MigrationSummary;
  error?: string;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  completedAt?: string;
  durationMs?: number;
  tokensUsed?: number;
}

export interface MigrationCreate {
  name: string;
  sourceXml: string;
  sourceType: MuleSourceType;
  targetFramework: TargetFramework;
  config: MigrationConfig;
  uploadedFiles?: Array<{ name: string; content: string; size: number; path: string }>;
}

export interface MigrationConfig {
  groupId: string;
  artifactId: string;
  basePackage: string;
  javaVersion: "17" | "21";
  springBootVersion: "3.2" | "3.3";
  buildTool: "maven" | "gradle";
  includeTests: boolean;
  includeSwagger: boolean;
  includeDocs: boolean;
  llmProvider: string;
  llmModel: string;
  llmEnabled?: boolean;
}

export type MuleSourceType = "mule3" | "mule4";
export type TargetFramework = "spring-boot" | "spring-webflux";

export interface MigrationFile {
  id: string;
  migrationId: string;
  path: string;
  filename: string;
  content: string;
  language: FileLanguage;
  agentSource: string;
  size: number;
  createdAt: string;
}

export type FileLanguage = "java" | "xml" | "yaml" | "properties" | "sql" | "json" | "markdown" | "dockerfile" | "text";

export interface MigrationSummary {
  totalFiles: number;
  totalLines: number;
  endpoints: EndpointMapping[];
  components: ComponentMapping[];
  warnings: string[];
  suggestions: string[];
  testCoverage?: number;
  qualityScore?: number;
}

export interface EndpointMapping {
  muleFlowName: string;
  httpMethod: string;
  path: string;
  springController: string;
  springMethod: string;
}

export interface ComponentMapping {
  muleComponent: string;
  springEquivalent: string;
  status: "mapped" | "partial" | "manual";
  notes?: string;
}

export interface MigrationStats {
  totalMigrations: number;
  successfulMigrations: number;
  failedMigrations: number;
  averageDurationMs: number;
  totalTokensUsed: number;
  successRate: number;
  migrationsThisWeek: number;
  migrationsThisMonth: number;
}
