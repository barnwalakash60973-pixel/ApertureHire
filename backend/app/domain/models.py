"""
Domain models: pure data structures representing the review problem.

These are pydantic models (for validation + easy JSON/LLM structured
output) but carry no infrastructure concerns - no DB, no HTTP, no LLM
client references.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import AnswerStatus, HiringRecommendation, IssueType, MatchDecision


class Question(BaseModel):
    """A single question extracted from the assignment question paper."""

    id: str = Field(description="Stable id, e.g. 'A.1' or 'B.3.a'")
    section: str = Field(description="Part label, e.g. 'Part A'")
    number: str = Field(description="Question number/label as written, e.g. 'A.1'")
    text: str
    subquestions: list[str] = Field(default_factory=list)


class Answer(BaseModel):
    """A block of submission text believed to correspond to one Question."""

    question_id: str | None = Field(default=None, description="Matched Question.id, if any")
    text: str
    status: AnswerStatus = AnswerStatus.UNANSWERED


class DimensionScores(BaseModel):
    """The six scoring dimensions the assignment requires, 0-10 each."""

    requirement_coverage: int = Field(ge=0, le=10)
    technical_correctness: int = Field(ge=0, le=10)
    ai_engineering: int = Field(ge=0, le=10)
    software_engineering: int = Field(ge=0, le=10)
    production_readiness: int = Field(ge=0, le=10)
    reasoning_depth: int = Field(ge=0, le=10)

    def average(self) -> float:
        values = [
            self.requirement_coverage,
            self.technical_correctness,
            self.ai_engineering,
            self.software_engineering,
            self.production_readiness,
            self.reasoning_depth,
        ]
        return round(sum(values) / len(values), 2)


class Issue(BaseModel):
    """A single detected problem in an answer, e.g. a hallucination or gap."""

    type: IssueType
    description: str
    severity: int = Field(ge=1, le=5, description="1=minor, 5=critical")


class QuestionReview(BaseModel):
    """The full LLM-graded review of one question/answer pair."""

    question: Question
    answer: Answer
    scores: DimensionScores
    score_explanations: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "One-sentence, evidence-based justification per scoring dimension, "
            "keyed the same as DimensionScores' fields (e.g. "
            "'technical_correctness'). Powers the explainable-evaluation view."
        ),
    )
    issues: list[Issue] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    summary: str = Field(description="1-3 sentence verdict on this answer")


class SectionReport(BaseModel):
    """Aggregated results for one Part (A/B/C/D)."""

    section: str
    question_reviews: list[QuestionReview]

    @property
    def average_score(self) -> float:
        if not self.question_reviews:
            return 0.0
        return round(
            sum(qr.scores.average() for qr in self.question_reviews) / len(self.question_reviews),
            2,
        )

    @property
    def unanswered_count(self) -> int:
        return sum(1 for qr in self.question_reviews if qr.answer.status == AnswerStatus.UNANSWERED)


class SkillMention(BaseModel):
    """One detected technology/skill and how often it was mentioned across
    all of the candidate's answers. Built by a deterministic keyword scan
    (see services/review/skill_graph.py) - no LLM call involved."""

    skill: str
    mentions: int = Field(ge=1)
    bar: str = Field(description="Precomputed unicode block-bar for simple text display, e.g. '██████████'")


class FinalReport(BaseModel):
    """The top-level deliverable: everything the API returns to the caller."""

    overall_score: float = Field(ge=0, le=10)
    section_reports: list[SectionReport]
    missing_topics: list[str]
    improvements: list[str]
    hiring_recommendation: HiringRecommendation
    hiring_rationale: str
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    statistics: dict[str, int] = Field(default_factory=dict)
    skill_graph: list[SkillMention] = Field(
        default_factory=list,
        description="Technologies/skills detected in the candidate's answers, sorted by mentions descending.",
    )


class ResumeMatchResult(BaseModel):
    """Output of the RULE-BASED (no LLM) JD<->resume matcher. Pure
    regex/dictionary comparison - zero LLM calls, safe to run at bulk
    scale (100-100,000 resumes)."""

    required_skills: list[str] = Field(default_factory=list, description="Skills detected in the JD text.")
    resume_skills: list[str] = Field(default_factory=list, description="Skills detected in the resume text.")
    matched_skills: list[str] = Field(default_factory=list, description="Required skills the resume also has.")
    missing_skills: list[str] = Field(default_factory=list, description="Required skills the resume is missing.")

    jd_min_years_experience: int | None = Field(
        default=None, description="Minimum years of experience the JD asks for, if detected. None if not stated."
    )
    candidate_years_experience: int | None = Field(
        default=None, description="Years of experience the resume claims, if detected. None if not found."
    )
    experience_satisfied: bool | None = Field(
        default=None,
        description=(
            "True/False if the JD stated a minimum and we could compare it. "
            "None if the JD didn't state a minimum, or the resume's experience couldn't be parsed."
        ),
    )

    # The flowchart's "Match Score" field, 0-100. Previously the matcher
    # returned only a binary decision + missing-skills list, so the
    # Candidate record had no score to store or rank by.
    #
    # Composition is deliberately simple and inspectable (see
    # resume_matcher._compute_score): it is a weighted skill-coverage
    # percentage with an experience adjustment. It is NOT a calibrated
    # probability of interview success - do not present it as one. Two
    # candidates 4 points apart are not meaningfully different.
    match_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Skill-coverage score, 0-100.")

    # From the "Resume Processing Service" box. Regex/heading-based, no
    # LLM. Empty list means "not confidently found", NOT "candidate has
    # none" - these are HR review aids and are NOT used by the screening
    # decision, which runs off skills + experience only.
    education: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    experience_entries: list[str] = Field(default_factory=list)

    decision: MatchDecision
    decision_reason: str = Field(description="Plain-English explanation of why this decision was reached.")
