import { type ReactNode, useState, useCallback, useEffect } from "react";
import Sidebar from "./Sidebar";
import Header from "./Header";
import { useSettingsStore } from "@/store/settings";
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from "lucide-react";
import type { Toast } from "@/types/common";

// Simple toast context for the app
let addToastFn: ((toast: Omit<Toast, "id">) => void) | null = null;

export function showToast(toast: Omit<Toast, "id">) {
  addToastFn?.(toast);
}

const toastIcons = {
  success: CheckCircle,
  error: AlertCircle,
  info: Info,
  warning: AlertTriangle,
};

const toastStyles = {
  success:
    "border-l-emerald-500 bg-emerald-50 dark:bg-emerald-500/10 text-emerald-800 dark:text-emerald-300",
  error:
    "border-l-red-500 bg-red-50 dark:bg-red-500/10 text-red-800 dark:text-red-300",
  info:
    "border-l-[#0070AD] bg-blue-50 dark:bg-[#0070AD]/10 text-[#0070AD] dark:text-[#12ABDB]",
  warning:
    "border-l-amber-500 bg-amber-50 dark:bg-amber-500/10 text-amber-800 dark:text-amber-300",
};

export default function Layout({ children }: { children: ReactNode }) {
  const collapsed = useSettingsStore((s) => s.sidebarCollapsed);
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Fetch Azure AD user info and set on sidebar/header
  useEffect(() => {
    fetch("/.auth/me")
      .then((r) => r.json())
      .then((data) => {
        const principal = data?.clientPrincipal;
        if (principal) {
          const name = principal.userDetails || principal.userId || "User";
          // Update sidebar user name
          const el = document.getElementById("sidebar-user-name");
          if (el) el.textContent = name;
          // Store in window for Header to use
          (window as any).__azureUser = { name, email: principal.userDetails };
        }
      })
      .catch(() => {});
  }, []);

  const addToast = useCallback((toast: Omit<Toast, "id">) => {
    const id = crypto.randomUUID();
    const newToast = { ...toast, id };
    setToasts((prev) => [...prev, newToast]);

    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, toast.duration || 5000);
  }, []);

  addToastFn = addToast;

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <div className="flex h-screen overflow-hidden bg-[#F5F5F5] dark:bg-navy-900">
      {/* Subtle background overlay (dark mode only) */}
      <div className="fixed inset-0 mesh-gradient pointer-events-none" />

      <Sidebar />

      <div
        className={`relative flex flex-1 flex-col transition-all duration-300 ease-in-out ${
          collapsed ? "ml-[68px]" : "ml-64"
        }`}
      >
        <Header />

        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>

      {/* Toast container - Capgemini styled */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-3">
        {toasts.map((toast) => {
          const Icon = toastIcons[toast.type];
          return (
            <div
              key={toast.id}
              className={`
                flex items-start gap-3 rounded-lg border-l-4 p-4
                bg-white dark:bg-navy-800/95 dark:backdrop-blur-xl
                border border-gray-200 dark:border-white/[0.08]
                shadow-card-hover
                animate-slide-in
                ${toastStyles[toast.type]}
              `}
              style={{ minWidth: 320 }}
            >
              <Icon className="mt-0.5 h-5 w-5 flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold">{toast.title}</p>
                {toast.message && (
                  <p className="mt-1 text-xs opacity-70">{toast.message}</p>
                )}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="flex-shrink-0 opacity-40 hover:opacity-100 transition-opacity"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
