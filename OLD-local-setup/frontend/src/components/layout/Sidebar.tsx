import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  ArrowRightLeft,
  History,
  FileJson2,
  Github,
  BookOpen,
  Settings,
  ChevronLeft,
  ChevronRight,
  Zap,
  User,
} from "lucide-react";
import { useSettingsStore } from "@/store/settings";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard", badge: null },
  { to: "/migrate", icon: ArrowRightLeft, label: "Migrate", badge: null },
  { to: "/history", icon: History, label: "History", badge: null },
  { to: "/swagger", icon: FileJson2, label: "Swagger", badge: null },
  { to: "/github", icon: Github, label: "GitHub", badge: null },
  { to: "/knowledge", icon: BookOpen, label: "Knowledge", badge: null },
];

export default function Sidebar() {
  const collapsed = useSettingsStore((s) => s.sidebarCollapsed);
  const toggle = useSettingsStore((s) => s.setSidebarCollapsed);

  return (
    <aside
      className={`fixed left-0 top-0 z-30 flex h-screen flex-col
        bg-[#1B365D] text-white
        transition-all duration-300 ease-in-out
        ${collapsed ? "w-[68px]" : "w-64"}`}
    >
      {/* Capgemini blue accent line at top */}
      <div className="absolute top-0 left-0 right-0 h-[3px] bg-[#0070AD]" />

      {/* Logo / Brand */}
      <div className="flex h-16 items-center gap-3 px-4 mt-[3px]">
        <div className="relative flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[#0070AD]">
          <Zap className="h-5 w-5 text-white" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden animate-fade-in">
            <h1 className="truncate text-sm font-bold text-white">
              Mule Migrator
            </h1>
            <p className="truncate text-[10px] text-[#12ABDB] font-medium tracking-wider uppercase">
              MuleSoft to Spring Boot
            </p>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="mx-3 h-px bg-white/10" />

      {/* Navigation */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium
              transition-all duration-200
              ${isActive
                ? "bg-[#0070AD] text-white"
                : "text-white/70 hover:bg-white/10 hover:text-white"
              }
              ${collapsed ? "justify-center px-2" : ""}`
            }
            title={collapsed ? item.label : undefined}
          >
            {({ isActive }) => (
              <>
                <item.icon
                  className={`h-[18px] w-[18px] flex-shrink-0 transition-colors duration-200
                    ${isActive ? "text-white" : "text-white/60 group-hover:text-white"}`}
                />
                {!collapsed && (
                  <span className="flex-1">{item.label}</span>
                )}
                {!collapsed && item.badge !== null && (
                  <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[#12ABDB]/20 px-1.5 text-[10px] font-semibold text-[#12ABDB]">
                    {item.badge}
                  </span>
                )}
                {/* Active indicator line */}
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 h-6 w-[3px] rounded-r-full bg-[#12ABDB]" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="space-y-1 px-3 pb-3">
        {/* Divider */}
        <div className="mx-0 h-px bg-white/10 mb-2" />

        {/* Settings */}
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            `group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium
            transition-all duration-200
            ${isActive
              ? "bg-[#0070AD] text-white"
              : "text-white/60 hover:bg-white/10 hover:text-white"
            }
            ${collapsed ? "justify-center px-2" : ""}`
          }
          title={collapsed ? "Settings" : undefined}
        >
          <Settings className="h-[18px] w-[18px] flex-shrink-0" />
          {!collapsed && <span>Settings</span>}
        </NavLink>

        {/* User info - hidden when collapsed */}
        {!collapsed && (
          <div className="mt-1 px-3 py-2">
            <div className="flex items-center gap-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#0070AD]">
                <User className="h-3.5 w-3.5 text-white" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-white/90 truncate" id="sidebar-user-name">User</p>
                <a
                  href="/.auth/logout?post_logout_redirect_uri=/"
                  className="text-[10px] text-red-300 hover:text-red-200 truncate block"
                >
                  Sign Out
                </a>
              </div>
            </div>
          </div>
        )}

        {/* Collapse toggle */}
        <button
          onClick={() => toggle(!collapsed)}
          className="flex w-full items-center justify-center rounded-lg p-2 text-white/50 transition-all duration-200 hover:bg-white/10 hover:text-white"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </div>
    </aside>
  );
}
