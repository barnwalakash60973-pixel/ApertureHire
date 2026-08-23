"""
API routes. Thin layer: validates uploads, saves them to a temp dir,
delegates to the use case, maps exceptions to HTTP responses, cleans up.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form

from app.api.schemas import (
    AssignmentGenerationRequest,
    AssignmentGenerationResponse,
    ResumeMatchResponse,
    ReviewResponse,
)
from app.application.use_cases.generate_assignment import GenerateAssignmentUseCase
from app.application.use_cases.match_resume import MatchResumeUseCase
from app.application.use_cases.review_submission import ReviewSubmissionUseCase
from app.core.config import Settings, get_settings
from app.core.container import (
    get_generate_assignment_use_case,
    get_match_resume_use_case,
    get_review_use_case,
)
from app.core.exceptions import (
    DocumentParsingError,
    LLMEvaluationError,
    QuestionMatchError,
    ReviewerError,
    SectionSplitError,
    UnsupportedFileTypeError,
)
from app.core.logging import get_logger

router = APIRouter(prefix="/api/v1", tags=["review"])
logger = get_logger(__name__)

_ALLOWED_SUFFIXES = {".docx", ".pdf"}


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/assignment/generate", response_model=AssignmentGenerationResponse)
async def generate_assignment(
    body: AssignmentGenerationRequest,
    use_case: GenerateAssignmentUseCase = Depends(get_generate_assignment_use_case),
) -> AssignmentGenerationResponse:
    """Generates a question-paper TEXT from an HR brief. Exactly 1 LLM
    call. Output is plain text in the same shape an HR-uploaded question
    paper would be - HR reviews/edits it, then it flows unchanged into the
    normal 3-call review pipeline like any other assignment."""

    try:
        question_paper_text = await use_case.execute(
            brief=body.brief,
            num_questions=body.num_questions,
            num_sections=body.num_sections,
            difficulty=body.difficulty,
        )
    except LLMEvaluationError as e:
        raise HTTPException(status_code=502, detail=f"Assignment generation failed: {e}") from e
    except ReviewerError as e:
        logger.exception("Unhandled reviewer error")
        raise HTTPException(status_code=500, detail=str(e)) from e

    return AssignmentGenerationResponse(question_paper_text=question_paper_text)


@router.post("/resume/match", response_model=ResumeMatchResponse)
async def match_resume(
    resume: UploadFile = File(..., description="Candidate's resume (.docx/.pdf)"),
    job_description: UploadFile | None = File(
        default=None, description="Job description file (.docx/.pdf) - required unless job_description_text is given"
    ),
    job_description_text: str | None = Form(
        default=None, description="Job description as plain text, if no file is uploaded"
    ),
    use_case: MatchResumeUseCase = Depends(get_match_resume_use_case),
) -> ResumeMatchResponse:
    """Rule-based (ZERO LLM calls) JD<->resume matcher, safe for bulk scale
    (100-100,000 resumes). This is the ONLY resume-selection mechanism in
    the app - a job description is REQUIRED, since rule-based matching has
    nothing to compare against without one."""

    settings = get_settings()
    _validate_upload(resume, settings)
    if job_description is not None:
        _validate_upload(job_description, settings)

    with tempfile.TemporaryDirectory() as tmp_dir:
        resume_path = await _save_upload(resume, tmp_dir, "resume")
        jd_path = await _save_upload(job_description, tmp_dir, "job_description") if job_description else None

        try:
            match = await use_case.execute(
                resume_path=resume_path,
                job_description_path=jd_path,
                job_description_text=job_description_text,
            )
        except UnsupportedFileTypeError as e:
            raise HTTPException(status_code=415, detail=str(e)) from e
        except DocumentParsingError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except ReviewerError as e:
            logger.exception("Unhandled reviewer error")
            raise HTTPException(status_code=500, detail=str(e)) from e

    return ResumeMatchResponse(match=match)


@router.post("/review", response_model=ReviewResponse)
async def review_submission(
    question_paper: UploadFile = File(..., description="Original assignment question paper (.docx/.pdf)"),
    submission: UploadFile = File(..., description="Candidate's completed submission (.docx/.pdf)"),
    
    use_case: ReviewSubmissionUseCase = Depends(get_review_use_case),
) -> ReviewResponse:
    settings = get_settings()

    _validate_upload(question_paper, settings)
    _validate_upload(submission, settings)

    with tempfile.TemporaryDirectory() as tmp_dir:
        question_paper_path = await _save_upload(question_paper, tmp_dir, "question_paper")
        submission_path = await _save_upload(submission, tmp_dir, "submission")

        try:
            report = await use_case.execute(question_paper_path, submission_path)
        except UnsupportedFileTypeError as e:
            raise HTTPException(status_code=415, detail=str(e)) from e
        except DocumentParsingError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except SectionSplitError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except QuestionMatchError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
        except LLMEvaluationError as e:
            raise HTTPException(status_code=502, detail=f"LLM evaluation failed: {e}") from e
        except ReviewerError as e:
            logger.exception("Unhandled reviewer error")
            raise HTTPException(status_code=500, detail=str(e)) from e

    return ReviewResponse(report=report)


def _validate_upload(file: UploadFile, settings: Settings) -> None:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415, detail=f"Unsupported file type '{suffix}'. Use .docx or .pdf."
        )


async def _save_upload(file: UploadFile, tmp_dir: str, label: str) -> str:
    suffix = Path(file.filename or "").suffix.lower()
    dest_path = str(Path(tmp_dir) / f"{label}{suffix}")
    contents = await file.read()
    Path(dest_path).write_bytes(contents)
    return dest_path
