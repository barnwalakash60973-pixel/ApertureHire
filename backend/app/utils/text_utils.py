"""Small stateless helpers shared across services."""

from __future__ import annotations

import json
import re
from typing import Any

from app.core.exceptions import LLMEvaluationError


def _normalize_response(raw_text: Any) -> str:
    """Normalize OpenAI/Gemini responses into a plain string."""

    if raw_text is None:
        return ""

    if isinstance(raw_text, str):
        return raw_text

    if isinstance(raw_text, list):
        parts = []

        for item in raw_text:
            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):
                parts.append(str(item.get("text", "")))

            elif hasattr(item, "text"):
                parts.append(str(item.text))

            else:
                parts.append(str(item))

        return "\n".join(parts)

    return str(raw_text)


def extract_json_block(raw_text: Any) -> str:
    """Extract the first JSON object or array from an LLM response."""

    cleaned = _normalize_response(raw_text).strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        cleaned,
        flags=re.MULTILINE,
    )

    match = re.search(
        r"(\{.*\}|\[.*\])",
        cleaned,
        flags=re.DOTALL,
    )

    if not match:
        raise LLMEvaluationError(
            f"No JSON found in response:\n{cleaned[:300]}"
        )

    return match.group(1)


def safe_json_loads(raw_text: Any) -> dict | list:
    """Parse JSON returned by an LLM."""

    block = extract_json_block(raw_text)

    try:
        return json.loads(block)

    except json.JSONDecodeError as e:
        raise LLMEvaluationError(
            f"Malformed JSON returned by LLM:\n{block[:300]}"
        ) from e


def truncate(text: str, max_chars: int = 6000) -> str:
    """Truncate long text for prompt inclusion."""

    if len(text) <= max_chars:
        return text

    half = max_chars // 2

    return (
        text[:half]
        + "\n...[truncated]...\n"
        + text[-half:]
    )