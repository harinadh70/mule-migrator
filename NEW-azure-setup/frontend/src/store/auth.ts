import { create } from "zustand";
import { persist } from "zustand/middleware";
import apiClient from "@/api/client";

interface User {
  id: string;
  email: string;
  name: string;
  avatarUrl?: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;

  login: (email: string, password: string) => Promise<void>;
  loginWithToken: (token: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User) => void;
  checkAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email: string, password: string) => {
        set({ isLoading: true });
        try {
          const response = await apiClient.post("/auth/login", {
            email,
            password,
          });
          const { user, token } = response.data;
          localStorage.setItem("auth-token", token);
          set({ user, token, isAuthenticated: true, isLoading: false });
        } catch {
          set({ isLoading: false });
          throw new Error("Login failed");
        }
      },

      loginWithToken: async (token: string) => {
        localStorage.setItem("auth-token", token);
        set({ token, isLoading: true });
        try {
          const response = await apiClient.get("/auth/me");
          set({
            user: response.data,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch {
          localStorage.removeItem("auth-token");
          set({
            token: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      },

      logout: () => {
        localStorage.removeItem("auth-token");
        set({ user: null, token: null, isAuthenticated: false });
      },

      setUser: (user) => set({ user }),

      checkAuth: async () => {
        const { token } = get();
        if (!token) return;

        set({ isLoading: true });
        try {
          const response = await apiClient.get("/auth/me");
          set({
            user: response.data,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch {
          localStorage.removeItem("auth-token");
          set({
            user: null,
            token: null,
            isAuthenticated: false,
            isLoading: false,
          });
        }
      },
    }),
    {
      name: "migrator-auth",
      partialize: (state) => ({
        token: state.token,
        user: state.user,
      }),
    }
  )
);
