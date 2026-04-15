import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/layout/Layout";
import AuthGuard from "./components/auth/AuthGuard";

const LoginPage = lazy(() => import("./components/auth/LoginPage"));
const DashboardPage = lazy(() => import("./components/dashboard/DashboardPage"));
const MigrationPage = lazy(() => import("./components/migration/MigrationPage"));
const MigrationHistory = lazy(() => import("./components/migration/MigrationHistory"));
const SwaggerPage = lazy(() => import("./components/swagger/SwaggerPage"));
const GitHubPage = lazy(() => import("./components/github/GitHubPage"));
const SettingsPage = lazy(() => import("./components/settings/SettingsPage"));
const KnowledgeBasePage = lazy(() => import("./components/rag/KnowledgeBasePage"));
const ValidationPage = lazy(() => import("./components/validation/ValidationPage"));

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

function ProtectedPage({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <Layout>
        <Suspense fallback={<PageLoader />}>{children}</Suspense>
      </Layout>
    </AuthGuard>
  );
}

export default function App() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected routes */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<ProtectedPage><DashboardPage /></ProtectedPage>} />
        <Route path="/migrate" element={<ProtectedPage><MigrationPage /></ProtectedPage>} />
        <Route path="/migrate/:id" element={<ProtectedPage><MigrationPage /></ProtectedPage>} />
        <Route path="/history" element={<ProtectedPage><MigrationHistory /></ProtectedPage>} />
        <Route path="/swagger" element={<ProtectedPage><SwaggerPage /></ProtectedPage>} />
        <Route path="/swagger/:migrationId" element={<ProtectedPage><SwaggerPage /></ProtectedPage>} />
        <Route path="/github" element={<ProtectedPage><GitHubPage /></ProtectedPage>} />
        <Route path="/github/:migrationId" element={<ProtectedPage><GitHubPage /></ProtectedPage>} />
        <Route path="/validate/:migrationId" element={<ProtectedPage><ValidationPage /></ProtectedPage>} />
        <Route path="/knowledge" element={<ProtectedPage><KnowledgeBasePage /></ProtectedPage>} />
        <Route path="/settings" element={<ProtectedPage><SettingsPage /></ProtectedPage>} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Suspense>
  );
}
