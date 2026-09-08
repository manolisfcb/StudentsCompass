from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.aiUsageModel import AIQuotaGrantModel, AIUsageEventModel
from app.services.ai.aiUsageService import AIFeature, AIUsageService
from app.services.ratelimit.counterStore import reset_counter_store


@pytest.mark.asyncio
async def test_reserve_enforces_daily_limit(db_session, test_user):
    await reset_counter_store()
    service = AIUsageService(db_session)

    for _ in range(3):  # AI_BASE_DAILY_LIMIT
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)

    with pytest.raises(HTTPException) as exc_info:
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_release_returns_the_slot(db_session, test_user):
    await reset_counter_store()
    service = AIUsageService(db_session)

    reservations = [
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
        for _ in range(3)
    ]
    # At the limit now; releasing one frees a slot for another reservation.
    await reservations[0].release()
    await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)

    with pytest.raises(HTTPException):
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)


@pytest.mark.asyncio
async def test_reserve_seeds_from_existing_db_usage(db_session, test_user):
    # A fresh counter must NOT hand back quota already spent and recorded in DB.
    await reset_counter_store()
    db_session.add_all(
        [AIUsageEventModel(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH) for _ in range(3)]
    )
    await db_session.commit()

    service = AIUsageService(db_session)
    with pytest.raises(HTTPException) as exc_info:
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_active_grant_expands_reservation_budget(db_session, test_user):
    await reset_counter_store()
    db_session.add(
        AIQuotaGrantModel(
            user_id=test_user.id,
            feature=AIFeature.CV_JOB_SEARCH,
            daily_extra_units=2,
            starts_at=datetime.utcnow() - timedelta(days=1),
            ends_at=datetime.utcnow() + timedelta(days=30),
            reason="test_pack",
        )
    )
    await db_session.commit()

    service = AIUsageService(db_session)
    for _ in range(5):  # base 3 + grant 2
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)

    with pytest.raises(HTTPException):
        await service.reserve(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
