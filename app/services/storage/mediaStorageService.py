from __future__ import annotations

import asyncio
from dataclasses import dataclass
import mimetypes
import os
from pathlib import Path
import shutil
import tempfile
from typing import Protocol

from fastapi import UploadFile
from imagekitio import ImageKit

from app.services.storage.storageService import (
    StorageService,
    get_media_storage_location_id,
    get_storage_service,
)


@dataclass(frozen=True)
class MediaUploadResult:
    url: str
    file_type: str
    name: str


class MediaStorageService(Protocol):
    async def upload_media(self, file: UploadFile, file_name: str, folder: str = "images/") -> MediaUploadResult:
        ...


class ImageKitMediaStorageService:
    def __init__(self, private_key: str | None = None):
        self.imagekit = ImageKit(private_key=private_key or os.environ.get("IMAGEKIT_PRIVATE_KEY"))

    async def upload_media(self, file: UploadFile, file_name: str, folder: str = "images/") -> MediaUploadResult:
        return await asyncio.to_thread(self._upload_media_sync, file, file_name, folder)

    def _upload_media_sync(self, file: UploadFile, file_name: str, folder: str) -> MediaUploadResult:
        temp_file_path: str | None = None
        try:
            suffix = os.path.splitext(file.filename or "")[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
                temp_file_path = temp_file.name
                shutil.copyfileobj(file.file, temp_file)

            upload_response = self.imagekit.files.upload(
                file=Path(temp_file_path),
                file_name=file_name,
                folder=folder,
                tags=["StudentsCompass-Uploads"],
            )
            return MediaUploadResult(
                url=upload_response.url,
                file_type=upload_response.file_type,
                name=upload_response.name,
            )
        finally:
            if temp_file_path:
                try:
                    os.unlink(temp_file_path)
                except FileNotFoundError:
                    pass


class S3MediaStorageService:
    def __init__(self, storage_service: StorageService | None = None):
        media_bucket = get_media_storage_location_id()
        self.storage_service = storage_service or get_storage_service(bucket_name=media_bucket)

    async def upload_media(self, file: UploadFile, file_name: str, folder: str = "images/") -> MediaUploadResult:
        raw_name = file_name or file.filename or "media_upload"
        safe_name = raw_name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] or "media_upload"
        content_type = file.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"
        upload_result = await self.storage_service.upload_file(
            file_bytes=await file.read(),
            file_name=safe_name,
            content_type=content_type,
            folder=folder.strip("/") or "images",
        )
        return MediaUploadResult(
            url=upload_result["file_url"],
            file_type=_file_type_from_content_type(content_type),
            name=safe_name,
        )


def _file_type_from_content_type(content_type: str) -> str:
    media_type = (content_type or "").split("/", 1)[0].strip().lower()
    return media_type or "file"


def get_media_storage_provider() -> str:
    return (os.getenv("MEDIA_STORAGE_PROVIDER") or "imagekit").strip().lower()


def get_media_storage_service(provider: str | None = None) -> MediaStorageService:
    selected_provider = (provider or get_media_storage_provider()).strip().lower()
    if selected_provider == "imagekit":
        return ImageKitMediaStorageService()
    if selected_provider == "s3":
        return S3MediaStorageService()
    raise ValueError(f"Unsupported media storage provider: {selected_provider}")
