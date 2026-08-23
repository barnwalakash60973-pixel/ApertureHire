from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings
from app.infrastructure.storage.base import FileStorage
from app.infrastructure.storage.local_storage import LocalFileStorage


@lru_cache(maxsize=1)
def get_file_storage() -> FileStorage:
    from app.core.config import get_settings

    settings: Settings = get_settings()

    if settings.storage_backend == "s3":
        if not (settings.aws_s3_bucket and settings.aws_access_key_id and settings.aws_secret_access_key):
            raise RuntimeError(
                "STORAGE_BACKEND=s3 but AWS_S3_BUCKET/AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY "
                "are not fully set. Fill in .env or switch STORAGE_BACKEND back to 'local'."
            )
        from app.infrastructure.storage.s3_storage import S3FileStorage

        return S3FileStorage(
            bucket=settings.aws_s3_bucket,
            region=settings.aws_region,
            access_key=settings.aws_access_key_id,
            secret_key=settings.aws_secret_access_key,
            endpoint_url=settings.aws_s3_endpoint_url or None,
        )

    return LocalFileStorage(settings.local_storage_dir)
