"""
GenerateAssignmentUseCase: thin orchestrator around AssignmentGenerator.
Stateless (Part A of the plan, no DB dependency) - the generated text is
handed straight back to the caller (HR reviews/edits it before it becomes
a stored Assignment once Part B's database exists).
"""

from __future__ import annotations

from app.application.interfaces import AssignmentGenerator
from app.core.logging import get_logger

logger = get_logger(__name__)


class GenerateAssignmentUseCase:
    def __init__(self, assignment_generator: AssignmentGenerator) -> None:
        self._assignment_generator = assignment_generator

    async def execute(
        self,
        brief: str,
        job_description_text: str = "",
        num_questions: int = 8,
        num_sections: int = 2,
        difficulty: str = "mid-level",
    ) -> str:
        question_paper_text = await self._assignment_generator.generate(
            brief=brief, job_description_text=job_description_text,
            num_questions=num_questions, num_sections=num_sections, difficulty=difficulty,
        )
        logger.info("Assignment generated (1 LLM call), ready for HR review")
        return question_paper_text
