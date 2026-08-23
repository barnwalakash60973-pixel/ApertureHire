"""
Campaign endpoints: create a campaign, IMPORT resumes for HR review
(rule-based matching + regex name/email extraction, 0 LLM), let HR
correct any wrong name/email, CONFIRM the import (which is when Email 1
actually goes out), list/dashboard/timeline, and trigger evaluation.

Bulk upload is processed SYNCHRONOUSLY within the request - fine up to a
few hundred/thousand resumes since matching is pure regex (no network
calls); genuinely 100,000-resume batches need a real background job
queue (Celery/RQ) to avoid an HTTP timeout.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    ApproveEvaluationResponse,
    BulkResumeImportResponse,
    CampaignDashboardResponse,
    CampaignEventResponse,
    CampaignResponse,
    CandidateEditRequest,
    CandidateResponse,
    ConfirmImportResponse,
    DeadlineStatusResponse,
    CandidateDecisionRequest,
    CandidateDecisionResponse,
    EvaluateCampaignRequest,
    EvaluateCampaignResponse,
    SelectedCandidateResponse,
)
from app.core.config import get_settings
from app.core.container import get_email_sender_dep, get_resume_matcher, get_review_use_case
from app.core.exceptions import DocumentParsingError, ReviewerError, UnsupportedFileTypeError
from app.core.logging import get_logger
from app.domain.enums import MatchDecision
from app.infrastructure.db.database import get_session
from app.infrastructure.db.models import (
    AssignmentORM,
    AssignmentVersionORM,
    CampaignEventORM,
    CampaignORM,
    CandidateORM,
    SubmissionORM,
)
from app.infrastructure.email.templates import (
    FINAL_REJECTED_EMAIL_BODY,
    FINAL_REJECTED_EMAIL_SUBJECT,
    FINAL_SELECTED_EMAIL_BODY,
    FINAL_SELECTED_EMAIL_SUBJECT,
    REJECTED_EMAIL_BODY,
    REJECTED_EMAIL_SUBJECT,
    SHORTLIST_EMAIL_BODY,
    SHORTLIST_EMAIL_SUBJECT,
)
from app.infrastructure.parsers.document_factory import get_parser_for
from app.infrastructure.storage.factory import get_file_storage
from app.infrastructure.storage.keys import report_key, resume_key
from app.services.review.contact_extractor import extract_email, extract_name
from app.services.review.report_pdf import render_report_pdf

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])
logger = get_logger(__name__)

_ALLOWED_SUFFIXES = {".docx", ".pdf"}
# NOTE: the old module-level _FINAL_SELECTION_SCORE_THRESHOLD = 6.0 is gone.
# The final-selection cutoff is no longer a constant baked into this module -
# it is per-request config (EvaluateCampaignRequest.score_threshold, still
# defaulting to 6.0), because the flowchart's HR Decision Layer requires HR
# to be able to change the cutoff, use Top-N instead, or select manually.


def _retention_deadline(settings) -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.rejected_candidate_retention_days)


def _to_candidate_response(c: CandidateORM) -> CandidateResponse:
    return CandidateResponse(
        id=c.id, campaign_id=c.campaign_id, name=c.name, email=c.email,
        phone=c.phone, degree=c.degree, cgpa=c.cgpa, college=c.college, graduation_year=c.graduation_year,
        status=c.status, match_result=c.match_result,
        resume_available=bool(c.resume_storage_key), created_at=c.created_at,
    )


def _validate_upload(file: UploadFile) -> None:
    suffix = "." + file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
    if suffix not in _ALLOWED_SUFFIXES:
        raise UnsupportedFileTypeError(f"Unsupported file type '{suffix}' for '{file.filename}'. Allowed: .docx, .pdf")


def _as_utc(dt: datetime | None) -> datetime | None:
    """SQLite (via aiosqlite) doesn't reliably round-trip tzinfo on
    DateTime(timezone=True) columns. We only ever write UTC, so a naive
    read is safely assumed to be UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def _log_event(session: AsyncSession, campaign_id: str, event_type: str, message: str) -> None:
    session.add(CampaignEventORM(campaign_id=campaign_id, event_type=event_type, message=message))


async def _campaign_counts(session: AsyncSession, campaign_id: str) -> tuple[int, int, int]:
    total = (await session.execute(
        select(func.count()).select_from(CandidateORM).where(CandidateORM.campaign_id == campaign_id)
    )).scalar_one()
    # Cumulative - everyone who was EVER shortlisted, not just those
    # currently sitting in that exact state (same reasoning as the
    # dashboard endpoint - stays 120 even after progressing further).
    shortlisted = (await session.execute(
        select(func.count()).select_from(CandidateORM)
        .where(CandidateORM.campaign_id == campaign_id, CandidateORM.status.in_(
            ["shortlisted", "assignment_sent", "submitted", "submission_overdue", "evaluated", "final_selected", "final_rejected"]
        ))
    )).scalar_one()
    not_shortlisted = (await session.execute(
        select(func.count()).select_from(CandidateORM)
        .where(CandidateORM.campaign_id == campaign_id, CandidateORM.status == "not_shortlisted")
    )).scalar_one()
    return total, shortlisted, not_shortlisted


async def _latest_approved_assignment(session: AsyncSession, campaign_id: str) -> AssignmentORM | None:
    result = await session.execute(
        select(AssignmentORM)
        .where(AssignmentORM.campaign_id == campaign_id, AssignmentORM.status == "approved")
        .order_by(AssignmentORM.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _mark_overdue_candidates(session: AsyncSession, campaign_id: str) -> None:
    """No scheduler exists yet, so this runs lazily: any time HR looks at
    the dashboard/candidates/deadline-status/evaluate for this campaign,
    first flip any assignment_sent candidate whose deadline has passed to
    submission_overdue. Cheap (one query), idempotent, and keeps "who
    never submitted" visible without needing a background job."""

    assignment = await _latest_approved_assignment(session, campaign_id)
    if assignment is None or assignment.deadline is None:
        return
    if datetime.now(timezone.utc) <= _as_utc(assignment.deadline):
        return

    result = await session.execute(
        select(CandidateORM).where(CandidateORM.campaign_id == campaign_id, CandidateORM.status == "assignment_sent")
    )
    overdue_candidates = result.scalars().all()
    for candidate in overdue_candidates:
        candidate.status = "submission_overdue"

    if overdue_candidates:
        logger.info("Marked %d candidates as submission_overdue for campaign %s (deadline passed)", len(overdue_candidates), campaign_id)

    await _maybe_log_ready_for_evaluation(session, campaign_id)


async def _maybe_log_ready_for_evaluation(session: AsyncSession, campaign_id: str) -> None:
    """Logs the 'Campaign Ready for Evaluation' timeline event exactly
    once, the moment every shortlisted candidate is either submitted or
    overdue - i.e. nobody is still just sitting in assignment_sent."""

    already_logged = (await session.execute(
        select(func.count()).select_from(CampaignEventORM)
        .where(CampaignEventORM.campaign_id == campaign_id, CampaignEventORM.event_type == "campaign_ready_for_evaluation")
    )).scalar_one()
    if already_logged:
        return

    still_pending = (await session.execute(
        select(func.count()).select_from(CandidateORM)
        .where(CandidateORM.campaign_id == campaign_id, CandidateORM.status == "assignment_sent")
    )).scalar_one()
    total_sent = (await session.execute(
        select(func.count()).select_from(CandidateORM)
        .where(CandidateORM.campaign_id == campaign_id, CandidateORM.status.in_(["assignment_sent", "submitted", "submission_overdue", "evaluated", "final_selected", "final_rejected"]))
    )).scalar_one()
    if total_sent == 0 or still_pending > 0:
        return

    submitted_count = (await session.execute(
        select(func.count()).select_from(CandidateORM)
        .where(CandidateORM.campaign_id == campaign_id, CandidateORM.status.in_(["submitted", "evaluated", "final_selected", "final_rejected"]))
    )).scalar_one()
    overdue_count = (await session.execute(
        select(func.count()).select_from(CandidateORM)
        .where(CandidateORM.campaign_id == campaign_id, CandidateORM.status == "submission_overdue")
    )).scalar_one()

    await _log_event(
        session, campaign_id, "campaign_ready_for_evaluation",
        f"{submitted_count} candidates submitted, {overdue_count} overdue - Campaign Ready for Evaluation.",
    )


@router.post("", response_model=CampaignResponse)
async def create_campaign(
    name: str = Form(...),
    job_title: str | None = Form(default=None),
    job_description_file: UploadFile | None = File(default=None, description="Job description as .docx/.pdf - preferred over pasting text"),
    job_description_text: str | None = Form(default=None, description="Fallback if no file is uploaded"),
    session: AsyncSession = Depends(get_session),
) -> CampaignResponse:
    """JD is extracted from a PDF/DOCX file via the same parser used for
    resumes/assignments - not typed/pasted text. `job_description_text`
    remains as a fallback for quick testing/API use, but the file upload
    is the intended path."""

    if job_description_file is not None:
        _validate_upload(job_description_file)
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = f"{tmp_dir}/{job_description_file.filename}"
            with open(path, "wb") as f:
                f.write(await job_description_file.read())
            try:
                job_description_text = await get_parser_for(path).extract_text(path)
            except DocumentParsingError as e:
                raise HTTPException(status_code=422, detail=str(e)) from e

    if not job_description_text or not job_description_text.strip():
        raise HTTPException(status_code=422, detail="Provide a job description: upload job_description_file (.docx/.pdf) or job_description_text.")

    campaign = CampaignORM(name=name, job_title=job_title or name, job_description_text=job_description_text)
    session.add(campaign)
    await session.flush()
    await _log_event(session, campaign.id, "campaign_created", f"Campaign '{campaign.name}' created.")
    await session.commit()
    await session.refresh(campaign)

    return CampaignResponse(
        id=campaign.id, name=campaign.name, job_title=campaign.job_title, status=campaign.status,
        created_at=campaign.created_at, candidate_count=0, shortlisted_count=0, not_shortlisted_count=0,
    )


@router.get("", response_model=list[CampaignResponse])
async def list_campaigns(session: AsyncSession = Depends(get_session)) -> list[CampaignResponse]:
    result = await session.execute(select(CampaignORM).order_by(CampaignORM.created_at.desc()))
    campaigns = result.scalars().all()

    responses = []
    for campaign in campaigns:
        total, shortlisted, not_shortlisted = await _campaign_counts(session, campaign.id)
        responses.append(CampaignResponse(
            id=campaign.id, name=campaign.name, job_title=campaign.job_title, status=campaign.status,
            created_at=campaign.created_at, candidate_count=total, shortlisted_count=shortlisted, not_shortlisted_count=not_shortlisted,
        ))
    return responses


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> CampaignResponse:
    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")
    total, selected, auto_rejected = await _campaign_counts(session, campaign_id)
    return CampaignResponse(
        id=campaign.id, name=campaign.name, job_title=campaign.job_title, status=campaign.status,
        created_at=campaign.created_at, candidate_count=total, shortlisted_count=selected, not_shortlisted_count=auto_rejected,
    )


@router.post("/{campaign_id}/resumes/import", response_model=BulkResumeImportResponse)
async def import_resumes(
    campaign_id: str,
    resumes: list[UploadFile] = File(..., description="One or more resume files (.docx/.pdf)"),
    session: AsyncSession = Depends(get_session),
) -> BulkResumeImportResponse:
    """Step 1 of 2: parses + rule-matches + extracts name/email (regex,
    0 LLM), creates candidates as `pending_review`. NO email is sent yet -
    HR reviews/corrects extracted names/emails, then calls
    /resumes/confirm to finalize and trigger Email 1."""

    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")

    matcher = get_resume_matcher()
    storage = get_file_storage()
    created: list[CandidateORM] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        for upload in resumes:
            try:
                _validate_upload(upload)
            except UnsupportedFileTypeError as e:
                raise HTTPException(status_code=415, detail=str(e)) from e

            path = f"{tmp_dir}/{upload.filename}"
            content = await upload.read()
            with open(path, "wb") as f:
                f.write(content)

            try:
                resume_text = await get_parser_for(path).extract_text(path)
            except DocumentParsingError as e:
                logger.warning("Skipping unparseable resume %s: %s", upload.filename, e)
                continue
            if not resume_text.strip():
                logger.warning("Skipping empty resume %s", upload.filename)
                continue

            match_result = matcher.match(campaign.job_description_text, resume_text)
            candidate = CandidateORM(
                campaign_id=campaign_id,
                name=extract_name(resume_text),  # None if not confidently found - shown as "Not Found" by the frontend
                email=extract_email(resume_text),
                resume_text=resume_text,
                match_result=match_result.model_dump(mode="json"),
                status="pending_review",
                application_source="hr_import",
            )
            session.add(candidate)
            await session.flush()  # need candidate.id for the storage key before saving the file

            # Persist the ORIGINAL file bytes, not just the parsed text -
            # previously discarded once resume_text was extracted, so
            # "Download Resume" / the final archive had nothing to serve.
            key = resume_key(campaign_id, candidate.id, upload.filename)
            candidate.resume_storage_key = await storage.save(key, content)

            created.append(candidate)

    if created:
        would_shortlist = sum(1 for c in created if c.match_result["decision"] == MatchDecision.SHORTLISTED.value)
        await _log_event(
            session, campaign_id, "resumes_uploaded",
            f"{len(created)} resumes uploaded ({would_shortlist} would be shortlisted) - pending HR review.",
        )

    await session.commit()
    for c in created:
        await session.refresh(c)

    would_shortlist_count = sum(1 for c in created if c.match_result["decision"] == MatchDecision.SHORTLISTED.value)
    would_not_shortlist_count = len(created) - would_shortlist_count

    return BulkResumeImportResponse(
        campaign_id=campaign_id, total_uploaded=len(created),
        would_shortlist_count=would_shortlist_count, would_not_shortlist_count=would_not_shortlist_count,
        candidates=[
            _to_candidate_response(c)
            for c in created
        ],
    )


@router.patch("/{campaign_id}/candidates/{candidate_id}", response_model=CandidateResponse)
async def edit_candidate(
    campaign_id: str, candidate_id: str, body: CandidateEditRequest, session: AsyncSession = Depends(get_session)
) -> CandidateResponse:
    """HR correcting an extracted name/email during import review, per the
    'Edit' action in the import summary."""

    candidate = await session.get(CandidateORM, candidate_id)
    if candidate is None or candidate.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found in this campaign.")

    if body.name is not None:
        candidate.name = body.name
    if body.email is not None:
        candidate.email = body.email
    await session.commit()
    await session.refresh(candidate)

    return _to_candidate_response(candidate)


@router.post("/{campaign_id}/resumes/confirm", response_model=ConfirmImportResponse)
async def confirm_import(campaign_id: str, session: AsyncSession = Depends(get_session)) -> ConfirmImportResponse:
    """Step 2 of 2: the 'Continue' button. Finalizes every pending_review
    candidate to selected/auto_rejected based on their already-computed
    match_result, and sends Email 1 to selected candidates who have an
    email (0 LLM - fixed template)."""

    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")

    result = await session.execute(
        select(CandidateORM).where(CandidateORM.campaign_id == campaign_id, CandidateORM.status == "pending_review")
    )
    pending = result.scalars().all()
    if not pending:
        raise HTTPException(status_code=409, detail="No pending_review candidates to confirm for this campaign.")

    email_sender = get_email_sender_dep()
    settings = get_settings()
    shortlisted_count = 0
    not_shortlisted_count = 0
    emails_sent = 0
    rejection_emails_sent = 0

    for candidate in pending:
        decision = candidate.match_result["decision"]
        candidate.status = "shortlisted" if decision == MatchDecision.SHORTLISTED.value else "not_shortlisted"
        if candidate.status == "shortlisted":
            shortlisted_count += 1
            if candidate.email:
                email_sender.send(
                    to_email=candidate.email, subject=SHORTLIST_EMAIL_SUBJECT,
                    body=SHORTLIST_EMAIL_BODY.format(candidate_name=candidate.name or "Candidate", job_title=campaign.job_title),
                )
                emails_sent += 1
        else:
            not_shortlisted_count += 1
            # Was previously silent - the spec lists a "Rejected" email
            # template that nothing ever sent. Also starts the retention
            # clock: this candidate's resume file/text gets purged by the
            # scheduler after settings.rejected_candidate_retention_days
            # (see core/scheduler.py:purge_expired_candidates).
            candidate.retention_deadline = _retention_deadline(settings)
            if candidate.email:
                email_sender.send(
                    to_email=candidate.email, subject=REJECTED_EMAIL_SUBJECT,
                    body=REJECTED_EMAIL_BODY.format(candidate_name=candidate.name or "Candidate", job_title=campaign.job_title),
                )
                rejection_emails_sent += 1

    await _log_event(session, campaign_id, "candidates_shortlisted", f"{shortlisted_count} candidates shortlisted, {not_shortlisted_count} not shortlisted.")
    await _log_event(session, campaign_id, "shortlist_email_sent", f"Shortlist email sent to {emails_sent} candidates.")
    if rejection_emails_sent:
        await _log_event(session, campaign_id, "rejection_email_sent", f"Rejection email sent to {rejection_emails_sent} candidates.")
    await session.commit()

    logger.info("Import confirmed for campaign %s: %d shortlisted, %d not shortlisted, %d emails sent (0 LLM calls)", campaign_id, shortlisted_count, not_shortlisted_count, emails_sent)
    return ConfirmImportResponse(campaign_id=campaign_id, shortlisted_count=shortlisted_count, not_shortlisted_count=not_shortlisted_count, emails_sent=emails_sent)


@router.get("/{campaign_id}/assignment")
async def get_campaign_assignment(campaign_id: str, session: AsyncSession = Depends(get_session)):
    """Returns the campaign's most recent assignment (draft or approved),
    if one exists. Lets the frontend restore existing state on page
    load/revisit instead of always showing the generate/upload chooser -
    without this, refreshing the Assignment page looked like the
    assignment had vanished even though it was still there in the DB."""

    from app.api.routes_assignments import _to_response  # local import avoids a module-load-order cycle

    result = await session.execute(
        select(AssignmentORM).where(AssignmentORM.campaign_id == campaign_id).order_by(AssignmentORM.created_at.desc()).limit(1)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="No assignment exists yet for this campaign.")

    return await _to_response(session, assignment)


async def _rank_candidates_with_reports(
    session: AsyncSession, candidates: list[CandidateORM]
) -> list[SelectedCandidateResponse]:
    """Shared by /candidates/selected and /candidates/pending-approval:
    ranks a set of evaluated candidates high score to low, with
    strengths/weaknesses so HR can see WHY - not just the number.
    pending_decision on the input candidates (set only for
    pending_approval) is carried through to the response so the
    pending-approval view can show HR each candidate's computed outcome."""

    scored: list[tuple[CandidateORM, dict, bool]] = []
    for candidate in candidates:
        sub_result = await session.execute(
            select(SubmissionORM)
            .where(SubmissionORM.candidate_id == candidate.id)
            .order_by(SubmissionORM.created_at.desc())
            .limit(1)
        )
        submission = sub_result.scalar_one_or_none()
        submission_available = submission is not None
        if submission is None or submission.report is None:
            logger.warning("Candidate %s has no report - excluding from ranking", candidate.id)
            continue
        scored.append((candidate, submission.report, submission_available))

    # High score to low. Ties broken by created_at (earlier submission
    # ranks higher) so the order is always deterministic, not
    # dependent on however the DB happened to return rows.
    scored.sort(key=lambda item: (-item[1]["overall_score"], item[0].created_at))

    responses: list[SelectedCandidateResponse] = []
    for i, (candidate, report, submission_available) in enumerate(scored):
        strengths: list[str] = []
        for section in report.get("section_reports", []):
            for qr in section.get("question_reviews", []):
                for s in qr.get("strengths", []):
                    if s not in strengths:
                        strengths.append(s)
        # Weaknesses come from Issue types raised during evaluation, NOT
        # missing_topics (that field actually means "unanswered question
        # references", not "skill gaps" - a poor semantic fit here, since
        # it would miss weaknesses on questions the candidate DID answer
        # but answered poorly).
        weaknesses: list[str] = []
        for section in report.get("section_reports", []):
            for qr in section.get("question_reviews", []):
                for issue in qr.get("issues", []):
                    label = issue["type"].replace("_", " ").capitalize()
                    if label not in weaknesses and issue["type"] != "other":
                        weaknesses.append(label)

        responses.append(SelectedCandidateResponse(
            id=candidate.id, name=candidate.name, email=candidate.email,
            overall_score=report["overall_score"], hiring_recommendation=report["hiring_recommendation"],
            strengths=strengths[:5], weaknesses=weaknesses[:5],
            resume_available=bool(candidate.resume_text), submission_available=submission_available,
            report_available=True, rank=i + 1, pending_decision=candidate.pending_decision,
        ))
    return responses


@router.get("/{campaign_id}/candidates/selected", response_model=list[SelectedCandidateResponse])
async def list_selected_candidates(campaign_id: str, session: AsyncSession = Depends(get_session)) -> list[SelectedCandidateResponse]:
    """Final Selected candidates only, ranked high score to low, with
    strengths/weaknesses so HR can see WHY - not just the number.
    final_selected candidates never get a retention_deadline set (see
    confirm_import/evaluate_campaign), so their resume/submission files
    are never purged."""

    result = await session.execute(
        select(CandidateORM).where(CandidateORM.campaign_id == campaign_id, CandidateORM.status == "final_selected")
    )
    return await _rank_candidates_with_reports(session, result.scalars().all())


@router.get("/{campaign_id}/candidates/pending-approval", response_model=list[SelectedCandidateResponse])
async def list_pending_approval_candidates(campaign_id: str, session: AsyncSession = Depends(get_session)) -> list[SelectedCandidateResponse]:
    """The auto-computed threshold/top_n outcome from evaluate_campaign,
    ranked the same way as the final list, but not yet released - this is
    what HR reviews before calling POST .../evaluations/approve. Includes
    both computed selects and rejects (pending_decision distinguishes
    them) so HR sees the whole picture, not just who's about to be hired."""

    result = await session.execute(
        select(CandidateORM).where(CandidateORM.campaign_id == campaign_id, CandidateORM.status == "pending_approval")
    )
    return await _rank_candidates_with_reports(session, result.scalars().all())


@router.get("/{campaign_id}/candidates", response_model=list[CandidateResponse])
async def list_candidates(campaign_id: str, status: str | None = None, session: AsyncSession = Depends(get_session)) -> list[CandidateResponse]:
    await _mark_overdue_candidates(session, campaign_id)
    await session.commit()

    query = select(CandidateORM).where(CandidateORM.campaign_id == campaign_id)
    if status:
        query = query.where(CandidateORM.status == status)
    result = await session.execute(query)
    candidates = result.scalars().all()
    return [
        _to_candidate_response(c)
        for c in candidates
    ]


@router.get("/{campaign_id}/dashboard", response_model=CampaignDashboardResponse)
async def campaign_dashboard(campaign_id: str, session: AsyncSession = Depends(get_session)) -> CampaignDashboardResponse:
    """Pure DB-query dashboard - no LLM involved. Also drives the
    frontend's 'guided workflow' next-action indicator, so the UI doesn't
    have to re-derive campaign state logic itself."""

    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")

    await _mark_overdue_candidates(session, campaign_id)
    await session.commit()

    async def _count(*statuses: str) -> int:
        return (await session.execute(
            select(func.count()).select_from(CandidateORM).where(CandidateORM.campaign_id == campaign_id, CandidateORM.status.in_(statuses))
        )).scalar_one()

    total_resumes = (await session.execute(
        select(func.count()).select_from(CandidateORM).where(CandidateORM.campaign_id == campaign_id)
    )).scalar_one()

    # "shortlisted" is CUMULATIVE - everyone who was ever shortlisted, not
    # just those currently sitting in that exact state - stays 120 even
    # after all 120 have progressed to assignment_sent/submitted/etc.
    shortlisted = await _count("shortlisted", "assignment_sent", "submitted", "submission_overdue", "evaluated", "pending_approval", "final_selected", "final_rejected")
    not_shortlisted = await _count("not_shortlisted")
    assignment_sent = await _count("assignment_sent", "submitted", "submission_overdue", "evaluated", "pending_approval", "final_selected", "final_rejected")
    submitted = await _count("submitted", "evaluated", "pending_approval", "final_selected", "final_rejected")
    overdue = await _count("submission_overdue")
    pending_approval = await _count("pending_approval")
    final_selected = await _count("final_selected")
    final_rejected = await _count("final_rejected")

    assignment = await _latest_approved_assignment(session, campaign_id)
    deadline = _as_utc(assignment.deadline) if assignment else None
    days_remaining = (deadline - datetime.now(timezone.utc)).days if deadline else None
    ready_for_evaluation = assignment_sent > 0 and (submitted + overdue) >= assignment_sent

    next_action = _compute_next_action(
        has_candidates=total_resumes > 0, has_shortlisted=shortlisted > 0,
        has_approved_assignment=assignment is not None, ready_for_evaluation=ready_for_evaluation,
        has_pending_approval=pending_approval > 0, has_final_results=(final_selected + final_rejected) > 0,
    )

    return CampaignDashboardResponse(
        campaign_id=campaign_id, total_resumes=total_resumes,
        shortlisted_count=shortlisted, not_shortlisted_count=not_shortlisted,
        assignment_sent_count=assignment_sent, submitted_count=submitted, overdue_count=overdue,
        pending_approval_count=pending_approval,
        final_selected_count=final_selected, final_rejected_count=final_rejected,
        deadline=deadline, days_remaining=days_remaining,
        ready_for_evaluation=ready_for_evaluation, next_action=next_action,
    )


def _compute_next_action(
    has_candidates: bool, has_shortlisted: bool, has_approved_assignment: bool,
    ready_for_evaluation: bool, has_pending_approval: bool, has_final_results: bool,
) -> str:
    """Single source of truth for 'what should HR do next' - so the
    frontend just displays this string instead of re-deriving campaign
    state logic in JS."""

    if has_pending_approval:
        return "Approve & Send Results"
    if has_final_results:
        return "Review Final Results"
    if not has_candidates:
        return "Import Resumes"
    if not has_shortlisted:
        return "Confirm Import"
    if not has_approved_assignment:
        return "Approve Assignment"
    if not ready_for_evaluation:
        return "Waiting for Submissions"
    return "Evaluate Assignments"


@router.get("/{campaign_id}/timeline", response_model=list[CampaignEventResponse])
async def campaign_timeline(campaign_id: str, session: AsyncSession = Depends(get_session)) -> list[CampaignEventResponse]:
    result = await session.execute(select(CampaignEventORM).where(CampaignEventORM.campaign_id == campaign_id).order_by(CampaignEventORM.created_at))
    events = result.scalars().all()
    return [CampaignEventResponse(event_type=e.event_type, message=e.message, created_at=e.created_at) for e in events]


@router.get("/{campaign_id}/deadline-status", response_model=DeadlineStatusResponse)
async def deadline_status(campaign_id: str, session: AsyncSession = Depends(get_session)) -> DeadlineStatusResponse:
    await _mark_overdue_candidates(session, campaign_id)
    await session.commit()

    assignment = await _latest_approved_assignment(session, campaign_id)
    if assignment is None or assignment.deadline is None:
        raise HTTPException(status_code=404, detail="No approved assignment with a deadline found for this campaign.")

    sent_count = (await session.execute(
        select(func.count()).select_from(CandidateORM).where(CandidateORM.campaign_id == campaign_id, CandidateORM.status.in_(["assignment_sent", "submitted", "submission_overdue", "evaluated", "final_selected", "final_rejected"]))
    )).scalar_one()
    submitted_count = (await session.execute(
        select(func.count()).select_from(CandidateORM).where(CandidateORM.campaign_id == campaign_id, CandidateORM.status.in_(["submitted", "evaluated", "final_selected", "final_rejected"]))
    )).scalar_one()

    deadline = _as_utc(assignment.deadline)
    return DeadlineStatusResponse(
        assignment_id=assignment.id, deadline=deadline, deadline_passed=datetime.now(timezone.utc) > deadline,
        sent_count=sent_count, submitted_count=submitted_count, not_submitted_count=sent_count - submitted_count,
    )


@router.post("/{campaign_id}/evaluations", response_model=EvaluateCampaignResponse)
async def evaluate_campaign(
    campaign_id: str,
    body: EvaluateCampaignRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> EvaluateCampaignResponse:
    """The ONLY LLM-using step in this whole campaign flow - the existing,
    unchanged 3-call pipeline, once per submitted candidate.

    RESTRUCTURED into two phases so the flowchart's HR Decision Layer is
    real. Previously scoring and selection were fused: each candidate was
    graded and immediately compared against a hardcoded 6.0, which made
    "Top N" impossible to express (you cannot know the top 20 until every
    score exists) and gave HR no way to change the cutoff.

      Phase 1 - grade every submission, persist the report (+ render its
                PDF), rank by score. No accept/reject decision is made here.
      Phase 2 - apply the selected mode (threshold / top_n / manual) to
                the completed ranking. For threshold/top_n this computes
                who WOULD be selected/rejected and parks them in
                "pending_approval" - nothing is finalized and NO email is
                sent yet. HR reviews via GET .../candidates/pending-approval
                and releases the outcome (finalize + email) via
                POST .../evaluations/approve. "manual" mode is unchanged:
                candidates stay "evaluated" for per-candidate override.

    Defaults to threshold@6.0 when no body is sent.
    """

    config = body or EvaluateCampaignRequest()

    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")

    await _mark_overdue_candidates(session, campaign_id)
    await session.commit()

    result = await session.execute(select(CandidateORM).where(CandidateORM.campaign_id == campaign_id, CandidateORM.status == "submitted"))
    submitted_candidates = result.scalars().all()
    if not submitted_candidates:
        return EvaluateCampaignResponse(campaign_id=campaign_id, evaluated_count=0, pending_selected_count=0, pending_rejected_count=0, failed_count=0)

    settings = get_settings()
    use_case = get_review_use_case()
    storage = get_file_storage()
    semaphore = asyncio.Semaphore(settings.max_concurrent_llm_calls)

    # ---- Phase 1: grade everyone, decide nothing -------------------------
    async def _grade_one(candidate: CandidateORM) -> tuple[CandidateORM, float | None]:
        sub_result = await session.execute(
            select(SubmissionORM).where(SubmissionORM.candidate_id == candidate.id).order_by(SubmissionORM.created_at.desc()).limit(1)
        )
        submission = sub_result.scalar_one_or_none()
        if submission is None:
            logger.warning("Candidate %s marked submitted but no Submission row found - skipping", candidate.id)
            return candidate, None

        assignment = await session.get(AssignmentORM, submission.assignment_id)
        if assignment is None or assignment.approved_version_id is None:
            logger.warning("No approved version found for submission %s - skipping", submission.id)
            return candidate, None
        version = await session.get(AssignmentVersionORM, assignment.approved_version_id)

        async with semaphore:
            try:
                report = await use_case.execute_from_texts(version.question_paper_text, submission.submission_text)
            except ReviewerError as e:
                logger.warning("Evaluation failed for candidate %s: %s", candidate.id, e)
                return candidate, None

        # Every graded report is now persisted, selected or not. The old
        # code kept reports ONLY for selected candidates, which made
        # "Top N" and re-running selection at a different threshold
        # impossible - you would have thrown away the scores you need to
        # rank by. Rejected candidates' reports are still removed later,
        # by the retention purge, so this is a change of WHEN not WHETHER.
        submission.report = report.model_dump(mode="json")
        pdf_buffer = render_report_pdf(candidate.name or "Candidate", campaign.job_title, report)
        submission.report_storage_key = await storage.save(report_key(campaign_id, candidate.id), pdf_buffer.getvalue())
        candidate.status = "evaluated"
        return candidate, report.overall_score

    graded = await asyncio.gather(*[_grade_one(c) for c in submitted_candidates])
    await session.flush()

    scored = [(c, s) for c, s in graded if s is not None]
    failed = sum(1 for _, s in graded if s is None)

    # ---- Phase 2: apply the HR Decision Layer -----------------------------
    scored.sort(key=lambda pair: pair[1], reverse=True)

    if config.mode == "threshold":
        selected_ids = {c.id for c, score in scored if score >= config.score_threshold}
        mode_desc = f"threshold >= {config.score_threshold}"
    elif config.mode == "top_n":
        selected_ids = {c.id for c, _ in scored[: config.top_n]}
        mode_desc = f"top {config.top_n}"
    else:  # manual - grade and rank only, HR decides per candidate
        selected_ids = set()
        mode_desc = "manual (no automatic selection)"

    pending_selected = 0
    pending_rejected = 0

    for candidate, score in scored:
        if config.mode == "manual":
            # Left at "evaluated". No decision, pending or final - telling
            # someone they were rejected before a human has actually
            # looked would be both wrong and unrecoverable.
            continue

        candidate.status = "pending_approval"
        if candidate.id in selected_ids:
            candidate.pending_decision = "select"
            pending_selected += 1
        else:
            candidate.pending_decision = "reject"
            pending_rejected += 1

    await _log_event(
        session, campaign_id, "evaluation_completed",
        f"Evaluated {len(scored)} candidates using {mode_desc}: {pending_selected} pending selection, "
        f"{pending_rejected} pending rejection, {failed} failed. Awaiting HR approval before emailing outcomes."
        if config.mode != "manual" else
        f"Evaluated {len(scored)} candidates (manual mode): {failed} failed. Awaiting per-candidate HR decisions.",
    )
    await session.commit()

    logger.info(
        "Campaign %s evaluated (%s): %d graded, %d pending selection, %d pending rejection, %d failed (%d LLM calls)",
        campaign_id, mode_desc, len(scored), pending_selected, pending_rejected, failed, len(scored) * 3,
    )
    return EvaluateCampaignResponse(
        campaign_id=campaign_id, evaluated_count=len(scored),
        pending_selected_count=pending_selected, pending_rejected_count=pending_rejected, failed_count=failed,
    )


@router.post("/{campaign_id}/evaluations/approve", response_model=ApproveEvaluationResponse)
async def approve_evaluation(campaign_id: str, session: AsyncSession = Depends(get_session)) -> ApproveEvaluationResponse:
    """The HR approval gate: releases the threshold/top_n outcome computed
    by evaluate_campaign. This is the ONLY place final_selected/
    final_rejected get set for auto-evaluated candidates, and the only
    place FINAL_SELECTED/FINAL_REJECTED emails get sent for them - HR must
    call this explicitly after reviewing GET .../candidates/pending-approval
    (or hand-correcting individual candidates via
    POST .../candidates/{id}/decision, which also works on pending_approval
    candidates)."""

    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")

    result = await session.execute(
        select(CandidateORM).where(CandidateORM.campaign_id == campaign_id, CandidateORM.status == "pending_approval")
    )
    pending = result.scalars().all()
    if not pending:
        raise HTTPException(status_code=409, detail="No candidates awaiting approval for this campaign.")

    settings = get_settings()
    email_sender = get_email_sender_dep()
    final_selected = 0
    final_rejected = 0
    emails_sent = 0

    for candidate in pending:
        if candidate.pending_decision == "select":
            candidate.status = "final_selected"
            final_selected += 1
            subject, template = FINAL_SELECTED_EMAIL_SUBJECT, FINAL_SELECTED_EMAIL_BODY
        else:
            candidate.status = "final_rejected"
            candidate.retention_deadline = _retention_deadline(settings)
            final_rejected += 1
            subject, template = FINAL_REJECTED_EMAIL_SUBJECT, FINAL_REJECTED_EMAIL_BODY
        candidate.pending_decision = None

        if candidate.email:
            email_sender.send(
                to_email=candidate.email, subject=subject,
                body=template.format(candidate_name=candidate.name or "Candidate", job_title=campaign.job_title),
            )
            emails_sent += 1

    await _log_event(
        session, campaign_id, "evaluation_approved",
        f"HR approved the evaluation outcome: {final_selected} selected, {final_rejected} rejected, {emails_sent} emails sent.",
    )
    await session.commit()

    logger.info("Campaign %s evaluation approved: %d selected, %d rejected, %d emails sent", campaign_id, final_selected, final_rejected, emails_sent)
    return ApproveEvaluationResponse(
        campaign_id=campaign_id, final_selected_count=final_selected, final_rejected_count=final_rejected, emails_sent=emails_sent,
    )


@router.post("/{campaign_id}/candidates/{candidate_id}/decision", response_model=CandidateDecisionResponse)
async def override_candidate_decision(
    campaign_id: str,
    candidate_id: str,
    body: CandidateDecisionRequest,
    session: AsyncSession = Depends(get_session),
) -> CandidateDecisionResponse:
    """Manual override - the third mode of the HR Decision Layer, and the
    escape hatch for the other two. A recruiter can select or reject any
    evaluated candidate regardless of what the automatic layer decided.

    Every override is written to the campaign timeline with its reason,
    so a human reversing the machine is always visible in the audit
    trail rather than looking like the model's own output.
    """

    candidate = await session.get(CandidateORM, candidate_id)
    if candidate is None or candidate.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found in this campaign.")

    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")

    if candidate.status not in ("evaluated", "pending_approval", "final_selected", "final_rejected"):
        raise HTTPException(
            status_code=409,
            detail=f"Candidate is '{candidate.status}' - only evaluated candidates can be selected or rejected.",
        )

    previous = candidate.status
    settings = get_settings()
    email_sender = get_email_sender_dep()
    # Hand-deciding one candidate out of a batch takes it out of the
    # pending-approval pool - the batch approve endpoint only sees
    # candidates that still have a pending_decision.
    candidate.pending_decision = None

    if body.decision == "select":
        candidate.status = "final_selected"
        # Reversing an earlier rejection must also stop the retention
        # clock, or a manually-rescued candidate's files get purged.
        candidate.retention_deadline = None
        subject, template = FINAL_SELECTED_EMAIL_SUBJECT, FINAL_SELECTED_EMAIL_BODY
    else:
        candidate.status = "final_rejected"
        candidate.retention_deadline = _retention_deadline(settings)
        subject, template = FINAL_REJECTED_EMAIL_SUBJECT, FINAL_REJECTED_EMAIL_BODY

    # Only email when the outcome actually CHANGED - re-confirming an
    # existing decision must not re-send a rejection to someone who
    # already got one.
    outcome_changed = previous != candidate.status
    if outcome_changed and candidate.email:
        email_sender.send(
            to_email=candidate.email, subject=subject,
            body=template.format(candidate_name=candidate.name or "Candidate", job_title=campaign.job_title),
        )

    reason = f" Reason: {body.reason}" if body.reason else ""
    await _log_event(
        session, campaign_id, "manual_override",
        f"HR manually {body.decision}ed {candidate.name or candidate.id} (was '{previous}').{reason}"[:500],
    )
    await session.commit()

    logger.info("Manual override on candidate %s: %s -> %s", candidate_id, previous, candidate.status)
    return CandidateDecisionResponse(candidate_id=candidate.id, status=candidate.status, overridden=outcome_changed)
