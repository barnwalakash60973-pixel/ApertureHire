"""
Shared plain-text PDF rendering, built on PyMuPDF (`fitz`) - already a
dependency for parsing, so no extra library is needed just to write one
back out. Originally lived only in routes_assignments.py (question-paper
download); extracted here so report_pdf.py can reuse the same pagination
logic without importing from a routes module.
"""

from __future__ import annotations

import io

import fitz  # PyMuPDF


def wrap_line(line: str, fontname: str, fontsize: float, max_width: float) -> list[str]:
    """Greedy word-wrap using PyMuPDF's own text-measuring so lines never
    overflow the page width, regardless of font metrics."""

    if not line.strip():
        return [""]

    wrapped: list[str] = []
    current = ""
    for word in line.split(" "):
        candidate = f"{current} {word}".strip()
        if current and fitz.get_text_length(candidate, fontname=fontname, fontsize=fontsize) > max_width:
            wrapped.append(current)
            current = word
        else:
            current = candidate
    if current:
        wrapped.append(current)
    return wrapped


def render_paginated_text_pdf(title: str, body_lines: list[str]) -> io.BytesIO:
    """Renders a title + pre-split body lines as a simple paginated PDF.
    Each body line is word-wrapped to the page width before layout."""

    fontname = "helv"
    title_size, body_size = 16.0, 10.5
    margin = 54.0  # ~0.75"
    page_width, page_height = fitz.paper_size("letter")
    max_width = page_width - 2 * margin
    line_height = body_size * 1.45

    lines: list[str] = []
    for raw_line in body_lines:
        lines.extend(wrap_line(raw_line, fontname, body_size, max_width))

    doc = fitz.open()
    page = doc.new_page(width=page_width, height=page_height)
    y = margin + title_size
    page.insert_text((margin, y), title, fontsize=title_size, fontname=fontname)
    y += title_size * 1.8

    for line in lines:
        if y + line_height > page_height - margin:
            page = doc.new_page(width=page_width, height=page_height)
            y = margin
        page.insert_text((margin, y), line, fontsize=body_size, fontname=fontname)
        y += line_height

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
