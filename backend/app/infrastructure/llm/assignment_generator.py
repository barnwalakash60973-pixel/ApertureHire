"""
Assignment Generator: ONE LLM call turns an HR brief into a formatted
question-paper TEXT (not JSON) - deliberately the same shape a human
would upload, so it flows unchanged into the existing 3-call review
pipeline. Implements the AssignmentGenerator port.

Skills are extracted from the JD via the same rule-based extractor used
for resume matching (extract_skill_set) - zero LLM cost - and handed to
the model as an explicit list, not left for it to infer from prose. This
is what makes generation "skills-dependent": the prompt names the exact
skills to build questions around, rather than hoping the model notices
them itself while reading the raw JD text.
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.exceptions import LLMEvaluationError
from app.core.logging import get_logger
from app.services.prompts.templates import (
    ASSIGNMENT_GENERATION_SYSTEM_PROMPT,
    ASSIGNMENT_GENERATION_USER_PROMPT,
)
from app.services.review.skill_graph import extract_skill_set

logger = get_logger(__name__)


class LLMAssignmentGenerator:
    """Uses the chat model to draft a question paper in a single call."""

    def __init__(self, chat_model: BaseChatModel, settings: Settings) -> None:
        self._chat_model = chat_model
        self._settings = settings

    async def generate(
        self,
        brief: str,
        job_description_text: str = "",
        num_questions: int = 8,
        num_sections: int = 2,
        difficulty: str = "mid-level",
    ) -> str:
        if not brief.strip():
            raise LLMEvaluationError("Assignment brief cannot be empty.")

        skills = sorted(extract_skill_set(job_description_text)) if job_description_text.strip() else []
        skills_text = ", ".join(skills) if skills else "(no specific skills detected - use judgment from the brief/JD prose)"

        messages = [
            SystemMessage(content=ASSIGNMENT_GENERATION_SYSTEM_PROMPT),
            HumanMessage(
                content=ASSIGNMENT_GENERATION_USER_PROMPT.format(
                    job_description_text=job_description_text.strip()
                    or "(No job description provided - ground questions in the brief alone.)",
                    skills=skills_text,
                    brief=brief.strip(),
                    num_questions=num_questions,
                    num_sections=num_sections,
                    difficulty=difficulty,
                )
            ),
        ]

        response = await self._chat_model.with_config(
            run_name="generate_assignment", tags=["pipeline:generation"]
        ).ainvoke(messages)
        if isinstance(response.content, str):
            question_paper_text = response.content.strip()
        else:
            parts = []

            for block in response.content:
                if getattr(block, "type", None) == "text":
                    parts.append(block.text)
                elif isinstance(block, dict) and block.get("type") == "text":
                    parts.append(block.get("text", ""))

            question_paper_text = "\n".join(parts).strip()

        if not question_paper_text:
            raise LLMEvaluationError("Assignment generation returned empty output.")

        logger.info(
            "Generated assignment in 1 call: brief=%r, jd_chars=%d, skills=%s, ~%d chars output",
            brief[:60], len(job_description_text), skills, len(question_paper_text),
        )
        return question_paper_text
