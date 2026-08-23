import { AxiosError } from "axios";
import { apiClient } from "./client";
import type { ApiErrorBody } from "@/types/report";
import type {
  ApproveEvaluationResponse,
  Assignment,
  AssignmentSendResult,
  AssignmentVersion,
  BulkResumeImportResponse,
  Campaign,
  CampaignDashboard,
  CampaignEvent,
  Candidate,
  CandidateDecisionResponse,
  ConfirmImportResponse,
  EvaluateCampaignResponse,
  SelectedCandidate,
} from "@/types/campaign";

export class CampaignApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.name = "CampaignApiError";
    this.status = status;
  }
}

function unwrap<T>(promise: Promise<{ data: T }>): Promise<T> {
  return promise
    .then((res) => res.data)
    .catch((err) => {
      const axiosErr = err as AxiosError<ApiErrorBody>;
      const detail =
        axiosErr.response?.data?.detail ??
        axiosErr.response?.data?.error ??
        axiosErr.message ??
        "Something went wrong.";
      throw new CampaignApiError(detail, axiosErr.response?.status);
    });
}

/** POST /api/v1/campaigns - JD is a file upload (.docx/.pdf), not typed text. */
export async function createCampaign(params: {
  name: string;
  jobTitle?: string;
  jobDescriptionFile: File;
}): Promise<Campaign> {
  const formData = new FormData();
  formData.append("name", params.name);
  if (params.jobTitle) formData.append("job_title", params.jobTitle);
  formData.append("job_description_file", params.jobDescriptionFile);

  return unwrap(
    apiClient.post<Campaign>("/api/v1/campaigns", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  );
}

export async function listCampaigns(): Promise<Campaign[]> {
  return unwrap(apiClient.get<Campaign[]>("/api/v1/campaigns"));
}

export async function getCampaign(campaignId: string): Promise<Campaign> {
  return unwrap(apiClient.get<Campaign>(`/api/v1/campaigns/${campaignId}`));
}

/** Step 1 of 2: preview import - no email sent yet. */
export async function importResumes(campaignId: string, resumes: File[]): Promise<BulkResumeImportResponse> {
  const formData = new FormData();
  resumes.forEach((f) => formData.append("resumes", f));
  return unwrap(
    apiClient.post<BulkResumeImportResponse>(`/api/v1/campaigns/${campaignId}/resumes/import`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  );
}

export async function editCandidate(
  campaignId: string,
  candidateId: string,
  patch: { name?: string; email?: string }
): Promise<Candidate> {
  return unwrap(apiClient.patch<Candidate>(`/api/v1/campaigns/${campaignId}/candidates/${candidateId}`, patch));
}

/** Step 2 of 2: finalizes shortlisted/not_shortlisted, sends shortlist emails. */
export async function confirmImport(campaignId: string): Promise<ConfirmImportResponse> {
  return unwrap(apiClient.post<ConfirmImportResponse>(`/api/v1/campaigns/${campaignId}/resumes/confirm`));
}

export async function listCandidates(campaignId: string, status?: string): Promise<Candidate[]> {
  return unwrap(
    apiClient.get<Candidate[]>(`/api/v1/campaigns/${campaignId}/candidates`, { params: status ? { status } : {} })
  );
}

// Ranked final_selected candidates, high score to low, with strengths/
// weaknesses so HR can see WHY - not just the score.
export async function listSelectedCandidates(campaignId: string): Promise<SelectedCandidate[]> {
  return unwrap(apiClient.get<SelectedCandidate[]>(`/api/v1/campaigns/${campaignId}/candidates/selected`));
}

// The auto-computed threshold/top_n outcome, ranked the same way, but not
// yet released - what HR reviews before calling approveEvaluation.
export async function listPendingApprovalCandidates(campaignId: string): Promise<SelectedCandidate[]> {
  return unwrap(apiClient.get<SelectedCandidate[]>(`/api/v1/campaigns/${campaignId}/candidates/pending-approval`));
}

// Hand-select or reject one candidate, overriding whatever the automatic
// layer decided (or is about to decide, for a pending_approval candidate).
export async function decideCandidate(
  campaignId: string,
  candidateId: string,
  decision: "select" | "reject",
  reason?: string
): Promise<CandidateDecisionResponse> {
  return unwrap(
    apiClient.post<CandidateDecisionResponse>(`/api/v1/campaigns/${campaignId}/candidates/${candidateId}/decision`, {
      decision,
      reason: reason ?? null,
    })
  );
}

// Same reasoning as downloadAssignment: these routes are JWT-gated so a
// plain <a href> won't carry the Authorization header - fetch the blob
// through apiClient and save it client-side instead.
async function downloadCandidateFile(
  campaignId: string,
  candidateId: string,
  kind: "resume" | "submission" | "report/download",
  fallbackName: string
): Promise<void> {
  let response;
  try {
    response = await apiClient.get(`/api/v1/campaigns/${campaignId}/candidates/${candidateId}/${kind}`, {
      responseType: "blob",
    });
  } catch (err) {
    const axiosErr = err as AxiosError<ApiErrorBody>;
    throw new CampaignApiError(axiosErr.message ?? "Something went wrong.", axiosErr.response?.status);
  }

  const disposition: string | undefined = response.headers["content-disposition"];
  const match = disposition?.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? fallbackName;

  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function downloadCandidateResume(campaignId: string, candidateId: string, candidateName?: string | null): Promise<void> {
  return downloadCandidateFile(campaignId, candidateId, "resume", `${candidateName ?? "candidate"}_resume.pdf`);
}

export async function downloadCandidateSubmission(campaignId: string, candidateId: string, candidateName?: string | null): Promise<void> {
  return downloadCandidateFile(campaignId, candidateId, "submission", `${candidateName ?? "candidate"}_submission.pdf`);
}

// The report has no dedicated file on disk - it's the FinalReport JSON
// stored on the submission row - so it's fetched as data and saved as a
// .json file client-side rather than streamed like resume/submission.
export async function downloadCandidateReport(campaignId: string, candidateId: string, candidateName?: string | null): Promise<void> {
  let report: unknown;
  try {
    const response = await apiClient.get(`/api/v1/campaigns/${campaignId}/candidates/${candidateId}/report`);
    report = response.data;
  } catch (err) {
    const axiosErr = err as AxiosError<ApiErrorBody>;
    throw new CampaignApiError(axiosErr.message ?? "Something went wrong.", axiosErr.response?.status);
  }

  const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${candidateName ?? "candidate"}_evaluation_report.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// The rendered report.pdf, stored alongside resume/submission - unlike
// downloadCandidateReport (JSON, fetched as data), this streams the
// actual file the same way downloadCandidateResume/Submission do.
export async function downloadCandidateReportPdf(campaignId: string, candidateId: string, candidateName?: string | null): Promise<void> {
  return downloadCandidateFile(campaignId, candidateId, "report/download", `${candidateName ?? "candidate"}_report.pdf`);
}

export async function getDashboard(campaignId: string): Promise<CampaignDashboard> {
  return unwrap(apiClient.get<CampaignDashboard>(`/api/v1/campaigns/${campaignId}/dashboard`));
}

export async function getTimeline(campaignId: string): Promise<CampaignEvent[]> {
  return unwrap(apiClient.get<CampaignEvent[]>(`/api/v1/campaigns/${campaignId}/timeline`));
}

export async function evaluateCampaign(campaignId: string): Promise<EvaluateCampaignResponse> {
  return unwrap(apiClient.post<EvaluateCampaignResponse>(`/api/v1/campaigns/${campaignId}/evaluations`));
}

// Releases the HR-approved shortlist: finalizes every pending_approval
// candidate to final_selected/final_rejected and sends the outcome emails.
export async function approveEvaluation(campaignId: string): Promise<ApproveEvaluationResponse> {
  return unwrap(apiClient.post<ApproveEvaluationResponse>(`/api/v1/campaigns/${campaignId}/evaluations/approve`));
}

// -- Assignments -----------------------------------------------------------

// Returns null (not an error) when the campaign has no assignment yet -
// that's the normal state before HR has generated/uploaded one, not a
// failure. Lets the Assignment page restore existing state on
// mount/revisit instead of always showing the generate/upload chooser.
export async function getCampaignAssignment(campaignId: string): Promise<Assignment | null> {
  try {
    return await unwrap(apiClient.get<Assignment>(`/api/v1/campaigns/${campaignId}/assignment`));
  } catch (err) {
    if (err instanceof CampaignApiError && err.status === 404) return null;
    throw err;
  }
}

export async function uploadAssignment(campaignId: string, title: string, file: File): Promise<Assignment> {
  const formData = new FormData();
  formData.append("title", title);
  formData.append("file", file);
  return unwrap(
    apiClient.post<Assignment>(`/api/v1/campaigns/${campaignId}/assignments/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  );
}

export async function linkAssignment(campaignId: string, title: string, googleDriveLink: string): Promise<Assignment> {
  return unwrap(
    apiClient.post<Assignment>(`/api/v1/campaigns/${campaignId}/assignments/link`, {
      title,
      google_drive_link: googleDriveLink,
    })
  );
}

export async function generateAssignment(
  campaignId: string,
  params: { title: string; brief: string; numQuestions?: number; numSections?: number; difficulty?: string }
): Promise<Assignment> {
  return unwrap(
    apiClient.post<Assignment>(`/api/v1/campaigns/${campaignId}/assignments/generate`, {
      title: params.title,
      brief: params.brief,
      num_questions: params.numQuestions ?? 8,
      num_sections: params.numSections ?? 2,
      difficulty: params.difficulty ?? "mid-level",
    })
  );
}

export async function regenerateAssignment(
  assignmentId: string,
  params: { title: string; brief: string; numQuestions?: number; numSections?: number; difficulty?: string }
): Promise<Assignment> {
  return unwrap(
    apiClient.post<Assignment>(`/api/v1/assignments/${assignmentId}/regenerate`, {
      title: params.title,
      brief: params.brief,
      num_questions: params.numQuestions ?? 8,
      num_sections: params.numSections ?? 2,
      difficulty: params.difficulty ?? "mid-level",
    })
  );
}

export async function editAssignment(assignmentId: string, questionPaperText: string): Promise<Assignment> {
  return unwrap(
    apiClient.patch<Assignment>(`/api/v1/assignments/${assignmentId}`, { question_paper_text: questionPaperText })
  );
}

export async function getAssignmentVersions(assignmentId: string): Promise<AssignmentVersion[]> {
  return unwrap(apiClient.get<AssignmentVersion[]>(`/api/v1/assignments/${assignmentId}/versions`));
}

export async function approveAssignment(
  assignmentId: string,
  deadlineDays: number,
  versionId?: string
): Promise<AssignmentSendResult> {
  return unwrap(
    apiClient.post<AssignmentSendResult>(`/api/v1/assignments/${assignmentId}/approve`, {
      deadline_days: deadlineDays,
      version_id: versionId ?? null,
    })
  );
}

// A plain <a href> can't attach the Authorization header, and this route
// is JWT-gated, so the file has to be fetched through apiClient (which
// attaches the token) and saved from the resulting blob instead.
export async function downloadAssignment(
  assignmentId: string,
  format: "docx" | "pdf" = "docx",
  versionId?: string
): Promise<void> {
  const params = new URLSearchParams({ format });
  if (versionId) params.set("version_id", versionId);
  let response;
  try {
    response = await apiClient.get(`/api/v1/assignments/${assignmentId}/download?${params}`, {
      responseType: "blob",
    });
  } catch (err) {
    const axiosErr = err as AxiosError<ApiErrorBody>;
    throw new CampaignApiError(axiosErr.message ?? "Something went wrong.", axiosErr.response?.status);
  }

  const disposition: string | undefined = response.headers["content-disposition"];
  const match = disposition?.match(/filename="?([^"]+)"?/);
  const filename = match?.[1] ?? `assignment.${format}`;

  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
