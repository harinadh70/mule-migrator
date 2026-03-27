import {
  ArrowRightLeft,
  CheckCircle,
  Clock,
  Coins,
  TrendingUp,
} from "lucide-react";
import AnimatedCounter from "@/components/common/AnimatedCounter";
import GlassCard from "@/components/common/GlassCard";
import type { MigrationStats } from "@/types/migration";

interface StatsCardsProps {
  stats: MigrationStats | null | undefined;
  isLoading: boolean;
}

interface StatCardProps {
  label: string;
  value: number;
  format?: "number" | "percentage" | "duration" | "compact";
  icon: typeof ArrowRightLeft;
  accentColor: "blue" | "purple" | "cyan" | "green" | "red" | "amber";
  iconBg: string;
  iconColor: string;
  trend?: string;
  trendUp?: boolean;
  isLoading: boolean;
}

function StatCard({
  label,
  value,
  format,
  icon: Icon,
  accentColor,
  iconBg,
  iconColor,
  trend,
  trendUp,
  isLoading,
}: StatCardProps) {
  if (isLoading) {
    return (
      <GlassCard accentColor={accentColor}>
        <div className="flex items-start justify-between">
          <div className="space-y-3 flex-1">
            <div className="skeleton h-3.5 w-24" />
            <div className="skeleton h-8 w-20" />
            <div className="skeleton h-3 w-16" />
          </div>
          <div className="skeleton h-11 w-11 rounded-xl" />
        </div>
      </GlassCard>
    );
  }

  return (
    <GlassCard accentColor={accentColor} hover>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium text-capText-muted dark:text-gray-500 uppercase tracking-wider">
            {label}
          </p>
          <p className="mt-2 text-3xl font-bold text-capText dark:text-white">
            <AnimatedCounter value={value} format={format} />
          </p>
          {trend && (
            <div className="mt-2 flex items-center gap-1">
              <TrendingUp
                className={`h-3 w-3 ${trendUp ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400 rotate-180"}`}
              />
              <span
                className={`text-xs font-medium ${trendUp ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"}`}
              >
                {trend}
              </span>
              <span className="text-xs text-capText-muted dark:text-gray-600">vs last week</span>
            </div>
          )}
        </div>
        <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${iconBg}`}>
          <Icon className={`h-5 w-5 ${iconColor}`} />
        </div>
      </div>
    </GlassCard>
  );
}

export default function StatsCards({ stats, isLoading }: StatsCardsProps) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        label="Total Migrations"
        value={stats?.totalMigrations ?? 0}
        icon={ArrowRightLeft}
        accentColor="blue"
        iconBg="bg-[#0070AD]/10"
        iconColor="text-[#0070AD]"
        trend="+12%"
        trendUp={true}
        isLoading={isLoading}
      />
      <StatCard
        label="Success Rate"
        value={stats?.successRate ?? 0}
        format="percentage"
        icon={CheckCircle}
        accentColor="green"
        iconBg="bg-emerald-500/10"
        iconColor="text-emerald-600 dark:text-emerald-400"
        trend="+3.2%"
        trendUp={true}
        isLoading={isLoading}
      />
      <StatCard
        label="Avg Duration"
        value={stats?.averageDurationMs ?? 0}
        format="duration"
        icon={Clock}
        accentColor="blue"
        iconBg="bg-[#12ABDB]/10"
        iconColor="text-[#12ABDB]"
        trend="-8%"
        trendUp={true}
        isLoading={isLoading}
      />
      <StatCard
        label="Tokens Used"
        value={stats?.totalTokensUsed ?? 0}
        format="compact"
        icon={Coins}
        accentColor="amber"
        iconBg="bg-amber-500/10"
        iconColor="text-amber-600 dark:text-amber-400"
        isLoading={isLoading}
      />
    </div>
  );
}
