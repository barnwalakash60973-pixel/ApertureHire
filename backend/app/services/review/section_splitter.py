"""
Section splitter: deterministic regex-based split of a document's text
into "Part A" / "Part B" / etc. sections.

This is intentionally NOT an LLM call - section headers are structurally
predictable, so a regex is faster, cheaper, and more reliable than an LLM
for this specific step. Reserve LLM calls for the steps that actually need
semantic understanding.
"""

from __future__ import annotations

import re

from app.core.exceptions import SectionSplitError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Matches headers like "Part A", "PART B:", "Section C -", "Part D."
_SECTION_HEADER_RE = re.compile(
    r"^\s*(?:part|section)\s+([A-D])\b[\s:.\-–—]*(.*)$",
    re.IGNORECASE | re.MULTILINE,
)


class RegexSectionSplitter:
    """Splits text on 'Part A/B/C/D' headers."""

    def split(self, text: str) -> dict[str, str]:
        matches = list(_SECTION_HEADER_RE.finditer(text))

        # Standard assignment format
        if matches:
            sections: dict[str, str] = {}

            for i, match in enumerate(matches):
                label = f"Part {match.group(1).upper()}"
                start = match.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

                body = text[start:end].strip()

                if label in sections:
                    sections[label] += "\n" + body
                else:
                    sections[label] = body

            logger.info("Split document into sections: %s", list(sections.keys()))
            return sections

    # Fallback
        logger.warning("No Part A/B/C/D headers found. Treating entire document as Part A.")

        return {
        "Part A": text.strip()
      }