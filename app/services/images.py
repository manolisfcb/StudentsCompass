from fastapi import UploadFile

from app.services.mediaStorageService import MediaUploadResult, get_media_storage_service


def upload_media(file: UploadFile, file_name: str, folder: str = "images/") -> MediaUploadResult:
    return get_media_storage_service().upload_media(file=file, file_name=file_name, folder=folder)
