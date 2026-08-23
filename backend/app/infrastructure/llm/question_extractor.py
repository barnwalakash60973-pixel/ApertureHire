"""
Extracts every Question in the assignment from the COMPLETE question-paper
text using EXACTLY ONE LLM call (Call 1 of the 3-call pipeline). Implements
the QuestionExtractor port.

If the document is longer than Settings.max_chars_extraction it is
truncated (head+tail), never split into additional calls - the call count
for this step is always 1.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.exceptions import LLMEvaluationError
from app.core.logging import get_logger
from app.domain.models import Question
from app.services.prompts.templates import (
    QUESTION_EXTRACTION_DOCUMENT_SYSTEM_PROMPT,
    QUESTION_EXTRACTION_DOCUMENT_USER_PROMPT,
)
from app.utils.text_utils import safe_json_loads, truncate

logger = get_logger(__name__)


class LLMQuestionExtractor:
    """Uses the chat model to pull every question out of the question paper
    in a single call."""

    def __init__(self, chat_model: BaseChatModel, settings: Settings) -> None:
        self._chat_model = chat_model
        self._settings = settings

    async def extract(self, document_text: str) -> list[Question]:
        messages = [
            SystemMessage(content=QUESTION_EXTRACTION_DOCUMENT_SYSTEM_PROMPT),
            HumanMessage(
                content=QUESTION_EXTRACTION_DOCUMENT_USER_PROMPT.format(
                    document_text=truncate(document_text, max_chars=self._settings.max_chars_extraction)
                )
            ),
        ]

        response = await self._chat_model.with_config(
            run_name="extract_questions", tags=["pipeline:extraction"]
        ).ainvoke(messages)
        parsed = safe_json_loads(response.content)

        if isinstance(parsed, list):
            # Tolerate a bare sections array if the model skips the {"sections": ...} wrapper.
            sections_payload = parsed
        elif isinstance(parsed, dict):
            sections_payload = parsed.get("sections", [])
        else:
            raise LLMEvaluationError(f"Expected a JSON object with 'sections', got: {type(parsed)}")

        questions = self._parse_sections_payload(sections_payload)
        logger.info("Extracted %d questions from whole document in 1 call", len(questions))
        return questions

    @staticmethod
    def _parse_sections_payload(sections_payload: object) -> list[Question]:
        if not isinstance(sections_payload, list):
            raise LLMEvaluationError(f"Expected 'sections' to be a JSON array, got: {type(sections_payload)}")

        questions: list[Question] = []
        for section_item in sections_payload:
            if not isinstance(section_item, dict):
                continue
            section_label = str(section_item.get("section", "Part A")).strip() or "Part A"
            for item in section_item.get("questions", []):
                number = str(item.get("number", "")).strip()
                if not number:
                    logger.warning("Skipping question with no number in section %s", section_label)
                    continue
                questions.append(
                    Question(
                        id=number,
                        section=section_label,
                        number=number,
                        text=str(item.get("text", "")).strip(),
                        subquestions=[str(s) for s in item.get("subquestions", [])],
                    )
                )
        return questions
