import { useState, useRef, useEffect } from "react";
import { useLocation, Link } from "react-router-dom";
import { Sun, Moon, Monitor, ChevronRight, User, LogOut, Bell } from "lucide-react";
import { useSettingsStore, type Theme } from "@/store/settings";
import { useAuthStore } from "@/store/auth";

const routeLabels: Record<string, string> = {
  dashboard: "Dashboard",
  migrate: "Migration",
  history: "Migration History",
  build: "Build & Test",
  swagger: "Swagger Preview",
  github: "GitHub Integration",
  knowledge: "RAG Knowledge Base",
  settings: "Settings",
};

const themeOptions: { value: Theme; icon: typeof Sun; label: string }[] = [
  { value: "light", icon: Sun, label: "Light" },
  { value: "dark", icon: Moon, label: "Dark" },
  { value: "system", icon: Monitor, label: "System" },
];

export default function Header() {
  const location = useLocation();
  const theme = useSettingsStore((s) => s.theme);
  const setTheme = useSettingsStore((s) => s.setTheme);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const segments = location.pathname.split("/").filter(Boolean);
  const breadcrumbs = segments.map((seg, i) => ({
    label: routeLabels[seg] || seg,
    path: "/" + segments.slice(0, i + 1).join("/"),
  }));

  const currentThemeOption = themeOptions.find((t) => t.value === theme);
  const ThemeIcon = currentThemeOption?.icon || Monitor;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function cycleTheme() {
    const idx = themeOptions.findIndex((t) => t.value === theme);
    const next = themeOptions[(idx + 1) % themeOptions.length];
    setTheme(next.value);
  }

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between px-6
      bg-white dark:bg-navy-800/90 dark:backdrop-blur-xl
      border-b-2 border-[#0070AD]/20 dark:border-[#0070AD]/30">

      {/* Breadcrumbs */}
      <nav className="flex items-center gap-1.5 text-sm">
        <Link
          to="/dashboard"
          className="text-capText-muted dark:text-gray-500 hover:text-primary dark:hover:text-gray-300 transition-colors duration-200"
        >
          Home
        </Link>
        {breadcrumbs.map((crumb) => (
          <span key={crumb.path} className="flex items-center gap-1.5">
            <ChevronRight className="h-3 w-3 text-gray-400 dark:text-gray-600" />
            <Link
              to={crumb.path}
              className="font-medium text-capText dark:text-gray-300 hover:text-primary dark:hover:text-white transition-colors duration-200"
            >
              {crumb.label}
            </Link>
          </span>
        ))}
      </nav>

      {/* Right side actions */}
      <div className="flex items-center gap-1">
        {/* Notification bell */}
        <button
          className="relative flex h-8 w-8 items-center justify-center rounded-lg text-capText-light dark:text-gray-500 transition-all duration-200 hover:bg-gray-100 dark:hover:bg-white/[0.04] hover:text-primary dark:hover:text-gray-300"
          title="Notifications"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute top-1.5 right-1.5 h-1.5 w-1.5 rounded-full bg-[#0070AD]" />
        </button>

        {/* Theme toggle */}
        <button
          onClick={cycleTheme}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-capText-light dark:text-gray-500 transition-all duration-200 hover:bg-gray-100 dark:hover:bg-white/[0.04] hover:text-primary dark:hover:text-gray-300"
          title={`Theme: ${currentThemeOption?.label}`}
        >
          <ThemeIcon className="h-4 w-4" />
        </button>

        {/* Divider */}
        <div className="mx-2 h-5 w-px bg-gray-200 dark:bg-white/[0.08]" />

        {/* User menu */}
        <div className="relative" ref={menuRef}>
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex h-8 items-center gap-2 rounded-lg px-2 text-sm transition-all duration-200 hover:bg-gray-100 dark:hover:bg-white/[0.04]"
          >
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#0070AD]">
              <User className="h-3 w-3 text-white" />
            </div>
            <span className="hidden text-xs font-medium text-capText-light dark:text-gray-400 sm:inline">
              {user?.name || "User"}
            </span>
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 top-full mt-2 w-52 rounded-xl overflow-hidden
              bg-white dark:bg-navy-800/95 dark:backdrop-blur-xl
              border border-gray-200 dark:border-white/[0.08]
              shadow-card-hover dark:shadow-glass-lg
              animate-slide-up">
              {user && (
                <div className="border-b border-gray-200 dark:border-white/[0.06] px-4 py-3">
                  <p className="text-sm font-semibold text-capText dark:text-white">
                    {user.name}
                  </p>
                  <p className="text-xs text-capText-muted dark:text-gray-500 mt-0.5">
                    {user.email}
                  </p>
                </div>
              )}
              <div className="p-1">
                <Link
                  to="/settings"
                  onClick={() => setUserMenuOpen(false)}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-capText-light dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-white/[0.04] hover:text-capText dark:hover:text-gray-200 transition-colors"
                >
                  Settings
                </Link>
                <button
                  onClick={() => {
                    logout();
                    setUserMenuOpen(false);
                  }}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 transition-colors"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Sign out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
