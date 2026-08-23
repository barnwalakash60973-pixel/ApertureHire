/**
 * Mirrors app/api/schemas.py and app/domain/enums.py for the campaign
 * workflow. Keep in sync with the backend - these are not independently
 * guessed types.
 */

export type CandidateStatus =
  | "pending_review"
  | "shortlisted"
  | "not_shortlisted"
  | "assignment_sent"
  | "submission_overdue"
  | "submitted"
  | "evaluated"
  | "pending_approval"
  | "final_selected"
  | "final_rejected";

export type MatchDecision = "shortlisted" | "not_shortlisted";

export interface ResumeMatchResult {
  required_skills: string[];
  resume_skills: string[];
  matched_skills: string[];
  missing_skills: string[];
  jd_min_years_experience: number | null;
  candidate_years_experience: number | null;
  experience_satisfied: boolean | null;
  decision: MatchDecision;
  decision_reason: string;
}

export interface Campaign {
  id: string;
  name: string;
  job_title: string;
  status: string;
  created_at: string;
  candidate_count: number;
  shortlisted_count: number;
  not_shortlisted_count: number;
}

export interface Candidate {
  id: string;
  campaign_id: string;
  name: string | null;
  email: string | null;
  status: CandidateStatus;
  match_result: ResumeMatchResult | null;
  created_at: string;
}

export interface SelectedCandidate {
  id: string;
  name: string | null;
  email: string | null;
  overall_score: number;
  hiring_recommendation: string;
  strengths: string[];
  weaknesses: string[];
  resume_available: boolean;
  submission_available: boolean;
  report_available: boolean;
  rank: number;
  // Set only on the pending-approval listing: the auto-computed outcome
  // awaiting HR release. Null on the final_selected listing.
  pending_decision?: "select" | "reject" | null;
}

export interface BulkResumeImportResponse {
  campaign_id: string;
  total_uploaded: number;
  would_shortlist_count: number;
  would_not_shortlist_count: number;
  candidates: Candidate[];
}

export interface ConfirmImportResponse {
  campaign_id: string;
  shortlisted_count: number;
  not_shortlisted_count: number;
  emails_sent: number;
}

export interface AssignmentVersion {
  id: string;
  version_number: number;
  question_paper_text: string;
  source: "uploaded" | "generated" | "edited" | "link";
  label: string;
  google_drive_link: string | null;
  created_at: string;
  is_approved: boolean;
}

export interface Assignment {
  id: string;
  campaign_id: string | null;
  title: string;
  status: "draft" | "approved";
  deadline: string | null;
  sent_at: string | null;
  created_at: string;
  current_version: AssignmentVersion;
  version_count: number;
}

export interface AssignmentSendResult {
  assignment_id: string;
  approved_version_number: number;
  candidates_notified: number;
  deadline: string;
}

// -- Candidate submission portal (public, token-gated, no login) ----------

export interface SubmissionView {
  candidate_name: string | null;
  campaign_name: string;
  assignment_title: string;
  question_paper_text: string;
  deadline: string | null;
  status: "not_submitted" | "submitted" | "waiting_for_evaluation" | "overdue" | "evaluated";
  submitted_on: string | null;
  assignment_link: string;
  assignment_is_drive_link: boolean;
}

export interface SubmissionSubmitResult {
  candidate_id: string;
  assignment_id: string;
  status: string;
  submitted_on: string;
}

export interface CampaignDashboard {
  campaign_id: string;
  total_resumes: number;
  shortlisted_count: number;
  not_shortlisted_count: number;
  assignment_sent_count: number;
  submitted_count: number;
  overdue_count: number;
  pending_approval_count: number;
  final_selected_count: number;
  final_rejected_count: number;
  deadline: string | null;
  days_remaining: number | null;
  ready_for_evaluation: boolean;
  next_action: string;
}

export interface CampaignEvent {
  event_type: string;
  message: string;
  created_at: string;
}

export interface EvaluateCampaignResponse {
  campaign_id: string;
  evaluated_count: number;
  pending_selected_count: number;
  pending_rejected_count: number;
  failed_count: number;
}

export interface ApproveEvaluationResponse {
  campaign_id: string;
  final_selected_count: number;
  final_rejected_count: number;
  emails_sent: number;
}

export interface CandidateDecisionResponse {
  candidate_id: string;
  status: string;
  overridden: boolean;
}
