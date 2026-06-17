from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile
from typing import Protocol

from fastapi import UploadFile
from imagekitio import ImageKit


@dataclass(frozen=True)
class MediaUploadResult:
    url: str
    file_type: str
    name: str


class MediaStorageService(Protocol):
    def upload_media(self, file: UploadFile, file_name: str, folder: str = "images/") -> MediaUploadResult:
        ...


class ImageKitMediaStorageService:
    def __init__(self, private_key: str | None = None):
        self.imagekit = ImageKit(private_key=private_key or os.environ.get("IMAGEKIT_PRIVATE_KEY"))

    def upload_media(self, file: UploadFile, file_name: str, folder: str = "images/") -> MediaUploadResult:
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


def get_media_storage_provider() -> str:
    return (os.getenv("MEDIA_STORAGE_PROVIDER") or "imagekit").strip().lower()


def get_media_storage_service(provider: str | None = None) -> MediaStorageService:
    selected_provider = (provider or get_media_storage_provider()).strip().lower()
    if selected_provider == "imagekit":
        return ImageKitMediaStorageService()
    raise ValueError(f"Unsupported media storage provider: {selected_provider}")
