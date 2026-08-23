"""
Builds the FinalReport from a list of SectionReports. Pure aggregation
logic - no LLM calls, no I/O - so it's trivially unit-testable.
"""

from __future__ import annotations

from app.core.config import Settings
from app.domain.enums import AnswerStatus, HiringRecommendation
from app.domain.models import FinalReport, SectionReport
from app.services.review.skill_graph import build_skill_graph


class ReportBuilder:
    """Turns per-section reviews into the top-level FinalReport."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def build(self, section_reports: list[SectionReport]) -> FinalReport:
        overall_score = self._overall_score(section_reports)
        missing_topics = self._missing_topics(section_reports)
        improvements = self._top_improvements(section_reports)
        statistics = self._statistics(section_reports)
        recommendation, rationale = self._hiring_recommendation(
                                overall_score, section_reports,statistics,)

        return FinalReport(
            overall_score=overall_score,
            section_reports=section_reports,
            missing_topics=missing_topics,
            improvements=improvements,
            hiring_recommendation=recommendation,
            hiring_rationale=rationale,
            score_breakdown=self._score_breakdown(section_reports),
            statistics=statistics,
            skill_graph=build_skill_graph(section_reports),
        )
    


    @staticmethod
    def _overall_score(section_reports: list[SectionReport]) -> float:
        if not section_reports:
            return 0.0
        return round(
            sum(sr.average_score for sr in section_reports) / len(section_reports), 2
        )

    @staticmethod
    def _missing_topics(section_reports: list[SectionReport]) -> list[str]:
        missing: list[str] = []
        for sr in section_reports:
            for qr in sr.question_reviews:
                if qr.answer.status == AnswerStatus.UNANSWERED:
                    missing.append(f"{qr.question.id}: {qr.question.text[:80]}")
        return missing

    @staticmethod
    def _top_improvements(section_reports: list[SectionReport], limit: int = 10) -> list[str]:
        """Surface the highest-severity issues across the whole submission."""
        all_issues = [
            (issue.severity, f"{qr.question.id} — {issue.type.value}: {issue.description}")
            for sr in section_reports
            for qr in sr.question_reviews
            for issue in qr.issues
        ]
        all_issues.sort(key=lambda pair: pair[0], reverse=True)
        return [text for _, text in all_issues[:limit]]
    @staticmethod
    def _score_breakdown(section_reports: list[SectionReport]) -> dict[str, float]:
        reviews = [
            qr
            for sr in section_reports
            for qr in sr.question_reviews
        ]

        if not reviews:
            return {}

        n = len(reviews)

        return {
            "requirement_coverage": round(
            sum(r.scores.requirement_coverage for r in reviews) / n, 2
            ),
            "technical_correctness": round(
            sum(r.scores.technical_correctness for r in reviews) / n, 2
            ),
            "ai_engineering": round(
            sum(r.scores.ai_engineering for r in reviews) / n, 2
            ),
            "software_engineering": round(
            sum(r.scores.software_engineering for r in reviews) / n, 2
            ),
            "production_readiness": round(
            sum(r.scores.production_readiness for r in reviews) / n, 2
            ),
            "reasoning_depth": round(
            sum(r.scores.reasoning_depth for r in reviews) / n, 2
           ),
       }
    @staticmethod
    def _statistics(section_reports: list[SectionReport]) -> dict[str, int]:
        reviews = [
            qr
            for sr in section_reports
            for qr in sr.question_reviews
        ]

        issues = [
            issue
            for review in reviews
            for issue in review.issues
        ]

        return {
            "questions": len(reviews),
            "answered": sum(
            1
            for r in reviews
            if r.answer.status == AnswerStatus.ANSWERED
           ),
           "unanswered": sum(
            1
            for r in reviews
            if r.answer.status == AnswerStatus.UNANSWERED
           ),
           "critical_issues": sum(
            1
            for i in issues
            if i.severity >= 5
           ),
        }

    def _hiring_recommendation(
        self, overall_score: float, section_reports: list[SectionReport]
         ,statistics: dict[str, int], 
    ) -> tuple[HiringRecommendation, str]:
        total_questions = sum(len(sr.question_reviews) for sr in section_reports)
        unanswered = sum(sr.unanswered_count for sr in section_reports)
        unanswered_ratio = (unanswered / total_questions) if total_questions else 1.0
        critical_issues = statistics["critical_issues"]

        if (overall_score >= 8.5 and unanswered_ratio == 0 and critical_issues == 0
            ):
              return (
                HiringRecommendation.STRONG_HIRE,
                "Excellent technical performance with no critical issues.",
            )
        if overall_score >= 7.0 and unanswered_ratio < 0.1 and critical_issues <= 2:
            return (
                HiringRecommendation.HIRE,
                "Good technical understanding with only minor improvements required.",
            )
        if overall_score >= 5.5:
            return (
                HiringRecommendation.LEAN_HIRE,
                "Candidate demonstrates potential but requires mentoring.",
            )
        if overall_score >= 4.0:
            return (
                HiringRecommendation.NO_HIRE,
                "Technical depth is below the expected hiring bar.",
            )
        return (
            HiringRecommendation.STRONG_NO_HIRE,
            "Large portions unanswered or technically incorrect.",
        )
