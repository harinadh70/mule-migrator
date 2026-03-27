import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Search,
  Filter,
  ExternalLink,
  Trash2,
  Clock,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useMigrationList, useDeleteMigration } from "@/hooks/useMigration";
import type { Status } from "@/types/common";
import { showToast } from "@/components/layout/Layout";

const STATUS_OPTIONS: { label: string; value: string }[] = [
  { label: "All Status", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Running", value: "running" },
  { label: "Completed", value: "completed" },
  { label: "Failed", value: "failed" },
  { label: "Cancelled", value: "cancelled" },
];

function StatusBadge({ status }: { status: Status }) {
  const classes: Record<Status, string> = {
    pending: "badge-pending",
    running: "badge-running",
    completed: "badge-completed",
    failed: "badge-failed",
    cancelled: "badge-cancelled",
  };

  return (
    <span className={classes[status]}>
      {status === "running" && (
        <span className="mr-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
      )}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

export default function MigrationHistory() {
  const [page, setPage] = useState(1);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const pageSize = 15;

  const { data, isLoading } = useMigrationList({
    page,
    pageSize,
    status: statusFilter || undefined,
    search: searchQuery || undefined,
  });

  const deleteMutation = useDeleteMigration();

  function handleDelete(id: string, name: string) {
    if (!confirm(`Delete migration "${name}"? This cannot be undone.`)) return;

    deleteMutation.mutate(id, {
      onSuccess: () => {
        showToast({ type: "success", title: "Migration deleted" });
      },
      onError: () => {
        showToast({ type: "error", title: "Failed to delete migration" });
      },
    });
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function formatDuration(ms: number | undefined): string {
    if (!ms) return "--";
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
    return `${(ms / 60_000).toFixed(1)}m`;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          Migration History
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Browse and manage all past migration jobs
        </p>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search migrations..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            className="input pl-9"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="select w-40"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800/50">
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Name</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Status</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Source</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Duration</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Created</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Tokens</th>
                <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400" />
              </tr>
            </thead>
            <tbody>
              {isLoading &&
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="border-b border-gray-100 dark:border-gray-700">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="skeleton h-4 w-20" />
                      </td>
                    ))}
                  </tr>
                ))}

              {!isLoading && data?.items.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-500">
                    No migrations found.
                  </td>
                </tr>
              )}

              {!isLoading &&
                data?.items.map((m) => (
                  <tr
                    key={m.id}
                    className="border-b border-gray-100 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800/30"
                  >
                    <td className="px-4 py-3">
                      <Link
                        to={`/migrate/${m.id}`}
                        className="font-medium text-gray-900 hover:text-brand-600 dark:text-white"
                      >
                        {m.name}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={m.status} />
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-300">
                      {m.sourceType}
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-300">
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3.5 w-3.5" />
                        {formatDuration(m.durationMs)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                      {formatDate(m.createdAt)}
                    </td>
                    <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                      {m.tokensUsed?.toLocaleString() || "--"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <Link
                          to={`/migrate/${m.id}`}
                          className="btn-ghost px-2 py-1"
                          title="View"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Link>
                        <button
                          onClick={() => handleDelete(m.id, m.name)}
                          className="btn-ghost px-2 py-1 text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20"
                          title="Delete"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.totalPages > 1 && (
          <div className="flex items-center justify-between border-t border-gray-200 px-4 py-3 dark:border-gray-700">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Showing {(page - 1) * pageSize + 1}-
              {Math.min(page * pageSize, data.total)} of {data.total}
            </p>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="btn-ghost px-2 py-1"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              {Array.from({ length: Math.min(data.totalPages, 5) }).map(
                (_, i) => {
                  const pageNum = i + 1;
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setPage(pageNum)}
                      className={`rounded-lg px-3 py-1 text-sm ${
                        page === pageNum
                          ? "bg-brand-600 text-white"
                          : "text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800"
                      }`}
                    >
                      {pageNum}
                    </button>
                  );
                }
              )}
              <button
                onClick={() =>
                  setPage((p) => Math.min(data.totalPages, p + 1))
                }
                disabled={page === data.totalPages}
                className="btn-ghost px-2 py-1"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
