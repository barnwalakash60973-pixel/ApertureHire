import { AxiosError } from "axios";
import { apiClient, setStoredToken } from "./client";
import type { ApiErrorBody } from "@/types/report";

export class AuthApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "AuthApiError";
    this.status = status;
  }
}

function unwrap<T>(promise: Promise<{ data: T }>): Promise<T> {
  return promise.then((res) => res.data).catch((err: unknown) => {
    const axiosErr = err as AxiosError<ApiErrorBody>;
    const detail = axiosErr.response?.data?.detail ?? axiosErr.message ?? "Something went wrong.";
    throw new AuthApiError(String(detail), axiosErr.response?.status);
  });
}

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  mobile_number: string | null;
  role: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export async function register(params: {
  name: string;
  email: string;
  mobileNumber?: string;
  password: string;
}): Promise<TokenResponse> {
  const result = await unwrap(
    apiClient.post<TokenResponse>("/api/v1/auth/register", {
      name: params.name,
      email: params.email,
      mobile_number: params.mobileNumber || undefined,
      password: params.password,
    })
  );
  setStoredToken(result.access_token);
  return result;
}

export async function login(identifier: string, password: string): Promise<TokenResponse> {
  const result = await unwrap(apiClient.post<TokenResponse>("/api/v1/auth/login", { identifier, password }));
  setStoredToken(result.access_token);
  return result;
}

export function logout(): void {
  setStoredToken(null);
}

export async function forgotPassword(identifier: string): Promise<{ message: string }> {
  return unwrap(apiClient.post("/api/v1/auth/forgot-password", { identifier }));
}

export async function resetPassword(identifier: string, otp: string, newPassword: string): Promise<{ message: string }> {
  return unwrap(apiClient.post("/api/v1/auth/reset-password", { identifier, otp, new_password: newPassword }));
}
