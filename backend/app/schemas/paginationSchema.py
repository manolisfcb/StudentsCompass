"""The two collection envelopes of plan 08 §5.1.

A direct resource is returned without an envelope. A *paginated* collection is
not a direct resource: the caller needs to know where it is in the walk, and
that information has nowhere to live in a bare JSON array. Both shapes below
are generic so a route declares ``CursorPage[MessageRead]`` and OpenAPI —
which TASK-043 turns into TypeScript — carries the item type through.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT")


class CursorPage(BaseModel, Generic[ItemT]):
    """One bounded page of a keyset walk.

    ``next_cursor`` addresses the row the *next* page starts from; it is
    ``None`` when the walk is finished. That is the reliable end-of-collection
    signal — a full page does not by itself mean another one exists, which is
    why ``has_more`` is derived from a probe row rather than from ``len(items)``.

    ``limit`` echoes the size the **server** used, which is not necessarily the
    one the client asked for: an over-large request is clamped, and the client
    should be told what it actually got.
    """

    items: list[ItemT]
    next_cursor: str | None = None
    has_more: bool = False
    limit: int


class Page(BaseModel, Generic[ItemT]):
    """One page of a numbered walk: ``{items, page, page_size, total}``.

    ``total`` is the count of rows matching the query, not of rows returned;
    it is what lets a caller render "page 3 of 12". It costs a second query, so
    this shape belongs to catalogues that need jumps, not to feeds.
    """

    items: list[ItemT]
    page: int
    page_size: int
    total: int
