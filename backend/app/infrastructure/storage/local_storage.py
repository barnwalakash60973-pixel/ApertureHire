"""
Local-filesystem FileStorage backend. Default backend - zero external
dependencies, zero cloud account needed to run the app end to end. Not
what you deploy to production with (no redundancy, no CDN, disk-bound),
but it makes "resume/submission/report actually persists and is
downloadable" true today, and is a drop-in swap for S3FileStorage later
(same interface, same call sites) once AWS credentials exist.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from app.infrastructure.storage.base import FileStorage


class LocalFileStorage(FileStorage):
    def __init__(self, root_dir: str) -> None:
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        # key is always produced by our own code (campaign/candidate ids +
        # uuid, never raw user filenames) - see storage_keys.py - so this
        # is not attacker-controlled path traversal surface.
        path = (self._root / key).resolve()
        if self._root.resolve() not in path.parents and path != self._root.resolve():
            raise ValueError(f"Invalid storage key '{key}' escapes storage root.")
        return path

    async def save(self, key: str, content: bytes, content_type: str | None = None) -> str:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)
        return str(path)

    async def get_url(self, key: str) -> str:
        # Local mode has no HTTP file server built in - the download
        # endpoints stream bytes directly (see routes_campaigns.py),
        # so "url" here is just the storage key the endpoint needs.
        return key

    async def delete(self, key: str) -> None:
        path = self._path_for(key)
        await asyncio.to_thread(path.unlink, missing_ok=True)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._path_for(key).exists)

    async def read(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path_for(key).read_bytes)
