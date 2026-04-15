import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ShieldCheck,
  ThumbsUp,
  ThumbsDown,
  MinusCircle,
} from "lucide-react";
import GlassCard from "@/components/common/GlassCard";
import GradientButton from "@/components/common/GradientButton";
import ValidationConfig from "./ValidationConfig";
import ValidationStatus from "./ValidationStatus";
import ComparisonResults from "./ComparisonResults";
import ContainerLogs from "./ContainerLogs";
import {
  useValidationDetail,
  useValidationsForMigration,
  useCreateValidation,
  useRunComparison,
  useSubmitVerdict,
  useTeardownValidation,
  useValidationLogs,
} from "@/hooks/useValidation";
import { useMigrationDetail, useMigrationFiles } from "@/hooks/useMigration";
import { useValidationStore } from "@/store/validation";
import type { ValidationCreate } from "@/types/validation";

export default function ValidationPage() {
  const { migrationId } = useParams<{ migrationId: string }>();
  const navigate = useNavigate();

  const { activeValidationId, setActiveValidationId } = useValidationStore();

  // Fetch migration detail and files (for endpoint extraction)
  const { data: migration } = useMigrationDetail(migrationId);
  const { data: migrationFiles } = useMigrationFiles(migrationId);

  // Fetch existing validations for this migration
  const { data: validations } = useValidationsForMigration(migrationId);

  // On mount: clear stale validation selection, then auto-select if there's an active one
  useEffect(() => {
    setActiveValidationId(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [migrationId]);

  // Auto-select latest active (non-terminal) validation
  useEffect(() => {
    if (!activeValidationId && validations && validations.length > 0) {
      const active = validations.find(
        (v) => !["completed", "expired", "failed"].includes(v.status)
      );
      if (active) {
        setActiveValidationId(active.id);
      }
    }
  }, [validations, activeValidationId, setActiveValidationId]);

  // Current validation detail
  const { data: validation } = useValidationDetail(activeValidationId || undefined);

  // Logs
  const isLogsLive =
    validation?.status === "running" ||
    validation?.status === "building_image" ||
    validation?.status === "deploying";
  const { data: logs } = useValidationLogs(
    activeValidationId || undefined,
    !!activeValidationId
  );

  // Mutations
  const createMutation = useCreateValidation();
  const compareMutation = useRunComparison();
  const verdictMutation = useSubmitVerdict();
  const teardownMutation = useTeardownValidation();

  const handleCreate = async (config: ValidationCreate) => {
    const result = await createMutation.mutateAsync(config);
    setActiveValidationId(result.id);
  };

  const handleVerdict = (verdict: "pass" | "fail" | "partial") => {
    if (activeValidationId) {
      verdictMutation.mutate({ validationId: activeValidationId, verdict });
    }
  };

  const showConfig = !activeValidationId || !validation;
  const showResults =
    validation &&
    validation.testResults &&
    validation.testResults.length > 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => navigate(`/migrate/${migrationId}`)}
          className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-white/[0.04]"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-6 w-6 text-[#0070AD]" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            Test & Validate
          </h1>
        </div>
      </div>

      {/* Previous Validations */}
      {validations && validations.length > 0 && (
        <GlassCard padding="sm">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
              Previous:
            </span>
            {validations.map((v) => (
              <button
                key={v.id}
                onClick={() => setActiveValidationId(v.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                  activeValidationId === v.id
                    ? "bg-[#0070AD] text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-white/[0.04] dark:text-gray-400"
                }`}
              >
                {v.status} - {new Date(v.createdAt).toLocaleString()}
              </button>
            ))}
            <button
              onClick={() => setActiveValidationId(null)}
              className="rounded-lg px-3 py-1.5 text-xs font-medium text-[#0070AD] hover:bg-[#0070AD]/5"
            >
              + New
            </button>
          </div>
        </GlassCard>
      )}

      {/* Config Form (when no active validation) */}
      {showConfig && migrationId && (
        <ValidationConfig
          migrationId={migrationId}
          onSubmit={handleCreate}
          isLoading={createMutation.isPending}
          detectedEndpoints={migration?.summary?.endpoints}
          migrationFiles={migrationFiles}
        />
      )}

      {/* Active Validation Status */}
      {validation && (
        <>
          <ValidationStatus
            validation={validation}
            onTeardown={() =>
              activeValidationId &&
              teardownMutation.mutate(activeValidationId)
            }
            onRunComparison={() =>
              activeValidationId &&
              compareMutation.mutate(activeValidationId)
            }
            isTearingDown={teardownMutation.isPending}
            isComparing={compareMutation.isPending}
          />

          {/* Manual Verdict Buttons (for manual mode when running) */}
          {validation.mode === "manual" &&
            validation.status === "running" &&
            !validation.userVerdict && (
              <GlassCard accentColor="purple">
                <h3 className="mb-3 text-lg font-semibold text-gray-900 dark:text-white">
                  Submit Your Verdict
                </h3>
                <p className="mb-4 text-sm text-gray-500 dark:text-gray-400">
                  After testing the deployed application, submit your assessment.
                </p>
                <div className="flex flex-wrap gap-3">
                  <GradientButton
                    onClick={() => handleVerdict("pass")}
                    loading={verdictMutation.isPending}
                    icon={<ThumbsUp className="h-4 w-4" />}
                    className="bg-emerald-600 hover:bg-emerald-700"
                  >
                    Pass
                  </GradientButton>
                  <GradientButton
                    variant="secondary"
                    onClick={() => handleVerdict("partial")}
                    loading={verdictMutation.isPending}
                    icon={<MinusCircle className="h-4 w-4" />}
                  >
                    Partial
                  </GradientButton>
                  <GradientButton
                    variant="danger"
                    onClick={() => handleVerdict("fail")}
                    loading={verdictMutation.isPending}
                    icon={<ThumbsDown className="h-4 w-4" />}
                  >
                    Fail
                  </GradientButton>
                </div>
              </GlassCard>
            )}

          {/* Comparison Results */}
          {showResults && <ComparisonResults results={validation.testResults} />}

          {/* Container Logs */}
          <ContainerLogs logs={logs || ""} isLive={isLogsLive} />
        </>
      )}
    </div>
  );
}
