import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Github,
  Lock,
  Unlock,
  Loader2,
  CheckCircle,
  ExternalLink,
  GitBranch,
  FileCode,
} from "lucide-react";
import {
  pushToGithub,
  listRepos,
  getGitHubStatus,
  type PushResponse,
} from "@/api/github";
import { useMigrationDetail, useMigrationFiles } from "@/hooks/useMigration";
import { showToast } from "@/components/layout/Layout";

export default function GitHubPage() {
  const { migrationId } = useParams<{ migrationId: string }>();
  const [searchParams] = useSearchParams();
  const queryMigrationId = searchParams.get("migrationId");

  // Use URL param first, then query param
  const initialMigrationId = migrationId || queryMigrationId || "";

  const [inputMigrationId, setInputMigrationId] = useState(initialMigrationId);
  const [repoName, setRepoName] = useState("");
  const [commitMessage, setCommitMessage] = useState("");
  const [isPrivate, setIsPrivate] = useState(true);
  const [branch, setBranch] = useState("main");
  const [createNewRepo, setCreateNewRepo] = useState(true);
  const [pushResult, setPushResult] = useState<PushResponse | null>(null);
  const [githubToken, setGithubToken] = useState("");
  const [showToken, setShowToken] = useState(false);
  const [tokenConnected, setTokenConnected] = useState(false);
  const [githubUsername, setGithubUsername] = useState("");

  const { data: migration } = useMigrationDetail(inputMigrationId || undefined);
  const { data: migrationFiles } = useMigrationFiles(inputMigrationId || undefined);

  const fileCount = migrationFiles?.length ?? 0;

  const { data: ghStatus } = useQuery({
    queryKey: ["githubStatus"],
    queryFn: getGitHubStatus,
  });

  const { data: repos, isLoading: reposLoading } = useQuery({
    queryKey: ["githubRepos"],
    queryFn: listRepos,
    enabled: ghStatus?.connected === true && !createNewRepo,
  });

  useEffect(() => {
    if (migrationId) setInputMigrationId(migrationId);
    else if (queryMigrationId) setInputMigrationId(queryMigrationId);
  }, [migrationId, queryMigrationId]);

  useEffect(() => {
    if (migration) {
      setRepoName(
        migration.config.artifactId ||
          migration.name.toLowerCase().replace(/\s+/g, "-")
      );
      setCommitMessage(
        `feat: migrate ${migration.name} from MuleSoft to Spring Boot`
      );
    }
  }, [migration]);

  const pushMutation = useMutation({
    mutationFn: () =>
      pushToGithub({
        migrationId: inputMigrationId,
        repoName: repoName.includes("/") ? repoName : `${githubUsername}/${repoName}`,
        commitMessage,
        isPrivate,
        branch,
        createRepo: createNewRepo,
        token: githubToken,
      }),
    onSuccess: (result) => {
      setPushResult(result);
      showToast({
        type: "success",
        title: "Pushed to GitHub",
        message: `${result.filesPushed} files pushed to ${result.repoUrl}`,
      });
    },
    onError: () => {
      showToast({ type: "error", title: "Failed to push to GitHub" });
    },
  });

  function handlePush() {
    if (!githubToken || !tokenConnected) {
      showToast({ type: "error", title: "Please connect your GitHub token first" });
      return;
    }
    if (!inputMigrationId || !repoName || !commitMessage) {
      showToast({ type: "error", title: "Please fill in all required fields" });
      return;
    }
    pushMutation.mutate();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
          GitHub Integration
        </h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Push your generated Spring Boot project to a GitHub repository
        </p>
      </div>

      {/* File count banner when navigated from migration */}
      {inputMigrationId && migration && fileCount > 0 && (
        <div className="flex items-center gap-3 rounded-lg border border-[#0070AD]/20 bg-[#0070AD]/5 dark:bg-[#0070AD]/10 px-4 py-3">
          <FileCode className="h-5 w-5 text-[#0070AD]" />
          <div>
            <p className="text-sm font-medium text-[#1B365D] dark:text-white">
              {migration.name}
            </p>
            <p className="text-xs text-[#0070AD] dark:text-[#12ABDB]">
              {fileCount} file{fileCount !== 1 ? "s" : ""} ready to push
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Configuration */}
        <div className="space-y-4 xl:col-span-2">
          {/* GitHub Token */}
          <div className="card">
            <div className="flex items-center gap-3 mb-3">
              <Github className="h-6 w-6 text-gray-900 dark:text-white" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">
                  GitHub Connection
                </p>
                {tokenConnected ? (
                  <p className="text-sm text-green-600 dark:text-green-400">
                    Connected as @{githubUsername}
                  </p>
                ) : (
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    Enter a GitHub Personal Access Token to connect
                  </p>
                )}
              </div>
            </div>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type={showToken ? "text" : "password"}
                  value={githubToken}
                  onChange={(e) => { setGithubToken(e.target.value); setTokenConnected(false); }}
                  placeholder="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                  className="input w-full pr-10"
                />
                <button
                  onClick={() => setShowToken(!showToken)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                >
                  {showToken ? <Unlock className="h-4 w-4" /> : <Lock className="h-4 w-4" />}
                </button>
              </div>
              <button
                onClick={async () => {
                  if (githubToken.length < 10) {
                    showToast({ type: "error", title: "Enter a valid GitHub token" });
                    return;
                  }
                  try {
                    const res = await fetch("https://api.github.com/user", {
                      headers: { Authorization: `Bearer ${githubToken}` },
                    });
                    if (res.ok) {
                      const user = await res.json();
                      setGithubUsername(user.login);
                      setTokenConnected(true);
                      showToast({ type: "success", title: `Connected as @${user.login}` });
                    } else {
                      showToast({ type: "error", title: "Invalid token -- check permissions" });
                    }
                  } catch {
                    showToast({ type: "error", title: "Failed to verify token" });
                  }
                }}
                className="btn-primary whitespace-nowrap"
              >
                Connect
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-400">
              Create a token at{" "}
              <a href="https://github.com/settings/tokens" target="_blank" className="text-brand-500 hover:underline">
                github.com/settings/tokens
              </a>
              {" "}with <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">repo</code> scope
            </p>
          </div>

          {/* Push form */}
          <div className="card space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Push Configuration
            </h3>

            {!migrationId && !queryMigrationId && (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Migration ID *
                </label>
                <input
                  type="text"
                  value={inputMigrationId}
                  onChange={(e) => setInputMigrationId(e.target.value)}
                  placeholder="Enter completed migration ID"
                  className="input"
                />
                {migration && (
                  <p className="mt-1 text-xs text-gray-500">
                    {migration.name} - {migration.status}
                    {fileCount > 0 && ` (${fileCount} files)`}
                  </p>
                )}
              </div>
            )}

            <div className="flex items-center gap-4">
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={createNewRepo}
                  onChange={() => setCreateNewRepo(true)}
                  className="h-4 w-4 text-brand-600"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Create new repo
                </span>
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="radio"
                  checked={!createNewRepo}
                  onChange={() => setCreateNewRepo(false)}
                  className="h-4 w-4 text-brand-600"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  Use existing repo
                </span>
              </label>
            </div>

            {createNewRepo ? (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Repository Name *
                </label>
                <input
                  type="text"
                  value={repoName}
                  onChange={(e) => setRepoName(e.target.value)}
                  placeholder="my-spring-boot-service"
                  className="input"
                />
              </div>
            ) : (
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Select Repository *
                </label>
                {reposLoading ? (
                  <div className="skeleton h-10 w-full" />
                ) : (
                  <select
                    value={repoName}
                    onChange={(e) => setRepoName(e.target.value)}
                    className="select"
                  >
                    <option value="">Select a repository...</option>
                    {repos?.map((repo) => (
                      <option key={repo.id} value={repo.name}>
                        {repo.fullName}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Branch
              </label>
              <div className="flex items-center gap-2">
                <GitBranch className="h-4 w-4 text-gray-400" />
                <input
                  type="text"
                  value={branch}
                  onChange={(e) => setBranch(e.target.value)}
                  placeholder="main"
                  className="input"
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">
                Commit Message *
              </label>
              <textarea
                value={commitMessage}
                onChange={(e) => setCommitMessage(e.target.value)}
                placeholder="Initial commit: Migrated from MuleSoft"
                rows={3}
                className="input resize-none"
              />
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setIsPrivate(!isPrivate)}
                className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors ${
                  isPrivate
                    ? "border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-700 dark:bg-amber-900/20 dark:text-amber-400"
                    : "border-green-300 bg-green-50 text-green-700 dark:border-green-700 dark:bg-green-900/20 dark:text-green-400"
                }`}
              >
                {isPrivate ? (
                  <>
                    <Lock className="h-4 w-4" /> Private
                  </>
                ) : (
                  <>
                    <Unlock className="h-4 w-4" /> Public
                  </>
                )}
              </button>
            </div>

            <button
              onClick={handlePush}
              disabled={
                pushMutation.isPending ||
                !inputMigrationId ||
                !repoName ||
                !commitMessage ||
                !tokenConnected ||
                migration?.status !== "completed"
              }
              className="btn-primary w-full"
            >
              {pushMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Pushing {fileCount > 0 ? `${fileCount} files` : ""}...
                </>
              ) : (
                <>
                  <Github className="h-4 w-4" />
                  Push to GitHub{fileCount > 0 ? ` (${fileCount} files)` : ""}
                </>
              )}
            </button>
          </div>
        </div>

        {/* Result / Info panel */}
        <div className="space-y-4">
          {pushResult && (
            <div className="card border-green-200 bg-green-50 dark:border-green-800 dark:bg-green-900/20">
              <div className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-green-500" />
                <h4 className="font-semibold text-green-800 dark:text-green-300">
                  Push Successful
                </h4>
              </div>
              <div className="mt-3 space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-green-600 dark:text-green-400">
                    Files pushed
                  </span>
                  <span className="font-medium text-green-800 dark:text-green-200">
                    {pushResult.filesPushed}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-green-600 dark:text-green-400">
                    Branch
                  </span>
                  <span className="font-medium text-green-800 dark:text-green-200">
                    {pushResult.branch}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-green-600 dark:text-green-400">
                    Commit
                  </span>
                  <span className="font-mono text-xs text-green-800 dark:text-green-200">
                    {pushResult.commitSha.substring(0, 8)}
                  </span>
                </div>
                <a
                  href={pushResult.repoUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-primary mt-3 w-full text-sm"
                >
                  <ExternalLink className="h-4 w-4" />
                  Open Repository
                </a>
              </div>
            </div>
          )}

          <div className="card">
            <h4 className="mb-3 font-semibold text-gray-900 dark:text-white">
              What Gets Pushed
            </h4>
            <ul className="space-y-2 text-sm text-gray-600 dark:text-gray-300">
              <li className="flex items-center gap-2">
                <FileCode className="h-4 w-4 text-brand-500" />
                All generated Java source files
              </li>
              <li className="flex items-center gap-2">
                <FileCode className="h-4 w-4 text-brand-500" />
                Maven/Gradle build configuration
              </li>
              <li className="flex items-center gap-2">
                <FileCode className="h-4 w-4 text-brand-500" />
                Application properties/YAML
              </li>
              <li className="flex items-center gap-2">
                <FileCode className="h-4 w-4 text-brand-500" />
                Test files (if generated)
              </li>
              <li className="flex items-center gap-2">
                <FileCode className="h-4 w-4 text-brand-500" />
                OpenAPI/Swagger spec (if generated)
              </li>
              <li className="flex items-center gap-2">
                <FileCode className="h-4 w-4 text-brand-500" />
                Dockerfile and documentation
              </li>
            </ul>
            {fileCount > 0 && (
              <div className="mt-4 rounded-md bg-[#0070AD]/5 dark:bg-[#0070AD]/10 px-3 py-2">
                <p className="text-xs font-medium text-[#0070AD] dark:text-[#12ABDB]">
                  {fileCount} file{fileCount !== 1 ? "s" : ""} from this migration
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
