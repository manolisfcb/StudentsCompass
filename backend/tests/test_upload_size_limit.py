"""Uploads are bounded before they cost memory, disk or a provider call.

The limit used to be checked after ``await file.read()``, so the multipart
parser had already spooled the whole body; and the only early gate was
``Content-Length``, which a chunked request simply omits. The post endpoint had
no byte or type cap at all, and a DOCX passing the file-size cap could still
expand to gigabytes of XML.
"""
from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import UploadFile
from httpx import ASGITransport, AsyncClient
from starlette.datastructures import Headers

import app.routes.postRoute as post_route
import app.routes.resumeRoute as resume_route
from app.core.uploads import ensure_allowed_upload, read_upload_within_limit
from app.middleware.body_size import RequestBodySizeLimitMiddleware

PDF_BYTES = b"%PDF-1.4 minimal"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"body"


# --------------------------------------------------------------------------
# The route-level budget
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_oversized_cv_upload_is_rejected(client: AsyncClient, auth_headers: dict, monkeypatch):
    monkeypatch.setattr(resume_route, "MAX_UPLOAD_BYTES", 50)

    response = await client.post(
        "/api/v1/profile/cv/upload",
        headers=auth_headers,
        files={"cv": ("resume.pdf", PDF_BYTES + b"x" * 500, "application/pdf")},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_a_small_valid_cv_still_works(client: AsyncClient, auth_headers: dict, monkeypatch):
    """The cap must not be the kind that also blocks the legitimate case."""

    class FakeStorage:
        async def upload_file(self, file_bytes, file_name, content_type="", folder="", owner_id=None):
            return {
                "file_key": "resumes/k",
                "file_url": "https://storage.example/resumes/k",
                "bucket": "b",
            }

        async def download_file(self, file_key):
            return b""

        async def delete_file(self, file_key):
            return True

    monkeypatch.setenv("BUCKET_NAME", "test-resume-bucket")
    monkeypatch.setattr(
        "app.services.resumes.resumeService.get_storage_service", lambda: FakeStorage()
    )

    response = await client.post(
        "/api/v1/profile/cv/upload",
        headers=auth_headers,
        files={"cv": ("resume.pdf", io.BytesIO(PDF_BYTES), "application/pdf")},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_a_payload_that_is_not_what_it_claims_is_rejected(
    client: AsyncClient, auth_headers: dict
):
    response = await client.post(
        "/api/v1/profile/cv/upload",
        headers=auth_headers,
        files={"cv": ("resume.pdf", io.BytesIO(b"MZ\x90\x00 not a pdf"), "application/pdf")},
    )

    assert response.status_code == 400
    assert "declared type" in response.json()["detail"]


@pytest.mark.asyncio
async def test_oversized_post_media_is_rejected(client: AsyncClient, auth_headers: dict, monkeypatch):
    """This endpoint had no byte cap at all before it hit disk and the provider."""
    monkeypatch.setattr(post_route, "MAX_POST_UPLOAD_BYTES", 50)

    response = await client.post(
        "/api/v1/upload_post",
        headers=auth_headers,
        data={"caption": "x"},
        files={"file": ("photo.png", io.BytesIO(PNG_BYTES + b"x" * 500), "image/png")},
    )

    assert response.status_code == 413


@pytest.mark.asyncio
async def test_post_media_type_outside_the_allowlist_is_rejected(
    client: AsyncClient, auth_headers: dict
):
    response = await client.post(
        "/api/v1/upload_post",
        headers=auth_headers,
        data={"caption": "x"},
        files={"file": ("payload.svg", io.BytesIO(b"<svg/>"), "image/svg+xml")},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_post_media_signature_must_match_declared_type(
    client: AsyncClient, auth_headers: dict
):
    response = await client.post(
        "/api/v1/upload_post",
        headers=auth_headers,
        data={"caption": "x"},
        files={"file": ("photo.png", io.BytesIO(b"not a png at all"), "image/png")},
    )

    assert response.status_code == 400


# --------------------------------------------------------------------------
# Incremental read
# --------------------------------------------------------------------------


def _upload(data: bytes, content_type: str = "application/pdf") -> UploadFile:
    return UploadFile(
        filename="f.pdf",
        file=io.BytesIO(data),
        headers=Headers({"content-type": content_type}),
    )


@pytest.mark.asyncio
async def test_read_stops_at_the_budget():
    with pytest.raises(Exception) as raised:
        await read_upload_within_limit(_upload(b"x" * 5_000), 1_000)
    assert raised.value.status_code == 413


@pytest.mark.asyncio
async def test_read_returns_a_payload_at_exactly_the_budget():
    data = b"x" * 1_000
    assert await read_upload_within_limit(_upload(data), 1_000) == data


def test_signature_check_accepts_a_real_pdf():
    assert (
        ensure_allowed_upload(
            data=PDF_BYTES,
            content_type="application/pdf",
            allowed_content_types=frozenset({"application/pdf"}),
        )
        == "application/pdf"
    )


def test_signature_check_ignores_content_type_parameters():
    assert (
        ensure_allowed_upload(
            data=PNG_BYTES,
            content_type="image/png; charset=binary",
            allowed_content_types=frozenset({"image/png"}),
        )
        == "image/png"
    )


# --------------------------------------------------------------------------
# The raw body, before the multipart parser
# --------------------------------------------------------------------------


def _echo_app_reading_the_body(seen: list[int]):
    """A minimal ASGI app that consumes the whole body, like the parser does."""

    async def app(scope, receive, send):
        total = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                break
            total += len(message.get("body", b""))
            if not message.get("more_body"):
                break
        seen.append(total)
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": b"ok"})

    return app


@pytest.mark.asyncio
async def test_declared_length_over_budget_is_refused_without_reading():
    seen: list[int] = []
    app = RequestBodySizeLimitMiddleware(
        _echo_app_reading_the_body(seen), default_max_bytes=100
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        response = await http.post("/anything", content=b"x" * 1_000)

    assert response.status_code == 413
    assert seen == [], "the body must not be read at all when it is declared too large"


@pytest.mark.asyncio
async def test_a_chunked_body_with_no_content_length_is_still_bounded():
    """The case the old Content-Length pre-check could not see."""
    seen: list[int] = []
    app = RequestBodySizeLimitMiddleware(
        _echo_app_reading_the_body(seen), default_max_bytes=1_000
    )

    async def flood():
        for _ in range(50):
            yield b"x" * 1_000

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        response = await http.post("/anything", content=flood())

    assert response.status_code == 413
    assert seen == [], "the app must never see a completed oversized body"


@pytest.mark.asyncio
async def test_a_body_within_budget_passes_through():
    seen: list[int] = []
    app = RequestBodySizeLimitMiddleware(
        _echo_app_reading_the_body(seen), default_max_bytes=1_000
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as http:
        response = await http.post("/anything", content=b"x" * 500)

    assert response.status_code == 200
    assert seen == [500]


def test_the_longest_matching_prefix_wins():
    middleware = RequestBodySizeLimitMiddleware(
        None,
        default_max_bytes=10,
        budgets={"/api": 100, "/api/v1/profile/cv/": 5_000},
    )

    assert middleware.limit_for("/api/v1/profile/cv/upload") == 5_000
    assert middleware.limit_for("/api/v1/posts") == 100
    assert middleware.limit_for("/health") == 10


@pytest.mark.asyncio
async def test_the_running_app_bounds_a_non_upload_route(client: AsyncClient, auth_headers: dict):
    """The default budget applies to everything that is not an upload route."""
    from app.config import MAX_REQUEST_BODY_BYTES

    response = await client.post(
        "/api/v1/posts",
        headers=auth_headers,
        content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
    )

    assert response.status_code == 413


# --------------------------------------------------------------------------
# DOCX expansion
# --------------------------------------------------------------------------


def _docx_with_document(xml: bytes) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_a_normal_docx_is_still_read():
    from app.core.resume_analyzer.resume_text_extractor import extract_resume_text_from_bytes

    xml = (
        b'<?xml version="1.0"?>'
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b"<w:p><w:t>Hello resume</w:t></w:p></w:document>"
    )
    text = await extract_resume_text_from_bytes(
        _docx_with_document(xml),
        filename="cv.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert text == "Hello resume"


@pytest.mark.asyncio
async def test_a_small_archive_that_expands_hugely_fails_in_a_controlled_way(monkeypatch):
    """A cap on the compressed file says nothing about the cost of expanding it."""
    import app.core.resume_analyzer.resume_text_extractor as extractor
    from app.core.resume_analyzer.resume_text_extractor import extract_resume_text_from_bytes

    monkeypatch.setattr(extractor, "MAX_DOCX_EXPANDED_BYTES", 10_000)

    # Compresses to a few hundred bytes, expands to 5 MB.
    bomb = _docx_with_document(b"<w:document>" + b"A" * 5_000_000 + b"</w:document>")
    assert len(bomb) < 100_000, "the uploaded archive itself is small"

    # Pinned at the guard, not at the outcome: this XML would fail to parse
    # anyway, so asserting only on the empty result would pass with no guard.
    with zipfile.ZipFile(io.BytesIO(bomb)) as archive:
        with pytest.raises(extractor.DocxExpansionTooLarge):
            extractor._read_document_part_within_limit(archive)

    text = await extract_resume_text_from_bytes(
        bomb,
        filename="cv.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert text == ""


def test_an_implausible_compression_ratio_is_refused(monkeypatch):
    import app.core.resume_analyzer.resume_text_extractor as extractor
    from app.core.resume_analyzer.resume_text_extractor import (
        DocxExpansionTooLarge,
        _read_document_part_within_limit,
    )

    monkeypatch.setattr(extractor, "MAX_DOCX_COMPRESSION_RATIO", 5)

    bomb = _docx_with_document(b"A" * 1_000_000)
    with zipfile.ZipFile(io.BytesIO(bomb)) as archive:
        with pytest.raises(DocxExpansionTooLarge, match="compression ratio"):
            _read_document_part_within_limit(archive)


def test_an_archive_without_a_document_part_is_refused():
    from app.core.resume_analyzer.resume_text_extractor import (
        DocxExpansionTooLarge,
        _read_document_part_within_limit,
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("not/what/we/want.xml", b"<a/>")

    with zipfile.ZipFile(io.BytesIO(buffer.getvalue())) as archive:
        with pytest.raises(DocxExpansionTooLarge):
            _read_document_part_within_limit(archive)
