import { useState } from "react";
import {
  Save,
  RotateCcw,
  Palette,
  Wrench,
  Shield,
  Check,
  Cloud,
  Zap,
} from "lucide-react";
import { useSettingsStore, type Theme } from "@/store/settings";
import { showToast } from "@/components/layout/Layout";

export default function SettingsPage() {
  const settings = useSettingsStore();
  const [saved, setSaved] = useState(false);

  function handleSave() {
    setSaved(true);
    showToast({ type: "success", title: "Settings saved" });
    setTimeout(() => setSaved(false), 2000);
  }

  function handleReset() {
    settings.resetDefaults();
    showToast({ type: "info", title: "Settings reset to defaults" });
  }

  const themeOptions: { value: Theme; label: string; icon: string }[] = [
    { value: "light", label: "Light", icon: "☀️" },
    { value: "dark", label: "Dark", icon: "🌙" },
    { value: "system", label: "System", icon: "💻" },
  ];

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-capText dark:text-white">Settings</h1>
        <p className="text-sm text-capText-light dark:text-gray-400 mt-1">
          Configure platform preferences and defaults
        </p>
      </div>

      {/* Azure OpenAI Status */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg bg-[#0070AD]/10">
            <Cloud className="h-5 w-5 text-[#0070AD]" />
          </div>
          <div>
            <h2 className="font-semibold text-capText dark:text-white">AI Engine</h2>
            <p className="text-xs text-capText-light dark:text-gray-400">Azure OpenAI GPT-4.1</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-xs font-medium text-green-600 dark:text-green-400">Connected</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="p-3 rounded-lg bg-gray-50 dark:bg-white/[0.03]">
            <p className="text-xs text-capText-light dark:text-gray-500">Chat Model</p>
            <p className="font-medium text-capText dark:text-white mt-0.5">GPT-4.1</p>
          </div>
          <div className="p-3 rounded-lg bg-gray-50 dark:bg-white/[0.03]">
            <p className="text-xs text-capText-light dark:text-gray-500">Embeddings</p>
            <p className="font-medium text-capText dark:text-white mt-0.5">text-embedding-3-large</p>
          </div>
          <div className="p-3 rounded-lg bg-gray-50 dark:bg-white/[0.03]">
            <p className="text-xs text-capText-light dark:text-gray-500">Region</p>
            <p className="font-medium text-capText dark:text-white mt-0.5">Southeast Asia</p>
          </div>
          <div className="p-3 rounded-lg bg-gray-50 dark:bg-white/[0.03]">
            <p className="text-xs text-capText-light dark:text-gray-500">Authentication</p>
            <p className="font-medium text-capText dark:text-white mt-0.5">Managed Identity</p>
          </div>
        </div>
      </div>

      {/* Theme */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg bg-[#0070AD]/10">
            <Palette className="h-5 w-5 text-[#0070AD]" />
          </div>
          <h2 className="font-semibold text-capText dark:text-white">Appearance</h2>
        </div>
        <div className="grid grid-cols-3 gap-3">
          {themeOptions.map((opt) => (
            <button
              key={opt.value}
              onClick={() => settings.setTheme(opt.value)}
              className={`p-3 rounded-lg border text-sm font-medium transition-all ${
                settings.theme === opt.value
                  ? "border-[#0070AD] bg-[#0070AD]/5 text-[#0070AD]"
                  : "border-gray-200 dark:border-white/[0.08] text-capText-light dark:text-gray-400 hover:border-[#0070AD]/30"
              }`}
            >
              <span className="text-lg">{opt.icon}</span>
              <p className="mt-1">{opt.label}</p>
            </button>
          ))}
        </div>
      </div>

      {/* Project Defaults */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg bg-[#0070AD]/10">
            <Wrench className="h-5 w-5 text-[#0070AD]" />
          </div>
          <h2 className="font-semibold text-capText dark:text-white">Project Defaults</h2>
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-capText-light dark:text-gray-400 mb-1">Group ID</label>
            <input
              value={settings.defaultGroupId}
              onChange={(e) => settings.setDefaultGroupId(e.target.value)}
              className="input"
              placeholder="com.example"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-capText-light dark:text-gray-400 mb-1">Java Version</label>
            <select
              value={settings.defaultJavaVersion}
              onChange={(e) => settings.setDefaultJavaVersion(e.target.value)}
              className="input"
            >
              <option value="17">Java 17</option>
              <option value="21">Java 21</option>
              <option value="11">Java 11</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-capText-light dark:text-gray-400 mb-1">Spring Boot Version</label>
            <select
              value={settings.defaultSpringBootVersion}
              onChange={(e) => settings.setDefaultSpringBootVersion(e.target.value)}
              className="input"
            >
              <option value="3.2">3.2.x (Latest)</option>
              <option value="3.1">3.1.x</option>
              <option value="2.7">2.7.x (Legacy)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-capText-light dark:text-gray-400 mb-1">Base Package</label>
            <input
              value={settings.defaultBasePackage}
              onChange={(e) => settings.setDefaultBasePackage(e.target.value)}
              className="input"
              placeholder="com.example.app"
            />
          </div>
        </div>
      </div>

      {/* Security Info */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 rounded-lg bg-green-500/10">
            <Shield className="h-5 w-5 text-green-600" />
          </div>
          <h2 className="font-semibold text-capText dark:text-white">Security</h2>
        </div>
        <div className="space-y-2 text-sm">
          {[
            "Azure AD Authentication (Entra ID)",
            "Managed Identity — no API keys in code",
            "Key Vault for all secrets",
            "PostgreSQL SSL/TLS required",
            "Redis TLS 1.2 minimum",
            "Input validation with XXE prevention",
            "Rate limiting via Redis",
          ].map((item, i) => (
            <div key={i} className="flex items-center gap-2 text-capText-light dark:text-gray-400">
              <Check className="h-3.5 w-3.5 text-green-500 flex-shrink-0" />
              <span>{item}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          className="btn-primary flex items-center gap-2"
        >
          {saved ? <Check className="h-4 w-4" /> : <Save className="h-4 w-4" />}
          {saved ? "Saved!" : "Save Settings"}
        </button>
        <button
          onClick={handleReset}
          className="btn-secondary flex items-center gap-2"
        >
          <RotateCcw className="h-4 w-4" />
          Reset to Defaults
        </button>
      </div>
    </div>
  );
}
