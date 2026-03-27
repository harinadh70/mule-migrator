import { create } from "zustand";
import { persist } from "zustand/middleware";

export type Theme = "light" | "dark" | "system";
export type LLMProvider = "openai" | "anthropic" | "azure" | "local";

interface SettingsState {
  theme: Theme;
  llmProvider: LLMProvider;
  llmModel: string;
  apiKeys: Record<string, string>;
  defaultGroupId: string;
  defaultBasePackage: string;
  defaultJavaVersion: "17" | "21";
  defaultSpringBootVersion: "3.2" | "3.3";
  defaultBuildTool: "maven" | "gradle";
  sidebarCollapsed: boolean;

  setTheme: (theme: Theme) => void;
  setLLMProvider: (provider: LLMProvider) => void;
  setLLMModel: (model: string) => void;
  setApiKey: (provider: string, key: string) => void;
  setDefaultGroupId: (id: string) => void;
  setDefaultBasePackage: (pkg: string) => void;
  setDefaultJavaVersion: (version: "17" | "21") => void;
  setDefaultSpringBootVersion: (version: "3.2" | "3.3") => void;
  setDefaultBuildTool: (tool: "maven" | "gradle") => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: "system",
      llmProvider: "openai",
      llmModel: "gpt-4o",
      apiKeys: {},
      defaultGroupId: "com.example",
      defaultBasePackage: "com.example.app",
      defaultJavaVersion: "21",
      defaultSpringBootVersion: "3.3",
      defaultBuildTool: "maven",
      sidebarCollapsed: false,

      setTheme: (theme) => {
        set({ theme });
        applyTheme(theme);
      },
      setLLMProvider: (llmProvider) => set({ llmProvider }),
      setLLMModel: (llmModel) => set({ llmModel }),
      setApiKey: (provider, key) =>
        set((state) => ({
          apiKeys: { ...state.apiKeys, [provider]: key },
        })),
      setDefaultGroupId: (defaultGroupId) => set({ defaultGroupId }),
      setDefaultBasePackage: (defaultBasePackage) =>
        set({ defaultBasePackage }),
      setDefaultJavaVersion: (defaultJavaVersion) =>
        set({ defaultJavaVersion }),
      setDefaultSpringBootVersion: (defaultSpringBootVersion) =>
        set({ defaultSpringBootVersion }),
      setDefaultBuildTool: (defaultBuildTool) => set({ defaultBuildTool }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
    }),
    {
      name: "migrator-settings",
      partialize: (state) => ({
        theme: state.theme,
        llmProvider: state.llmProvider,
        llmModel: state.llmModel,
        defaultGroupId: state.defaultGroupId,
        defaultBasePackage: state.defaultBasePackage,
        defaultJavaVersion: state.defaultJavaVersion,
        defaultSpringBootVersion: state.defaultSpringBootVersion,
        defaultBuildTool: state.defaultBuildTool,
        sidebarCollapsed: state.sidebarCollapsed,
      }),
    }
  )
);

function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") {
    const prefersDark = window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches;
    root.classList.toggle("dark", prefersDark);
  } else {
    root.classList.toggle("dark", theme === "dark");
  }
}

// Apply theme on load
const savedTheme = useSettingsStore.getState().theme;
applyTheme(savedTheme);

// Listen for system theme changes
window
  .matchMedia("(prefers-color-scheme: dark)")
  .addEventListener("change", () => {
    if (useSettingsStore.getState().theme === "system") {
      applyTheme("system");
    }
  });
