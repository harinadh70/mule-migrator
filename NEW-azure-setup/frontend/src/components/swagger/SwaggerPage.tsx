import { useState, useEffect, useMemo } from "react";
import { useParams } from "react-router-dom";
import {
  FileJson2,
  Copy,
  Check,
  Download,
  ExternalLink,
  ChevronRight,
  ChevronDown,
} from "lucide-react";
import Editor from "@monaco-editor/react";
import { useMigrationDetail, useMigrationFiles } from "@/hooks/useMigration";

interface EndpointGroup {
  tag: string;
  endpoints: ParsedEndpoint[];
}

interface ParsedEndpoint {
  method: string;
  path: string;
  summary: string;
  operationId?: string;
}

const METHOD_COLORS: Record<string, string> = {
  get: "bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300",
  post: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  put: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
  delete: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300",
  patch: "bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300",
};

function parseOpenApiSpec(spec: string): {
  info: { title: string; version: string; description?: string };
  groups: EndpointGroup[];
} | null {
  try {
    const parsed = JSON.parse(spec);
    const groups: Map<string, ParsedEndpoint[]> = new Map();

    if (parsed.paths) {
      for (const [path, methods] of Object.entries(
        parsed.paths as Record<string, Record<string, { summary?: string; tags?: string[]; operationId?: string }>>
      )) {
        for (const [method, details] of Object.entries(methods)) {
          if (["get", "post", "put", "delete", "patch"].includes(method)) {
            const tag = details.tags?.[0] || "default";
            if (!groups.has(tag)) groups.set(tag, []);
            groups.get(tag)!.push({
              method: method.toUpperCase(),
              path,
              summary: details.summary || "",
              operationId: details.operationId,
            });
          }
        }
      }
    }

    return {
      info: parsed.info || { title: "API", version: "1.0.0" },
      groups: Array.from(groups.entries()).map(([tag, endpoints]) => ({
        tag,
        endpoints,
      })),
    };
  } catch {
    return null;
  }
}

function EndpointGroupCard({
  group,
  defaultExpanded,
}: {
  group: EndpointGroup;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between p-4 text-left"
      >
        <h4 className="font-medium text-gray-900 dark:text-white">
          {group.tag}
          <span className="ml-2 text-sm text-gray-400">
            ({group.endpoints.length} endpoints)
          </span>
        </h4>
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronRight className="h-4 w-4 text-gray-400" />
        )}
      </button>

      {expanded && (
        <div className="border-t border-gray-200 dark:border-gray-700">
          {group.endpoints.map((ep, i) => (
            <div
              key={i}
              className="flex items-center gap-3 border-b border-gray-100 px-4 py-3 last:border-b-0 dark:border-gray-700"
            >
              <span
                className={`inline-flex w-20 items-center justify-center rounded-md px-2 py-1 text-xs font-bold ${
                  METHOD_COLORS[ep.method.toLowerCase()] || METHOD_COLORS.get
                }`}
              >
                {ep.method}
              </span>
              <span className="font-mono text-sm text-gray-800 dark:text-gray-200">
                {ep.path}
              </span>
              {ep.summary && (
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  - {ep.summary}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function SwaggerPage() {
  const { migrationId } = useParams<{ migrationId: string }>();
  const [inputId, setInputId] = useState(migrationId || "");
  const [activeView, setActiveView] = useState<"visual" | "raw">("visual");
  const [copied, setCopied] = useState(false);

  const { data: migration } = useMigrationDetail(inputId || undefined);
  const { data: files } = useMigrationFiles(inputId || undefined);

  useEffect(() => {
    if (migrationId) setInputId(migrationId);
  }, [migrationId]);

  // Find OpenAPI spec file
  const specFile = useMemo(
    () =>
      files?.find(
        (f) =>
          f.filename.includes("openapi") ||
          f.filename.includes("swagger") ||
          f.path.includes("openapi") ||
          f.path.includes("swagger")
      ),
    [files]
  );

  // Parse endpoints from Java controllers if no spec file
  const controllerEndpoints = useMemo(() => {
    if (specFile || !files) return null;
    const controllers = files.filter(
      (f) => f.path.includes("controller/") && f.filename.endsWith(".java") && !f.filename.includes("Test")
    );
    if (controllers.length === 0) return null;

    const groups: EndpointGroup[] = [];
    for (const ctrl of controllers) {
      const endpoints: ParsedEndpoint[] = [];
      const tagMatch = ctrl.content.match(/@Tag\s*\(\s*name\s*=\s*"([^"]+)"/);
      const tag = tagMatch ? tagMatch[1] : ctrl.filename.replace(".java", "");
      const basePath = ctrl.content.match(/@RequestMapping\s*\(\s*"([^"]+)"/)?.[1] || "";

      const methodRegex = /@(Get|Post|Put|Delete|Patch)Mapping\s*\(\s*"([^"]+)"\s*\)\s*\n\s*public\s+\S+\s+(\w+)/g;
      let match;
      while ((match = methodRegex.exec(ctrl.content)) !== null) {
        const method = match[1].toUpperCase();
        const path = basePath + match[2];
        const operationId = match[3];
        // Look for @Operation summary
        const before = ctrl.content.substring(Math.max(0, match.index - 200), match.index);
        const summaryMatch = before.match(/@Operation\s*\(\s*summary\s*=\s*"([^"]+)"/);
        endpoints.push({
          method,
          path,
          summary: summaryMatch ? summaryMatch[1] : `${method} ${path}`,
          operationId,
        });
      }
      if (endpoints.length > 0) {
        groups.push({ tag, endpoints });
      }
    }
    return groups.length > 0 ? { info: { title: (migration as any)?.project_name || "API", version: "1.0.0", description: "Auto-generated from Spring Boot controllers" }, groups } : null;
  }, [files, specFile, migration]);

  const parsedSpec = useMemo(
    () => specFile ? parseOpenApiSpec(specFile.content) : controllerEndpoints,
    [specFile, controllerEndpoints]
  );

  function getSpecContent(): string {
    if (specFile) return specFile.content;
    if (!parsedSpec) return "{}";
    return JSON.stringify({
      openapi: "3.0.3",
      info: parsedSpec.info,
      paths: Object.fromEntries(
        parsedSpec.groups.flatMap((g) =>
          g.endpoints.map((ep) => [
            ep.path,
            { [ep.method.toLowerCase()]: { summary: ep.summary, operationId: ep.operationId, tags: [g.tag], responses: { "200": { description: "Success" } } } }
          ])
        )
      )
    }, null, 2);
  }

  async function handleCopy() {
    const content = getSpecContent();
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function handleDownload() {
    const content = getSpecContent();
    const blob = new Blob([content], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = specFile?.filename || "openapi.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Swagger / OpenAPI Preview
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          View the generated OpenAPI specification for your migrated API
        </p>
      </div>

      {/* Migration ID input */}
      {!migrationId && (
        <div className="card max-w-md">
          <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
            Migration ID
          </label>
          <input
            type="text"
            value={inputId}
            onChange={(e) => setInputId(e.target.value)}
            placeholder="Enter a completed migration ID"
            className="input"
          />
        </div>
      )}

      {migration && !parsedSpec && !specFile && (
        <div className="card py-12 text-center">
          <FileJson2 className="mx-auto h-12 w-12 text-gray-300 dark:text-gray-600" />
          <p className="mt-3 text-gray-500 dark:text-gray-400">
            {migration.status === "completed"
              ? "No API endpoints found in the generated controllers."
              : `Migration is ${migration.status}. API spec will be available after completion.`}
          </p>
        </div>
      )}

      {(specFile || parsedSpec) && (
        <>
          {/* Header bar */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
              <button
                onClick={() => setActiveView("visual")}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  activeView === "visual"
                    ? "bg-white text-gray-900 shadow dark:bg-gray-700 dark:text-white"
                    : "text-gray-500 hover:text-gray-700 dark:text-gray-400"
                }`}
              >
                Visual
              </button>
              <button
                onClick={() => setActiveView("raw")}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                  activeView === "raw"
                    ? "bg-white text-gray-900 shadow dark:bg-gray-700 dark:text-white"
                    : "text-gray-500 hover:text-gray-700 dark:text-gray-400"
                }`}
              >
                Raw JSON
              </button>
            </div>

            <div className="flex items-center gap-2">
              <button onClick={handleCopy} className="btn-secondary text-sm">
                {copied ? (
                  <Check className="h-4 w-4 text-green-500" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
                Copy
              </button>
              <button onClick={handleDownload} className="btn-secondary text-sm">
                <Download className="h-4 w-4" />
                Download
              </button>
              <a
                href="https://editor.swagger.io"
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary text-sm"
              >
                <ExternalLink className="h-4 w-4" />
                Swagger Editor
              </a>
            </div>
          </div>

          {/* Visual view */}
          {activeView === "visual" && parsedSpec && (
            <div className="space-y-4">
              <div className="card">
                <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                  {parsedSpec.info.title}
                </h2>
                <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                  Version {parsedSpec.info.version}
                </p>
                {parsedSpec.info.description && (
                  <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
                    {parsedSpec.info.description}
                  </p>
                )}
              </div>

              {parsedSpec.groups.map((group) => (
                <EndpointGroupCard
                  key={group.tag}
                  group={group}
                  defaultExpanded={true}
                />
              ))}
            </div>
          )}

          {activeView === "visual" && !parsedSpec && (
            <div className="card py-12 text-center text-gray-500 dark:text-gray-400">
              Unable to parse the OpenAPI specification. Switch to Raw JSON view.
            </div>
          )}

          {/* Raw JSON view */}
          {activeView === "raw" && (
            <div className="h-[600px] overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700">
              <Editor
                height="100%"
                language="json"
                value={specFile?.content || JSON.stringify(parsedSpec ? {
                  openapi: "3.0.3",
                  info: parsedSpec.info,
                  paths: Object.fromEntries(
                    parsedSpec.groups.flatMap((g) =>
                      g.endpoints.map((ep) => [
                        ep.path,
                        { [ep.method.toLowerCase()]: { summary: ep.summary, operationId: ep.operationId, tags: [g.tag], responses: { "200": { description: "Success" } } } }
                      ])
                    )
                  )
                } : {}, null, 2)}
                theme="vs-dark"
                options={{
                  readOnly: true,
                  minimap: { enabled: true },
                  fontSize: 13,
                  fontFamily: "'JetBrains Mono', monospace",
                  scrollBeyondLastLine: false,
                  wordWrap: "on",
                  automaticLayout: true,
                }}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
