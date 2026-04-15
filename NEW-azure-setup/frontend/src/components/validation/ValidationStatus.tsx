import { useState, useEffect } from "react";
import {
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Box,
  Rocket,
  Heart,
  ExternalLink,
  Square,
  RefreshCw,
} from "lucide-react";
import GlassCard from "@/components/common/GlassCard";
import GradientButton from "@/components/common/GradientButton";
import type { Validation, ValidationStatus as VStatus } from "@/types/validation";

interface ValidationStatusProps {
  validation: Validation;
  onTeardown: () => void;
  onRunComparison: () => void;
  isTearingDown: boolean;
  isComparing: boolean;
}

const STEPS: { key: VStatus; label: string; icon: React.ReactNode }[] = [
  { key: "pending", label: "Queued", icon: <Clock className="h-5 w-5" /> },
  { key: "building_image", label: "Building Image", icon: <Box className="h-5 w-5" /> },
  { key: "deploying", label: "Deploying", icon: <Rocket className="h-5 w-5" /> },
  { key: "running", label: "Running", icon: <Heart className="h-5 w-5" /> },
];

function getStepIndex(status: VStatus): number {
  const idx = STEPS.findIndex((s) => s.key === status);
  return idx >= 0 ? idx : STEPS.length;
}

function CountdownTimer({ expiresAt }: { expiresAt: string }) {
  const [remaining, setRemaining] = useState("");

  useEffect(() => {
    const update = () => {
      const diff = new Date(expiresAt).getTime() - Date.now();
      if (diff <= 0) {
        setRemaining("Expired");
        return;
      }
      const mins = Math.floor(diff / 60000);
      const secs = Math.floor((diff % 60000) / 1000);
      setRemaining(`${mins}m ${secs.toString().padStart(2, "0")}s`);
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, [expiresAt]);

  return (
    <span className={`font-mono text-lg ${remaining === "Expired" ? "text-red-500" : "text-emerald-500"}`}>
      {remaining}
    </span>
  );
}

export default function ValidationStatus({
  validation,
  onTeardown,
  onRunComparison,
  isTearingDown,
  isComparing,
}: ValidationStatusProps) {
  const currentStep = getStepIndex(validation.status);
  const isTerminal = ["completed", "expired", "failed"].includes(validation.status);

  return (
    <div className="space-y-6">
      {/* Progress Stepper */}
      <GlassCard accentColor="cyan">
        <h3 className="mb-4 text-lg font-semibold text-gray-900 dark:text-white">
          Deployment Progress
        </h3>

        {/* Failed/Error state */}
        {validation.status === "failed" && (
          <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800/30 dark:bg-red-900/10">
            <XCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500" />
            <div>
              <div className="font-medium text-red-700 dark:text-red-400">
                Deployment Failed
              </div>
              {validation.error && (
                <div className="mt-1 text-sm text-red-600 dark:text-red-300">
                  {validation.error}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Stepper */}
        <div className="flex items-center justify-between">
          {STEPS.map((step, i) => {
            const isActive = i === currentStep && !isTerminal;
            const isDone = i < currentStep || (isTerminal && validation.status !== "failed");
            const isFailed = validation.status === "failed" && i === currentStep;

            return (
              <div key={step.key} className="flex flex-1 items-center">
                <div className="flex flex-col items-center gap-1.5">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-full transition-all ${
                      isDone
                        ? "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400"
                        : isActive
                        ? "bg-[#0070AD]/10 text-[#0070AD] dark:bg-[#0070AD]/20"
                        : isFailed
                        ? "bg-red-100 text-red-500 dark:bg-red-900/30"
                        : "bg-gray-100 text-gray-400 dark:bg-white/[0.04]"
                    }`}
                  >
                    {isDone ? (
                      <CheckCircle2 className="h-5 w-5" />
                    ) : isActive ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : isFailed ? (
                      <XCircle className="h-5 w-5" />
                    ) : (
                      step.icon
                    )}
                  </div>
                  <span
                    className={`text-xs font-medium ${
                      isDone
                        ? "text-emerald-600 dark:text-emerald-400"
                        : isActive
                        ? "text-[#0070AD]"
                        : "text-gray-400"
                    }`}
                  >
                    {step.label}
                  </span>
                </div>
                {i < STEPS.length - 1 && (
                  <div
                    className={`mx-2 h-0.5 flex-1 ${
                      i < currentStep
                        ? "bg-emerald-400 dark:bg-emerald-500"
                        : "bg-gray-200 dark:bg-white/[0.08]"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>
      </GlassCard>

      {/* Stop button for in-progress states (building, deploying, pending) */}
      {["pending", "building_image", "deploying"].includes(validation.status) && (
        <GlassCard accentColor="amber">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin text-[#0070AD]" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {validation.status === "pending" && "Waiting in queue..."}
                {validation.status === "building_image" && "Building Docker image..."}
                {validation.status === "deploying" && "Deploying container..."}
              </span>
            </div>
            <GradientButton
              variant="danger"
              onClick={onTeardown}
              loading={isTearingDown}
              icon={<Square className="h-4 w-4" />}
              size="sm"
            >
              Stop
            </GradientButton>
          </div>
        </GlassCard>
      )}

      {/* Running State — App URL + Countdown */}
      {validation.status === "running" && validation.appUrl && (
        <GlassCard accentColor="green">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Application Running
              </h3>
              <a
                href={validation.appUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-sm text-[#0070AD] hover:underline"
              >
                {validation.appUrl}
                <ExternalLink className="h-3.5 w-3.5" />
              </a>
            </div>
            <div className="text-right">
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Time Remaining
              </div>
              {validation.expiresAt && (
                <CountdownTimer expiresAt={validation.expiresAt} />
              )}
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-3">
            {validation.mode === "auto" && (
              <GradientButton
                onClick={onRunComparison}
                loading={isComparing}
                icon={<RefreshCw className="h-4 w-4" />}
                size="sm"
              >
                Run Comparison
              </GradientButton>
            )}
            <GradientButton
              variant="danger"
              onClick={onTeardown}
              loading={isTearingDown}
              icon={<Square className="h-4 w-4" />}
              size="sm"
            >
              Tear Down
            </GradientButton>
          </div>
        </GlassCard>
      )}

      {/* Completed/Expired */}
      {(validation.status === "completed" || validation.status === "expired") && (
        <GlassCard accentColor={validation.status === "completed" ? "green" : "amber"}>
          <div className="flex items-center gap-3">
            {validation.status === "completed" ? (
              <CheckCircle2 className="h-6 w-6 text-emerald-500" />
            ) : (
              <Clock className="h-6 w-6 text-amber-500" />
            )}
            <div>
              <div className="font-semibold text-gray-900 dark:text-white">
                {validation.status === "completed" ? "Validation Complete" : "Container Expired"}
              </div>
              {validation.userVerdict && (
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  Verdict: <span className="font-medium capitalize">{validation.userVerdict}</span>
                </div>
              )}
            </div>
          </div>
        </GlassCard>
      )}
    </div>
  );
}
