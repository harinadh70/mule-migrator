import { PublicClientApplication, LogLevel } from "@azure/msal-browser";

const clientId = import.meta.env.VITE_AZURE_AD_CLIENT_ID || "";
const tenantId = import.meta.env.VITE_AZURE_AD_TENANT_ID || "";
const redirectUri =
  import.meta.env.VITE_AZURE_AD_REDIRECT_URI || window.location.origin + "/";

export const isAzureAdEnabled = !!(clientId && tenantId);

export const msalInstance = new PublicClientApplication({
  auth: {
    clientId,
    authority: "https://login.microsoftonline.com/common",
    redirectUri,
    navigateToLoginRequestUrl: false,
  },
  cache: {
    cacheLocation: "localStorage",
    storeAuthStateInCookie: true,
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Error,
      loggerCallback: (_level, message, containsPii) => {
        if (!containsPii) console.error("[MSAL]", message);
      },
    },
    allowNativeBroker: false,
  },
});

export const loginScopes = ["openid", "profile", "email"];

/**
 * Scopes for calling the backend Function App API.
 * Uses the app registration's client ID as the API audience.
 */
const apiScope = clientId ? `api://${clientId}/.default` : "";

/**
 * Acquire an access token for the backend API (silent, then redirect fallback).
 * Returns the raw JWT access token string, or null if unavailable.
 */
export async function getApiAccessToken(): Promise<string | null> {
  if (!apiScope) return null;

  const account = msalInstance.getActiveAccount();
  if (!account) return null;

  try {
    const response = await msalInstance.acquireTokenSilent({
      scopes: [apiScope],
      account,
    });
    return response.accessToken;
  } catch {
    // Silent failed (expired, consent needed) — try interactive redirect
    try {
      await msalInstance.acquireTokenRedirect({ scopes: [apiScope] });
    } catch (err) {
      console.error("[MSAL] acquireTokenRedirect failed:", err);
    }
    return null;
  }
}

/**
 * Initialize MSAL and handle any redirect response.
 * Must be called ONCE before rendering the app.
 * Returns the authenticated user or null.
 */
export async function initAndHandleRedirect(): Promise<{
  id: string;
  email: string;
  name: string;
} | null> {
  await msalInstance.initialize();

  // This processes the auth response if we're returning from a redirect
  const response = await msalInstance.handleRedirectPromise();

  if (response?.account) {
    msalInstance.setActiveAccount(response.account);
  }

  // Check cache for existing account
  if (!msalInstance.getActiveAccount()) {
    const accounts = msalInstance.getAllAccounts();
    if (accounts.length > 0) {
      msalInstance.setActiveAccount(accounts[0]);
    }
  }

  const account = msalInstance.getActiveAccount();
  if (!account) return null;

  return {
    id: account.localAccountId,
    email: account.username,
    name: account.name || account.username,
  };
}

/**
 * Redirect to Microsoft login page (same tab, no popup).
 */
export function loginWithMicrosoft(): void {
  msalInstance.loginRedirect({
    scopes: loginScopes,
    prompt: "select_account",
  });
}

export function logout(): void {
  msalInstance.logoutRedirect({ postLogoutRedirectUri: redirectUri });
}
