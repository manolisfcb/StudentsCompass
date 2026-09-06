"""Storage keys that identify one object and one object only.

Resume keys used to be ``<timestamp to the second>_<filename>``, and media keys
were the sanitised filename on its own. Both are functions of things two users
share: two people uploading ``cv.pdf`` in the same second produced the same key,
and ``put_object`` silently overwrites, so one upload replaced the other's file.
Every reader that later followed the stored key — the analyser, the recruiter
download — got the wrong document.

A key built here is opaque and unique by construction: a random UUID, optionally
under the owner's own prefix so an object can be attributed and inventoried
without parsing a name. The human-readable name is not part of the key; it lives
in the database column that already holds it (``original_filename``), which also
keeps a hostile filename out of the object store entirely.

Keys already stored keep working: nothing here reads or rewrites them, and the
readers resolve whatever key the row carries.
"""
from __future__ import annotations

import re
import uuid

# Extensions are the one part of the key derived from user input, so they are
# whitelisted by shape rather than sanitised: short, lowercase, alphanumeric.
_EXTENSION = re.compile(r"^[a-z0-9]{1,10}$")
_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")

DEFAULT_FOLDER = "uploads"


def _safe_folder(folder: str | None) -> str:
    """Keep a caller-supplied prefix, minus anything that could escape it."""
    segments = [segment for segment in (folder or "").split("/") if segment]
    kept = [segment for segment in segments if _SAFE_SEGMENT.match(segment) and segment not in {".", ".."}]
    return "/".join(kept) or DEFAULT_FOLDER


def _owner_segment(owner_id) -> str | None:
    if owner_id is None:
        return None
    candidate = str(owner_id)
    return candidate if _SAFE_SEGMENT.match(candidate) else None


def extension_for(file_name: str | None) -> str:
    """``".pdf"`` for ``"report.PDF"``; empty string when there is nothing safe."""
    if not file_name or "." not in file_name:
        return ""
    suffix = file_name.rsplit(".", 1)[-1].strip().lower()
    return f".{suffix}" if _EXTENSION.match(suffix) else ""


def build_object_key(*, folder: str | None, file_name: str | None = None, owner_id=None) -> str:
    """Return a fresh, unique key: ``<folder>/[<owner>/]<uuid4><ext>``.

    Never returns the same key twice, so an upload cannot overwrite an object
    that another upload — or another user — is still referencing.
    """
    parts = [_safe_folder(folder)]
    owner = _owner_segment(owner_id)
    if owner:
        parts.append(owner)
    parts.append(f"{uuid.uuid4().hex}{extension_for(file_name)}")
    return "/".join(parts)
