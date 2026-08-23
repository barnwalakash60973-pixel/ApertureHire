"""
Application-layer interfaces (ports), following the Dependency Inversion
Principle: use cases depend on these abstractions, and infrastructure
provides concrete implementations. This is what lets us swap
docx/PyMuPDF parsers or OpenAI/Azure OpenAI without touching use-case code.

Pipeline is EXACTLY 3 LLM calls per assignment, always:
  1. QuestionExtractor.extract - whole question paper -> all questions
  2. AnswerMatcher.match       - whole submission -> all answers
  3. AnswerEvaluator.evaluate  - all question/answer pairs -> all reviews

There is no per-section or per-question call anywhere in this contract, and
no batching fallback. Oversized documents are truncated by the
implementation (see Settings.max_chars_*), not split into more calls.
"""

from __future__ import annotations

from typing import Protocol

from app.domain.models import Answer, Question, QuestionReview, ResumeMatchResult


class DocumentParser(Protocol):
    """Extracts raw text from a document file on disk."""

    async def extract_text(self, file_path: str) -> str:
        """Return the full plain-text content of the document."""
        ...


class QuestionExtractor(Protocol):
    """Parses every question out of the COMPLETE question-paper text in a
    single LLM call (Call 1 of 3)."""

    async def extract(self, document_text: str) -> list[Question]:
        ...


class AnswerMatcher(Protocol):
    """Matches the COMPLETE submission text to ALL questions in a single
    LLM call (Call 2 of 3)."""

    async def match(self, questions: list[Question], submission_text: str) -> list[Answer]:
        ...


class AnswerEvaluator(Protocol):
    """Scores every question/answer pair in the assignment in a single LLM
    call (Call 3 of 3)."""

    async def evaluate(self, questions: list[Question], answers: list[Answer]) -> list[QuestionReview]:
        ...


class AssignmentGenerator(Protocol):
    """Generates a formatted question-paper TEXT from an HR brief AND the
    job description in a single LLM call. Output is plain text in the
    same format an HR-uploaded question paper would be, so it flows
    unchanged into QuestionExtractor - no special-casing downstream."""

    async def generate(
        self, brief: str, job_description_text: str, num_questions: int, num_sections: int, difficulty: str
    ) -> str:
        ...


class ResumeMatcher(Protocol):
    """Rule-based (NO LLM) JD<->resume comparator, safe for bulk scale.
    This is the ONLY resume-selection mechanism in the app - there is no
    LLM-based resume screener."""

    def match(self, jd_text: str, resume_text: str) -> ResumeMatchResult:
        ...
