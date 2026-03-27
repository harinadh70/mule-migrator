import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/layout/Layout";

const DashboardPage = lazy(() => import("./components/dashboard/DashboardPage"));
const MigrationPage = lazy(() => import("./components/migration/MigrationPage"));
const MigrationHistory = lazy(() => import("./components/migration/MigrationHistory"));
const SwaggerPage = lazy(() => import("./components/swagger/SwaggerPage"));
const GitHubPage = lazy(() => import("./components/github/GitHubPage"));
const SettingsPage = lazy(() => import("./components/settings/SettingsPage"));
const KnowledgeBasePage = lazy(() => import("./components/rag/KnowledgeBasePage"));

function PageLoader() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="relative h-10 w-10">
          <div className="absolute inset-0 rounded-full border-2 border-white/[0.06]" />
          <div className="absolute inset-0 animate-spin rounded-full border-2 border-transparent border-t-[#0070AD] border-r-[#12ABDB]" />
        </div>
        <p className="text-sm font-medium text-gray-500">Loading...</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Layout>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/migrate" element={<MigrationPage />} />
          <Route path="/migrate/:id" element={<MigrationPage />} />
          <Route path="/history" element={<MigrationHistory />} />
          <Route path="/swagger" element={<SwaggerPage />} />
          <Route path="/swagger/:migrationId" element={<SwaggerPage />} />
          <Route path="/github" element={<GitHubPage />} />
          <Route path="/github/:migrationId" element={<GitHubPage />} />
          <Route path="/knowledge" element={<KnowledgeBasePage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}
