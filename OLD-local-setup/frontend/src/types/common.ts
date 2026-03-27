export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize?: number;
  size?: number;
  totalPages?: number;
  pages?: number;
}

export interface ApiError {
  status: number;
  message: string;
  detail?: string;
  errors?: Record<string, string[]>;
}

export interface HealthStatus {
  status: "healthy" | "degraded" | "unhealthy";
  version: string;
  uptime: number;
  services: {
    database: ServiceHealth;
    redis: ServiceHealth;
    rag: ServiceHealth;
    llm: ServiceHealth;
  };
}

export interface ServiceHealth {
  status: "up" | "down" | "unknown";
  latencyMs?: number;
  message?: string;
}

export type Status = "pending" | "queued" | "running" | "completed" | "failed" | "cancelled";

export interface SelectOption {
  label: string;
  value: string;
}

export interface Toast {
  id: string;
  type: "success" | "error" | "info" | "warning";
  title: string;
  message?: string;
  duration?: number;
}
