"""
Storage key naming. Centralized so the layout matches the flowchart's
final archive structure:

    campaigns/<campaign_id>/<candidate_id>/resume.<ext>
    campaigns/<campaign_id>/<candidate_id>/submission.<ext>
    campaigns/<campaign_id>/<candidate_id>/report.pdf

Keys are built from IDs we generated ourselves (never the raw uploaded
filename) specifically so a malicious filename can't be used for path
traversal or to collide with another candidate's object.
"""

from __future__ import annotations


def _ext(filename: str | None, default: str) -> str:
    if filename and "." in filename:
        return filename.rsplit(".", 1)[-1].lower()
    return default


def resume_key(campaign_id: str, candidate_id: str, filename: str | None) -> str:
    return f"campaigns/{campaign_id}/{candidate_id}/resume.{_ext(filename, 'pdf')}"


def submission_key(campaign_id: str, candidate_id: str, filename: str | None) -> str:
    return f"campaigns/{campaign_id}/{candidate_id}/submission.{_ext(filename, 'pdf')}"


def report_key(campaign_id: str, candidate_id: str) -> str:
    return f"campaigns/{campaign_id}/{candidate_id}/report.pdf"
