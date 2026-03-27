import { CheckCircle, XCircle, Loader2, Clock, AlertCircle } from "lucide-react";

type BadgeStatus = "running" | "completed" | "failed" | "pending" | "queued" | "cancelled";

const statusConfig: Record<
  BadgeStatus,
  {
    label: string;
    classes: string;
    icon: typeof Clock;
    iconClass: string;
  }
> = {
  pending: {
    label: "Pending",
    classes: "bg-gray-100 dark:bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-500/20",
    icon: Clock,
    iconClass: "text-gray-500 dark:text-gray-400",
  },
  queued: {
    label: "Queued",
    classes: "bg-gray-100 dark:bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-200 dark:border-gray-500/20",
    icon: Clock,
    iconClass: "text-gray-500 dark:text-gray-400",
  },
  running: {
    label: "Running",
    classes: "bg-[#0070AD]/10 text-[#0070AD] dark:text-[#12ABDB] border-[#0070AD]/20",
    icon: Loader2,
    iconClass: "text-[#0070AD] dark:text-[#12ABDB] animate-spin",
  },
  completed: {
    label: "Completed",
    classes: "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20",
    icon: CheckCircle,
    iconClass: "text-emerald-600 dark:text-emerald-400",
  },
  failed: {
    label: "Failed",
    classes: "bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20",
    icon: XCircle,
    iconClass: "text-red-600 dark:text-red-400",
  },
  cancelled: {
    label: "Cancelled",
    classes: "bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-200 dark:border-amber-500/20",
    icon: AlertCircle,
    iconClass: "text-amber-600 dark:text-amber-400",
  },
};

interface StatusBadgeProps {
  status: BadgeStatus;
  pulse?: boolean;
  showLabel?: boolean;
  size?: "sm" | "md";
}

export default function StatusBadge({
  status,
  pulse = false,
  showLabel = true,
  size = "md",
}: StatusBadgeProps) {
  const config = statusConfig[status] || statusConfig.pending;
  const Icon = config.icon;
  const shouldPulse = pulse || status === "running";

  const sizeClasses = size === "sm"
    ? "px-2 py-0.5 text-[10px] gap-1"
    : "px-2.5 py-1 text-xs gap-1.5";

  return (
    <span
      className={`
        inline-flex items-center rounded-full font-medium border
        transition-all duration-200
        ${config.classes}
        ${sizeClasses}
      `}
    >
      <span className="relative flex-shrink-0">
        <Icon className={`${size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} ${config.iconClass}`} />
        {shouldPulse && (
          <span className="absolute inset-0 rounded-full animate-ping opacity-20">
            <Icon className={`${size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} ${config.iconClass}`} />
          </span>
        )}
      </span>
      {showLabel && <span>{config.label}</span>}
    </span>
  );
}
