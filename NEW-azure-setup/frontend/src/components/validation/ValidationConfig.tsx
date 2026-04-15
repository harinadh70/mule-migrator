import { useState, useEffect, useMemo } from "react";
import {
  Play,
  Plus,
  Trash2,
  Server,
  Monitor,
  Zap,
  Wrench,
  ChevronDown,
  ChevronUp,
  RefreshCw,
} from "lucide-react";
import GlassCard from "@/components/common/GlassCard";
import GradientButton from "@/components/common/GradientButton";
import type { TestEndpoint, ValidationCreate } from "@/types/validation";
import type { EndpointMapping, MigrationFile } from "@/types/migration";

interface ParsedEndpoint {
  method: string;
  path: string;
  summary?: string;
}

/** Extract endpoints from an OpenAPI JSON spec string */
function parseOpenApiEndpoints(specContent: string): ParsedEndpoint[] {
  try {
    const parsed = JSON.parse(specContent);
    const endpoints: ParsedEndpoint[] = [];
    if (parsed.paths) {
      for (const [path, methods] of Object.entries(
        parsed.paths as Record<string, Record<string, { summary?: string }>>
      )) {
        for (const [method, details] of Object.entries(methods)) {
          if (["get", "post", "put", "delete", "patch"].includes(method)) {
            endpoints.push({
              method: method.toUpperCase(),
              path,
              summary: details?.summary,
            });
          }
        }
      }
    }
    return endpoints;
  } catch {
    return [];
  }
}

/** Extract endpoints from Java Spring Boot controller source */
function parseControllerEndpoints(content: string, allControllers: { content: string; filename: string }[]): ParsedEndpoint[] {
  const endpoints: ParsedEndpoint[] = [];
  for (const ctrl of allControllers) {
    const basePath = ctrl.content.match(/@RequestMapping\s*\(\s*"([^"]+)"/)?.[1] || "";
    const methodRegex = /@(Get|Post|Put|Delete|Patch)Mapping\s*\(\s*(?:"([^"]+)")?\s*\)/g;
    let match;
    while ((match = methodRegex.exec(ctrl.content)) !== null) {
      const method = match[1].toUpperCase();
      const path = basePath + (match[2] || "");
      endpoints.push({ method, path: path || "/" });
    }
  }
  return endpoints;
}

interface ValidationConfigProps {
  migrationId: string;
  onSubmit: (config: ValidationCreate) => void;
  isLoading: boolean;
  /** Endpoint mappings auto-detected from the migration summary */
  detectedEndpoints?: EndpointMapping[];
  /** Migration files for extracting endpoints from swagger/controllers */
  migrationFiles?: MigrationFile[];
}

export default function ValidationConfig({
  migrationId,
  onSubmit,
  isLoading,
  detectedEndpoints,
  migrationFiles,
}: ValidationConfigProps) {
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [javaVersion, setJavaVersion] = useState("17");
  const [keepAliveMin, setKeepAliveMin] = useState(15);
  const [mulesoftBaseUrl, setMulesoftBaseUrl] = useState("");
  const [comparisonMode, setComparisonMode] = useState<"server" | "client">("server");
  const [endpoints, setEndpoints] = useState<TestEndpoint[]>([
    { method: "GET", path: "/" },
  ]);
  const [expandedBodies, setExpandedBodies] = useState<Set<number>>(new Set());
  const [endpointSource, setEndpointSource] = useState<string>("");

  // Extract endpoints from migration files (OpenAPI spec > controllers > summary)
  const fileEndpoints = useMemo(() => {
    if (!migrationFiles || migrationFiles.length === 0) return null;

    // 1. Try OpenAPI spec file first
    const specFile = migrationFiles.find(
      (f) =>
        f.filename?.includes("openapi") ||
        f.filename?.includes("swagger") ||
        f.path?.includes("openapi") ||
        f.path?.includes("swagger")
    );
    if (specFile?.content) {
      const eps = parseOpenApiEndpoints(specFile.content);
      if (eps.length > 0) return { source: "OpenAPI spec", endpoints: eps };
    }

    // 2. Try extracting from Java controllers
    const controllers = migrationFiles.filter(
      (f) =>
        f.path?.includes("controller/") &&
        f.filename?.endsWith(".java") &&
        !f.filename?.includes("Test")
    );
    if (controllers.length > 0) {
      const eps = parseControllerEndpoints(
        "",
        controllers.map((c) => ({ content: c.content, filename: c.filename }))
      );
      if (eps.length > 0) return { source: "Spring controllers", endpoints: eps };
    }

    return null;
  }, [migrationFiles]);

  // Auto-populate endpoints: prefer file-based, fall back to summary
  useEffect(() => {
    if (fileEndpoints && fileEndpoints.endpoints.length > 0) {
      const mapped: TestEndpoint[] = fileEndpoints.endpoints.map((ep) => ({
        method: ep.method,
        path: ep.path,
        body: ["POST", "PUT", "PATCH"].includes(ep.method) ? "{}" : undefined,
      }));
      setEndpoints(mapped);
      setEndpointSource(fileEndpoints.source);
    } else if (detectedEndpoints && detectedEndpoints.length > 0) {
      const mapped: TestEndpoint[] = detectedEndpoints.map((ep) => ({
        method: ep.httpMethod?.toUpperCase() || "GET",
        path: ep.path || "/",
        body: ["POST", "PUT", "PATCH"].includes(ep.httpMethod?.toUpperCase()) ? "{}" : undefined,
      }));
      setEndpoints(mapped);
      setEndpointSource("Migration summary");
    }
  }, [fileEndpoints, detectedEndpoints]);

  const loadDetectedEndpoints = () => {
    if (fileEndpoints && fileEndpoints.endpoints.length > 0) {
      const mapped: TestEndpoint[] = fileEndpoints.endpoints.map((ep) => ({
        method: ep.method,
        path: ep.path,
        body: ["POST", "PUT", "PATCH"].includes(ep.method) ? "{}" : undefined,
      }));
      setEndpoints(mapped);
      setEndpointSource(fileEndpoints.source);
    } else if (detectedEndpoints && detectedEndpoints.length > 0) {
      const mapped: TestEndpoint[] = detectedEndpoints.map((ep) => ({
        method: ep.httpMethod?.toUpperCase() || "GET",
        path: ep.path || "/",
        body: ["POST", "PUT", "PATCH"].includes(ep.httpMethod?.toUpperCase()) ? "{}" : undefined,
      }));
      setEndpoints(mapped);
      setEndpointSource("Migration summary");
    }
  };

  const addEndpoint = () => {
    setEndpoints([...endpoints, { method: "GET", path: "" }]);
  };

  const removeEndpoint = (index: number) => {
    setEndpoints(endpoints.filter((_, i) => i !== index));
    setExpandedBodies((prev) => {
      const next = new Set<number>();
      prev.forEach((idx) => {
        if (idx < index) next.add(idx);
        else if (idx > index) next.add(idx - 1);
      });
      return next;
    });
  };

  const updateEndpoint = (index: number, field: keyof TestEndpoint, value: string) => {
    const updated = [...endpoints];
    updated[index] = { ...updated[index], [field]: value };
    setEndpoints(updated);
  };

  const toggleBody = (index: number) => {
    setExpandedBodies((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const needsBody = (method: string) => ["POST", "PUT", "PATCH"].includes(method);

  const handleSubmit = () => {
    onSubmit({
      migrationId,
      mode,
      javaVersion,
      keepAliveMin,
      mulesoftBaseUrl,
      testEndpoints: endpoints.filter((e) => e.path.trim()),
      comparisonMode,
    });
  };

  return (
    <div className="space-y-6">
      {/* Java Version & Keep Alive */}
      <GlassCard accentColor="cyan">
        <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
          Deployment Configuration
        </h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Java Version
            </label>
            <select
              value={javaVersion}
              onChange={(e) => setJavaVersion(e.target.value)}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm dark:border-white/[0.1] dark:bg-white/[0.04] dark:text-gray-200"
            >
              <option value="17">Java 17 (LTS)</option>
              <option value="21">Java 21 (LTS)</option>
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Keep Alive Duration
            </label>
            <select
              value={keepAliveMin}
              onChange={(e) => setKeepAliveMin(Number(e.target.value))}
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm dark:border-white/[0.1] dark:bg-white/[0.04] dark:text-gray-200"
            >
              <option value={5}>5 minutes</option>
              <option value={15}>15 minutes</option>
              <option value={30}>30 minutes</option>
              <option value={60}>60 minutes</option>
            </select>
          </div>
        </div>
      </GlassCard>

      {/* Testing Mode */}
      <GlassCard accentColor="blue">
        <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
          Testing Mode
        </h3>
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => setMode("auto")}
            className={`flex items-center gap-3 rounded-lg border-2 p-4 text-left transition-all ${
              mode === "auto"
                ? "border-[#0070AD] bg-[#0070AD]/5 dark:bg-[#0070AD]/10"
                : "border-gray-200 dark:border-white/[0.08] hover:border-gray-300"
            }`}
          >
            <Zap
              className={`h-5 w-5 ${
                mode === "auto" ? "text-[#0070AD]" : "text-gray-400"
              }`}
            />
            <div>
              <div className="font-medium text-gray-900 dark:text-white">
                Auto Compare
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Automatically compare API responses
              </div>
            </div>
          </button>
          <button
            type="button"
            onClick={() => setMode("manual")}
            className={`flex items-center gap-3 rounded-lg border-2 p-4 text-left transition-all ${
              mode === "manual"
                ? "border-[#0070AD] bg-[#0070AD]/5 dark:bg-[#0070AD]/10"
                : "border-gray-200 dark:border-white/[0.08] hover:border-gray-300"
            }`}
          >
            <Wrench
              className={`h-5 w-5 ${
                mode === "manual" ? "text-[#0070AD]" : "text-gray-400"
              }`}
            />
            <div>
              <div className="font-medium text-gray-900 dark:text-white">
                Manual Test
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Get URL & test manually, submit verdict
              </div>
            </div>
          </button>
        </div>
      </GlassCard>

      {/* Auto Compare Config */}
      {mode === "auto" && (
        <GlassCard accentColor="green">
          <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
            Comparison Settings
          </h3>

          {/* Comparison location */}
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
              Comparison Location
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => setComparisonMode("server")}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-all ${
                  comparisonMode === "server"
                    ? "border-[#0070AD] bg-[#0070AD]/5 text-[#0070AD] dark:bg-[#0070AD]/10"
                    : "border-gray-200 text-gray-600 dark:border-white/[0.08] dark:text-gray-400"
                }`}
              >
                <Server className="h-4 w-4" />
                Server-side (Azure)
              </button>
              <button
                type="button"
                onClick={() => setComparisonMode("client")}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-all ${
                  comparisonMode === "client"
                    ? "border-[#0070AD] bg-[#0070AD]/5 text-[#0070AD] dark:bg-[#0070AD]/10"
                    : "border-gray-200 text-gray-600 dark:border-white/[0.08] dark:text-gray-400"
                }`}
              >
                <Monitor className="h-4 w-4" />
                Client-side (Browser)
              </button>
            </div>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {comparisonMode === "server"
                ? "Azure Function calls both APIs — works for public endpoints."
                : "Browser calls both APIs — use for VPN/internal MuleSoft instances."}
            </p>
          </div>

          {/* MuleSoft Base URL */}
          <div className="mb-4">
            <label className="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">
              MuleSoft Base URL
            </label>
            <input
              type="url"
              value={mulesoftBaseUrl}
              onChange={(e) => setMulesoftBaseUrl(e.target.value)}
              placeholder="https://mulesoft-app.example.com/api"
              className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm dark:border-white/[0.1] dark:bg-white/[0.04] dark:text-gray-200"
            />
          </div>

          {/* Test Endpoints */}
          <div>
            <div className="mb-2 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Test Endpoints
                </label>
                <span className="rounded-full bg-[#0070AD]/10 px-2 py-0.5 text-xs font-medium text-[#0070AD]">
                  {endpoints.length} endpoint{endpoints.length !== 1 ? "s" : ""}
                </span>
              </div>
              <div className="flex items-center gap-2">
                {(fileEndpoints || (detectedEndpoints && detectedEndpoints.length > 0)) && (
                  <button
                    type="button"
                    onClick={loadDetectedEndpoints}
                    className="flex items-center gap-1 text-xs text-emerald-600 hover:underline dark:text-emerald-400"
                    title="Reload endpoints detected from migration"
                  >
                    <RefreshCw className="h-3 w-3" /> Reload from {fileEndpoints?.source || "Migration"}
                  </button>
                )}
                <button
                  type="button"
                  onClick={addEndpoint}
                  className="flex items-center gap-1 text-xs text-[#0070AD] hover:underline"
                >
                  <Plus className="h-3.5 w-3.5" /> Add Endpoint
                </button>
              </div>
            </div>

            {endpointSource && endpoints.length > 1 && (
              <p className="mb-2 text-xs text-emerald-600 dark:text-emerald-400">
                ✓ {endpoints.length} endpoint{endpoints.length !== 1 ? "s" : ""} auto-loaded from {endpointSource}
              </p>
            )}

            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-1">
              {endpoints.map((ep, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <select
                      value={ep.method}
                      onChange={(e) => updateEndpoint(i, "method", e.target.value)}
                      className="w-24 rounded-lg border border-gray-300 bg-white px-2 py-2 text-sm dark:border-white/[0.1] dark:bg-white/[0.04] dark:text-gray-200"
                    >
                      <option value="GET">GET</option>
                      <option value="POST">POST</option>
                      <option value="PUT">PUT</option>
                      <option value="PATCH">PATCH</option>
                      <option value="DELETE">DELETE</option>
                    </select>
                    <input
                      type="text"
                      value={ep.path}
                      onChange={(e) => updateEndpoint(i, "path", e.target.value)}
                      placeholder="/api/v1/resource"
                      className="flex-1 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-white/[0.1] dark:bg-white/[0.04] dark:text-gray-200"
                    />
                    {needsBody(ep.method) && (
                      <button
                        type="button"
                        onClick={() => toggleBody(i)}
                        className={`rounded p-1.5 text-xs transition-colors ${
                          expandedBodies.has(i)
                            ? "bg-[#0070AD]/10 text-[#0070AD]"
                            : "text-gray-400 hover:bg-gray-100 dark:hover:bg-white/[0.04]"
                        }`}
                        title="Toggle request body"
                      >
                        {expandedBodies.has(i) ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )}
                      </button>
                    )}
                    {endpoints.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeEndpoint(i)}
                        className="rounded p-1.5 text-gray-400 hover:bg-red-50 hover:text-red-500 dark:hover:bg-red-900/20"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                  {/* Request body for POST/PUT/PATCH */}
                  {needsBody(ep.method) && expandedBodies.has(i) && (
                    <textarea
                      value={(ep.body as string) || ""}
                      onChange={(e) => updateEndpoint(i, "body", e.target.value)}
                      placeholder='{"key": "value"}'
                      rows={3}
                      className="ml-[104px] w-[calc(100%-104px)] rounded-lg border border-gray-300 bg-white px-3 py-2 text-xs font-mono dark:border-white/[0.1] dark:bg-white/[0.04] dark:text-gray-200"
                    />
                  )}
                </div>
              ))}
            </div>
          </div>
        </GlassCard>
      )}

      {/* Submit */}
      <GradientButton
        onClick={handleSubmit}
        loading={isLoading}
        icon={<Play className="h-4 w-4" />}
        size="lg"
        className="w-full"
      >
        Deploy & {mode === "auto" ? "Compare" : "Test"}
      </GradientButton>
    </div>
  );
}
