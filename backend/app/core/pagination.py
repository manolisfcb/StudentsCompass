"""One pagination contract for every collection this API returns.

Two shapes, and the choice between them is not stylistic:

* **Cursor** (keyset) for anything that grows at the head and is walked in
  order — messages, the community feed, a user's applications. An offset over a
  live table shifts under the reader: rows inserted while a client pages push
  every later offset along, so the walk repeats and skips. A cursor addresses a
  *row*, so it survives writes.
* **Page number** for catalogues a caller needs to jump around in, where the
  total is meaningful and the table is not being appended to constantly.

Both are bounded here rather than at each call site. A collection without a
server ceiling is a latent denial of service: the caller picks the row count and
the server pays for it. ``clamp_page_size`` is the only place that decides, and
it clamps rather than rejects, so an over-large ``limit`` still answers.

The cursor format is the one TASK-024 established for messages —
``base64url(created_at.isoformat() + "|" + id)`` — reused verbatim, not
reinvented: cursors already handed to clients stay valid, and there is one
format to reason about instead of two.
"""
from __future__ import annotations

import base64
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, literal, tuple_

#: Rows returned when a caller does not ask for a size.
DEFAULT_PAGE_SIZE = 20

#: The most any single request may return, whatever it asks for. This is the
#: bound that makes a payload finite; it is a property of the server, not a
#: default the client can raise.
MAX_PAGE_SIZE = 100

#: Ceiling for collections that answer as a bare list — the legacy shape, kept
#: while callers migrate to a paged endpoint. Higher than MAX_PAGE_SIZE because
#: these endpoints have no "next page" to follow yet, so the bound has to be a
#: whole screen's worth of history rather than one page of it. It is still a
#: bound: before this, these queries had none at all.
MAX_COLLECTION_ROWS = 200


class InvalidCursor(ValueError):
    """The cursor did not come from :func:`encode_cursor`.

    A cursor is client-supplied input. A malformed one is a 400 — never a 500,
    and never a silently dropped filter, which would answer with the wrong page
    as though it were the right one.
    """

    def __init__(self, cursor: str):
        super().__init__("The pagination cursor is not valid.")
        self.cursor = cursor


def encode_cursor(created_at: datetime, identifier: UUID | str) -> str:
    """An opaque cursor addressing one row by ``(created_at, id)``.

    Both fields, not just the timestamp: rows created in the same millisecond
    are ordinary — a client retrying, two people acting at once, a batch insert
    — and a cursor over the timestamp alone leaves the boundary between pages
    ambiguous, so a row is repeated or lost.
    """
    raw = f"{created_at.isoformat()}|{identifier}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Parse a cursor, or refuse it. Raises :class:`InvalidCursor`."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        timestamp, _, identifier = raw.partition("|")
        return datetime.fromisoformat(timestamp), UUID(identifier)
    except Exception as exc:  # noqa: BLE001 — every malformed shape is one answer
        raise InvalidCursor(cursor) from exc


def clamp_page_size(
    requested: int | None,
    *,
    default: int = DEFAULT_PAGE_SIZE,
    maximum: int = MAX_PAGE_SIZE,
) -> int:
    """The page size the server will actually use.

    Clamped, not rejected: a caller asking for 10 000 rows gets the ceiling and
    a working response. ``None`` means "did not say"; zero and negatives are
    nonsense for a page size and land on 1.
    """
    size = default if requested is None else requested
    return max(1, min(size, maximum))


def clamp_page_number(requested: int | None) -> int:
    """Page numbers are 1-based; anything below that is page 1."""
    return max(1, requested or 1)


def keyset_before(
    created_at_column: Any,
    id_column: Any,
    cursor: str,
) -> ColumnElement[bool]:
    """``(created_at, id) < cursor`` as a row-value comparison.

    A row value rather than ``created_at < x OR (created_at = x AND id < y)``:
    the tie-break becomes part of the index scan instead of a filter applied
    after it, which is what lets a composite index answer the page.

    Each half of the cursor is bound **with the type of the column it is
    compared against**. An untyped ``literal()`` is rendered by whatever type
    SQLAlchemy infers from the Python value, and a comparison is only meaningful
    when both sides are encoded the same way. That agreement used to be a
    coincidence: an untyped ``literal(UUID(...))`` happens to render as 32 bare
    hex digits, which is also what ``postgresql.UUID`` produced outside
    PostgreSQL. The moment the column's encoding changed — ``app/db_types.py``
    now stores the canonical dashed form off PostgreSQL — the two sides stopped
    lining up and the tie-break silently compared two different spellings of the
    same id, so a page could repeat. Naming the type makes the agreement a fact
    instead of a coincidence.
    """
    cursor_created_at, cursor_id = decode_cursor(cursor)
    return tuple_(created_at_column, id_column) < tuple_(
        literal(cursor_created_at, created_at_column.type),
        literal(cursor_id, id_column.type),
    )


def fetch_probe_limit(page_size: int) -> int:
    """Ask for one row more than the page.

    Whether another page exists is a fact about the data. Inferring it from "the
    page came back full" is wrong exactly at the boundary, where the last page
    happens to be full and the client is told to walk into an empty one.
    """
    return page_size + 1


def split_probe(rows: list, page_size: int) -> tuple[list, bool]:
    """Cut the probe row off the page and report whether it was there."""
    has_more = len(rows) > page_size
    return rows[:page_size], has_more
