"""Bounding an upload before it costs anything.

The size check used to happen after ``await file.read()``, which is too late in
two different ways. By then the whole body had already been through the
multipart parser and spooled — to memory, then to a temp file — so the work the
limit was supposed to prevent had already been done. And the pre-check it
relied on, ``Content-Length``, is optional: a chunked request simply omits it
and sailed past.

So the limit is enforced in three places, each for a reason the others cannot
cover:

* :mod:`app.middleware.body_size` caps the raw ASGI body *before* the multipart
  parser sees it, which is the only point where a chunked flood can be stopped.
* :func:`read_upload_within_limit` reads the parsed part incrementally and stops
  at one byte past the budget, so the route never materialises more than that.
* :func:`ensure_allowed_upload` rejects a declared type the route does not serve
  and a payload whose leading bytes contradict that type.
"""
from __future__ import annotations

from fastapi import HTTPException, UploadFile

# Large enough that a single read is cheap, small enough that overshooting the
# budget costs at most this much memory.
CHUNK_SIZE = 64 * 1024

_ZIP = b"PK\x03\x04"
_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _starts_with(*prefixes: bytes):
    return lambda data: any(data.startswith(prefix) for prefix in prefixes)


def _is_riff(fourcc: bytes):
    # RIFF containers name their real format at offset 8, so the leading bytes
    # alone would also accept a WAV file claiming to be an image.
    return lambda data: data[:4] == b"RIFF" and data[8:12] == fourcc


def _is_iso_media(data: bytes) -> bool:
    # MP4 and MOV are ISO base media: a box header, then "ftyp" at offset 4.
    return data[4:8] == b"ftyp"


# What a file of a given type must actually look like. The declared
# Content-Type comes from the client and is worth nothing on its own, so the
# payload has to agree with it before anything spends disk or a provider call.
_SIGNATURES = {
    "application/pdf": _starts_with(b"%PDF-"),
    # DOCX is a ZIP container.
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": _starts_with(_ZIP),
    # Legacy .doc is an OLE2 compound file. ZIP is accepted too: browsers derive
    # the type from the extension, so a .docx saved as .doc arrives labelled
    # this way and is a perfectly ordinary document, not an attack.
    "application/msword": _starts_with(_OLE2, _ZIP),
    "image/png": _starts_with(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": _starts_with(b"\xff\xd8\xff"),
    "image/gif": _starts_with(b"GIF87a", b"GIF89a"),
    "image/webp": _is_riff(b"WEBP"),
    "video/mp4": _is_iso_media,
    "video/quicktime": _is_iso_media,
    "video/webm": _starts_with(b"\x1a\x45\xdf\xa3"),
}


def too_large(limit_bytes: int) -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=f"File is too large. Maximum allowed size is {limit_bytes // 1_000_000} MB.",
    )


async def read_upload_within_limit(upload: UploadFile, limit_bytes: int) -> bytes:
    """Read at most ``limit_bytes``; raise 413 the moment that is exceeded.

    Reads in chunks and stops as soon as the total passes the budget, so an
    oversized upload never occupies more than one chunk beyond it.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limit_bytes:
            raise too_large(limit_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


def ensure_allowed_upload(
    *,
    data: bytes,
    content_type: str | None,
    allowed_content_types: frozenset[str],
    what: str = "file",
) -> str:
    """Validate the declared type and check the bytes agree with it.

    Returns the accepted content type. Raises 400 when the type is not one this
    route serves, or when the payload's signature contradicts it — a PDF
    endpoint should not accept an executable that merely claims to be a PDF.
    """
    declared = (content_type or "").split(";", 1)[0].strip().lower()
    if declared not in allowed_content_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported {what} type. Allowed: "
            + ", ".join(sorted(allowed_content_types)),
        )

    matches_signature = _SIGNATURES.get(declared)
    if matches_signature and not matches_signature(data):
        raise HTTPException(
            status_code=400,
            detail=f"The uploaded {what} does not match its declared type.",
        )

    return declared
