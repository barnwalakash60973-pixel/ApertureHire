"""
FastAPI-facing schemas. Kept separate from domain models so the API's
public contract can evolve independently of internal domain types (e.g.
if we later want a leaner API response than the full FinalReport).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models import FinalReport, ResumeMatchResult


class ReviewResponse(BaseModel):
    """Top-level API response wrapping the domain FinalReport."""

    report: FinalReport


class ResumeMatchResponse(BaseModel):
    """Top-level API response wrapping the rule-based (0 LLM) ResumeMatchResult."""

    match: ResumeMatchResult


class AssignmentGenerationResponse(BaseModel):
    """Top-level API response for the AI-generated question paper text."""

    question_paper_text: str


class AssignmentGenerationRequest(BaseModel):
    """Request body for POST /assignment/generate."""

    brief: str = Field(min_length=1, description="What the assignment should test for, e.g. 'RAG + FastAPI backend, mid-level'.")
    num_questions: int = Field(default=8, ge=1, le=30)
    num_sections: int = Field(default=2, ge=1, le=10)
    difficulty: str = Field(default="mid-level")





class CampaignResponse(BaseModel):
    id: str
    name: str
    job_title: str
    status: str
    created_at: datetime
    candidate_count: int
    shortlisted_count: int
    not_shortlisted_count: int


class CandidateResponse(BaseModel):
    id: str
    campaign_id: str
    name: str | None
    email: str | None
    phone: str | None = None
    degree: str | None = None
    cgpa: str | None = None
    college: str | None = None
    graduation_year: int | None = None
    status: str
    match_result: ResumeMatchResult | None
    resume_available: bool = False
    created_at: datetime


class CandidateApplicationRequest(BaseModel):
    """Body for the public, unauthenticated apply endpoint - the
    "Candidates Apply" step of the flowchart, previously missing
    entirely (only HR-side bulk import of already-collected resumes
    existed). Matches the diagram's Required/Optional field split."""

    full_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=255)
    phone_number: str = Field(min_length=3, max_length=32)
    degree: str = Field(min_length=1, max_length=255)
    cgpa: str = Field(min_length=1, max_length=16)
    college: str = Field(min_length=1, max_length=255)
    graduation_year: int = Field(ge=1980, le=2100)

    # Optional per the diagram
    skills: str | None = Field(default=None, max_length=500, description="Comma-separated")
    github_url: str | None = Field(default=None, max_length=500)
    portfolio_url: str | None = Field(default=None, max_length=500)
    linkedin_url: str | None = Field(default=None, max_length=500)


class CandidateApplicationResponse(BaseModel):
    candidate_id: str
    campaign_id: str
    message: str = "Application received."


class PublicCampaignResponse(BaseModel):
    """Deliberately narrow: only what a public job posting page needs.
    No candidate counts, no screening config, no internal status - this
    is readable by anyone holding the share link."""

    campaign_id: str
    name: str
    job_title: str
    job_description_text: str


class SelectedCandidateResponse(BaseModel):
    """One row in the ranked 'Final Selected' view - high score to low,
    with enough context that HR can see WHY, not just the score.

    strengths/weaknesses come from data the evaluator already computed
    (no new LLM call): strengths are pulled from each question's
    evidence-based strengths list, weaknesses from the report's
    top-level missing_topics - both real evaluation output, not
    fabricated or re-derived from a fresh model call."""

    id: str
    name: str | None
    email: str | None
    overall_score: float
    hiring_recommendation: str
    strengths: list[str]
    weaknesses: list[str]
    resume_available: bool
    submission_available: bool
    report_available: bool
    rank: int
    # Set only on the pending-approval listing: the auto-computed outcome
    # (from evaluate_campaign's threshold/top_n mode) awaiting HR release.
    # Null for the final_selected listing, where the outcome already is final.
    pending_decision: Literal["select", "reject"] | None = None


class CandidateEditRequest(BaseModel):
    """HR correcting an extracted name/email during import review."""

    name: str | None = None
    email: str | None = None


class BulkResumeImportResponse(BaseModel):
    """Import PREVIEW - candidates are created as pending_review, no email
    sent yet. HR edits any wrong name/email, then calls /resumes/confirm."""

    campaign_id: str
    total_uploaded: int
    would_shortlist_count: int
    would_not_shortlist_count: int
    candidates: list[CandidateResponse]


class ConfirmImportResponse(BaseModel):
    campaign_id: str
    shortlisted_count: int
    not_shortlisted_count: int
    emails_sent: int


class AssignmentVersionResponse(BaseModel):
    id: str
    version_number: int
    question_paper_text: str
    source: str
    label: str
    google_drive_link: str | None = None
    created_at: datetime
    is_approved: bool


class AssignmentResponse(BaseModel):
    id: str
    campaign_id: str | None
    title: str
    status: str
    deadline: datetime | None
    sent_at: datetime | None
    created_at: datetime
    current_version: AssignmentVersionResponse
    version_count: int


class GenerateCampaignAssignmentRequest(BaseModel):
    title: str = Field(min_length=1)
    brief: str = Field(min_length=1)
    num_questions: int = Field(default=8, ge=1, le=30)
    num_sections: int = Field(default=2, ge=1, le=10)
    difficulty: str = Field(default="mid-level")


class CreateAssignmentLinkRequest(BaseModel):
    """Body for POST /campaigns/{campaign_id}/assignments/link - the
    'Provide Google Drive Link' alternative to uploading a file."""

    title: str = Field(min_length=1)
    google_drive_link: str = Field(min_length=1, max_length=1000)


class EditAssignmentRequest(BaseModel):
    question_paper_text: str = Field(min_length=1)


class ApproveAssignmentRequest(BaseModel):
    deadline_days: int = Field(default=7, ge=1, le=90)
    version_id: str | None = Field(default=None, description="Approve a SPECIFIC version (rollback). Defaults to the latest.")


class ExtendDeadlineRequest(BaseModel):
    additional_days: int = Field(ge=1, le=90)


class AssignmentSendResult(BaseModel):
    assignment_id: str
    approved_version_number: int
    candidates_notified: int
    deadline: datetime


class DeadlineStatusResponse(BaseModel):
    assignment_id: str
    deadline: datetime
    deadline_passed: bool
    sent_count: int
    submitted_count: int
    not_submitted_count: int


class CampaignDashboardResponse(BaseModel):
    """Pure DB-query dashboard - no LLM involved."""

    campaign_id: str
    total_resumes: int
    shortlisted_count: int
    not_shortlisted_count: int
    assignment_sent_count: int
    submitted_count: int
    overdue_count: int
    pending_approval_count: int
    final_selected_count: int
    final_rejected_count: int
    deadline: datetime | None
    days_remaining: int | None
    ready_for_evaluation: bool
    next_action: str


class CampaignEventResponse(BaseModel):
    event_type: str
    message: str
    created_at: datetime


class SubmissionSubmitResponse(BaseModel):
    candidate_id: str
    assignment_id: str
    status: str
    submitted_on: datetime


class SubmissionViewResponse(BaseModel):
    candidate_name: str | None
    campaign_name: str
    assignment_title: str
    question_paper_text: str
    deadline: datetime | None
    status: str  # not_submitted | submitted | waiting_for_evaluation | evaluated
    submitted_on: datetime | None
    # Where "Open Assignment" / "Download Assignment" should point: the HR's
    # Google Drive link if they provided one, otherwise a token-gated link
    # to this backend that serves the uploaded/generated question paper as
    # a .docx - never the HR-only /api/v1/assignments/{id}/download route.
    assignment_link: str
    assignment_is_drive_link: bool


class EvaluateCampaignResponse(BaseModel):
    """Nothing is final yet after this call for threshold/top_n mode -
    candidates land in 'pending_approval' with a computed pending_decision.
    See ApproveEvaluationResponse for the step that actually finalizes and
    emails."""

    campaign_id: str
    evaluated_count: int
    pending_selected_count: int
    pending_rejected_count: int
    failed_count: int


class ApproveEvaluationResponse(BaseModel):
    """Result of releasing the HR-approved shortlist: every pending_approval
    candidate is finalized to final_selected/final_rejected and emailed."""

    campaign_id: str
    final_selected_count: int
    final_rejected_count: int
    emails_sent: int


class EvaluateCampaignRequest(BaseModel):
    """HR Decision Layer config. The flowchart specifies three selection
    modes; previously the code had exactly one, hardcoded at 6.0, with
    no way for HR to change it or to override an outcome.

    Modes are mutually exclusive:
      - "threshold": select everyone scoring >= score_threshold
      - "top_n": select the top N by score, regardless of absolute score
      - "manual": select nobody automatically - evaluate and rank only,
        then HR picks via /candidates/{id}/decision

    Note the modes answer different questions. "threshold" asks "is this
    candidate good enough?" and can select nobody (or everybody).
    "top_n" asks "who are the best available?" and will fill N seats
    even if the whole pool is weak - which is exactly the failure mode
    to watch for when a campaign gets few applicants.
    """

    mode: Literal["threshold", "top_n", "manual"] = Field(default="threshold")
    score_threshold: float = Field(default=6.0, ge=0.0, le=10.0, description="Used when mode='threshold'.")
    top_n: int = Field(default=20, ge=1, le=1000, description="Used when mode='top_n'.")


class CandidateDecisionRequest(BaseModel):
    """Manual override - the flowchart's 'Recruiter can manually
    select/reject'. Always beats whatever the automatic layer decided,
    and is recorded on the campaign timeline so an override is never
    silent."""

    decision: Literal["select", "reject"]
    reason: str | None = Field(default=None, max_length=500)


class CandidateDecisionResponse(BaseModel):
    candidate_id: str
    status: str
    overridden: bool


class PurgeResponse(BaseModel):
    """Result of an HR-triggered retention purge. Rows are kept (so
    counts and audit history stay correct) - only the resume file and
    extracted text are cleared."""

    campaign_id: str
    purged_count: int


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


class RegisterRequest(BaseModel):
    """HR account creation. Not wired to a public signup page for now -
    intended to be called once during setup/onboarding."""

    name: str = Field(min_length=1)
    email: str = Field(min_length=3)
    mobile_number: str | None = Field(default=None)
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, description="Email OR mobile number.")
    password: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    mobile_number: str | None
    role: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1, description="Email OR mobile number.")


class ForgotPasswordResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1)
    otp: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)
