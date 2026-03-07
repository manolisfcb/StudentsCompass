from __future__ import annotations

import asyncio
import os
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from xml.etree import ElementTree as ET

from app.core.ResumeAnalizer.read_pdf_data import extract_text_from_pdf

_docx_executor = ThreadPoolExecutor(max_workers=3)


def _extract_text_from_docx_sync(docx_path: str) -> str:
    try:
        with zipfile.ZipFile(docx_path) as zf:
            xml_data = zf.read("word/document.xml")
        root = ET.fromstring(xml_data)
        paragraphs: list[str] = []
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        for paragraph in root.iter(f"{ns}p"):
            texts = [node.text for node in paragraph.iter(f"{ns}t") if node.text]
            if texts:
                paragraphs.append("".join(texts))
        return "\n".join(paragraphs).strip()
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
            return await loop.run_in_executor(_docx_executor, _extract_text_from_docx_sync, temp_path)
        return ""
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
