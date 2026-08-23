"""
Factory that selects the right DocumentParser implementation by file
extension. This is the single place that needs to change if a new format
(e.g. .txt, .md) is added later.
"""

from __future__ import annotations

from pathlib import Path

from app.application.interfaces import DocumentParser
from app.core.exceptions import UnsupportedFileTypeError
from app.infrastructure.parsers.docx_parser import DocxParser
from app.infrastructure.parsers.pdf_parser import PdfParser

_PARSERS: dict[str, DocumentParser] = {
    ".docx": DocxParser(),
    ".pdf": PdfParser(),
}


def get_parser_for(file_path: str) -> DocumentParser:
    """Return the DocumentParser matching the file's extension.

    Raises:
        UnsupportedFileTypeError: if the extension isn't .docx or .pdf.
    """
    suffix = Path(file_path).suffix.lower()
    parser = _PARSERS.get(suffix)
    if parser is None:
        raise UnsupportedFileTypeError(
            f"Unsupported file type '{suffix}'. Only .docx and .pdf are supported."
        )
    return parser
