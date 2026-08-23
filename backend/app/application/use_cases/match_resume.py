"""
MatchResumeUseCase: parses the JD (file or raw text) and resume, then runs
the rule-based (NO LLM) matcher. Safe to call at bulk scale - zero network
calls, purely local computation after text extraction.
"""

from __future__ import annotations

from app.application.interfaces import ResumeMatcher
from app.core.exceptions import DocumentParsingError
from app.core.logging import get_logger
from app.domain.models import ResumeMatchResult

logger = get_logger(__name__)


class MatchResumeUseCase:
    """Runs the rule-based JD<->resume match for one candidate."""

    def __init__(
        self,
        get_parser_for,  # Callable[[str], DocumentParser]
        resume_matcher: ResumeMatcher,
    ) -> None:
        self._get_parser_for = get_parser_for
        self._resume_matcher = resume_matcher

    async def execute(
        self,
        resume_path: str,
        job_description_path: str | None = None,
        job_description_text: str | None = None,
    ) -> ResumeMatchResult:
        resume_text = await self._get_parser_for(resume_path).extract_text(resume_path)
        if not resume_text.strip():
            raise DocumentParsingError("Resume contains no extractable text.")

        jd_text = job_description_text or ""
        if job_description_path:
            jd_text = await self._get_parser_for(job_description_path).extract_text(job_description_path)

        if not jd_text.strip():
            raise DocumentParsingError(
                "No job description provided - rule-based matching requires a JD to compare against "
                "(unlike Phase 1's LLM screener, which can assess general resume quality without one)."
            )

        result = self._resume_matcher.match(jd_text, resume_text)
        logger.info("Resume matched (0 LLM calls): %s", result.decision.value)
        return result
