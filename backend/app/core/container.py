"""
Lightweight dependency-injection wiring for FastAPI.

We use plain factory functions + FastAPI's Depends() rather than a heavy
DI framework - it's explicit, type-checked, and easy to override in tests
(FastAPI's dependency_overrides). Each factory is cached where the
underlying object is safe to share across requests (chat model, settings)
and created fresh per request otherwise (the use case itself, since it
holds no per-request state but keeps wiring simple to reason about).

Pipeline is EXACTLY 3 LLM calls per assignment - see
app/application/use_cases/review_submission.py.

Resume selection is 100% RULE-BASED (see resume_matcher.py) - ZERO LLM
calls, deliberately, so it's safe to run at bulk scale (100-100,000
resumes). There is no LLM-based resume screener in this codebase anymore.
"""

from __future__ import annotations

from functools import lru_cache

from app.application.use_cases.generate_assignment import GenerateAssignmentUseCase
from app.application.use_cases.match_resume import MatchResumeUseCase
from app.application.use_cases.review_submission import ReviewSubmissionUseCase
from app.core.config import Settings, get_settings
from app.infrastructure.email.email_sender import EmailSender, get_email_sender
from app.infrastructure.llm.answer_evaluator import LLMAnswerEvaluator
from app.infrastructure.llm.answer_matcher import LLMAnswerMatcher
from app.infrastructure.llm.assignment_generator import LLMAssignmentGenerator
from app.infrastructure.llm.chat_model_factory import get_chat_model
from app.infrastructure.llm.question_extractor import LLMQuestionExtractor
from app.infrastructure.parsers.document_factory import get_parser_for
from app.services.review.report_builder import ReportBuilder
from app.services.review.resume_matcher import RuleBasedResumeMatcher


@lru_cache(maxsize=1)
def get_report_builder() -> ReportBuilder:
    return ReportBuilder(get_settings())


@lru_cache(maxsize=1)
def get_question_extractor() -> LLMQuestionExtractor:
    return LLMQuestionExtractor(get_chat_model(), get_settings())


@lru_cache(maxsize=1)
def get_answer_matcher() -> LLMAnswerMatcher:
    return LLMAnswerMatcher(get_chat_model(), get_settings())


@lru_cache(maxsize=1)
def get_answer_evaluator() -> LLMAnswerEvaluator:
    return LLMAnswerEvaluator(get_chat_model(), get_settings())


@lru_cache(maxsize=1)
def get_resume_matcher() -> RuleBasedResumeMatcher:
    return RuleBasedResumeMatcher()


@lru_cache(maxsize=1)
def get_email_sender_dep() -> EmailSender:
    return get_email_sender(get_settings())


def get_match_resume_use_case() -> MatchResumeUseCase:
    """Build a MatchResumeUseCase (rule-based, zero LLM calls, bulk-safe).
    This is the ONLY resume-selection mechanism in the app."""

    return MatchResumeUseCase(
        get_parser_for=get_parser_for,
        resume_matcher=get_resume_matcher(),
    )


def get_review_use_case() -> ReviewSubmissionUseCase:
    """Build a ReviewSubmissionUseCase with all dependencies wired."""

    settings = get_settings()

    return ReviewSubmissionUseCase(
        settings=settings,
        get_parser_for=get_parser_for,
        question_extractor=get_question_extractor(),
        answer_matcher=get_answer_matcher(),
        answer_evaluator=get_answer_evaluator(),
        report_builder=get_report_builder(),
    )


@lru_cache(maxsize=1)
def get_assignment_generator() -> LLMAssignmentGenerator:
    return LLMAssignmentGenerator(get_chat_model(), get_settings())


def get_generate_assignment_use_case() -> GenerateAssignmentUseCase:
    """Build a GenerateAssignmentUseCase (stateless, 1 LLM call)."""

    return GenerateAssignmentUseCase(assignment_generator=get_assignment_generator())
