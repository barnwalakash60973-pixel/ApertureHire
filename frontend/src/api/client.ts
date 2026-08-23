import axios from "axios";

/**
 * Single axios instance. Nothing outside this /api folder should import
 * axios directly — components and hooks go through api/review.ts /
 * api/campaigns.ts / api/auth.ts.
 */
export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 120_000, // LLM evaluation can legitimately take a while
});

const TOKEN_STORAGE_KEY = "ai_recruitment_access_token";

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_STORAGE_KEY);
}

export function setStoredToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
  else localStorage.removeItem(TOKEN_STORAGE_KEY);
}

// Attaches the JWT to every request automatically - callers never set
// this header manually.
apiClient.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A 401 means the token is missing/expired/invalid - clear it and let the
// app redirect to login on the next render, rather than silently
// retrying with a dead token.
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      setStoredToken(null);
    }
    return Promise.reject(error);
  }
);
