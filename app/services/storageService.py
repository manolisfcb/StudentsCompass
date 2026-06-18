from __future__ import annotations

import os
from typing import Protocol


class StorageService(Protocol):
    async def upload_file(
        self,
        file_bytes: bytes,
        file_name: str,
        content_type: str = "application/octet-stream",
        folder: str = "resumes",
    ) -> dict:
        ...

    async def download_file(self, file_key: str) -> bytes:
        ...

    async def delete_file(self, file_key: str) -> bool:
        ...


def get_storage_service(*, bucket_name: str | None = None) -> StorageService:
    from app.services.s3Service import S3Service

    return S3Service(bucket_name=bucket_name)


def get_resume_storage_location_id() -> str | None:
    return os.getenv("BUCKET_NAME")


def get_resource_storage_location_id() -> str | None:
    return os.getenv("RESOURCES_BUCKET_NAME") or os.getenv("BUCKET_NAME")
