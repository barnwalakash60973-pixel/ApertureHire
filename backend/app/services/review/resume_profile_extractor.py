"""
Structured resume extraction - the flowchart's "Resume Processing
Service" step, which lists Skills, Education, Experience, Projects,
Certifications and Resume Text as the things to extract.

Before this, only two of the six existed: skills (skill_graph.py) and
years-of-experience (experience_extractor.py). Education, Projects and
Certifications were never pulled out, so the "Store Metadata in
Database" step had nothing to store for them.

Deliberately regex/heading-based, NO LLM - consistent with the rest of
the screening path, which must stay free to run over 100,000 resumes.
The approach: find a section heading, take everything until the next
known heading, split into non-empty lines.

Honest accuracy note: this handles conventionally-formatted resumes with
recognisable section headings. It will do poorly on multi-column PDF
layouts (where text extraction interleaves columns), heavily designed
templates, and resumes that use unusual headings. It returns empty lists
rather than guessing when it can't find a section - an empty list means
"not confidently found", NOT "the candidate has none". Do not treat
these fields as authoritative for screening decisions; they are HR
review aids. Screening still runs off skills + experience only.
"""

from __future__ import annotations

import re

# Canonical section name -> heading variants that introduce it.
_SECTION_PATTERNS: dict[str, list[str]] = {
    "education": ["education", "academic background", "academics", "academic qualifications", "qualifications"],
    "experience": ["experience", "work experience", "professional experience", "employment", "employment history", "work history", "internships", "internship experience"],
    "projects": ["projects", "personal projects", "academic projects", "key projects", "selected projects"],
    "certifications": ["certifications", "certificates", "certification", "licenses", "courses", "certifications & courses"],
    "skills": ["skills", "technical skills", "core skills", "technologies", "tech stack", "skills & tools"],
    "summary": ["summary", "objective", "profile", "about me", "career objective"],
    "awards": ["awards", "achievements", "honors", "honours", "accomplishments"],
    "publications": ["publications", "papers", "research"],
}

# Any of these, on their own line, ends the previous section.
_ALL_HEADINGS = sorted({v for variants in _SECTION_PATTERNS.values() for v in variants}, key=len, reverse=True)

_HEADING_RE = re.compile(
    r"^[\s\W]*(" + "|".join(re.escape(h) for h in _ALL_HEADINGS) + r")[\s\W]*$",
    re.IGNORECASE,
)

# Lines longer than this are almost certainly body text, not a heading -
# guards against a paragraph that merely starts with the word "Projects".
_MAX_HEADING_CHARS = 60

_MAX_ITEMS_PER_SECTION = 20
_MAX_ITEM_CHARS = 300


def _canonical(heading: str) -> str | None:
    lowered = heading.strip().lower()
    for canonical, variants in _SECTION_PATTERNS.items():
        if lowered in variants:
            return canonical
    return None


def split_sections(resume_text: str) -> dict[str, list[str]]:
    """Split resume text into {canonical_section: [lines]}.

    Sections not found are simply absent from the dict. A later heading
    for the same section (some resumes repeat "Projects") extends the
    earlier one rather than overwriting it.
    """

    sections: dict[str, list[str]] = {}
    current: str | None = None

    for raw_line in resume_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if len(line) <= _MAX_HEADING_CHARS:
            match = _HEADING_RE.match(line)
            if match:
                current = _canonical(match.group(1))
                if current:
                    sections.setdefault(current, [])
                continue

        if current:
            # Strip common bullet glyphs so items are comparable.
            cleaned = re.sub(r"^[\-\*\u2022\u25cf\u25aa\u00b7\u2023\u2043>]+\s*", "", line).strip()
            if cleaned and len(sections[current]) < _MAX_ITEMS_PER_SECTION:
                sections[current].append(cleaned[:_MAX_ITEM_CHARS])

    return {k: v for k, v in sections.items() if v}


def extract_education(resume_text: str) -> list[str]:
    return split_sections(resume_text).get("education", [])


def extract_projects(resume_text: str) -> list[str]:
    return split_sections(resume_text).get("projects", [])


def extract_certifications(resume_text: str) -> list[str]:
    return split_sections(resume_text).get("certifications", [])


def extract_experience_entries(resume_text: str) -> list[str]:
    """Raw experience-section lines. Distinct from
    experience_extractor.extract_candidate_years, which returns a NUMBER
    of years for the screening gate - this returns the human-readable
    entries for HR to read."""
    return split_sections(resume_text).get("experience", [])


def extract_resume_profile(resume_text: str) -> dict[str, list[str]]:
    """Everything the 'Resume Processing Service' box asks for, minus
    skills (skill_graph) and years (experience_extractor), which already
    have dedicated extractors used by the screening engine."""

    sections = split_sections(resume_text)
    return {
        "education": sections.get("education", []),
        "experience_entries": sections.get("experience", []),
        "projects": sections.get("projects", []),
        "certifications": sections.get("certifications", []),
    }
