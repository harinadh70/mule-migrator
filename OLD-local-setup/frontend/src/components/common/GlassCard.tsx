import type { ReactNode, HTMLAttributes } from "react";

const accentStyles = {
  blue: "border-t-[#0070AD]",
  purple: "border-t-[#2B0A3D]",
  cyan: "border-t-[#12ABDB]",
  green: "border-t-emerald-500",
  red: "border-t-red-500",
  amber: "border-t-amber-500",
} as const;

interface GlassCardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  className?: string;
  accentColor?: keyof typeof accentStyles;
  hover?: boolean;
  padding?: "none" | "sm" | "md" | "lg";
}

const paddingMap = {
  none: "",
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
};

export default function GlassCard({
  children,
  className = "",
  accentColor,
  hover = false,
  padding = "md",
  ...props
}: GlassCardProps) {
  const baseClasses =
    "bg-white dark:bg-white/[0.04] dark:backdrop-blur-xl border border-gray-200 dark:border-white/[0.08] rounded-xl shadow-card dark:shadow-glass transition-all duration-200";
  const hoverClasses = hover
    ? "hover:shadow-card-hover dark:hover:bg-white/[0.06] dark:hover:border-white/[0.12] cursor-pointer"
    : "";
  const accentClasses = accentColor ? `border-t-[3px] ${accentStyles[accentColor]}` : "";
  const pad = paddingMap[padding];

  return (
    <div
      className={`${baseClasses} ${hoverClasses} ${accentClasses} ${pad} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
