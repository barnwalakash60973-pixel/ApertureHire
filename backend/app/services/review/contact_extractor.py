"""
Extracts candidate name and email from resume text using regex/heuristics
only - NO LLM call, consistent with the rest of the bulk-screening path
staying zero-cost at any volume.

Honest limitation: name extraction from free-form resume text is
inherently heuristic. This looks at the first few non-empty lines for
something that looks like a person's name (2-4 capitalized words, no
digits, not a section header). It WILL fail on unusual resume layouts -
that's exactly why the import preview step exists, so HR corrects
anything wrong before candidates are finalized, rather than trusting this
blindly.
"""

from __future__ import annotations

import re

_EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")

# Lines that are clearly NOT a name, even if they superficially match the
# capitalized-words shape (resume section headers, common document titles).
_NON_NAME_LINES = {
    "resume", "curriculum vitae", "cv", "contact", "contact information",
    "personal details", "profile", "summary", "objective", "career objective",
}

# A candidate name line: 2-4 words, each starting with a capital letter,
# letters/hyphens/periods/apostrophes only (covers "Jane Doe", "Mary-Anne
# O'Brien", "J. R. Smith"), no digits, reasonable total length.
_NAME_LINE_PATTERN = re.compile(
    r"^[A-Z][a-zA-Z'\-.]*(?:\s+[A-Z][a-zA-Z'\-.]*){1,3}$"
)

_MAX_LINES_TO_SCAN_FOR_NAME = 6
_MAX_NAME_LENGTH = 50


def extract_email(text: str) -> str | None:
    if not text:
        return None
    match = _EMAIL_PATTERN.search(text)
    return match.group(0) if match else None


def extract_name(text: str) -> str | None:
    if not text:
        return None

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines[:_MAX_LINES_TO_SCAN_FOR_NAME]:
        if len(line) > _MAX_NAME_LENGTH:
            continue
        if line.lower() in _NON_NAME_LINES:
            continue
        if _EMAIL_PATTERN.search(line):
            continue  # a line with an email in it is not just a name
        if any(ch.isdigit() for ch in line):
            continue
        if _NAME_LINE_PATTERN.match(line):
            return line

    return None
