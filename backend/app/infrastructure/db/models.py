"""
ORM models for the recruitment platform. Deliberately lean - 4 tables, not
8 - because the rich Pydantic results you already have (ResumeMatchResult,
FinalReport) are stored as JSON columns rather than fully normalized into
their own tables. This avoids maintaining two parallel schemas (Pydantic +
SQL) for data that's always read/written as a whole object anyway.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CampaignORM(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    job_title: Mapped[str] = mapped_column(String(255))
    job_description_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")  # active | closed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    candidates: Mapped[list["CandidateORM"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")
    assignments: Mapped[list["AssignmentORM"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class CandidateORM(Base):
    __tablename__ = "candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resume_text: Mapped[str] = mapped_column(Text)

    # -- Structured application-form fields --------------------------------
    # Required by the spec's "Candidates Apply" step but previously not
    # collected anywhere - bulk-import only ever regex-extracted name/
    # email from resume text. Populated directly when a candidate applies
    # via POST /api/v1/public/campaigns/{id}/apply; left null for
    # HR-bulk-imported resumes (that path only ever has resume text to
    # work with, so these stay null there - not every candidate has to
    # have come through the public form).
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    degree: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cgpa: Mapped[str | None] = mapped_column(String(16), nullable=True)
    college: Mapped[str | None] = mapped_column(String(255), nullable=True)
    graduation_year: Mapped[int | None] = mapped_column(nullable=True)
    skills: Mapped[str | None] = mapped_column(String(500), nullable=True)  # optional, comma-separated
    github_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    portfolio_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    application_source: Mapped[str] = mapped_column(
        String(32), default="hr_import"
    )  # "public_form" | "hr_import" - which intake path created this row

    # Stores ResumeMatchResult.model_dump() - the full rule-based match
    # output (skills, experience, decision, reason), null until matched.
    match_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # pending_review (just imported, HR reviewing extracted name/email) ->
    # shortlisted|not_shortlisted (after HR confirms import) -> assignment_sent
    # -> submitted -> evaluated -> pending_approval (auto threshold/top_n
    # outcome computed, awaiting HR release - see evaluate_campaign) ->
    # final_selected|final_rejected. "manual" evaluation mode skips
    # pending_approval and goes straight from evaluated to a per-candidate
    # override (see override_candidate_decision).
    status: Mapped[str] = mapped_column(String(32), default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # "select" | "reject" - the auto-computed outcome from evaluate_campaign's
    # threshold/top_n mode, held here while status == "pending_approval" so
    # POST .../evaluations/approve knows what to finalize without
    # recomputing. Cleared once approved or individually overridden.
    pending_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # -- File storage (see infrastructure/storage/) -------------------------
    # Key into the active FileStorage backend (local path or S3 key) for
    # the ORIGINAL resume file - previously the file bytes were parsed to
    # text and discarded, so "Download Resume" had nothing to serve.
    resume_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # -- Retention (see core/scheduler.py) -----------------------------------
    # Set the moment a candidate enters not_shortlisted or final_rejected.
    # A periodic job deletes resume_storage_key + blanks resume_text once
    # this passes - previously nothing ever expired.
    retention_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_purged: Mapped[bool] = mapped_column(default=False)

    # Unauthenticated candidates access their submission portal via this
    # token (mailed as part of the assignment link) rather than a full
    # login system - simplest thing that works for a take-home assignment.
    submission_token: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)

    campaign: Mapped["CampaignORM"] = relationship(back_populates="candidates")
    submissions: Mapped[list["SubmissionORM"]] = relationship(back_populates="candidate", cascade="all, delete-orphan")


class AssignmentORM(Base):
    """Container for an assignment's lifecycle - the actual question-paper
    TEXT lives in AssignmentVersionORM (versioned, never overwritten).
    This table just tracks which version is approved, plus deadline/send
    state, per the versioning requirement: every generate/edit/regenerate
    creates a new version; approving picks ONE version (rollback = approve
    an older version instead of the latest)."""

    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255))

    # draft -> approved (nothing is emailed to candidates until approved)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    approved_version_id: Mapped[str | None] = mapped_column(ForeignKey("assignment_versions.id"), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    campaign: Mapped["CampaignORM | None"] = relationship(back_populates="assignments")
    versions: Mapped[list["AssignmentVersionORM"]] = relationship(
        back_populates="assignment", cascade="all, delete-orphan", foreign_keys="AssignmentVersionORM.assignment_id"
    )
    submissions: Mapped[list["SubmissionORM"]] = relationship(back_populates="assignment", cascade="all, delete-orphan")


class AssignmentVersionORM(Base):
    """One immutable version of an assignment's question-paper text. Every
    generate/regenerate/edit/upload creates a NEW row here - nothing is
    ever overwritten, so HR can roll back by approving an older version."""

    __tablename__ = "assignment_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"))
    version_number: Mapped[int] = mapped_column()
    question_paper_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))  # "uploaded" | "generated" | "edited" | "link"
    label: Mapped[str] = mapped_column(String(64))  # e.g. "Generated", "Edited by HR", "Regenerated"
    # Set when HR provides a Google Drive link instead of an uploaded/
    # generated question paper (source="link"). Null for every other source.
    google_drive_link: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    assignment: Mapped["AssignmentORM"] = relationship(back_populates="versions", foreign_keys=[assignment_id])


class CampaignEventORM(Base):
    """Timeline entry - one row per notable campaign action, for the
    'Campaign Timeline' view. Purely additive logging, no LLM."""

    __tablename__ = "campaign_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SubmissionORM(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("candidates.id"))
    assignment_id: Mapped[str] = mapped_column(ForeignKey("assignments.id"))
    submission_text: Mapped[str] = mapped_column(Text)

    # Key into the active FileStorage backend for the original submitted
    # file (.pdf/.docx/.zip) - same "was discarded after parsing, now
    # persisted" fix as CandidateORM.resume_storage_key.
    submission_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Stores FinalReport.model_dump() once evaluated. Null while pending.
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Key into the active FileStorage backend for the rendered report.pdf
    # (see services/review/report_pdf.py) - same "was only a DB column, now
    # also a real downloadable file" fix as the resume/submission keys.
    report_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    candidate: Mapped["CandidateORM"] = relationship(back_populates="submissions")
    assignment: Mapped["AssignmentORM"] = relationship(back_populates="submissions")


class UserORM(Base):
    """HR user. Login accepts either email OR mobile_number - both are
    unique identifiers, either can be used interchangeably at login. A
    single role ("hr") for now; RBAC (Admin/HR Manager/Recruiter) is a
    documented follow-up, not built yet."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    mobile_number: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="hr")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Password reset OTP - one active OTP at a time is enough for this
    # scope; a new "forgot password" request simply overwrites it.
    reset_otp_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reset_otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
