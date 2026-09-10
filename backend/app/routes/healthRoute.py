"""The two probes Cloud Run reads. Not part of the client contract.

``include_in_schema=False`` and no ``/api/v1`` prefix, for the same reason the
internal task routes are excluded: the OpenAPI document is the contract the
frontend's types are generated from (TASK-043), and these endpoints are
addressed by the platform, never by a client. Publishing them would put two
operations into every regenerated type file that no caller will ever use.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.health import database_ready
from app.db import get_session

router = APIRouter()


@router.get("/healthz", include_in_schema=False)
async def healthz() -> Response:
    """Liveness: the process is up and serving. Touches nothing."""
    return JSONResponse({"status": "ok"})


@router.get("/readyz", include_in_schema=False)
async def readyz(session: AsyncSession = Depends(get_session)) -> Response:
    """Readiness: this replica can serve real traffic.

    503 rather than 500 when it cannot: the platform reads it as "not yet", the
    revision stays out of the load balancer, and the deploy gate refuses to
    promote it. A 500 would read as a bug in the probe.
    """
    if not await database_ready(session):
        return JSONResponse(
            {"status": "not_ready", "checks": {"database": "unavailable"}},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return JSONResponse({"status": "ready", "checks": {"database": "ok"}})
