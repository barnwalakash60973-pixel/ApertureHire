"""
Matches submission text to questions by meaning (not just numbering), for
ALL questions against the COMPLETE submission in EXACTLY ONE LLM call
(Call 2 of the 3-call pipeline). Implements the AnswerMatcher port.

If the submission is longer than Settings.max_chars_matching it is
truncated (head+tail), never split into additional calls - the call count
for this step is always 1.
"""

from __future__ import annotations

import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.exceptions import LLMEvaluationError
from app.core.logging import get_logger
from app.domain.enums import AnswerStatus
from app.domain.models import Answer, Question
from app.services.prompts.templates import (
    ANSWER_MATCHING_SYSTEM_PROMPT,
    ANSWER_MATCHING_USER_PROMPT,
)
from app.utils.text_utils import safe_json_loads, truncate

logger = get_logger(__name__)


class LLMAnswerMatcher:
    """Uses the chat model to align submission text with question ids in a
    single call covering every question and the whole submission."""

    def __init__(self, chat_model: BaseChatModel, settings: Settings) -> None:
        self._chat_model = chat_model
        self._settings = settings

    async def match(self, questions: list[Question], submission_text: str) -> list[Answer]:
        if not questions:
            return []

        # Truncate the RAW text first, then number lines - this guarantees
        # the [N] line numbers the LLM sees are identical to the indices we
        # slice back out of `lines` below. Numbering-then-truncating would
        # cut lines out of the middle and desync the two.
        truncated_text = truncate(submission_text, max_chars=self._settings.max_chars_matching)
        lines = truncated_text.splitlines()
        numbered_text = "\n".join(f"[{i + 1}] {line}" for i, line in enumerate(lines))

        questions_payload = [
            {"id": q.id, "section": q.section, "text": q.text, "subquestions": q.subquestions}
            for q in questions
        ]

        messages = [
            SystemMessage(content=ANSWER_MATCHING_SYSTEM_PROMPT),
            HumanMessage(
                content=ANSWER_MATCHING_USER_PROMPT.format(
                    questions_json=json.dumps(questions_payload, indent=2),
                    submission_text=numbered_text,
                )
            ),
        ]

        response = await self._chat_model.with_config(
            run_name="match_answers", tags=["pipeline:matching"]
        ).ainvoke(messages)
        parsed = safe_json_loads(response.content)

        if not isinstance(parsed, list):
            raise LLMEvaluationError(f"Expected a JSON array of answers, got: {type(parsed)}")

        known_ids = {q.id for q in questions}
        answers_by_id: dict[str, Answer] = {}
        for item in parsed:
            question_id = item.get("question_id")
            if question_id not in known_ids:
                continue
            status_raw = str(item.get("status", "unanswered")).lower()
            try:
                status = AnswerStatus(status_raw)
            except ValueError:
                status = AnswerStatus.UNANSWERED

            text = self._extract_verbatim_text(
                lines, item.get("start_line"), item.get("end_line"), question_id
            )
            if not text:
                status = AnswerStatus.UNANSWERED

            answers_by_id[question_id] = Answer(question_id=question_id, text=text, status=status)

        # Ensure every question has an Answer entry, even if the LLM omitted it.
        answers: list[Answer] = []
        for q in questions:
            if q.id in answers_by_id:
                answers.append(answers_by_id[q.id])
            else:
                logger.warning("No match returned for question %s - marking unanswered", q.id)
                answers.append(Answer(question_id=q.id, text="", status=AnswerStatus.UNANSWERED))

        logger.info("Matched %d answers against whole submission in 1 call", len(answers))
        return answers

    @staticmethod
    def _extract_verbatim_text(
        lines: list[str],
        start_line: object,
        end_line: object,
        question_id: str,
    ) -> str:
        """
        Slices the ORIGINAL submission lines using the LLM's line range.
        The LLM never supplies answer text directly - this guarantees the
        stored Answer.text is byte-for-byte what the candidate wrote,
        instead of an LLM paraphrase of it.
        """
        if not lines or not isinstance(start_line, int) or not isinstance(end_line, int):
            return ""

        # LLM line numbers are 1-indexed and inclusive; clamp defensively
        # rather than trusting them blindly.
        start = max(1, start_line)
        end = min(len(lines), end_line)

        if start > end:
            logger.warning(
                "Invalid line range for question %s: start=%s end=%s (of %d lines)",
                question_id, start_line, end_line, len(lines),
            )
            return ""

        return "\n".join(lines[start - 1:end]).strip()
