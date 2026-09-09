"""``Idempotency-Key``: the same intention, sent twice, charged once.

Plan 08 §5.1 asks for this header where a repeat costs money or creates a
duplicate — applications, uploads that trigger AI, job creation. The mechanic:

1. The key is **claimed** by inserting a row, which commits before any work
   starts. The unique constraint decides who claimed it; a check-then-insert
   would let two simultaneous retries both pass.
2. The work runs. Its response is stored on the record.
3. The same key arriving later replays that stored response verbatim, without
   running anything.

Three answers, and the difference between them matters:

* **same key, same body, finished** → the original response, byte for byte,
  with ``Idempotent-Replay: true``. Not a 409: the client is retrying because
  it never saw the first answer, and its intention was carried out exactly once.
* **same key, different body** → ``409``. Replaying the first body would be
  worse than an error — it would confirm a request the client did not make.
* **same key, still running** → ``409``. There is no result to replay yet, and
  the alternative, doing the work again, is the thing this module exists to
  prevent.

A request that *fails* releases its key, so a client may retry a 500. A crash
between claim and completion leaves the record in progress; it stops blocking
after ``IN_PROGRESS_LEASE``, which is what stops one dead process from making a
key permanently unusable.

Sending no key at all is allowed and changes nothing — the legacy clients do
not send one. That is a transition, not the destination: the React client sends
it on every one of these endpoints.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idempotencyModel import IdempotencyRecordModel, IdempotencyStatus

#: The header clients send. Spelled once.
IDEMPOTENCY_HEADER = "Idempotency-Key"

#: How long a stored response stays replayable. A key is a retry window, not an
#: audit log: long enough to cover a client's own retry policy and a user
#: refreshing a stuck page, short enough that the table does not grow forever.
IDEMPOTENCY_RETENTION = timedelta(hours=24)

#: How long a claimed-but-unfinished record blocks its key. Longer than any of
#: these requests takes; short enough that a killed process does not lock a key
#: out for a day.
IN_PROGRESS_LEASE = timedelta(minutes=15)

#: Keys are client-chosen strings. Bounded so the column cannot be used as
#: storage, and non-empty so a blank header is a mistake rather than a key.
MAX_KEY_LENGTH = 255

CODE_IDEMPOTENCY_KEY_REUSE = "idempotency_key_reuse"
CODE_IDEMPOTENCY_IN_PROGRESS = "idempotency_request_in_progress"
CODE_IDEMPOTENCY_KEY_INVALID = "idempotency_key_invalid"


def read_idempotency_key(request: Request) -> str | None:
    """The header's value, or ``None`` when the caller did not send one."""
    raw = request.headers.get(IDEMPOTENCY_HEADER)
    if raw is None:
        return None
    key = raw.strip()
    if not key or len(key) > MAX_KEY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"{IDEMPOTENCY_HEADER} must be a non-empty string of at most "
            f"{MAX_KEY_LENGTH} characters.",
            headers={"X-Error-Code": CODE_IDEMPOTENCY_KEY_INVALID},
        )
    return key


def fingerprint(payload: Any) -> str:
    """A stable digest of what was requested.

    JSON with sorted keys, so a client that serialises its object in a
    different field order is still recognised as sending the same request.
    Bytes (an upload) are hashed directly: the file *is* the request.
    """
    if payload is None:
        digest_source = b""
    elif isinstance(payload, (bytes, bytearray)):
        digest_source = bytes(payload)
    elif isinstance(payload, str):
        digest_source = payload.encode("utf-8")
    else:
        digest_source = json.dumps(
            jsonable_encoder(payload), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    return hashlib.sha256(digest_source).hexdigest()


def actor_key(kind: str, identifier: UUID | str) -> str:
    """``"user:<id>"``. Two actors never share a key namespace."""
    return f"{kind}:{identifier}"


def _conflict(code: str, message: str) -> HTTPException:
    return HTTPException(status_code=409, detail=message, headers={"X-Error-Code": code})


class IdempotentRequest:
    """The handle a route holds for the duration of one guarded request.

    ``replay`` is a ready response when this key has already been answered; the
    route returns it and does no work. Otherwise the route does its work and
    hands the result to :meth:`store`.
    """

    def __init__(
        self,
        session: AsyncSession,
        record: IdempotencyRecordModel | None,
        replay: JSONResponse | None = None,
    ):
        self.session = session
        self.record = record
        self.replay = replay

    @property
    def is_replay(self) -> bool:
        return self.replay is not None

    async def store(self, payload: Any, *, status_code: int = 200) -> Any:
        """Record the response and return it.

        Without a key there is nothing to record, and the payload is returned
        untouched — the response is then serialised by FastAPI exactly as it was
        before this guard existed. With a key, the encoded body is stored and
        returned as a ``JSONResponse`` so the replay can be byte-identical.
        """
        if self.record is None:
            return payload

        body = jsonable_encoder(payload)
        self.record.status = IdempotencyStatus.COMPLETED
        self.record.response_status_code = status_code
        self.record.response_body = json.dumps(body)
        self.record.completed_at = datetime.utcnow()
        self.session.add(self.record)
        await self.session.commit()
        return JSONResponse(content=body, status_code=status_code)

    async def release(self) -> None:
        """Give the key back after a failure, so the client may retry.

        A request that raised produced no result to replay. Leaving the record
        in place would answer the retry with a 409 for as long as the lease
        lasts, which turns one transient failure into a locked-out user.
        """
        if self.record is None:
            return
        try:
            await self.session.rollback()
            await self.session.delete(self.record)
            await self.session.commit()
        except Exception:  # pragma: no cover - never mask the original failure
            await self.session.rollback()


async def begin_idempotent_request(
    session: AsyncSession,
    *,
    request: Request,
    actor: str,
    endpoint: str,
    payload: Any,
) -> IdempotentRequest:
    """Claim this request's key, or produce the answer it already has."""
    key = read_idempotency_key(request)
    if key is None:
        return IdempotentRequest(session, None)

    digest = fingerprint(payload)
    now = datetime.utcnow()

    existing = await _find_live_record(session, actor=actor, endpoint=endpoint, key=key, now=now)
    if existing is not None:
        return _answer_for_existing(session, existing, digest, now)

    record = IdempotencyRecordModel(
        actor_key=actor,
        endpoint=endpoint,
        idempotency_key=key,
        request_fingerprint=digest,
        status=IdempotencyStatus.IN_PROGRESS,
        created_at=now,
        expires_at=now + IDEMPOTENCY_RETENTION,
    )
    session.add(record)
    try:
        # Committed before any work: the claim has to be visible to the other
        # request that is retrying right now, and an uncommitted row is not.
        await session.commit()
    except IntegrityError:
        # Someone else claimed the key between the read and the insert. The
        # database settled it; re-read and answer from their record.
        await session.rollback()
        existing = await _find_live_record(
            session, actor=actor, endpoint=endpoint, key=key, now=now
        )
        if existing is None:  # pragma: no cover - only if it expired in between
            raise _conflict(
                CODE_IDEMPOTENCY_IN_PROGRESS,
                "A request with this Idempotency-Key is already being processed.",
            ) from None
        return _answer_for_existing(session, existing, digest, now)

    return IdempotentRequest(session, record)


async def _find_live_record(
    session: AsyncSession,
    *,
    actor: str,
    endpoint: str,
    key: str,
    now: datetime,
) -> IdempotencyRecordModel | None:
    """The record for this key that still counts.

    An expired one does not: past retention the key is free again, and past the
    lease an unfinished one is abandoned. Both are deleted rather than reused,
    so the new request starts from a clean claim.
    """
    result = await session.execute(
        select(IdempotencyRecordModel).where(
            IdempotencyRecordModel.actor_key == actor,
            IdempotencyRecordModel.endpoint == endpoint,
            IdempotencyRecordModel.idempotency_key == key,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None

    stale_claim = (
        record.status == IdempotencyStatus.IN_PROGRESS
        and record.created_at is not None
        and record.created_at + IN_PROGRESS_LEASE <= now
    )
    if record.expires_at <= now or stale_claim:
        await session.delete(record)
        await session.commit()
        return None
    return record


def _answer_for_existing(
    session: AsyncSession,
    record: IdempotencyRecordModel,
    digest: str,
    now: datetime,
) -> IdempotentRequest:
    if record.request_fingerprint != digest:
        raise _conflict(
            CODE_IDEMPOTENCY_KEY_REUSE,
            "This Idempotency-Key was already used with a different request body.",
        )
    if record.status != IdempotencyStatus.COMPLETED:
        raise _conflict(
            CODE_IDEMPOTENCY_IN_PROGRESS,
            "A request with this Idempotency-Key is already being processed.",
        )
    body = json.loads(record.response_body) if record.response_body else None
    replay = JSONResponse(
        content=body,
        status_code=record.response_status_code or 200,
        headers={"Idempotent-Replay": "true"},
    )
    return IdempotentRequest(session, None, replay=replay)


async def purge_expired_records(session: AsyncSession, *, now: datetime | None = None) -> int:
    """Drop records past retention. Returns how many were removed."""
    from sqlalchemy import delete

    moment = now or datetime.utcnow()
    result = await session.execute(
        delete(IdempotencyRecordModel).where(IdempotencyRecordModel.expires_at <= moment)
    )
    await session.commit()
    return result.rowcount or 0
