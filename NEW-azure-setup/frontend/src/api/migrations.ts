import apiClient from "./client";
import type {
  MigrationJob,
  MigrationCreate,
  MigrationFile,
  MigrationStats,
} from "@/types/migration";
import type { PaginatedResponse } from "@/types/common";
import type { AgentTrace } from "@/types/agent";

/** Split XML input into multiple files. Supports:
 *  - Multiple <mule> blocks separated by comments like <!-- filename.xml -->
 *  - Single XML pasted as one file
 */
function splitXmlFiles(xml: string, projectName: string): Array<{name: string; content: string; size: number}> {
  const baseName = projectName.toLowerCase().replace(/\s+/g, "-");

  // Try splitting on XML comment separators like <!-- filename.xml -->
  const commentPattern = /<!--\s*([\w\-]+\.xml)\s*-->/gi;
  const matches = [...xml.matchAll(commentPattern)];

  if (matches.length >= 2) {
    const files: Array<{name: string; content: string; size: number}> = [];
    for (let i = 0; i < matches.length; i++) {
      const name = matches[i][1];
      const start = matches[i].index! + matches[i][0].length;
      const end = i + 1 < matches.length ? matches[i + 1].index! : xml.length;
      const content = xml.slice(start, end).trim();
      if (content) {
        files.push({ name, content, size: new Blob([content]).size });
      }
    }
    return files;
  }

  // Try splitting on multiple <?xml declarations
  const xmlDecls = xml.split(/(?=<\?xml\s)/);
  if (xmlDecls.filter(s => s.trim()).length > 1) {
    return xmlDecls
      .map(s => s.trim())
      .filter(Boolean)
      .map((content, i) => ({
        name: i === 0 ? `${baseName}.xml` : `${baseName}-${i + 1}.xml`,
        content,
        size: new Blob([content]).size,
      }));
  }

  // Single file
  return [{
    name: `${baseName}.xml`,
    content: xml,
    size: new Blob([xml]).size,
  }];
}

export async function createMigration(
  data: MigrationCreate
): Promise<MigrationJob> {
  // Build input_xml_files and dataweave_scripts from uploaded files or pasted XML
  let inputXmlFiles: Array<{ name: string; content: string; size: number }>;
  const dataweaveScripts: Record<string, string> = {};

  console.log("[createMigration] uploadedFiles:", data.uploadedFiles?.length ?? 0, "sourceXml length:", data.sourceXml?.length ?? 0);

  if (data.uploadedFiles && data.uploadedFiles.length > 0) {
    // Use uploaded files directly — separate XML from supporting files
    inputXmlFiles = [];
    for (const f of data.uploadedFiles) {
      const lower = f.name.toLowerCase();
      if (lower.endsWith(".xml")) {
        inputXmlFiles.push({ name: f.name, content: f.content, size: f.size });
      } else {
        // Send RAML, YAML, DWL, properties, etc. as dataweave_scripts context
        dataweaveScripts[f.path || f.name] = f.content;
      }
    }
    // Ensure at least one XML file
    if (inputXmlFiles.length === 0) {
      inputXmlFiles = splitXmlFiles(data.sourceXml, data.name);
    }
  } else {
    // Pasted XML mode — use splitter
    inputXmlFiles = splitXmlFiles(data.sourceXml, data.name);
  }

  // Transform frontend shape to backend API shape
  const payload = {
    project_name: data.name,
    group_id: data.config.groupId || "com.example",
    java_version: data.config.javaVersion || "17",
    input_xml_files: inputXmlFiles,
    dataweave_scripts: Object.keys(dataweaveScripts).length > 0 ? dataweaveScripts : undefined,
    llm_config: {
      provider: data.config.llmEnabled ? (data.config.llmProvider || "github_copilot") : "",
      model: data.config.llmEnabled ? (data.config.llmModel || "gpt-4.1") : "",
      enabled: !!data.config.llmEnabled,
    },
    source_type: data.sourceType,
    target_framework: data.targetFramework,
    artifact_id: data.config.artifactId,
    base_package: data.config.basePackage,
    include_tests: data.config.includeTests,
    include_swagger: data.config.includeSwagger,
    include_docs: data.config.includeDocs,
  };
  const response = await apiClient.post<any>("/migrations", payload);
  // Transform backend response to frontend shape
  const job = response.data;
  return {
    id: job.id,
    name: job.project_name,
    status: job.status,
    sourceXml: data.sourceXml,
    sourceType: data.sourceType,
    targetFramework: data.targetFramework,
    config: data.config,
    files: [],
    agentTraces: [],
    summary: job.summary || undefined,
    error: undefined,
    createdAt: job.created_at,
    updatedAt: job.created_at,
    startedAt: job.started_at,
    completedAt: job.completed_at,
    durationMs: job.duration_ms,
    tokensUsed: job.total_tokens_used,
  };
}

export async function getMigration(id: string): Promise<MigrationJob> {
  const response = await apiClient.get<any>(`/migrations/${id}`);
  const job = response.data;
  return {
    id: job.id,
    name: job.project_name,
    status: job.status,
    sourceXml: "",
    sourceType: "mule4",
    targetFramework: "spring-boot",
    config: { groupId: job.group_id, artifactId: "", basePackage: "", javaVersion: job.java_version || "17", springBootVersion: "3.2", buildTool: "maven", includeTests: true, includeSwagger: true, includeDocs: true, llmProvider: "", llmModel: "" },
    files: [],
    agentTraces: [],
    summary: job.summary || undefined,
    error: undefined,
    createdAt: job.created_at,
    updatedAt: job.created_at,
    startedAt: job.started_at,
    completedAt: job.completed_at,
    durationMs: job.duration_ms,
    tokensUsed: job.total_tokens_used,
  };
}

export async function listMigrations(params?: {
  page?: number;
  pageSize?: number;
  status?: string;
  search?: string;
  sortBy?: string;
  sortOrder?: "asc" | "desc";
}): Promise<PaginatedResponse<MigrationJob>> {
  const response = await apiClient.get<any>("/migrations", { params });
  const data = response.data;
  return {
    ...data,
    totalPages: data.pages || data.totalPages || Math.ceil((data.total || 0) / (params?.pageSize || 20)),
    items: (data.items || []).map((job: any) => ({
      id: job.id,
      name: job.project_name,
      status: job.status,
      sourceXml: "",
      sourceType: "mule4",
      targetFramework: "spring-boot",
      config: { groupId: "", artifactId: "", basePackage: "", javaVersion: "17", springBootVersion: "3.2", buildTool: "maven", includeTests: true, includeSwagger: true, includeDocs: true, llmProvider: "", llmModel: "" },
      files: [],
      agentTraces: [],
      createdAt: job.created_at,
      updatedAt: job.created_at,
      durationMs: job.duration_ms,
      tokensUsed: job.total_tokens_used,
    })),
  };
}

export async function cancelMigration(id: string): Promise<MigrationJob> {
  const response = await apiClient.post<MigrationJob>(
    `/migrations/${id}/cancel`
  );
  return response.data;
}

export async function deleteMigration(id: string): Promise<void> {
  await apiClient.delete(`/migrations/${id}`);
}

export async function getMigrationFiles(
  id: string
): Promise<MigrationFile[]> {
  try {
    const response = await apiClient.get<any>(`/migrations/${id}/files`);
    const data = response.data;
    if (Array.isArray(data)) return data;
    // Backend returns {files: {path: content}} - transform to MigrationFile[]
    if (data && typeof data === "object") {
      return Object.entries(data.files || data).map(([path, content], i) => ({
        id: `file-${i}`,
        migrationId: id,
        path,
        filename: path.split("/").pop() || path,
        content: String(content),
        language: guessLanguage(path),
        agentSource: "coder",
        size: new Blob([String(content)]).size,
        createdAt: new Date().toISOString(),
      }));
    }
    return [];
  } catch {
    return [];
  }
}

/** Save edited files back to the API */
export async function updateMigrationFiles(
  id: string,
  files: Record<string, string>
): Promise<void> {
  await apiClient.put(`/migrations/${id}/files`, {
    output_files: files,
  });
}

function guessLanguage(path: string): import("@/types/migration").FileLanguage {
  if (path.endsWith(".java")) return "java";
  if (path.endsWith(".xml")) return "xml";
  if (path.endsWith(".yaml") || path.endsWith(".yml")) return "yaml";
  if (path.endsWith(".properties")) return "properties";
  if (path.endsWith(".sql")) return "sql";
  if (path.endsWith(".json")) return "json";
  if (path.endsWith(".md")) return "markdown";
  if (path.includes("Dockerfile")) return "dockerfile";
  return "text";
}

export async function getMigrationStats(): Promise<MigrationStats> {
  const response = await apiClient.get<any>("/stats/migrations");
  const s = response.data;
  return {
    totalMigrations: s.total || 0,
    successfulMigrations: s.by_status?.completed || 0,
    failedMigrations: s.by_status?.failed || 0,
    averageDurationMs: s.avg_duration_ms || 0,
    totalTokensUsed: s.total_tokens_used || 0,
    successRate: s.total > 0 ? ((s.by_status?.completed || 0) / s.total) * 100 : 0,
    migrationsThisWeek: s.total || 0,
    migrationsThisMonth: s.total || 0,
  };
}

export async function getAgentTraces(
  migrationId: string
): Promise<AgentTrace[]> {
  try {
    // Try /agents endpoint (which exists) instead of /traces
    const response = await apiClient.get<any>(
      `/migrations/${migrationId}/agents`
    );
    const data = response.data;
    return (data.agents || []).map((a: any) => ({
      id: a.id || a.agent_name,
      migrationId,
      agentType: a.agent_name || a.agentType,
      status: a.status || "pending",
      startedAt: a.started_at,
      completedAt: a.completed_at,
      durationMs: a.duration_ms,
      tokensUsed: a.token_usage || 0,
      ragQueriesCount: a.rag_results_used || 0,
      error: a.error,
      score: null,
    }));
  } catch {
    return [];
  }
}

export async function retryMigration(id: string): Promise<MigrationJob> {
  const response = await apiClient.post<MigrationJob>(
    `/migrations/${id}/retry`
  );
  return response.data;
}
