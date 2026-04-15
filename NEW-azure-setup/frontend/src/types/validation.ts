export type ValidationStatus =
  | "pending"
  | "building_image"
  | "deploying"
  | "running"
  | "completed"
  | "expired"
  | "failed";

export interface TestEndpoint {
  method: string;
  path: string;
  headers?: Record<string, string>;
  body?: unknown;
}

export interface TestResult {
  method: string;
  path: string;
  mulesoft: {
    status?: number;
    body?: string;
    headers?: Record<string, string>;
    error?: string;
  };
  springboot: {
    status?: number;
    body?: string;
    headers?: Record<string, string>;
    error?: string;
  };
  match: boolean;
}

export interface Validation {
  id: string;
  migrationId: string;
  userId?: string;
  status: ValidationStatus;
  mode: "auto" | "manual";
  javaVersion: string;
  keepAliveMin: number;
  aciName?: string;
  aciFqdn?: string;
  appUrl?: string;
  acrImageTag?: string;
  mulesoftBaseUrl?: string;
  testEndpoints: TestEndpoint[];
  comparisonMode: "server" | "client";
  testResults: TestResult[];
  userVerdict?: "pass" | "fail" | "partial";
  error?: string;
  deployedAt?: string;
  expiresAt?: string;
  tornDownAt?: string;
  createdAt: string;
}

export interface ValidationCreate {
  migrationId: string;
  mode: "auto" | "manual";
  javaVersion: string;
  keepAliveMin: number;
  mulesoftBaseUrl: string;
  testEndpoints: TestEndpoint[];
  comparisonMode: "server" | "client";
}
