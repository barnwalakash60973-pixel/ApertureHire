"""
S3 FileStorage backend - what the flowchart actually specifies
("Resume Stored in AWS S3", final archive under
Campaign/Selected Candidates/<name>/...).

Not wired as the default because this sandbox/dev environment has no AWS
credentials and no network route to amazonaws.com to ever test it
against a real bucket. The interface and call sites are identical to
LocalFileStorage though (see base.py) - set STORAGE_BACKEND=s3 plus the
aws_* settings in .env and this activates with no other code changes.
boto3 is a sync SDK, so calls are pushed to a thread to avoid blocking
the event loop.
"""

from __future__ import annotations

import asyncio
from functools import cached_property
from typing import Any


class S3FileStorage:
    def __init__(self, bucket: str, region: str, access_key: str, secret_key: str, endpoint_url: str | None = None) -> None:
        self._bucket = bucket
        self._region = region
        self._access_key = access_key
        self._secret_key = secret_key
        self._endpoint_url = endpoint_url or None

    @cached_property
    def _client(self) -> Any:
        import boto3  # imported lazily: only required if S3 backend is actually selected

        return boto3.client(
            "s3",
            region_name=self._region,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            endpoint_url=self._endpoint_url,
        )

    async def save(self, key: str, content: bytes, content_type: str | None = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}
        await asyncio.to_thread(self._client.put_object, Bucket=self._bucket, Key=key, Body=content, **extra)
        return f"s3://{self._bucket}/{key}"

    async def get_url(self, key: str) -> str:
        # Presigned, time-limited - never a public/permanent link, since
        # resumes and evaluation reports are personal data.
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=3600,
        )

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)

    async def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            await asyncio.to_thread(self._client.head_object, Bucket=self._bucket, Key=key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey"):
                return False
            raise

    async def read(self, key: str) -> bytes:
        obj = await asyncio.to_thread(self._client.get_object, Bucket=self._bucket, Key=key)
        return await asyncio.to_thread(obj["Body"].read)
