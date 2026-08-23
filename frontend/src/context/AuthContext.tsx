import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import * as authApi from "@/api/auth";
import { getStoredToken, setStoredToken } from "@/api/client";
import type { AuthUser } from "@/api/auth";

interface AuthContextValue {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean; // true only during the initial "do we already have a valid session" check
  login: (identifier: string, password: string) => Promise<void>;
  register: (params: { name: string; email: string; mobileNumber?: string; password: string }) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// Stored alongside the token so a page refresh doesn't lose "who is this"
// without needing a dedicated "whoami" endpoint.
const USER_STORAGE_KEY = "ai_recruitment_user";

function loadStoredUser(): AuthUser | null {
  const raw = localStorage.getItem(USER_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // No "verify token with the server" round-trip on load - the token is
    // opaque client-side, so we trust localStorage until an actual API
    // call gets a 401 (handled by the response interceptor, which clears
    // the token - see api/client.ts). This keeps app load instant.
    const token = getStoredToken();
    setUser(token ? loadStoredUser() : null);
    setIsLoading(false);
  }, []);

  const login = async (identifier: string, password: string) => {
    const result = await authApi.login(identifier, password);
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(result.user));
    setUser(result.user);
  };

  const register = async (params: { name: string; email: string; mobileNumber?: string; password: string }) => {
    const result = await authApi.register(params);
    localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(result.user));
    setUser(result.user);
  };

  const logout = () => {
    setStoredToken(null);
    localStorage.removeItem(USER_STORAGE_KEY);
    setUser(null);
  };

  const value = useMemo(
    () => ({ user, isAuthenticated: user !== null, isLoading, login, register, logout }),
    [user, isLoading]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
