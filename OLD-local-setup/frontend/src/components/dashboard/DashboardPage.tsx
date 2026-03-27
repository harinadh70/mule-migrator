import { Link } from "react-router-dom";
import {
  Plus,
  TrendingUp,
  Calendar,
  ArrowRight,
  Activity,
  BookOpen,
  Settings,
  Zap,
} from "lucide-react";
import StatsCards from "./StatsCards";
import RecentMigrations from "./RecentMigrations";
import GlassCard from "@/components/common/GlassCard";
import GradientButton from "@/components/common/GradientButton";
import { useMigrationStats, useMigrationList } from "@/hooks/useMigration";

// Simple CSS bar chart data
const chartBars = [
  { label: "Mon", value: 65 },
  { label: "Tue", value: 80 },
  { label: "Wed", value: 45 },
  { label: "Thu", value: 90 },
  { label: "Fri", value: 70 },
  { label: "Sat", value: 30 },
  { label: "Sun", value: 55 },
];

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useMigrationStats();
  const { data: migrationsData, isLoading: migrationsLoading } =
    useMigrationList({ page: 1, pageSize: 10 });

  return (
    <div className="space-y-8 animate-fade-in">
      {/* Hero section */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-[#0070AD] uppercase tracking-wider">
              Agentic AI Migration Platform
            </span>
          </div>
          <h1 className="text-3xl font-bold text-capText dark:text-white">
            Welcome to Mule Migrator
          </h1>
          <p className="mt-2 text-sm text-capText-light dark:text-gray-400 max-w-lg">
            Overview of your MuleSoft to Spring Boot migrations. Monitor agent activity,
            track progress, and launch new migrations.
          </p>
        </div>
        <Link to="/migrate">
          <GradientButton variant="primary" icon={<Plus className="h-4 w-4" />}>
            New Migration
          </GradientButton>
        </Link>
      </div>

      {/* Stats Cards */}
      <StatsCards stats={stats} isLoading={statsLoading} />

      {/* Content grid */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Recent migrations - takes 2/3 */}
        <div className="xl:col-span-2">
          <RecentMigrations
            migrations={migrationsData?.items}
            isLoading={migrationsLoading}
          />
        </div>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Agent Activity / Chart */}
          <GlassCard accentColor="blue">
            <div className="flex items-center justify-between mb-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-capText dark:text-white">
                <Activity className="h-4 w-4 text-[#0070AD]" />
                Weekly Activity
              </h3>
              <span className="text-[10px] font-medium text-capText-muted dark:text-gray-500 uppercase tracking-wider">
                Last 7 days
              </span>
            </div>
            {/* CSS Bar Chart */}
            <div className="flex items-end gap-2 h-28">
              {chartBars.map((bar, i) => (
                <div key={i} className="flex-1 flex flex-col items-center gap-1.5">
                  <div className="w-full relative" style={{ height: "100%" }}>
                    <div
                      className="absolute bottom-0 w-full rounded-t-md bg-[#0070AD]/60 dark:bg-[#0070AD]/40
                        hover:bg-[#0070AD]/80 dark:hover:bg-[#0070AD]/60
                        transition-all duration-200 cursor-pointer"
                      style={{ height: `${bar.value}%` }}
                    />
                  </div>
                  <span className="text-[9px] text-capText-muted dark:text-gray-500 font-medium">{bar.label}</span>
                </div>
              ))}
            </div>
          </GlassCard>

          {/* This Week summary */}
          <GlassCard accentColor="blue">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-capText dark:text-white">
              <TrendingUp className="h-4 w-4 text-[#0070AD]" />
              This Week
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-capText-light dark:text-gray-500">Migrations</span>
                <span className="text-sm font-semibold text-capText dark:text-white tabular-nums">
                  {stats?.migrationsThisWeek ?? 0}
                </span>
              </div>
              <div className="h-px bg-gray-200 dark:bg-white/[0.04]" />
              <div className="flex items-center justify-between">
                <span className="text-sm text-capText-light dark:text-gray-500">Successful</span>
                <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 tabular-nums">
                  {stats?.successfulMigrations ?? 0}
                </span>
              </div>
              <div className="h-px bg-gray-200 dark:bg-white/[0.04]" />
              <div className="flex items-center justify-between">
                <span className="text-sm text-capText-light dark:text-gray-500">Failed</span>
                <span className="text-sm font-semibold text-red-600 dark:text-red-400 tabular-nums">
                  {stats?.failedMigrations ?? 0}
                </span>
              </div>
            </div>
          </GlassCard>

          {/* This Month */}
          <GlassCard accentColor="blue">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-capText dark:text-white">
              <Calendar className="h-4 w-4 text-[#12ABDB]" />
              This Month
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-capText-light dark:text-gray-500">Total Migrations</span>
                <span className="text-sm font-semibold text-capText dark:text-white tabular-nums">
                  {stats?.migrationsThisMonth ?? 0}
                </span>
              </div>
              <div className="h-px bg-gray-200 dark:bg-white/[0.04]" />
              <div className="flex items-center justify-between">
                <span className="text-sm text-capText-light dark:text-gray-500">Tokens Consumed</span>
                <span className="text-sm font-semibold text-capText dark:text-white tabular-nums">
                  {stats?.totalTokensUsed
                    ? (stats.totalTokensUsed / 1000).toFixed(1) + "K"
                    : "0"}
                </span>
              </div>
              <div className="h-px bg-gray-200 dark:bg-white/[0.04]" />
              <div className="flex items-center justify-between">
                <span className="text-sm text-capText-light dark:text-gray-500">Success Rate</span>
                <span className="text-sm font-semibold text-emerald-600 dark:text-emerald-400 tabular-nums">
                  {stats?.successRate?.toFixed(1) ?? "0"}%
                </span>
              </div>
            </div>
          </GlassCard>

          {/* Quick Actions */}
          <GlassCard>
            <h3 className="mb-4 text-sm font-semibold text-capText dark:text-white">
              Quick Actions
            </h3>
            <div className="space-y-2">
              <Link
                to="/migrate"
                className="group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-capText-light dark:text-gray-400
                  hover:bg-gray-50 dark:hover:bg-white/[0.04] hover:text-capText dark:hover:text-white transition-all duration-200"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#0070AD]/10">
                  <Zap className="h-4 w-4 text-[#0070AD]" />
                </div>
                <span className="flex-1">New Migration</span>
                <ArrowRight className="h-3.5 w-3.5 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
              </Link>
              <Link
                to="/knowledge"
                className="group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-capText-light dark:text-gray-400
                  hover:bg-gray-50 dark:hover:bg-white/[0.04] hover:text-capText dark:hover:text-white transition-all duration-200"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#1B365D]/10">
                  <BookOpen className="h-4 w-4 text-[#1B365D] dark:text-[#12ABDB]" />
                </div>
                <span className="flex-1">Manage Knowledge Base</span>
                <ArrowRight className="h-3.5 w-3.5 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
              </Link>
              <Link
                to="/history"
                className="group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-capText-light dark:text-gray-400
                  hover:bg-gray-50 dark:hover:bg-white/[0.04] hover:text-capText dark:hover:text-white transition-all duration-200"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#12ABDB]/10">
                  <Settings className="h-4 w-4 text-[#12ABDB]" />
                </div>
                <span className="flex-1">Migration History</span>
                <ArrowRight className="h-3.5 w-3.5 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all" />
              </Link>
            </div>
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
