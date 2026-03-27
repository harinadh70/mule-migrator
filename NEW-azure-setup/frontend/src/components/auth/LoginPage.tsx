import { login } from "@/auth/msalConfig";
import { Zap } from "lucide-react";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#f5f5f5] dark:bg-[#0a0f1e]">
      <div className="w-full max-w-md p-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-[#0070AD] mb-4">
            <Zap className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-[#1B365D] dark:text-white">
            Mule Migrator
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            MuleSoft to Spring Boot — Agentic AI Platform
          </p>
        </div>

        {/* Login Card */}
        <div className="bg-white dark:bg-white/[0.05] rounded-xl border border-gray-200 dark:border-white/[0.08] p-8 shadow-sm">
          <h2 className="text-lg font-semibold text-[#1B365D] dark:text-white text-center mb-2">
            Sign In
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 text-center mb-6">
            Use your organization account to continue
          </p>

          <button
            onClick={() => login()}
            className="w-full flex items-center justify-center gap-3 px-4 py-3 bg-[#0070AD] text-white rounded-lg font-medium hover:bg-[#005A8A] transition-colors"
          >
            <svg className="h-5 w-5" viewBox="0 0 21 21" fill="none">
              <rect width="10" height="10" fill="#f25022" />
              <rect x="11" width="10" height="10" fill="#7fba00" />
              <rect y="11" width="10" height="10" fill="#00a4ef" />
              <rect x="11" y="11" width="10" height="10" fill="#ffb900" />
            </svg>
            Sign in with Microsoft
          </button>

          <div className="mt-6 pt-4 border-t border-gray-100 dark:border-white/[0.06]">
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
              <span>Secured by Azure Entra ID</span>
            </div>
          </div>
        </div>

        <p className="text-xs text-gray-400 text-center mt-6">
          Protected by enterprise-grade security
        </p>
      </div>
    </div>
  );
}
