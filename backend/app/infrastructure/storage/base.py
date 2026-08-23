"""
File storage abstraction.

The spec calls for resumes/assignments/submissions/evaluation reports to
live in AWS S3, with only extracted metadata in the database. Previously
this codebase parsed uploaded files to text and then discarded the bytes
entirely - "Resume URL (S3)" was a field in nobody's schema, and
"Download Resume" / the final campaign archive had nothing to serve.

FileStorage is the seam that fixes that without hard-coupling the app to
AWS: LocalFileStorage (default, zero external deps) and S3FileStorage
(boto3, used when AWS credentials are configured) both implement the same
interface, so callers never know which backend is active.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class FileStorage(ABC):
    """Content-addressable-ish blob storage: save bytes under a key,
    get them back, get a URL/path a human or the frontend can use, and
    delete them (for retention-policy cleanup)."""

    @abstractmethod
    async def save(self, key: str, content: bytes, content_type: str | None = None) -> str:
        """Persist `content` under `key`. Returns the stored object's
        URL (S3) or path (local) - what gets written to the DB."""

    @abstractmethod
    async def get_url(self, key: str) -> str:
        """Return a URL/path the candidate/HR can use to fetch the file.
        For S3 this should be a presigned URL (time-limited); for local
        storage it's a path served via the download endpoint."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the object. Used by retention cleanup. Must be
        idempotent - deleting an already-gone key is not an error."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...

    @abstractmethod
    async def read(self, key: str) -> bytes:
        """Return the stored bytes. Used by the download endpoints, which
        stream through the API rather than exposing raw storage URLs."""
