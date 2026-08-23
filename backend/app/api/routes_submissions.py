"""
Candidate-facing endpoints. Access is via `submission_token` (mailed to
the candidate) instead of a full login system.
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import SubmissionSubmitResponse, SubmissionViewResponse
from app.api.routes_campaigns import _mark_overdue_candidates, _maybe_log_ready_for_evaluation
from app.core.exceptions import DocumentParsingError
from app.core.logging import get_logger
from app.infrastructure.db.database import get_session
from app.infrastructure.db.models import AssignmentORM, AssignmentVersionORM, CampaignORM, CandidateORM, SubmissionORM
from app.infrastructure.parsers.document_factory import get_parser_for
from app.infrastructure.storage.factory import get_file_storage
from app.infrastructure.storage.keys import submission_key
from app.utils.archive import extract_text_from_zip

router = APIRouter(prefix="/api/v1/submissions", tags=["submissions"])
logger = get_logger(__name__)

# .zip added: the spec's submission portal explicitly accepts ZIP project
# submissions, which this endpoint previously rejected outright.
_ALLOWED_SUFFIXES = {".docx", ".pdf", ".zip"}


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


async def _get_candidate_by_token(session: AsyncSession, token: str) -> CandidateORM:
    result = await session.execute(select(CandidateORM).where(CandidateORM.submission_token == token))
    candidate = result.scalar_one_or_none()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Invalid or expired submission link.")
    return candidate


async def _get_assignment_for_candidate(session: AsyncSession, candidate: CandidateORM) -> AssignmentORM:
    result = await session.execute(
        select(AssignmentORM).where(AssignmentORM.campaign_id == candidate.campaign_id, AssignmentORM.status == "approved").order_by(AssignmentORM.created_at.desc()).limit(1)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        raise HTTPException(status_code=404, detail="No approved assignment found for this candidate.")
    return assignment


async def _latest_submission(session: AsyncSession, candidate_id: str) -> SubmissionORM | None:
    result = await session.execute(select(SubmissionORM).where(SubmissionORM.candidate_id == candidate_id).order_by(SubmissionORM.created_at.desc()).limit(1))
    return result.scalar_one_or_none()


def _portal_status(candidate_status: str) -> str:
    if candidate_status in ("evaluated", "final_selected", "final_rejected"):
        return "evaluated"
    if candidate_status == "submitted":
        return "waiting_for_evaluation"
    if candidate_status == "submission_overdue":
        return "overdue"
    return "not_submitted"


@router.get("/{token}", response_model=SubmissionViewResponse)
async def view_assignment(token: str, session: AsyncSession = Depends(get_session)) -> SubmissionViewResponse:
    """Candidate portal landing page - 'Welcome {name}', campaign, assignment,
    deadline, and current status."""

    candidate = await _get_candidate_by_token(session, token)
    if candidate.campaign_id:
        await _mark_overdue_candidates(session, candidate.campaign_id)
        await session.commit()
        await session.refresh(candidate)

    assignment = await _get_assignment_for_candidate(session, candidate)
    campaign = await session.get(CampaignORM, candidate.campaign_id)
    version = await session.get(AssignmentVersionORM, assignment.approved_version_id)
    submission = await _latest_submission(session, candidate.id)

    from app.api.routes_assignments import candidate_assignment_link  # local import avoids a module-load-order cycle

    assignment_link, assignment_is_drive_link = candidate_assignment_link(version, token)

    return SubmissionViewResponse(
        candidate_name=candidate.name,
        campaign_name=campaign.job_title if campaign else "",
        assignment_title=assignment.title,
        question_paper_text=version.question_paper_text,
        deadline=_as_utc(assignment.deadline),
        status=_portal_status(candidate.status),
        submitted_on=_as_utc(submission.created_at) if submission else None,
        assignment_link=assignment_link,
        assignment_is_drive_link=assignment_is_drive_link,
    )


@router.get("/{token}/assignment")
async def download_candidate_assignment(token: str, session: AsyncSession = Depends(get_session)):
    """Token-gated equivalent of the HR-only /api/v1/assignments/{id}/download
    route - what the candidate portal's "Download Assignment" button and
    the assignment email's link actually point to when HR didn't provide
    a Google Drive link. Redirects to the Drive link instead when one is
    set, so this single URL always works as "the assignment link"."""

    candidate = await _get_candidate_by_token(session, token)
    assignment = await _get_assignment_for_candidate(session, candidate)
    version = await session.get(AssignmentVersionORM, assignment.approved_version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Assignment has no approved version.")

    if version.google_drive_link:
        return RedirectResponse(version.google_drive_link)

    from app.api.routes_assignments import _render_docx  # local import avoids a module-load-order cycle

    buffer = _render_docx(assignment.title, version.question_paper_text)
    filename = f"{assignment.title.replace(' ', '_')}.docx"
    return StreamingResponse(buffer, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/{token}", response_model=SubmissionSubmitResponse)
async def submit_assignment(token: str, solution: UploadFile = File(..., description="Candidate's solution file (.docx/.pdf)"), session: AsyncSession = Depends(get_session)) -> SubmissionSubmitResponse:
    """Candidate uploads their solution. No LLM call here - evaluation
    only happens when HR explicitly triggers /campaigns/{id}/evaluate."""

    candidate = await _get_candidate_by_token(session, token)
    assignment = await _get_assignment_for_candidate(session, candidate)

    # One submission per candidate - once a solution is on file, the
    # portal (and this endpoint) must not accept another, even if the
    # candidate replays the upload request directly.
    if await _latest_submission(session, candidate.id) is not None:
        raise HTTPException(status_code=409, detail="You have already submitted a solution for this assignment. Resubmission is not allowed.")

    suffix = "." + solution.filename.rsplit(".", 1)[-1].lower() if solution.filename and "." in solution.filename else ""
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '{suffix}'. Allowed: .docx, .pdf")

    content = await solution.read()

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = f"{tmp_dir}/{solution.filename}"
        with open(path, "wb") as f:
            f.write(content)
        try:
            if suffix == ".zip":
                # ZIP project submissions: concatenate the readable
                # source/doc files inside so the evaluator has text to
                # grade, rather than failing on an unparseable binary.
                submission_text = await extract_text_from_zip(path)
            else:
                submission_text = await get_parser_for(path).extract_text(path)
        except DocumentParsingError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

    if not submission_text.strip():
        raise HTTPException(status_code=422, detail="No readable text could be extracted from the submitted file.")

    submission = SubmissionORM(candidate_id=candidate.id, assignment_id=assignment.id, submission_text=submission_text)
    session.add(submission)
    candidate.status = "submitted"
    await session.flush()

    # Persist the ORIGINAL uploaded file - previously parsed to text and
    # discarded, so HR's "Download Submission" and the final campaign
    # archive had nothing to serve.
    storage = get_file_storage()
    key = submission_key(candidate.campaign_id, candidate.id, solution.filename)
    submission.submission_storage_key = await storage.save(key, content)

    if candidate.campaign_id:
        await _maybe_log_ready_for_evaluation(session, candidate.campaign_id)

    await session.commit()
    await session.refresh(submission)

    logger.info("Candidate %s submitted assignment %s (0 LLM calls)", candidate.id, assignment.id)
    return SubmissionSubmitResponse(candidate_id=candidate.id, assignment_id=assignment.id, status=candidate.status, submitted_on=_as_utc(submission.created_at))
