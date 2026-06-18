import fitz
from dotenv import load_dotenv
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
load_dotenv()

# Thread pool for CPU-bound PDF extraction
_pdf_executor: ThreadPoolExecutor | None = None


def _get_pdf_executor() -> ThreadPoolExecutor:
    global _pdf_executor
    if _pdf_executor is None:
        _pdf_executor = ThreadPoolExecutor(max_workers=5)
    return _pdf_executor


def shutdown_pdf_executor() -> None:
    global _pdf_executor
    if _pdf_executor is not None:
        _pdf_executor.shutdown(wait=True)
        _pdf_executor = None


def _extract_text_from_pdf_sync(upload_file: str) -> str:
    """Synchronous helper to extract text from PDF using PyMuPDF (fitz)."""
    text = ""
    try:
        with fitz.open(upload_file) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        LOGGER.error(f"Error reading {upload_file}: {e}")
    return text


async def extract_text_from_pdf(upload_file: str) -> str:
    """Async wrapper to extract text from a PDF file using PyMuPDF (fitz)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_get_pdf_executor(), _extract_text_from_pdf_sync, upload_file)
