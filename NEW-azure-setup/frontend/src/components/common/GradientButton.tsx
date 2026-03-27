import type { ReactNode, ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

const variantStyles = {
  primary:
    "bg-[#0070AD] text-white hover:bg-[#005A8A] active:bg-[#004368] focus:ring-[#0070AD]/40",
  secondary:
    "bg-white dark:bg-white/[0.04] border border-[#0070AD]/30 dark:border-white/[0.1] text-[#0070AD] dark:text-gray-300 hover:bg-[#0070AD]/5 dark:hover:bg-white/[0.07] hover:border-[#0070AD]/50 focus:ring-[#0070AD]/20",
  danger:
    "bg-red-600 text-white hover:bg-red-700 active:bg-red-800 focus:ring-red-500/40",
  gradient:
    "bg-[#0070AD] text-white hover:bg-[#005A8A] active:bg-[#004368] focus:ring-[#0070AD]/40",
} as const;

const sizeStyles = {
  sm: "px-3 py-1.5 text-xs rounded-md gap-1.5",
  md: "px-4 py-2.5 text-sm rounded-lg gap-2",
  lg: "px-6 py-3 text-base rounded-lg gap-2.5",
} as const;

interface GradientButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  variant?: keyof typeof variantStyles;
  size?: keyof typeof sizeStyles;
  loading?: boolean;
  icon?: ReactNode;
}

export default function GradientButton({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  icon,
  className = "",
  disabled,
  ...props
}: GradientButtonProps) {
  return (
    <button
      className={`
        inline-flex items-center justify-center font-medium
        transition-all duration-200
        focus:outline-none focus:ring-2 focus:ring-offset-2
        dark:focus:ring-offset-navy-900
        disabled:opacity-40 disabled:cursor-not-allowed disabled:pointer-events-none
        ${variantStyles[variant]}
        ${sizeStyles[size]}
        ${className}
      `}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : icon ? (
        <span className="flex-shrink-0">{icon}</span>
      ) : null}
      {children}
    </button>
  );
}
