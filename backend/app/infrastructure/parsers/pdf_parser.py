"""
PDF parser implementing the DocumentParser port, backed by PyMuPDF (fitz).

PyMuPDF is fast and handles most text-based PDFs well. It does NOT do OCR -
scanned/image-only PDFs will yield no text; callers should treat an empty
result as a parsing failure rather than "zero questions found".
"""

from __future__ import annotations

import asyncio

import fitz  # PyMuPDF

from app.core.exceptions import DocumentParsingError
from app.core.logging import get_logger

logger = get_logger(__name__)


class PdfParser:
    """Extracts text from a .pdf file, page by page, in reading order."""

    async def extract_text(self, file_path: str) -> str:
        try:
            return await asyncio.to_thread(self._extract_sync, file_path)
        except DocumentParsingError:
            raise
        except Exception as e:
            logger.exception("Failed to parse PDF: %s", file_path)
            raise DocumentParsingError(f"Could not read PDF file: {e}") from e

    @staticmethod
    def _extract_sync(file_path: str) -> str:
        text_parts: list[str] = []
        with fitz.open(file_path) as document:
            for page in document:
                page_text = page.get_text("text")
                if page_text.strip():
                    text_parts.append(page_text)

        text = "\n".join(text_parts)
        if not text.strip():
            raise DocumentParsingError(
                f"No extractable text found in {file_path} "
                "(it may be a scanned/image-only PDF requiring OCR)."
            )
        return text
