from dotenv import load_dotenv
import os
from imagekitio import ImageKit
from pathlib import Path
from imagekitio.types.file_upload_response import FileUploadResponse
import tempfile
import shutil
from fastapi import UploadFile
load_dotenv()

imagekit = ImageKit(
    private_key=os.environ.get("IMAGEKIT_PRIVATE_KEY")
)

def upload_media(file: UploadFile, file_name: str, folder: str = "images/") -> FileUploadResponse:
    temp_file_path = None
    
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
        
        upload_response = imagekit.files.upload(
            file=Path(temp_file_path),
            file_name=file_name,
            folder=folder,
            tags=["StudentsCompass-Uploads"]
        )
        return upload_response
    except Exception as e:
        raise e
