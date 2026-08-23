"""
Renders a FinalReport as a downloadable PDF, saved alongside the
candidate's resume/submission (see infrastructure/storage/keys.py's
report_key). Previously the evaluation report only existed as a JSON DB
column, with nothing to serve for "Download Report" as an actual file.

Plain-text layout via the shared PyMuPDF renderer (app/utils/pdf.py) -
matches the same simple paginated style already used for the assignment
question-paper download, no new dependency.
"""

from __future__ import annotations

import io

from app.domain.models import FinalReport
from app.utils.pdf import render_paginated_text_pdf


def render_report_pdf(candidate_name: str, job_title: str, report: FinalReport) -> io.BytesIO:
    lines: list[str] = [
        f"Candidate: {candidate_name}",
        f"Position: {job_title}",
        "",
        f"Overall Score: {report.overall_score:.1f} / 10",
        f"Hiring Recommendation: {report.hiring_recommendation.value.replace('_', ' ').title()}",
        report.hiring_rationale,
        "",
    ]

    if report.missing_topics:
        lines.append("Missing Topics: " + ", ".join(report.missing_topics))
    if report.improvements:
        lines.append("Suggested Improvements: " + ", ".join(report.improvements))
    if report.missing_topics or report.improvements:
        lines.append("")

    for section in report.section_reports:
        lines.append(f"=== {section.section} (avg {section.average_score:.1f}/10) ===")
        lines.append("")
        for qr in section.question_reviews:
            lines.append(f"Q{qr.question.number}: {qr.question.text}")
            dims = ", ".join(f"{k}: {v}" for k, v in qr.scores.model_dump().items())
            lines.append(f"Scores - {dims} (avg {qr.scores.average():.1f})")
            lines.append(f"Verdict: {qr.summary}")
            if qr.strengths:
                lines.append("Strengths: " + "; ".join(qr.strengths))
            if qr.issues:
                lines.append("Issues: " + "; ".join(f"[{i.type.value}] {i.description}" for i in qr.issues))
            lines.append("")

    return render_paginated_text_pdf(f"Evaluation Report - {candidate_name}", lines)
