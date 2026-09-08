"""Reusable measurement and concurrency helpers for the test lanes.

Kept engine-agnostic on purpose: the SQLite fast lane and the PostgreSQL
integration lane both build their fixtures on top of these.
"""
from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass, field

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

__all__ = ["QueryCounter", "count_queries", "two_sessions"]

_VERB = re.compile(r"^\s*(?:/\*.*?\*/\s*)?(\w+)", re.S)


@dataclass
class QueryCounter:
    """Counts statements executed on an engine, split by SQL verb.

    Used to express N+1 budgets as assertions ("this endpoint issues a constant
    number of SELECTs regardless of row count") rather than as a stopwatch.
    """

    statements: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.statements)

    def count(self, verb: str) -> int:
        verb = verb.upper()
        return sum(1 for statement in self.statements if self._verb(statement) == verb)

    @property
    def selects(self) -> int:
        return self.count("SELECT")

    @property
    def writes(self) -> int:
        return sum(self.count(verb) for verb in ("INSERT", "UPDATE", "DELETE"))

    @staticmethod
    def _verb(statement: str) -> str:
        match = _VERB.match(statement)
        return match.group(1).upper() if match else ""

    def matching(self, fragment: str) -> list[str]:
        needle = fragment.lower()
        return [s for s in self.statements if needle in s.lower()]


@contextlib.contextmanager
def count_queries(engine: AsyncEngine):
    """Count every statement the engine executes inside the block."""
    counter = QueryCounter()
    sync_engine = engine.sync_engine

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        counter.statements.append(statement)

    event.listen(sync_engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield counter
    finally:
        event.remove(sync_engine, "before_cursor_execute", before_cursor_execute)


@contextlib.asynccontextmanager
async def two_sessions(session_factory: async_sessionmaker[AsyncSession]):
    """Yield two independent sessions for interleaved-transaction tests.

    Each session gets its own connection, so ``SELECT ... FOR UPDATE``, unique
    violations and lost updates behave the way they do in production. Never
    share one AsyncSession across concurrent tasks; use this instead.
    """
    async with session_factory() as first, session_factory() as second:
        yield first, second
