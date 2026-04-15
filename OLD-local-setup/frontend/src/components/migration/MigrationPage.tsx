import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Play,
  StopCircle,
  Download,
  Github,
  FileJson2,
  Loader2,
  PenLine,
  Save,
  ChevronDown,
  ChevronRight,
  ClipboardList,
} from "lucide-react";
import XmlEditor from "./XmlEditor";
import FileDropZone from "./FileDropZone";
import FileTree from "./FileTree";
import FileViewer from "./FileViewer";
import AgentPipeline from "./AgentPipeline";
import AgentLiveFeed from "./AgentLiveFeed";
import MigrationProgress from "./MigrationProgress";
import GlassCard from "@/components/common/GlassCard";
import GradientButton from "@/components/common/GradientButton";
import StatusBadge from "@/components/common/StatusBadge";
import {
  useMigrationDetail,
  useMigrationFiles,
  useCreateMigration,
  useCancelMigration,
  useAgentTraces,
} from "@/hooks/useMigration";
import { updateMigrationFiles } from "@/api/migrations";
import { useAgentStream } from "@/hooks/useAgentStream";
import { useMigrationStore } from "@/store/migration";
import { useSettingsStore } from "@/store/settings";
import { showToast } from "@/components/layout/Layout";
import type { MigrationFile, MuleSourceType, TargetFramework } from "@/types/migration";
import type { AgentType } from "@/types/agent";
import type { UploadSummary } from "@/api/migrations";

export default function MigrationPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // Form state for new migration
  const [name, setName] = useState("");
  const [sourceXml, setSourceXml] = useState("");
  const [sourceType, setSourceType] = useState<MuleSourceType>("mule4");
  const [targetFramework, setTargetFramework] = useState<TargetFramework>("spring-boot");
  const [groupId, setGroupId] = useState("");
  const [artifactId, setArtifactId] = useState("");
  const [basePackage, setBasePackage] = useState("");
  const [includeTests, setIncludeTests] = useState(true);
  const [includeSwagger, setIncludeSwagger] = useState(true);
  const [includeDocs, setIncludeDocs] = useState(true);
  const [aiEnhancement, setAiEnhancement] = useState(true);
  const [aiProvider, setAiProvider] = useState<"github_copilot" | "azure_openai">("github_copilot");
  const [uploadedFiles, setUploadedFiles] = useState<Array<{name: string; content: string; size: number}>>([]);
  const [inputMode, setInputMode] = useState<"editor" | "upload">("upload");

  // View state
  const [selectedFile, setSelectedFile] = useState<MigrationFile | null>(null);

  // Edit mode state
  const [editMode, setEditMode] = useState(false);
  const [modifiedFiles, setModifiedFiles] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);

  // Build instructions collapsible
  const [buildInstructionsOpen, setBuildInstructionsOpen] = useState(false);

  // Settings defaults
  const settings = useSettingsStore();

  // Initialize defaults from settings
  useEffect(() => {
    if (!id) {
      setGroupId(settings.defaultGroupId);
      setBasePackage(settings.defaultBasePackage);
    }
  }, [id, settings.defaultGroupId, settings.defaultBasePackage]);

  // Queries
  const { data: migration } = useMigrationDetail(id);
  const { data: files } = useMigrationFiles(id);
  const { data: traces } = useAgentTraces(id);
  const createMutation = useCreateMigration();
  const cancelMutation = useCancelMigration();

  // Store
  const pipelineStatus = useMigrationStore((s) => s.pipelineStatus);

  // WebSocket stream for live updates
  useAgentStream(id);

  // Handle file content changes from editor
  const handleContentChange = useCallback((filePath: string, newContent: string) => {
    setModifiedFiles((prev) => ({ ...prev, [filePath]: newContent }));
  }, []);

  // Save modified files to API
  async function handleSaveChanges() {
    if (!id || Object.keys(modifiedFiles).length === 0) return;
    setIsSaving(true);
    try {
      await updateMigrationFiles(id, modifiedFiles);
      showToast({
        type: "success",
        title: "Files saved",
        message: `${Object.keys(modifiedFiles).length} file(s) updated successfully`,
      });
      setModifiedFiles({});
    } catch {
      showToast({ type: "error", title: "Failed to save files" });
    } finally {
      setIsSaving(false);
    }
  }

  // Download all files as individual files
  async function handleDownloadAll() {
    if (!files || files.length === 0) return;
    try {
      const JSZip = (await import("jszip")).default;
      const zip = new JSZip();
      const projectName = migration?.project_name || "spring-boot-app";

      // Add each file to ZIP with proper folder structure
      files.forEach((f) => {
        const content = modifiedFiles[f.path] ?? f.content;
        zip.file(`${projectName}/${f.path}`, content);
      });

      const blob = await zip.generateAsync({ type: "blob" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${projectName}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // Fallback: download files individually
      files.forEach((f) => {
        const content = modifiedFiles[f.path] ?? f.content;
        const blob = new Blob([content], { type: "text/plain" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = f.filename;
        a.click();
        URL.revokeObjectURL(url);
      });
    }
    showToast({
      type: "success",
      title: "Download started",
      message: `${files.length} file(s) downloading`,
    });
  }

  async function handleSubmit() {
    if (!sourceXml.trim()) {
      showToast({ type: "error", title: "Please provide MuleSoft XML" });
      return;
    }
    if (!name.trim()) {
      showToast({ type: "error", title: "Please enter a migration name" });
      return;
    }

    try {
      const result = await createMutation.mutateAsync({
        name: name.trim(),
        sourceXml,
        sourceType,
        targetFramework,
        config: {
          groupId: groupId || settings.defaultGroupId,
          artifactId: artifactId || name.toLowerCase().replace(/\s+/g, "-"),
          basePackage: basePackage || settings.defaultBasePackage,
          javaVersion: settings.defaultJavaVersion,
          springBootVersion: settings.defaultSpringBootVersion,
          buildTool: settings.defaultBuildTool,
          includeTests,
          includeSwagger,
          includeDocs,
          llmProvider: aiEnhancement ? aiProvider : "",
          llmModel: aiEnhancement ? (aiProvider === "github_copilot" ? "gpt-4.1" : "gpt-4.1") : "",
          llmEnabled: aiEnhancement,
        },
      });

      showToast({
        type: "success",
        title: "Migration started",
        message: `Job "${result.name}" is now running`,
      });
      navigate(`/migrate/${result.id}`);
    } catch {
      showToast({ type: "error", title: "Failed to start migration" });
    }
  }

  function handleCancel() {
    if (!id) return;
    cancelMutation.mutate(id, {
      onSuccess: () => {
        showToast({ type: "info", title: "Migration cancelled" });
      },
    });
  }

  function handleAgentClick(agentType: AgentType) {
    // No-op for now since we removed the pipeline tab
  }

  // Handle ZIP upload completing (migration created server-side)
  const handleZipMigrationCreated = useCallback(
    (migrationId: string, _summary: UploadSummary) => {
      showToast({
        type: "success",
        title: "Migration started from ZIP",
        message: `Found ${_summary.xml_files_found} XML file(s). Migration is now running.`,
      });
      navigate(`/migrate/${migrationId}`);
    },
    [navigate]
  );

  const isViewMode = !!id && !!migration;
  const isRunning = migration?.status === "running" || migration?.status === "pending" || migration?.status === "queued";
  const isCompleted = migration?.status === "completed";
  const isFailed = migration?.status === "failed";
  const modifiedCount = Object.keys(modifiedFiles).length;

  // Derive pipeline agents from traces, store, or summary
  const defaultAgentTypes = ["planner", "engine", "coder", "reviewer", "tester", "docs"] as const;
  const executedAgents = (migration?.summary as any)?.agents_executed as string[] | undefined;

  const pipelineAgents = pipelineStatus?.agents ?? (
    traces && traces.length > 0
      ? traces.map((t) => ({
          agentType: t.agentType,
          status: t.status,
          progress: t.status === "completed" ? 100 : t.status === "running" ? 50 : 0,
          message: t.error || undefined,
          durationMs: t.durationMs,
          tokensUsed: t.tokensUsed,
        }))
      : defaultAgentTypes.map((agentType) => {
          const isDone = migration?.status === "completed";
          const wasExecuted = executedAgents?.some(
            (a) => a === agentType || a === "static_engine" && agentType === "engine"
          );
          return {
            agentType,
            status: isDone && wasExecuted ? ("completed" as const) : isDone ? ("completed" as const) : ("pending" as const),
            progress: isDone ? 100 : 0,
          };
        })
  );

  // Build AgentLiveFeed props from traces / summary / pipeline data
  const agentTraceForFeed = buildAgentTrace(traces, pipelineStatus, migration);
  const summaryForFeed = {
    status: migration?.status || "pending",
    total_files: migration?.summary?.totalFiles ?? files?.length ?? 0,
    errors: migration?.summary?.warnings ?? (migration?.error ? [migration.error] : []),
  };
  const totalTokens = migration?.tokensUsed ?? traces?.reduce((sum, t) => sum + (t.tokensUsed ?? 0), 0) ?? 0;
  const totalCost = (totalTokens / 1000) * 0.01; // rough estimate
  const totalDuration = migration?.durationMs ?? 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-capText dark:text-white">
              {isViewMode ? migration.name : "New Migration"}
            </h1>
            {isViewMode && migration.status && (
              <StatusBadge status={migration.status as any} />
            )}
          </div>
          <p className="text-sm text-capText-light dark:text-gray-500">
            {isViewMode
              ? `Migration ${migration.sourceType} to ${migration.targetFramework}`
              : "Convert MuleSoft XML to Spring Boot application"}
          </p>
        </div>

        {/* Action bar for completed migrations */}
        {isViewMode && isCompleted && (
          <div className="flex items-center gap-2">
            {/* Edit Mode Toggle */}
            <button
              onClick={() => {
                setEditMode(!editMode);
                if (editMode) {
                  setModifiedFiles({});
                }
              }}
              className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium transition-all duration-200 border ${
                editMode
                  ? "bg-[#0070AD] text-white border-[#0070AD]"
                  : "bg-white dark:bg-white/[0.04] text-[#0070AD] dark:text-gray-300 border-[#0070AD]/30 dark:border-white/[0.1] hover:bg-[#0070AD]/5 dark:hover:bg-white/[0.07]"
              }`}
              title={editMode ? "Disable edit mode" : "Enable edit mode"}
            >
              <PenLine className="h-3.5 w-3.5" />
              {editMode ? "Editing" : "Edit Mode"}
            </button>

            {/* Save Changes (only in edit mode with modifications) */}
            {editMode && modifiedCount > 0 && (
              <GradientButton
                variant="primary"
                size="sm"
                loading={isSaving}
                icon={<Save className="h-3.5 w-3.5" />}
                onClick={handleSaveChanges}
              >
                Save Changes ({modifiedCount})
              </GradientButton>
            )}

            {/* Download All */}
            <GradientButton
              variant="secondary"
              size="sm"
              icon={<Download className="h-3.5 w-3.5" />}
              onClick={handleDownloadAll}
            >
              Download All
            </GradientButton>

            {/* Swagger */}
            <GradientButton
              variant="secondary"
              size="sm"
              icon={<FileJson2 className="h-3.5 w-3.5" />}
              onClick={() => navigate(`/swagger/${migration.id}`)}
            >
              Swagger
            </GradientButton>

            {/* Push to GitHub */}
            <GradientButton
              variant="secondary"
              size="sm"
              icon={<Github className="h-3.5 w-3.5" />}
              onClick={() => navigate(`/github/${migration.id}`)}
            >
              Push to GitHub
            </GradientButton>
          </div>
        )}

        {/* Cancel button when running */}
        {isViewMode && isRunning && (
          <GradientButton
            variant="danger"
            size="sm"
            onClick={handleCancel}
            icon={<StopCircle className="h-3.5 w-3.5" />}
          >
            Cancel Migration
          </GradientButton>
        )}
      </div>

      {/* Input form (new migration) */}
      {!isViewMode && (
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2">
            {/* Input Mode Toggle */}
            <div className="flex gap-1 p-1 rounded-lg bg-gray-100 dark:bg-white/[0.04] mb-3">
              <button
                onClick={() => setInputMode("upload")}
                className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                  inputMode === "upload"
                    ? "bg-white dark:bg-white/[0.1] text-[#0070AD] shadow-sm"
                    : "text-capText-light dark:text-gray-400 hover:text-capText"
                }`}
              >
                Upload Files
              </button>
              <button
                onClick={() => setInputMode("editor")}
                className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
                  inputMode === "editor"
                    ? "bg-white dark:bg-white/[0.1] text-[#0070AD] shadow-sm"
                    : "text-capText-light dark:text-gray-400 hover:text-capText"
                }`}
              >
                Paste XML
              </button>
            </div>

            {inputMode === "upload" ? (
              <FileDropZone
                files={uploadedFiles}
                onFilesLoaded={(xml, files) => {
                  setSourceXml(xml);
                  setUploadedFiles(files);
                }}
                onZipMigrationCreated={handleZipMigrationCreated}
                groupId={groupId || settings.defaultGroupId}
                javaVersion={settings.defaultJavaVersion}
                aiEnhancement={aiEnhancement}
              />
            ) : (
              <XmlEditor value={sourceXml} onChange={setSourceXml} />
            )}
          </div>

          <div className="space-y-4">
            <GlassCard accentColor="blue">
              <div className="space-y-5">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-semibold text-capText dark:text-white">
                    Configuration
                  </h3>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-medium text-capText-light dark:text-gray-400 uppercase tracking-wider">
                    Migration Name *
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="e.g., Order Service Migration"
                    className="input"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-capText-light dark:text-gray-400 uppercase tracking-wider">
                      Source Type
                    </label>
                    <select
                      value={sourceType}
                      onChange={(e) => setSourceType(e.target.value as MuleSourceType)}
                      className="select"
                    >
                      <option value="mule3">Mule 3</option>
                      <option value="mule4">Mule 4</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-capText-light dark:text-gray-400 uppercase tracking-wider">
                      Target
                    </label>
                    <select
                      value={targetFramework}
                      onChange={(e) => setTargetFramework(e.target.value as TargetFramework)}
                      className="select"
                    >
                      <option value="spring-boot">Spring Boot</option>
                      <option value="spring-webflux">Spring WebFlux</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-medium text-capText-light dark:text-gray-400 uppercase tracking-wider">
                    Group ID
                  </label>
                  <input
                    type="text"
                    value={groupId}
                    onChange={(e) => setGroupId(e.target.value)}
                    placeholder="com.example"
                    className="input"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-medium text-capText-light dark:text-gray-400 uppercase tracking-wider">
                    Artifact ID
                  </label>
                  <input
                    type="text"
                    value={artifactId}
                    onChange={(e) => setArtifactId(e.target.value)}
                    placeholder="my-service"
                    className="input"
                  />
                </div>

                <div>
                  <label className="mb-1.5 block text-xs font-medium text-capText-light dark:text-gray-400 uppercase tracking-wider">
                    Base Package
                  </label>
                  <input
                    type="text"
                    value={basePackage}
                    onChange={(e) => setBasePackage(e.target.value)}
                    placeholder="com.example.app"
                    className="input"
                  />
                </div>

                {/* Checkboxes with corporate styling */}
                <div className="space-y-3 pt-1">
                  {[
                    { checked: includeTests, onChange: setIncludeTests, label: "Generate test cases" },
                    { checked: includeSwagger, onChange: setIncludeSwagger, label: "Generate Swagger/OpenAPI" },
                    { checked: includeDocs, onChange: setIncludeDocs, label: "Generate documentation" },
                  ].map((item, i) => (
                    <label key={i} className="flex items-center gap-3 cursor-pointer group">
                      <div className="relative">
                        <input
                          type="checkbox"
                          checked={item.checked}
                          onChange={(e) => item.onChange(e.target.checked)}
                          className="peer sr-only"
                        />
                        <div className="h-4 w-4 rounded border border-gray-300 dark:border-white/[0.15] bg-white dark:bg-white/[0.04] transition-all
                          peer-checked:bg-[#0070AD] peer-checked:border-[#0070AD]
                          group-hover:border-[#0070AD]/50" />
                        <svg
                          className="absolute top-0.5 left-0.5 h-3 w-3 text-white opacity-0 peer-checked:opacity-100 transition-opacity"
                          viewBox="0 0 12 12"
                          fill="none"
                        >
                          <path
                            d="M2.5 6L5 8.5L9.5 3.5"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      </div>
                      <span className="text-sm text-capText-light dark:text-gray-400 group-hover:text-capText dark:group-hover:text-gray-300 transition-colors">
                        {item.label}
                      </span>
                    </label>
                  ))}
                </div>

                {/* AI Enhancement Toggle */}
                <div className="pt-2 border-t border-gray-200 dark:border-white/[0.08]">
                  <label className="flex items-center justify-between cursor-pointer group">
                    <div>
                      <span className="text-sm font-medium text-capText dark:text-white">
                        AI Enhancement
                      </span>
                      <p className="text-xs text-capText-light dark:text-gray-500 mt-0.5">
                        Uses AI to review and improve generated code
                      </p>
                    </div>
                    <div className="relative">
                      <input
                        type="checkbox"
                        checked={aiEnhancement}
                        onChange={(e) => setAiEnhancement(e.target.checked)}
                        className="peer sr-only"
                      />
                      <div className="h-6 w-11 rounded-full bg-gray-300 dark:bg-white/[0.1] transition-colors
                        peer-checked:bg-[#0070AD]" />
                      <div className="absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform
                        peer-checked:translate-x-5" />
                    </div>
                  </label>

                  {/* AI Provider Selection */}
                  {aiEnhancement && (
                    <div className="mt-3 flex gap-2">
                      <button
                        type="button"
                        onClick={() => setAiProvider("github_copilot")}
                        className={`flex-1 flex items-center justify-center gap-2 rounded-lg border-2 px-3 py-2.5 text-xs font-medium transition-all ${
                          aiProvider === "github_copilot"
                            ? "border-[#0070AD] bg-[#0070AD]/10 text-[#0070AD] dark:border-[#12ABDB] dark:bg-[#12ABDB]/10 dark:text-[#12ABDB]"
                            : "border-gray-200 text-gray-500 hover:border-gray-300 dark:border-white/[0.1] dark:text-gray-400 dark:hover:border-white/[0.2]"
                        }`}
                      >
                        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/>
                        </svg>
                        GitHub Copilot
                        {aiProvider === "github_copilot" && (
                          <span className="rounded bg-[#0070AD]/20 px-1.5 py-0.5 text-[9px] font-bold dark:bg-[#12ABDB]/20">GPT-4.1</span>
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => setAiProvider("azure_openai")}
                        className={`flex-1 flex items-center justify-center gap-2 rounded-lg border-2 px-3 py-2.5 text-xs font-medium transition-all ${
                          aiProvider === "azure_openai"
                            ? "border-[#0070AD] bg-[#0070AD]/10 text-[#0070AD] dark:border-[#12ABDB] dark:bg-[#12ABDB]/10 dark:text-[#12ABDB]"
                            : "border-gray-200 text-gray-500 hover:border-gray-300 dark:border-white/[0.1] dark:text-gray-400 dark:hover:border-white/[0.2]"
                        }`}
                      >
                        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M5.483 3.803l6.296 11.942-6.296 5.398L0 3.803h5.483zm2.33 0H24L7.813 21.143l-2.33-5.398 8.626-11.942h-6.296z"/>
                        </svg>
                        Azure OpenAI
                        {aiProvider === "azure_openai" && (
                          <span className="rounded bg-[#0070AD]/20 px-1.5 py-0.5 text-[9px] font-bold dark:bg-[#12ABDB]/20">GPT-4.1</span>
                        )}
                      </button>
                    </div>
                  )}
                </div>

                {/* Start Migration button */}
                <GradientButton
                  variant="primary"
                  className="w-full"
                  loading={createMutation.isPending}
                  disabled={!sourceXml.trim() || !name.trim()}
                  onClick={handleSubmit}
                  icon={
                    createMutation.isPending ? undefined : <Play className="h-4 w-4" />
                  }
                >
                  {createMutation.isPending ? "Starting Migration..." : "Start Migration"}
                </GradientButton>
              </div>
            </GlassCard>
          </div>
        </div>
      )}

      {/* Results section (viewing existing migration) */}
      {isViewMode && (
        <>
          {/* Compact horizontal agent pipeline bar */}
          <GlassCard padding="sm" className="overflow-hidden">
            <AgentPipeline
              agents={pipelineAgents}
              currentAgent={pipelineStatus?.currentAgent}
              onAgentClick={handleAgentClick}
            />
          </GlassCard>

          {/* Two-column layout: Code (left 65%) + Agent Feed (right 35%) */}
          <div className="grid grid-cols-1 xl:grid-cols-5 gap-4" style={{ minHeight: "600px" }}>
            {/* LEFT: File tree + File viewer (65%) */}
            <div className="xl:col-span-3 flex flex-col gap-4" style={{ maxHeight: "calc(100vh - 260px)" }}>
              {/* File Tree */}
              <GlassCard padding="none" className="overflow-hidden flex-shrink-0" style={{ maxHeight: "40%" }}>
                <div className="border-b border-gray-200 dark:border-white/[0.06] px-4 py-3 flex items-center justify-between">
                  <h4 className="text-xs font-medium text-capText-light dark:text-gray-400 uppercase tracking-wider">
                    Generated Files
                  </h4>
                  <div className="flex items-center gap-2">
                    {files && files.filter(f => f.path.includes("src/test/") || f.path.includes("Test.java") || f.path.includes("Tests.java")).length > 0 && (
                      <span className="flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold text-green-700 dark:bg-green-900/30 dark:text-green-400">
                        {files.filter(f => f.path.includes("src/test/") || f.path.includes("Test.java") || f.path.includes("Tests.java")).length} test cases
                      </span>
                    )}
                    {files && (
                      <span className="text-[10px] font-mono text-gray-400 dark:text-gray-500 tabular-nums">
                        {files.length} files
                      </span>
                    )}
                  </div>
                </div>
                <div className="overflow-y-auto" style={{ maxHeight: "calc(100% - 44px)" }}>
                  <FileTree
                    files={files || []}
                    selectedFile={selectedFile}
                    onSelectFile={setSelectedFile}
                  />
                </div>
              </GlassCard>

              {/* File Viewer */}
              <div className="flex-1 min-h-0 overflow-hidden">
                <FileViewer
                  file={selectedFile}
                  editable={editMode}
                  onContentChange={handleContentChange}
                />
              </div>
            </div>

            {/* RIGHT: Agent Feed (35%) - collapsible */}
            <div className="xl:col-span-2">
              <GlassCard padding="none" className="h-full overflow-hidden flex flex-col" style={{ maxHeight: "calc(100vh - 260px)" }}>
                <AgentLiveFeed
                  agentTrace={agentTraceForFeed}
                  summary={summaryForFeed}
                  totalTokens={totalTokens}
                  totalCost={totalCost}
                  durationMs={totalDuration}
                  migrationStatus={migration.status}
                />
              </GlassCard>
            </div>
          </div>

          {/* How to Build - Collapsible section */}
          {isCompleted && (
            <GlassCard padding="none" className="overflow-hidden">
              <button
                onClick={() => setBuildInstructionsOpen(!buildInstructionsOpen)}
                className="flex w-full items-center justify-between px-6 py-4 text-left transition-colors hover:bg-gray-50 dark:hover:bg-white/[0.02]"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#1B365D]/10 dark:bg-[#0070AD]/10">
                    <ClipboardList className="h-4 w-4 text-[#1B365D] dark:text-[#0070AD]" />
                  </div>
                  <span className="text-sm font-semibold text-capText dark:text-white">
                    Build Instructions
                  </span>
                </div>
                {buildInstructionsOpen ? (
                  <ChevronDown className="h-4 w-4 text-capText-muted dark:text-gray-500" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-capText-muted dark:text-gray-500" />
                )}
              </button>

              {buildInstructionsOpen && (
                <div className="border-t border-gray-200 dark:border-white/[0.06] px-6 py-5">
                  <ol className="space-y-4">
                    <li className="flex items-start gap-3">
                      <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#0070AD] text-xs font-bold text-white">
                        1
                      </span>
                      <div>
                        <p className="text-sm font-medium text-capText dark:text-gray-200">
                          Push to GitHub using the button above
                        </p>
                        <p className="mt-0.5 text-xs text-capText-muted dark:text-gray-500">
                          Use the "Push to GitHub" button in the action bar to create a repository
                        </p>
                      </div>
                    </li>
                    <li className="flex items-start gap-3">
                      <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#0070AD] text-xs font-bold text-white">
                        2
                      </span>
                      <div>
                        <p className="text-sm font-medium text-capText dark:text-gray-200">
                          Clone the repository
                        </p>
                        <code className="mt-1 block rounded-md bg-gray-100 dark:bg-white/[0.06] px-3 py-2 text-xs font-mono text-capText dark:text-gray-300">
                          git clone https://github.com/your-repo
                        </code>
                      </div>
                    </li>
                    <li className="flex items-start gap-3">
                      <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#0070AD] text-xs font-bold text-white">
                        3
                      </span>
                      <div>
                        <p className="text-sm font-medium text-capText dark:text-gray-200">
                          Build the project
                        </p>
                        <code className="mt-1 block rounded-md bg-gray-100 dark:bg-white/[0.06] px-3 py-2 text-xs font-mono text-capText dark:text-gray-300">
                          mvn clean package
                        </code>
                      </div>
                    </li>
                    <li className="flex items-start gap-3">
                      <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#0070AD] text-xs font-bold text-white">
                        4
                      </span>
                      <div>
                        <p className="text-sm font-medium text-capText dark:text-gray-200">
                          Run the application
                        </p>
                        <code className="mt-1 block rounded-md bg-gray-100 dark:bg-white/[0.06] px-3 py-2 text-xs font-mono text-capText dark:text-gray-300">
                          java -jar target/app.jar
                        </code>
                      </div>
                    </li>
                  </ol>
                </div>
              )}
            </GlassCard>
          )}
        </>
      )}
    </div>
  );
}

/* ── Helper: Build agent trace data for the AgentLiveFeed ── */

function buildAgentTrace(
  traces: any[] | undefined,
  pipelineStatus: any,
  migration: any
): {
  status: string;
  agent_results?: Record<string, {
    status: string;
    tokens?: number;
    error?: string;
    duration_ms?: number;
    files_enhanced?: string[];
    findings?: string[];
  }>;
} {
  const agentResults: Record<string, any> = {};

  // Prefer traces from the API (most detailed)
  if (traces && traces.length > 0) {
    for (const t of traces) {
      const findings: string[] = [];

      // Extract findings from metadata if available
      if (t.metadata) {
        const meta = t.metadata as Record<string, any>;
        if (meta.findings) {
          findings.push(...(meta.findings as string[]));
        }
        if (meta.files_generated) {
          findings.push(`Generated ${meta.files_generated} files`);
        }
        if (meta.files_enhanced) {
          findings.push(`Enhanced ${(meta.files_enhanced as string[]).length} files`);
        }
        if (meta.complexity) {
          findings.push(`Complexity: ${meta.complexity}`);
        }
        if (meta.strategy) {
          findings.push(`Strategy: ${meta.strategy}`);
        }
        if (meta.flows_found) {
          findings.push(`Found ${meta.flows_found} flows`);
        }
      }

      // Add the response snippet as a finding if short enough
      if (t.response && t.response.length < 200 && !findings.length) {
        findings.push(t.response);
      }

      agentResults[t.agentType] = {
        status: t.status,
        tokens: t.tokensUsed,
        error: t.error,
        duration_ms: t.durationMs,
        files_enhanced: (t.metadata as any)?.files_enhanced,
        findings: findings.length > 0 ? findings : undefined,
      };
    }
  }

  // Fallback to pipeline status from the store (WebSocket live data)
  if (pipelineStatus?.agents && Object.keys(agentResults).length === 0) {
    for (const a of pipelineStatus.agents) {
      if (a.status !== "pending" && a.status !== "queued") {
        agentResults[a.agentType] = {
          status: a.status,
          tokens: a.tokensUsed,
          duration_ms: a.durationMs,
          findings: a.message ? [a.message] : undefined,
        };
      }
    }
  }

  // Fallback to summary data
  if (migration?.summary && Object.keys(agentResults).length === 0) {
    const summary = migration.summary as any;
    const executedAgents = summary.agents_executed as string[] | undefined;
    if (executedAgents) {
      for (const agent of executedAgents) {
        agentResults[agent] = {
          status: "completed",
          findings: [`Completed as part of migration pipeline`],
        };
      }
    }
  }

  return {
    status: migration?.status || "pending",
    agent_results: Object.keys(agentResults).length > 0 ? agentResults : undefined,
  };
}
