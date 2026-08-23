"""
ZIP project-submission text extraction.

The spec's candidate submission portal accepts PDF/DOCX/ZIP, but the ZIP
case had no handler - the endpoint rejected .zip outright and the
evaluator only ever saw single-document submissions. A ZIP is the normal
shape of a real take-home (a repo), so this walks the archive and
concatenates the readable text files into one document the existing
3-call evaluation pipeline can grade unchanged.

Deliberate limits, because a ZIP is attacker-controlled input from an
unauthenticated endpoint:
  - only known text/source extensions are read (no binaries, no images)
  - vendor/build directories are skipped (node_modules, .git, venv, ...)
  - per-file and total byte caps, plus a max file count, to bound the
    zip-bomb blast radius
  - path traversal entries ("../", absolute paths) are skipped rather
    than trusted, since we never write extracted members to disk anyway

This is text CONCATENATION, not repo comprehension - the evaluator sees
files in archive order with path headers, not a dependency graph. Good
enough to grade reasoning and correctness; it will not reason about
project structure the way a human reviewer opening the repo would.
"""

from __future__ import annotations

import asyncio
import zipfile
from pathlib import PurePosixPath

_TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".rb", ".php",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".kt", ".swift", ".scala", ".sh", ".sql",
    ".md", ".txt", ".rst", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
    ".html", ".css", ".scss", ".env.example", ".dockerfile", ".tf",
}

_SKIP_DIR_PARTS = {
    "node_modules", ".git", ".venv", "venv", "__pycache__", "dist", "build",
    ".next", "target", ".idea", ".vscode", "site-packages", ".mypy_cache",
    ".pytest_cache", "vendor", "coverage",
}

_MAX_FILES = 300
_MAX_FILE_BYTES = 200_000
_MAX_TOTAL_BYTES = 2_000_000


def _is_readable(name: str) -> bool:
    path = PurePosixPath(name)
    if name.endswith("/"):
        return False
    # Reject traversal / absolute paths outright.
    if path.is_absolute() or ".." in path.parts:
        return False
    if any(part in _SKIP_DIR_PARTS for part in path.parts[:-1]):
        return False
    lowered = path.name.lower()
    if lowered in ("dockerfile", "makefile", "readme", ".gitignore"):
        return True
    return any(lowered.endswith(ext) for ext in _TEXT_EXTENSIONS)


def _extract_sync(zip_path: str) -> str:
    chunks: list[str] = []
    total = 0
    count = 0

    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            if count >= _MAX_FILES or total >= _MAX_TOTAL_BYTES:
                chunks.append("\n[... archive truncated: file/size limit reached ...]\n")
                break
            if not _is_readable(info.filename):
                continue
            # Guard against a small compressed entry expanding hugely.
            if info.file_size > _MAX_FILE_BYTES:
                continue

            try:
                raw = archive.read(info)
            except (zipfile.BadZipFile, RuntimeError):
                continue

            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue

            chunks.append(f"\n===== FILE: {info.filename} =====\n{text}")
            total += len(raw)
            count += 1

    return "\n".join(chunks)


async def extract_text_from_zip(zip_path: str) -> str:
    """Async wrapper - zipfile is sync and CPU/IO-bound, so it runs off
    the event loop."""
    return await asyncio.to_thread(_extract_sync, zip_path)
