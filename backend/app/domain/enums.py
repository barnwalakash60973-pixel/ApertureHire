"""Domain-level enumerations. Pure Python, no framework imports."""

from __future__ import annotations

from enum import Enum


class AnswerStatus(str, Enum):
    ANSWERED = "answered"
    PARTIALLY_ANSWERED = "partially_answered"
    UNANSWERED = "unanswered"


class IssueType(str, Enum):
    MISSING_SUBQUESTION = "missing_subquestion"
    WEAK_EXPLANATION = "weak_explanation"
    HALLUCINATION = "hallucination"
    INCORRECT_AZURE_ARCHITECTURE = "incorrect_azure_architecture"
    MISSING_PRODUCTION_CONCERNS = "missing_production_concerns"
    WEAK_RAG_DESIGN = "weak_rag_design"
    WEAK_AGENT_ARCHITECTURE = "weak_agent_architecture"
    WEAK_EVALUATION_FRAMEWORK = "weak_evaluation_framework"
    OTHER = "other"


class HiringRecommendation(str, Enum):
    STRONG_HIRE = "strong_hire"
    HIRE = "hire"
    LEAN_HIRE = "lean_hire"
    NO_HIRE = "no_hire"
    STRONG_NO_HIRE = "strong_no_hire"


class MatchDecision(str, Enum):
    """Outcome of the RULE-BASED (no LLM) JD<->resume SCREENING stage, per
    the bulk-screening diagram: 100% skill match or missing exactly 1
    skill -> shortlisted; missing >1 skill, or an unmet experience
    requirement counted as a "missing requirement", pushes the total over
    the threshold -> not_shortlisted.

    Deliberately NOT named selected/rejected - this is only the screening
    outcome (does the resume warrant sending an assignment?), not a final
    hiring decision. The actual hire/reject call happens later, after
    assignment evaluation (see HiringRecommendation /
    final_selected/final_rejected candidate statuses)."""

    SHORTLISTED = "shortlisted"
    NOT_SHORTLISTED = "not_shortlisted"
