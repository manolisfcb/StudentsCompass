import pytest
from fastapi import HTTPException
from sqlalchemy.exc import ProgrammingError

from app.routes.roadmapRoute import _run_roadmap_operation


@pytest.mark.asyncio
async def test_run_roadmap_operation_returns_successful_result():
    async def operation():
        return {"ok": True}

    assert await _run_roadmap_operation(operation) == {"ok": True}


@pytest.mark.asyncio
async def test_run_roadmap_operation_translates_missing_schema_error():
    async def operation():
        raise ProgrammingError(
            statement="select * from roadmaps",
            params={},
            orig=Exception('relation "roadmaps" does not exist'),
        )

    with pytest.raises(HTTPException) as exc_info:
        await _run_roadmap_operation(operation)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Roadmaps schema is not ready. Run: alembic upgrade head"


@pytest.mark.asyncio
async def test_run_roadmap_operation_reraises_unrelated_programming_error():
    original_error = ProgrammingError(
        statement="select broken",
        params={},
        orig=Exception("syntax error"),
    )

    async def operation():
        raise original_error

    with pytest.raises(ProgrammingError) as exc_info:
        await _run_roadmap_operation(operation)

    assert exc_info.value is original_error
