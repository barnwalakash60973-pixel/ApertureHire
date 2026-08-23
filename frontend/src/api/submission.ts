import { apiClient } from "./client";
import { CampaignApiError } from "./campaigns";
import type { SubmissionSubmitResult, SubmissionView } from "@/types/campaign";

/**
 * Public, token-gated candidate portal - no auth. Mirrors
 * routes_submissions.py. Kept separate from api/campaigns.ts since that
 * module is HR-only (JWT-backed) territory.
 */

async function unwrap<T>(promise: Promise<{ data: T }>): Promise<T> {
  try {
    const res = await promise;
    return res.data;
  } catch (err) {
    const axiosErr = err as { response?: { status?: number; data?: { detail?: string; error?: string } }; message?: string };
    const detail = axiosErr.response?.data?.detail ?? axiosErr.response?.data?.error ?? axiosErr.message ?? "Something went wrong.";
    throw new CampaignApiError(detail, axiosErr.response?.status);
  }
}

export async function getSubmissionView(token: string): Promise<SubmissionView> {
  return unwrap(apiClient.get<SubmissionView>(`/api/v1/submissions/${token}`));
}

export async function submitSolution(token: string, file: File): Promise<SubmissionSubmitResult> {
  const formData = new FormData();
  formData.append("solution", file);
  return unwrap(
    apiClient.post<SubmissionSubmitResult>(`/api/v1/submissions/${token}`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  );
}
