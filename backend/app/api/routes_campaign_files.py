"""
Campaign FILE endpoints (download resume/submission/report) and DATA
RETENTION endpoints (manual purge, archive).

Split out of routes_campaigns.py, which had grown past 800 lines owning
campaign CRUD, resume import, candidate editing, dashboard aggregation,
timeline, deadline status, evaluation triggering AND all of this - too
many responsibilities for one module in a codebase that is otherwise
carefully layered. These two concerns (serving stored bytes, deleting
stored bytes) belong together and share nothing with campaign
orchestration except the campaign/candidate lookup.

Same prefix and same JWT guard as routes_campaigns - splitting the
module does not change a single URL, so the frontend is unaffected.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import CampaignResponse, PurgeResponse
from app.api.routes_campaigns import _campaign_counts, _log_event
from app.core.logging import get_logger
from app.infrastructure.db.database import get_session
from app.infrastructure.db.models import CampaignORM, CandidateORM, SubmissionORM
from app.infrastructure.storage.factory import get_file_storage

router = APIRouter(prefix="/api/v1/campaigns", tags=["campaign-files"])
logger = get_logger(__name__)

# --------------------------------------------------------------------------
# File downloads. These are what makes the HR dashboard's "Download Resume" /
# "Download Submission" / "View Evaluation Report" actions real - before the
# storage layer existed, uploaded bytes were parsed to text and thrown away,
# so there was nothing on disk or in S3 to serve.
#
# Bytes are streamed through the API rather than handing out a raw storage
# path/URL, so (a) the local and S3 backends behave identically to the
# frontend, and (b) access stays behind the router's JWT dependency instead
# of a public object URL. For S3 at real scale you'd switch to a presigned
# URL redirect (S3FileStorage.get_url already returns one) to keep large
# files off the API process - not done here because it can't be tested
# without a live bucket.
# --------------------------------------------------------------------------


async def _stream_stored_file(key: str | None, filename: str, media_type: str) -> Response:
    if not key:
        raise HTTPException(status_code=404, detail="No file is stored for this record.")

    storage = get_file_storage()
    if not await storage.exists(key):
        # Most likely cause: the retention job already purged it.
        raise HTTPException(status_code=410, detail="This file is no longer available (it may have passed its retention period).")

    content = await storage.read(key)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _media_type_for(key: str) -> str:
    if key.endswith(".pdf"):
        return "application/pdf"
    if key.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if key.endswith(".zip"):
        return "application/zip"
    return "application/octet-stream"


@router.get("/{campaign_id}/candidates/{candidate_id}/resume")
async def download_resume(campaign_id: str, candidate_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    candidate = await session.get(CandidateORM, candidate_id)
    if candidate is None or candidate.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found in this campaign.")

    key = candidate.resume_storage_key
    if key is None and candidate.retention_purged:
        # Distinguish "deliberately purged under the retention policy"
        # (410 Gone) from "we never had one" (404) - HR seeing a bare 404
        # here would look like a bug rather than the policy working.
        raise HTTPException(status_code=410, detail="This resume was deleted under the data retention policy.")
    ext = key.rsplit(".", 1)[-1] if key and "." in key else "pdf"
    safe_name = (candidate.name or "candidate").replace(" ", "_")
    return await _stream_stored_file(key, f"{safe_name}_resume.{ext}", _media_type_for(key or ""))


@router.get("/{campaign_id}/candidates/{candidate_id}/submission")
async def download_submission(campaign_id: str, candidate_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    candidate = await session.get(CandidateORM, candidate_id)
    if candidate is None or candidate.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found in this campaign.")

    submission = (await session.execute(
        select(SubmissionORM).where(SubmissionORM.candidate_id == candidate_id).order_by(SubmissionORM.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="This candidate has not submitted an assignment.")

    key = submission.submission_storage_key
    ext = key.rsplit(".", 1)[-1] if key and "." in key else "pdf"
    safe_name = (candidate.name or "candidate").replace(" ", "_")
    return await _stream_stored_file(key, f"{safe_name}_submission.{ext}", _media_type_for(key or ""))


@router.get("/{campaign_id}/candidates/{candidate_id}/report")
async def get_evaluation_report(campaign_id: str, candidate_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    """The stored FinalReport as JSON. Served from the DB column rather
    than storage - it's structured data the frontend renders, not a file
    the browser downloads."""

    candidate = await session.get(CandidateORM, candidate_id)
    if candidate is None or candidate.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found in this campaign.")

    submission = (await session.execute(
        select(SubmissionORM).where(SubmissionORM.candidate_id == candidate_id).order_by(SubmissionORM.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if submission is None or submission.report is None:
        raise HTTPException(status_code=404, detail="No evaluation report exists for this candidate.")

    return submission.report


@router.get("/{campaign_id}/candidates/{candidate_id}/report/download")
async def download_evaluation_report(campaign_id: str, candidate_id: str, session: AsyncSession = Depends(get_session)) -> Response:
    """The rendered report.pdf (see services/review/report_pdf.py) -
    unlike the JSON route above, this is the actual downloadable file
    alongside the resume/submission, not data for on-screen rendering."""

    candidate = await session.get(CandidateORM, candidate_id)
    if candidate is None or candidate.campaign_id != campaign_id:
        raise HTTPException(status_code=404, detail=f"Candidate '{candidate_id}' not found in this campaign.")

    submission = (await session.execute(
        select(SubmissionORM).where(SubmissionORM.candidate_id == candidate_id).order_by(SubmissionORM.created_at.desc()).limit(1)
    )).scalar_one_or_none()
    if submission is None:
        raise HTTPException(status_code=404, detail="No evaluation report exists for this candidate.")

    safe_name = (candidate.name or "candidate").replace(" ", "_")
    return await _stream_stored_file(submission.report_storage_key, f"{safe_name}_report.pdf", "application/pdf")


# --------------------------------------------------------------------------
# Retention / manual cleanup. The spec's "Campaign Completion" step lets HR
# delete non-selected candidates, rejected resumes and evaluation records
# while KEEPING selected candidates and audit summaries. Nothing implemented
# any of this previously - data was retained forever.
# --------------------------------------------------------------------------


@router.post("/{campaign_id}/purge-rejected", response_model=PurgeResponse)
async def purge_rejected_candidates(campaign_id: str, session: AsyncSession = Depends(get_session)) -> PurgeResponse:
    """HR-triggered immediate purge, the manual counterpart to the
    scheduled retention job (core/scheduler.py). Same semantics: delete
    the stored resume file and blank the extracted text for every
    not_shortlisted / final_rejected candidate, but KEEP the row so
    campaign counts and the audit trail stay accurate. final_selected
    candidates are never touched."""

    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")

    candidates = (await session.execute(
        select(CandidateORM).where(
            CandidateORM.campaign_id == campaign_id,
            CandidateORM.status.in_(["not_shortlisted", "final_rejected"]),
            CandidateORM.retention_purged.is_(False),
        )
    )).scalars().all()

    storage = get_file_storage()
    purged = 0
    for candidate in candidates:
        if candidate.resume_storage_key:
            try:
                await storage.delete(candidate.resume_storage_key)
            except Exception:
                logger.exception("Failed to delete stored resume for candidate %s", candidate.id)
        candidate.resume_text = ""
        candidate.resume_storage_key = None
        candidate.retention_purged = True
        purged += 1

    await _log_event(session, campaign_id, "rejected_candidates_purged", f"{purged} rejected candidates' resume data purged by HR.")
    await session.commit()

    logger.info("Manual purge for campaign %s: %d rejected candidates cleared", campaign_id, purged)
    return PurgeResponse(campaign_id=campaign_id, purged_count=purged)


@router.post("/{campaign_id}/archive", response_model=CampaignResponse)
async def archive_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> CampaignResponse:
    """Marks a campaign closed. Closing stops the public application
    endpoint from accepting new applicants (routes_public.py checks
    status) but deletes nothing - purging is a separate, explicit
    action so 'archive' can never be a surprise data-loss button."""

    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found.")

    campaign.status = "closed"
    await _log_event(session, campaign_id, "campaign_archived", f"Campaign '{campaign.name}' archived.")
    await session.commit()

    total, shortlisted, not_shortlisted = await _campaign_counts(session, campaign_id)
    return CampaignResponse(
        id=campaign.id, name=campaign.name, job_title=campaign.job_title, status=campaign.status,
        created_at=campaign.created_at, candidate_count=total, shortlisted_count=shortlisted, not_shortlisted_count=not_shortlisted,
    )
