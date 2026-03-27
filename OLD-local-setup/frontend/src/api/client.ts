import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type { ApiError } from "@/types/common";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v2";
const IS_DEV = import.meta.env.DEV;

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    // Auth token from localStorage or SWA built-in auth cookie
    const token = localStorage.getItem("auth-token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    if (IS_DEV) {
      console.log(
        `[API] ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`,
        config.params || ""
      );
    }

    return config;
  },
  (error) => Promise.reject(error)
);

apiClient.interceptors.response.use(
  (response) => {
    if (IS_DEV) {
      console.log(
        `[API] Response ${response.status}`,
        response.config.url
      );
    }
    return response;
  },
  (error: AxiosError<ApiError>) => {
    if (IS_DEV) {
      console.error(
        `[API] Error ${error.response?.status}`,
        error.config?.url,
        error.response?.data
      );
    }

    if (error.response?.status === 401) {
      localStorage.removeItem("auth-token");
      const currentPath = window.location.pathname;
      if (currentPath !== "/login") {
        window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`;
      }
    }

    const apiError: ApiError = {
      status: error.response?.status || 0,
      message:
        error.response?.data?.message ||
        error.message ||
        "An unexpected error occurred",
      detail: error.response?.data?.detail,
      errors: error.response?.data?.errors,
    };

    return Promise.reject(apiError);
  }
);

export default apiClient;
