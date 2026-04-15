import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuthStore } from "@/store/auth";
import { isAzureAdEnabled, loginWithMicrosoft } from "@/auth/msalConfig";
import { Zap } from "lucide-react";
import api from "@/api/client";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirect = searchParams.get("redirect") || "/dashboard";
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // If already authenticated (e.g. just returned from MSAL redirect), go to dashboard
  useEffect(() => {
    if (isAuthenticated) {
      navigate(redirect, { replace: true });
    }
  }, [isAuthenticated, navigate, redirect]);

  function handleMicrosoftLogin() {
    // This navigates away from the page to Microsoft login
    // On return, main.tsx processes the response before React renders
    loginWithMicrosoft();
  }

  async function handleEmailLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { data } = await api.post("/auth/login", { email, password });
      localStorage.setItem("auth-token", data.token);
      useAuthStore.setState({
        isAuthenticated: true,
        token: data.token,
        user: data.user,
      });
      navigate(redirect, { replace: true });
    } catch (err: any) {
      setError(err?.message || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

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
            Choose your sign-in method
          </p>

          {error && (
            <div className="mb-4 rounded-lg bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 p-3 text-sm text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          {/* Microsoft Login */}
          {isAzureAdEnabled && (
            <>
              <button
                onClick={handleMicrosoftLogin}
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

              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200 dark:border-white/[0.08]" />
                </div>
                <div className="relative flex justify-center text-xs">
                  <span className="bg-white dark:bg-[#0d1117] px-3 text-gray-400">or</span>
                </div>
              </div>
            </>
          )}

          {/* Email/Password */}
          <form onSubmit={handleEmailLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 dark:border-white/[0.12] bg-white dark:bg-white/[0.04] text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#0070AD] focus:border-transparent"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                className="w-full px-3 py-2.5 rounded-lg border border-gray-300 dark:border-white/[0.12] bg-white dark:bg-white/[0.04] text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#0070AD] focus:border-transparent"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gray-800 dark:bg-white/[0.1] text-white rounded-lg font-medium hover:bg-gray-700 dark:hover:bg-white/[0.15] transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading && <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />}
              {loading ? "Signing in..." : "Sign in with Email"}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-gray-100 dark:border-white/[0.06]">
            <div className="flex items-center gap-2 text-xs text-gray-400">
              <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
              <span>Secured by Azure Entra ID</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
