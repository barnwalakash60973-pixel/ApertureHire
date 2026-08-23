"""
Extracts "years of experience" numbers from free text using regex only -
no LLM call. Used for two different things:
  - JD text: what's the MINIMUM required experience?
  - Resume text: what experience does the candidate CLAIM?

Honest limitation: this is a heuristic over unstructured text, not a real
NLP model. It will miss phrasing it doesn't recognize and can occasionally
misfire on unrelated numbers (e.g. "Python 3.11" won't match because it
requires the word "year(s)"/"yr(s)" adjacent to the number, but something
like "led a team of 5 years running" - rare, awkward phrasing - could).
Treat its output as a signal to show the recruiter, not an infallible
ground truth.
"""

from __future__ import annotations

import re

# Matches things like: "3 years", "3+ years", "3-5 years", "minimum 3 yrs",
# "at least 3 years of experience". Captures the first number in the range
# (the floor), which is what matters for a minimum-requirement check.
_YEARS_PATTERN = re.compile(
    r"(\d{1,2})\s*(?:\+|-\s*\d{1,2})?\s*(?:years?|yrs?)\b",
    re.IGNORECASE,
)

# JD requirement phrasing carries more weight when near these words -
# reduces false positives from unrelated numbers-near-"years" mentions.
_REQUIREMENT_CONTEXT = re.compile(
    r"(minimum|at least|require[sd]?|must have|need)[^.\n]{0,40}?(\d{1,2})\s*(?:\+|-\s*\d{1,2})?\s*(?:years?|yrs?)",
    re.IGNORECASE,
)


def extract_required_years(jd_text: str) -> int | None:
    """Best-effort extraction of the JD's minimum years-of-experience
    requirement. Prefers numbers found near explicit requirement language
    ("minimum", "at least", "requires") over a bare number-near-"years";
    falls back to the largest plain match if no requirement phrasing is
    found. Returns None if nothing looks like an experience requirement."""

    if not jd_text:
        return None

    context_matches = [int(m.group(2)) for m in _REQUIREMENT_CONTEXT.finditer(jd_text)]
    if context_matches:
        return max(context_matches)

    plain_matches = [int(m.group(1)) for m in _YEARS_PATTERN.finditer(jd_text)]
    return max(plain_matches) if plain_matches else None


def extract_candidate_years(resume_text: str) -> int | None:
    """Best-effort extraction of the candidate's claimed years of
    experience. Takes the MAX number found near "years"/"yrs" - resumes
    usually state total experience once, prominently (e.g. "5+ years of
    backend experience"), so the largest plausible match is a reasonable
    heuristic. Caps at 50 to ignore obvious noise (e.g. a stray "1999
    years" typo or an unrelated large number)."""

    if not resume_text:
        return None

    matches = [int(m.group(1)) for m in _YEARS_PATTERN.finditer(resume_text)]
    plausible = [y for y in matches if 0 < y <= 50]
    return max(plausible) if plausible else None
