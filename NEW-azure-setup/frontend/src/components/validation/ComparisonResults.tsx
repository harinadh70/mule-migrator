import { CheckCircle2, XCircle, ArrowLeftRight } from "lucide-react";
import GlassCard from "@/components/common/GlassCard";
import type { TestResult } from "@/types/validation";

interface ComparisonResultsProps {
  results: TestResult[];
}

function formatBody(body: string | undefined): string {
  if (!body) return "";
  try {
    const parsed = JSON.parse(body);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return body;
  }
}

export default function ComparisonResults({ results }: ComparisonResultsProps) {
  if (results.length === 0) return null;

  const passed = results.filter((r) => r.match).length;

  return (
    <GlassCard accentColor="blue">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Comparison Results
        </h3>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-emerald-600 dark:text-emerald-400">
            {passed} passed
          </span>
          <span className="text-gray-400">/</span>
          <span className="text-gray-600 dark:text-gray-300">
            {results.length} total
          </span>
        </div>
      </div>

      <div className="space-y-3">
        {results.map((result, i) => (
          <div
            key={i}
            className={`rounded-lg border p-4 ${
              result.match
                ? "border-emerald-200 bg-emerald-50/50 dark:border-emerald-800/20 dark:bg-emerald-900/5"
                : "border-red-200 bg-red-50/50 dark:border-red-800/20 dark:bg-red-900/5"
            }`}
          >
            {/* Header */}
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {result.match ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                ) : (
                  <XCircle className="h-4 w-4 text-red-500" />
                )}
                <span className="rounded bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-700 dark:bg-white/[0.08] dark:text-gray-300">
                  {result.method}
                </span>
                <span className="font-mono text-sm text-gray-900 dark:text-white">
                  {result.path}
                </span>
              </div>
              <span
                className={`text-xs font-medium ${
                  result.match
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-red-600 dark:text-red-400"
                }`}
              >
                {result.match ? "Match" : "Mismatch"}
              </span>
            </div>

            {/* Side-by-side comparison */}
            <div className="grid gap-3 sm:grid-cols-2">
              {/* MuleSoft */}
              <div>
                <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
                  <ArrowLeftRight className="h-3 w-3" />
                  MuleSoft
                  {result.mulesoft.status !== undefined && (
                    <span
                      className={`ml-auto rounded px-1.5 py-0.5 text-xs ${
                        result.mulesoft.status < 400
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                          : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                      }`}
                    >
                      {result.mulesoft.status}
                    </span>
                  )}
                </div>
                <pre className="max-h-40 overflow-auto rounded bg-gray-950 p-2 font-mono text-xs text-gray-300 whitespace-pre-wrap">
                  {result.mulesoft.error || formatBody(result.mulesoft.body) || "No response"}
                </pre>
              </div>

              {/* Spring Boot */}
              <div>
                <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
                  <ArrowLeftRight className="h-3 w-3" />
                  Spring Boot
                  {result.springboot.status !== undefined && (
                    <span
                      className={`ml-auto rounded px-1.5 py-0.5 text-xs ${
                        result.springboot.status < 400
                          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                          : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                      }`}
                    >
                      {result.springboot.status}
                    </span>
                  )}
                </div>
                <pre className="max-h-40 overflow-auto rounded bg-gray-950 p-2 font-mono text-xs text-gray-300 whitespace-pre-wrap">
                  {result.springboot.error || formatBody(result.springboot.body) || "No response"}
                </pre>
              </div>
            </div>
          </div>
        ))}
      </div>
    </GlassCard>
  );
}
