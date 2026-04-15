import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createValidation,
  getValidation,
  listValidationsForMigration,
  runComparison,
  submitVerdict,
  teardownValidation,
  getValidationLogs,
} from "@/api/validations";
import type { ValidationCreate } from "@/types/validation";

export function useValidationDetail(id: string | undefined) {
  return useQuery({
    queryKey: ["validation", id],
    queryFn: () => getValidation(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      // Poll while deploying/running, stop on terminal states
      if (
        status === "pending" ||
        status === "building_image" ||
        status === "deploying"
      ) {
        return 3000;
      }
      if (status === "running") {
        return 5000;
      }
      return false;
    },
  });
}

export function useValidationsForMigration(migrationId: string | undefined) {
  return useQuery({
    queryKey: ["validations", migrationId],
    queryFn: () => listValidationsForMigration(migrationId!),
    enabled: !!migrationId,
  });
}

export function useCreateValidation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ValidationCreate) => createValidation(data),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ["validations", variables.migrationId],
      });
    },
  });
}

export function useRunComparison() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (validationId: string) => runComparison(validationId),
    onSuccess: (_data, validationId) => {
      queryClient.invalidateQueries({
        queryKey: ["validation", validationId],
      });
    },
  });
}

export function useSubmitVerdict() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      validationId,
      verdict,
    }: {
      validationId: string;
      verdict: "pass" | "fail" | "partial";
    }) => submitVerdict(validationId, verdict),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: ["validation", data.id],
      });
    },
  });
}

export function useTeardownValidation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (validationId: string) => teardownValidation(validationId),
    onSuccess: (_data, validationId) => {
      queryClient.invalidateQueries({
        queryKey: ["validation", validationId],
      });
    },
  });
}

export function useValidationLogs(validationId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["validationLogs", validationId],
    queryFn: () => getValidationLogs(validationId!),
    enabled: !!validationId && enabled,
    refetchInterval: 5000,
  });
}
