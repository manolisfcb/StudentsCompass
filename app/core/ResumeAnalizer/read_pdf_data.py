import fitz
import os 
from dotenv import load_dotenv
import logging

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
load_dotenv()


def extract_text_from_pdf(upload_file: str) -> str:
    """Extracts text from a PDF file using PyMuPDF (fitz)."""
    text = ""
    try:
        with fitz.open(upload_file) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        LOGGER.error(f"Error reading {upload_file}: {e}")
    return text