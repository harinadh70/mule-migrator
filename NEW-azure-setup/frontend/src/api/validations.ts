import apiClient from "./client";
import type { Validation, ValidationCreate, TestResult } from "@/types/validation";

// Backend uses snake_case, frontend uses camelCase — transform here.
function mapValidation(raw: Record<string, unknown>): Validation {
  return {
    id: raw.id as string,
    migrationId: raw.migration_id as string,
    userId: raw.user_id as string | undefined,
    status: raw.status as Validation["status"],
    mode: raw.mode as Validation["mode"],
    javaVersion: raw.java_version as string,
    keepAliveMin: raw.keep_alive_min as number,
    aciName: raw.aci_name as string | undefined,
    aciFqdn: raw.aci_fqdn as string | undefined,
    appUrl: raw.app_url as string | undefined,
    acrImageTag: raw.acr_image_tag as string | undefined,
    mulesoftBaseUrl: raw.mulesoft_base_url as string | undefined,
    testEndpoints: (raw.test_endpoints as Validation["testEndpoints"]) || [],
    comparisonMode: (raw.comparison_mode as Validation["comparisonMode"]) || "server",
    testResults: (raw.test_results as Validation["testResults"]) || [],
    userVerdict: raw.user_verdict as Validation["userVerdict"],
    error: raw.error as string | undefined,
    deployedAt: raw.deployed_at as string | undefined,
    expiresAt: raw.expires_at as string | undefined,
    tornDownAt: raw.torn_down_at as string | undefined,
    createdAt: raw.created_at as string,
  };
}

export async function createValidation(data: ValidationCreate): Promise<Validation> {
  const response = await apiClient.post("/validations", {
    migration_id: data.migrationId,
    mode: data.mode,
    java_version: data.javaVersion,
    keep_alive_min: data.keepAliveMin,
    mulesoft_base_url: data.mulesoftBaseUrl,
    test_endpoints: data.testEndpoints,
    comparison_mode: data.comparisonMode,
  });
  return mapValidation(response.data);
}

export async function getValidation(id: string): Promise<Validation> {
  const response = await apiClient.get(`/validations/${id}`);
  return mapValidation(response.data);
}

export async function listValidationsForMigration(migrationId: string): Promise<Validation[]> {
  const response = await apiClient.get(`/migrations/${migrationId}/validations`);
  return (response.data.items || []).map(mapValidation);
}

export async function runComparison(validationId: string): Promise<TestResult[]> {
  const response = await apiClient.post(`/validations/${validationId}/compare`);
  return response.data.results || [];
}

export async function submitVerdict(
  validationId: string,
  verdict: "pass" | "fail" | "partial"
): Promise<Validation> {
  const response = await apiClient.post(`/validations/${validationId}/verdict`, { verdict });
  return mapValidation(response.data);
}

export async function teardownValidation(validationId: string): Promise<void> {
  await apiClient.post(`/validations/${validationId}/teardown`);
}

export async function getValidationLogs(validationId: string): Promise<string> {
  const response = await apiClient.get(`/validations/${validationId}/logs`);
  return response.data.logs || "";
}
