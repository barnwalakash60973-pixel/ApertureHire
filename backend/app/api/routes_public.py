"""
PUBLIC, unauthenticated candidate-facing endpoints - the "Share
Application Link -> Candidates Apply" half of the flowchart, which had
no implementation at all before this: the only intake path was HR
bulk-uploading resumes they had already collected elsewhere
(/campaigns/{id}/resumes/import).

The two endpoints here are what a LinkedIn/Naukri/Unstop/careers-page
link actually points at:
  GET  /api/v1/public/campaigns/{id}  - the job info the form renders
  POST /api/v1/public/campaigns/{id}/apply - the application itself

Deliberately NOT behind get_current_user (see main.py): applicants have
no HR account. That makes this the app's only unauthenticated write
endpoint reachable by anyone with a link, so the abuse surface is
treated explicitly rather than assumed away - see the notes on the POST
handler for what IS and (honestly) IS NOT defended against.
"""

from __future__ import annotations

import tempfile

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import CandidateApplicationRequest, CandidateApplicationResponse, PublicCampaignResponse
from app.core.config import get_settings
from app.core.container import get_resume_matcher
from app.core.exceptions import DocumentParsingError, UnsupportedFileTypeError
from app.core.logging import get_logger
from app.infrastructure.db.database import get_session
from app.infrastructure.db.models import CampaignEventORM, CampaignORM, CandidateORM
from app.infrastructure.parsers.document_factory import get_parser_for
from app.infrastructure.storage.factory import get_file_storage
from app.infrastructure.storage.keys import resume_key

router = APIRouter(prefix="/api/v1/public", tags=["public"])
logger = get_logger(__name__)

_ALLOWED_SUFFIXES = {".docx", ".pdf"}

# Cheap per-campaign flood ceiling. This is NOT real abuse protection -
# it's a blunt cap so a single open link can't grow a campaign
# unboundedly. Real protection is IP/email rate limiting at the edge
# (nginx/Cloudflare/slowapi) plus a CAPTCHA on the form; neither is
# built here, and neither can be meaningfully tested in this
# environment. Documented as a known gap, not silently omitted.
_MAX_APPLICATIONS_PER_CAMPAIGN = 10_000


@router.get("/campaigns/{campaign_id}", response_model=PublicCampaignResponse)
async def get_public_campaign(campaign_id: str, session: AsyncSession = Depends(get_session)) -> PublicCampaignResponse:
    """What the public application form renders its header from. Returns
    ONLY the job title/description - never candidate counts, screening
    thresholds, or anything else internal, since this is world-readable
    to anyone holding the link."""

    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="This job posting was not found.")
    if campaign.status != "active":
        raise HTTPException(status_code=410, detail="This job posting is no longer accepting applications.")

    return PublicCampaignResponse(
        campaign_id=campaign.id,
        name=campaign.name,
        job_title=campaign.job_title,
        job_description_text=campaign.job_description_text,
    )


@router.post("/campaigns/{campaign_id}/apply", response_model=CandidateApplicationResponse)
async def apply_to_campaign(
    campaign_id: str,
    full_name: str = Form(...),
    email: str = Form(...),
    phone_number: str = Form(...),
    degree: str = Form(...),
    cgpa: str = Form(...),
    college: str = Form(...),
    graduation_year: int = Form(...),
    skills: str | None = Form(default=None),
    github_url: str | None = Form(default=None),
    portfolio_url: str | None = Form(default=None),
    linkedin_url: str | None = Form(default=None),
    resume: UploadFile = File(..., description="Resume as .pdf or .docx"),
    session: AsyncSession = Depends(get_session),
) -> CandidateApplicationResponse:
    """A candidate applying via the shared link.

    Fields are taken as multipart Form data (not JSON) because the resume
    file rides along in the same request - one submit, not an upload
    step plus a metadata step.

    The structured fields are the point: previously name/email were
    regex-GUESSED out of resume text (contact_extractor), which silently
    produced "Not Found" rows that HR had to hand-correct. When the
    candidate types them, they are authoritative and the guessing never
    runs.

    Screening runs immediately (rule-based, 0 LLM, same matcher as bulk
    import) so HR sees a match score without a separate step, but the
    candidate is created as `pending_review` exactly like an imported
    one - the applicant is NOT auto-rejected by a regex at submit time,
    and no shortlist/rejection email fires here. HR still confirms the
    batch (/campaigns/{id}/resumes/confirm), which is where decisions and
    emails happen. Keeping one decision point matters: an
    auto-rejection triggered by an unauthenticated request would be
    unreviewable and, at scale, exactly the failure mode that gets
    hiring tools written about.
    """

    campaign = await session.get(CampaignORM, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="This job posting was not found.")
    if campaign.status != "active":
        raise HTTPException(status_code=410, detail="This job posting is no longer accepting applications.")

    # Validate the typed fields through the Pydantic model so the Form
    # path enforces the same constraints (lengths, year range) as the
    # documented schema, instead of two divergent sets of rules.
    try:
        application = CandidateApplicationRequest(
            full_name=full_name, email=email, phone_number=phone_number,
            degree=degree, cgpa=cgpa, college=college, graduation_year=graduation_year,
            skills=skills, github_url=github_url, portfolio_url=portfolio_url, linkedin_url=linkedin_url,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from e

    application_count = (await session.execute(
        select(func.count()).select_from(CandidateORM).where(CandidateORM.campaign_id == campaign_id)
    )).scalar_one()
    if application_count >= _MAX_APPLICATIONS_PER_CAMPAIGN:
        raise HTTPException(status_code=429, detail="This job posting is not accepting further applications right now.")

    # One application per email per campaign. Prevents both accidental
    # double-submits and the trivial "apply 500 times" case; does not
    # stop someone using 500 different addresses (see the rate-limiting
    # note at the top of this module).
    existing = (await session.execute(
        select(CandidateORM).where(
            CandidateORM.campaign_id == campaign_id,
            func.lower(CandidateORM.email) == application.email.lower(),
        )
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="An application with this email already exists for this job posting.")

    suffix = "." + resume.filename.rsplit(".", 1)[-1].lower() if resume.filename and "." in resume.filename else ""
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '{suffix}'. Please upload a .pdf or .docx resume.")

    settings = get_settings()
    content = await resume.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Resume exceeds the {settings.max_upload_mb} MB limit.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        path = f"{tmp_dir}/{resume.filename}"
        with open(path, "wb") as f:
            f.write(content)
        try:
            resume_text = await get_parser_for(path).extract_text(path)
        except (DocumentParsingError, UnsupportedFileTypeError) as e:
            raise HTTPException(status_code=422, detail=f"Could not read your resume file: {e}") from e

    if not resume_text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from your resume. If it is a scanned image, please upload a text-based PDF or DOCX.")

    match_result = get_resume_matcher().match(campaign.job_description_text, resume_text)

    candidate = CandidateORM(
        campaign_id=campaign_id,
        name=application.full_name,
        email=application.email,
        phone=application.phone_number,
        degree=application.degree,
        cgpa=application.cgpa,
        college=application.college,
        graduation_year=application.graduation_year,
        skills=application.skills,
        github_url=application.github_url,
        portfolio_url=application.portfolio_url,
        linkedin_url=application.linkedin_url,
        resume_text=resume_text,
        match_result=match_result.model_dump(mode="json"),
        status="pending_review",
        application_source="public_form",
    )
    session.add(candidate)
    await session.flush()  # need candidate.id to build the storage key

    storage = get_file_storage()
    candidate.resume_storage_key = await storage.save(
        resume_key(campaign_id, candidate.id, resume.filename), content
    )

    session.add(CampaignEventORM(
        campaign_id=campaign_id,
        event_type="application_received",
        message=f"Application received from {application.full_name} via the public form.",
    ))
    await session.commit()

    logger.info("Public application received for campaign %s (candidate %s, 0 LLM calls)", campaign_id, candidate.id)
    return CandidateApplicationResponse(
        candidate_id=candidate.id,
        campaign_id=campaign_id,
        message="Your application has been received. You will hear from us by email.",
    )
