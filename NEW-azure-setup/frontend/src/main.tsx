import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  isAzureAdEnabled,
  initAndHandleRedirect,
} from "@/auth/msalConfig";
import { useAuthStore } from "@/store/auth";
import App from "./App";
import "./index.css";

document.documentElement.classList.add("dark");

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 2, staleTime: 30_000, refetchOnWindowFocus: false },
    mutations: { retry: 0 },
  },
});

async function bootstrap() {
  // ── Handle MSAL redirect BEFORE rendering ──────────────────────────
  // If we're returning from Microsoft login, this processes the response
  // and sets the active account BEFORE React mounts.
  if (isAzureAdEnabled) {
    try {
      const msalUser = await initAndHandleRedirect();
      if (msalUser) {
        // User just returned from Microsoft login — set auth state
        localStorage.setItem("auth-token", "msal");
        useAuthStore.setState({
          isAuthenticated: true,
          token: "msal",
          user: {
            id: msalUser.id,
            email: msalUser.email,
            name: msalUser.name,
          },
        });
      }
    } catch (err) {
      console.warn("[MSAL] init error:", err);
    }
  }

  ReactDOM.createRoot(document.getElementById("root")!).render(
    <React.StrictMode>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </React.StrictMode>
  );
}

bootstrap();
