"""
Scores EVERY question/answer pair in the assignment, on the six required
dimensions, in EXACTLY ONE LLM call (Call 3 of the 3-call pipeline).
Implements the AnswerEvaluator port.

If the combined question+answer text is longer than
Settings.max_chars_evaluation, individual answers are truncated (head+tail)
to fit - never split into additional calls. The call count for this step
is always 1.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.exceptions import LLMEvaluationError
from app.core.logging import get_logger
from app.domain.enums import AnswerStatus, IssueType
from app.domain.models import Answer, DimensionScores, Issue, Question, QuestionReview
from app.services.prompts.templates import (
    EVALUATION_QA_BLOCK,
    EVALUATION_SYSTEM_PROMPT,
    EVALUATION_USER_PROMPT,
)
from app.utils.text_utils import safe_json_loads, truncate

logger = get_logger(__name__)


class LLMAnswerEvaluator:
    """Uses the chat model to grade every answer against its question in a
    single call."""

    def __init__(self, chat_model: BaseChatModel, settings: Settings) -> None:
        self._chat_model = chat_model
        self._settings = settings

    async def evaluate(self, questions: list[Question], answers: list[Answer]) -> list[QuestionReview]:
        if not questions:
            return []

        answers_by_id = {a.question_id: a for a in answers if a.question_id}
        pairs: list[tuple[Question, Answer]] = [
            (q, answers_by_id.get(q.id, Answer(question_id=q.id, text="", status=AnswerStatus.UNANSWERED)))
            for q in questions
        ]

        # Fair per-answer budget so one long answer can't starve the rest of
        # the single call's context window.
        per_answer_budget = max(300, self._settings.max_chars_evaluation // max(len(pairs), 1))

        qa_blocks = "\n".join(
            EVALUATION_QA_BLOCK.format(
                question_id=q.id,
                section=q.section,
                question_text=q.text,
                subquestions=q.subquestions or "None",
                answer_text=truncate(a.text, max_chars=per_answer_budget) or "[No answer submitted]",
            )
            for q, a in pairs
        )

        messages = [
            SystemMessage(content=EVALUATION_SYSTEM_PROMPT),
            HumanMessage(content=EVALUATION_USER_PROMPT.format(qa_blocks=qa_blocks)),
        ]

        response = await self._chat_model.with_config(
            run_name="evaluate_answers", tags=["pipeline:evaluation"]
        ).ainvoke(messages)
        parsed = safe_json_loads(response.content)

        if isinstance(parsed, dict):
            items = parsed.get("questions", [])
        elif isinstance(parsed, list):
            items = parsed
        else:
            raise LLMEvaluationError(f"Expected a JSON object with 'questions', got: {type(parsed)}")

        items_by_id = {str(item.get("question_id") or item.get("id") or ""): item for item in items}

        reviews: list[QuestionReview] = []
        for q, a in pairs:
            item = items_by_id.get(q.id)
            if item is None:
                logger.warning("No evaluation returned for question %s - scoring as 0", q.id)
                reviews.append(self._zero_review(q, a, "No evaluation was returned for this question."))
                continue
            reviews.append(self._parse_review(q, a, item))

        logger.info("Evaluated %d question/answer pairs in 1 call", len(reviews))
        return reviews

    def _parse_review(self, question: Question, answer: Answer, item: dict) -> QuestionReview:
        try:
            scores = DimensionScores(**item["scores"])
        except (KeyError, TypeError) as e:
            raise LLMEvaluationError(f"Malformed scores for question {question.id}: {e}") from e

        # Only keep explanations for known dimensions - guards against the
        # LLM inventing extra keys or misspelling a dimension name.
        valid_dimensions = set(DimensionScores.model_fields.keys())
        raw_explanations = item.get("score_explanations", {})
        score_explanations = {
            dim: str(reason)
            for dim, reason in (raw_explanations.items() if isinstance(raw_explanations, dict) else [])
            if dim in valid_dimensions and str(reason).strip()
        }

        issues: list[Issue] = []
        for raw_issue in item.get("issues", []):
            try:
                issue_type = IssueType(raw_issue.get("type", "other"))
            except ValueError:
                issue_type = IssueType.OTHER
            severity = max(1, min(int(raw_issue.get("severity", 3)), 5))
            issues.append(
                Issue(
                    type=issue_type,
                    description=str(raw_issue.get("description", "")),
                    severity=severity,
                )
            )

        return QuestionReview(
            question=question,
            answer=answer,
            scores=scores,
            score_explanations=score_explanations,
            issues=issues,
            strengths=[str(s) for s in item.get("strengths", [])],
            summary=str(item.get("summary", "")),
        )

    @staticmethod
    def _zero_review(question: Question, answer: Answer, reason: str) -> QuestionReview:
        zero_scores = DimensionScores(
            requirement_coverage=0,
            technical_correctness=0,
            ai_engineering=0,
            software_engineering=0,
            production_readiness=0,
            reasoning_depth=0,
        )
        return QuestionReview(
            question=question,
            answer=answer,
            scores=zero_scores,
            score_explanations={dim: reason for dim in DimensionScores.model_fields},
            issues=[Issue(type=IssueType.OTHER, description=reason, severity=5)],
            strengths=[],
            summary=reason,
        )
