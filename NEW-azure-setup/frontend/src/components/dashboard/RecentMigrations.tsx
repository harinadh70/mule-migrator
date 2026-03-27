import { Link } from "react-router-dom";
import { ExternalLink, Clock } from "lucide-react";
import type { MigrationJob } from "@/types/migration";
import type { Status } from "@/types/common";

interface RecentMigrationsProps {
  migrations: MigrationJob[] | undefined;
  isLoading: boolean;
}

function StatusBadge({ status }: { status: Status }) {
  const classes: Record<Status, string> = {
    pending: "badge-pending",
    running: "badge-running",
    completed: "badge-completed",
    failed: "badge-failed",
    cancelled: "badge-cancelled",
  };

  return (
    <span className={classes[status] || "badge-pending"}>
      {status === "running" && (
        <span className="mr-1.5 inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
      )}
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

function formatDuration(ms: number | undefined): string {
  if (!ms) return "--";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60_000).toFixed(1)}m`;
}

function SkeletonRow() {
  return (
    <tr className="border-b border-gray-100 dark:border-gray-700">
      <td className="px-4 py-3"><div className="skeleton h-4 w-40" /></td>
      <td className="px-4 py-3"><div className="skeleton h-5 w-20" /></td>
      <td className="px-4 py-3"><div className="skeleton h-4 w-16" /></td>
      <td className="px-4 py-3"><div className="skeleton h-4 w-24" /></td>
      <td className="px-4 py-3"><div className="skeleton h-4 w-8" /></td>
    </tr>
  );
}

export default function RecentMigrations({
  migrations,
  isLoading,
}: RecentMigrationsProps) {
  return (
    <div className="card overflow-hidden p-0">
      <div className="flex items-center justify-between border-b border-gray-200 px-6 py-4 dark:border-gray-700">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
          Recent Migrations
        </h3>
        <Link
          to="/history"
          className="text-sm font-medium text-brand-600 hover:text-brand-700 dark:text-brand-400"
        >
          View all
        </Link>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800/50">
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                Name
              </th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                Status
              </th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                Duration
              </th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">
                Created
              </th>
              <th className="px-4 py-3 font-medium text-gray-500 dark:text-gray-400" />
            </tr>
          </thead>
          <tbody>
            {isLoading &&
              Array.from({ length: 5 }).map((_, i) => (
                <SkeletonRow key={i} />
              ))}

            {!isLoading && migrations?.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-4 py-12 text-center text-gray-500 dark:text-gray-400"
                >
                  No migrations yet. Start your first migration to see it
                  here.
                </td>
              </tr>
            )}

            {!isLoading &&
              migrations?.slice(0, 10).map((migration) => (
                <tr
                  key={migration.id}
                  className="border-b border-gray-100 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:hover:bg-gray-800/30"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/migrate/${migration.id}`}
                      className="font-medium text-gray-900 hover:text-brand-600 dark:text-white dark:hover:text-brand-400"
                    >
                      {migration.name}
                    </Link>
                    <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                      {migration.sourceType} &rarr;{" "}
                      {migration.targetFramework}
                    </p>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={migration.status} />
                  </td>
                  <td className="px-4 py-3 text-gray-600 dark:text-gray-300">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      {formatDuration(migration.durationMs)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500 dark:text-gray-400">
                    {formatRelativeTime(migration.createdAt)}
                  </td>
                  <td className="px-4 py-3">
                    <Link
                      to={`/migrate/${migration.id}`}
                      className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </Link>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
