from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET

from app.config import MAX_DOCX_COMPRESSION_RATIO, MAX_DOCX_EXPANDED_BYTES
from app.core.resume_analyzer.read_pdf_data import extract_text_from_pdf, shutdown_pdf_executor

LOGGER = logging.getLogger(__name__)

DOCX_DOCUMENT_PART = "word/document.xml"

_docx_executor: ThreadPoolExecutor | None = None


def _get_docx_executor() -> ThreadPoolExecutor:
    global _docx_executor
    if _docx_executor is None:
        _docx_executor = ThreadPoolExecutor(max_workers=3)
    return _docx_executor


def shutdown_resume_text_extractors() -> None:
    global _docx_executor
    if _docx_executor is not None:
        _docx_executor.shutdown(wait=True)
        _docx_executor = None
    shutdown_pdf_executor()


class DocxExpansionTooLarge(Exception):
    """The archive declares, or produces, more data than the budget allows."""


def _read_document_part_within_limit(archive: zipfile.ZipFile) -> bytes:
    """Read ``word/document.xml`` without trusting what the archive says.

    A size cap on the uploaded file bounds the *compressed* bytes and nothing
    else: a few kilobytes of ZIP can declare gigabytes of XML, and reading it
    exhausts memory on a request that passed every earlier check. So the
    declared size is rejected up front, the compression ratio is rejected as
    implausible, and the actual read is still bounded — the header is attacker-
    controlled too, and only the third check does not depend on it.
    """
    try:
        info = archive.getinfo(DOCX_DOCUMENT_PART)
    except KeyError:
        raise DocxExpansionTooLarge("not a Word document") from None

    if info.file_size > MAX_DOCX_EXPANDED_BYTES:
        raise DocxExpansionTooLarge(
            f"declares {info.file_size} bytes of XML, over the budget"
        )
    if info.compress_size and (
        info.file_size / info.compress_size > MAX_DOCX_COMPRESSION_RATIO
    ):
        raise DocxExpansionTooLarge("compression ratio is not plausible for a document")

    with archive.open(DOCX_DOCUMENT_PART) as part:
        # One byte past the budget is enough to know it was exceeded, and it
        # catches a header that understated the real size.
        data = part.read(MAX_DOCX_EXPANDED_BYTES + 1)
    if len(data) > MAX_DOCX_EXPANDED_BYTES:
        raise DocxExpansionTooLarge("expanded beyond the budget while reading")
    return data


def _extract_text_from_docx_sync(docx_path: str) -> str:
    try:
        with zipfile.ZipFile(docx_path) as zf:
            xml_data = _read_document_part_within_limit(zf)
        root = ET.fromstring(xml_data)
        paragraphs: list[str] = []
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        for paragraph in root.iter(f"{ns}p"):
            texts = [node.text for node in paragraph.iter(f"{ns}t") if node.text]
            if texts:
                paragraphs.append("".join(texts))
        return "\n".join(paragraphs).strip()
    except DocxExpansionTooLarge as error:
        # Controlled failure: the caller gets "no text", same as any unreadable
        # document, but the reason is on record because this one is an attack
        # shape rather than a corrupt file.
        LOGGER.warning("Refused to expand DOCX: %s", error)
        return ""
    except Exception:
        return ""


async def extract_resume_text_from_bytes(
    file_bytes: bytes,
    *,
    filename: str,
    content_type: str,
) -> str:
    suffix = os.path.splitext(filename or "")[-1].lower() or ".pdf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file_bytes)
        temp_path = tmp.name

    try:
        if content_type == "application/pdf" or suffix == ".pdf":
            return await extract_text_from_pdf(temp_path)
        if (
            content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or suffix == ".docx"
        ):
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(_get_docx_executor(), _extract_text_from_docx_sync, temp_path)
        return ""
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
