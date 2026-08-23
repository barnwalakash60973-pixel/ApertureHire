import { AxiosError } from "axios";
import { apiClient } from "./client";
import type { ApiErrorBody, ReviewResponse } from "@/types/report";

export class ReviewApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "ReviewApiError";
    this.status = status;
  }
}

/**
 * Calls POST /api/v1/review with the two required files.
 * Matches app/api/routes.py exactly: multipart fields "question_paper"
 * and "submission", both required, .docx/.pdf only.
 */
export async function submitReview(
  questionPaper: File,
  submission: File
): Promise<ReviewResponse> {
  const formData = new FormData();
  formData.append("question_paper", questionPaper);
  formData.append("submission", submission);

  try {
    const { data } = await apiClient.post<ReviewResponse>(
      "/api/v1/review",
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    );
    return data;
  } catch (err) {
    const axiosErr = err as AxiosError<ApiErrorBody>;
    const detail =
      axiosErr.response?.data?.detail ??
      axiosErr.response?.data?.error ??
      axiosErr.message ??
      "Something went wrong while reviewing the submission.";
    throw new ReviewApiError(detail, axiosErr.response?.status);
  }
}

export async function checkHealth(): Promise<boolean> {
  try {
    const { data } = await apiClient.get<{ status: string }>("/api/v1/health");
    return data.status === "ok";
  } catch {
    return false;
  }
}
