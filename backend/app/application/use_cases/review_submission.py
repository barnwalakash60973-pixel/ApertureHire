"""
ReviewSubmissionUseCase: the single orchestrator that ties parsing,
extraction, matching, evaluation, and report building together.

This is the only place that knows the full pipeline order. Everything it
calls is injected as a port/interface, so the use case itself has zero
knowledge of docx/PyMuPDF/OpenAI specifics - that's what makes it testable
with fakes and swappable in production.

Pipeline makes EXACTLY 3 LLM calls total, regardless of how many sections
or questions the assignment has:
  1. self._question_extractor.extract(question_text)      -> all questions
  2. self._answer_matcher.match(questions, submission_text) -> all answers
  3. self._answer_evaluator.evaluate(questions, answers)    -> all reviews

Grouping the flat review list back into per-section SectionReports is pure
in-memory aggregation (no I/O, no LLM call).
"""

from __future__ import annotations

import asyncio

from app.application.interfaces import (
    AnswerEvaluator,
    AnswerMatcher,
    DocumentParser,
    QuestionExtractor,
)
from app.core.config import Settings
from app.core.exceptions import QuestionMatchError
from app.core.logging import get_logger
from app.domain.models import FinalReport, Question, QuestionReview, SectionReport
from app.services.review.report_builder import ReportBuilder

logger = get_logger(__name__)


class ReviewSubmissionUseCase:
    """Runs the end-to-end assignment review pipeline for one file pair."""

    def __init__(
        self,
        settings: Settings,
        get_parser_for,  # Callable[[str], DocumentParser] - factory, see infrastructure.parsers
        question_extractor: QuestionExtractor,
        answer_matcher: AnswerMatcher,
        answer_evaluator: AnswerEvaluator,
        report_builder: ReportBuilder,
    ) -> None:
        self._settings = settings
        self._get_parser_for = get_parser_for
        self._question_extractor = question_extractor
        self._answer_matcher = answer_matcher
        self._answer_evaluator = answer_evaluator
        self._report_builder = report_builder

    async def execute(self, question_paper_path: str, submission_path: str) -> FinalReport:
        question_text, submission_text = await asyncio.gather(
            self._get_parser_for(question_paper_path).extract_text(question_paper_path),
            self._get_parser_for(submission_path).extract_text(submission_path),
        )
        return await self.execute_from_texts(question_text, submission_text)

    async def execute_from_texts(self, question_text: str, submission_text: str) -> FinalReport:
        """Same pipeline as execute(), but skips file parsing - used when
        the question paper / submission text is already in hand (e.g. read
        straight out of the campaign database) instead of on disk."""

        # Call 1/3: extract every question from the whole question paper.
        questions = await self._question_extractor.extract(question_text)
        if not questions:
            raise QuestionMatchError("No questions could be extracted from the question paper.")
        logger.info("Call 1/3 (extraction) done: %d questions", len(questions))

        # Call 2/3: match every question against the whole submission.
        answers = await self._answer_matcher.match(questions, submission_text)
        logger.info("Call 2/3 (matching) done: %d answers", len(answers))

        # Call 3/3: evaluate every question/answer pair together.
        reviews = await self._answer_evaluator.evaluate(questions, answers)
        logger.info("Call 3/3 (evaluation) done: %d reviews", len(reviews))

        section_reports = self._group_by_section(questions, reviews)
        return self._report_builder.build(section_reports)

    @staticmethod
    def _group_by_section(
        questions: list[Question], reviews: list[QuestionReview]
    ) -> list[SectionReport]:
        """Splits the flat review list back into per-section reports, purely
        in memory - no LLM call, no I/O. Section order follows first
        appearance in `questions` (i.e. the order the extraction call
        returned them in)."""
        reviews_by_question_id = {r.question.id: r for r in reviews}

        ordered_sections: list[str] = []
        reviews_by_section: dict[str, list[QuestionReview]] = {}
        for q in questions:
            if q.section not in reviews_by_section:
                reviews_by_section[q.section] = []
                ordered_sections.append(q.section)
            review = reviews_by_question_id.get(q.id)
            if review is not None:
                reviews_by_section[q.section].append(review)
            else:
                logger.warning("No evaluation review found for question %s - omitting from report", q.id)

        return [
            SectionReport(section=section, question_reviews=reviews_by_section[section])
            for section in ordered_sections
        ]
