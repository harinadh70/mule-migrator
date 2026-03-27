import { PublicClientApplication, Configuration, LogLevel } from "@azure/msal-browser";

const clientId = import.meta.env.VITE_AZURE_AD_CLIENT_ID || "";
const tenantId = import.meta.env.VITE_AZURE_AD_TENANT_ID || "";
const redirectUri = import.meta.env.VITE_AZURE_AD_REDIRECT_URI || window.location.origin + "/";

export const isAzureAdEnabled = !!(clientId && tenantId);

const msalConfig: Configuration = {
  auth: {
    clientId,
    authority: `https://login.microsoftonline.com/${tenantId}`,
    redirectUri,
    postLogoutRedirectUri: redirectUri,
  },
  cache: {
    cacheLocation: "localStorage",
    storeAuthStateInCookie: false,
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Warning,
    },
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);

export const loginRequest = {
  scopes: [`api://${clientId}/api.access`],
};

export async function initializeMsal() {
  await msalInstance.initialize();
  const response = await msalInstance.handleRedirectPromise();
  if (response) {
    msalInstance.setActiveAccount(response.account);
  }
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length > 0) {
    msalInstance.setActiveAccount(accounts[0]);
  }
}

export async function getApiToken(): Promise<string | null> {
  if (!isAzureAdEnabled) return null;
  const account = msalInstance.getActiveAccount();
  if (!account) return null;
  try {
    const result = await msalInstance.acquireTokenSilent({
      ...loginRequest,
      account,
    });
    return result.accessToken;
  } catch {
    try {
      const result = await msalInstance.acquireTokenPopup(loginRequest);
      return result.accessToken;
    } catch {
      return null;
    }
  }
}

export function getActiveUser() {
  const account = msalInstance.getActiveAccount();
  if (!account) return null;
  return {
    name: account.name || account.username,
    email: account.username,
    id: account.localAccountId,
  };
}

export async function login() {
  try {
    const result = await msalInstance.loginPopup(loginRequest);
    if (result.account) {
      msalInstance.setActiveAccount(result.account);
    }
    return result;
  } catch (err) {
    console.error("Login failed:", err);
    // Fallback to redirect
    await msalInstance.loginRedirect(loginRequest);
  }
}

export async function logout() {
  try {
    await msalInstance.logoutPopup();
  } catch {
    await msalInstance.logoutRedirect();
  }
}
