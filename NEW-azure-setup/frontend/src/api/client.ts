import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";
import type { ApiError } from "@/types/common";
import { isAzureAdEnabled, getApiAccessToken } from "@/auth/msalConfig";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api/v2";
const IS_DEV = import.meta.env.DEV;

let isRedirecting = false;

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 60_000,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use(
  async (config: InternalAxiosRequestConfig) => {
    const storedToken = localStorage.getItem("auth-token");

    if (storedToken === "msal" && isAzureAdEnabled) {
      // MSAL user — acquire a real Azure AD access token for the API
      const accessToken = await getApiAccessToken();
      if (accessToken && config.headers) {
        config.headers.Authorization = `Bearer ${accessToken}`;
      }
    } else if (storedToken && config.headers) {
      // Custom email/password token — use as-is
      config.headers.Authorization = `Bearer ${storedToken}`;
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
  (response) => response,
  (error: AxiosError<ApiError>) => {
    // On 401, clear auth and redirect to login
    if (
      error.response?.status === 401 &&
      !isRedirecting
    ) {
      const currentPath = window.location.pathname;
      if (currentPath !== "/login") {
        isRedirecting = true;
        localStorage.removeItem("auth-token");
        localStorage.removeItem("migrator-auth");
        window.location.href = `/login?redirect=${encodeURIComponent(currentPath)}`;
        setTimeout(() => { isRedirecting = false; }, 5000);
      }
    }

    const apiError: ApiError = {
      status: error.response?.status || 0,
      message:
        error.response?.data?.message ||
        error.response?.data?.error ||
        error.message ||
        "An unexpected error occurred",
      detail: error.response?.data?.detail,
      errors: error.response?.data?.errors,
    };

    return Promise.reject(apiError);
  }
);

export default apiClient;
