from datetime import datetime, timedelta

import pytest

from app.models.aiUsageModel import AIQuotaGrantModel
from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
from app.services.aiUsageService import AIFeature, AIUsageService


@pytest.mark.asyncio
async def test_ai_usage_base_daily_limit_and_recording(db_session, test_user):
    service = AIUsageService(db_session)

    summary = await service.get_summary(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    assert summary.daily_limit == 3
    assert summary.used_today == 0
    assert summary.remaining_today == 3

    await service.record_usage(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    await db_session.commit()

    summary = await service.get_summary(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    assert summary.used_today == 1
    assert summary.remaining_today == 2


@pytest.mark.asyncio
async def test_ai_usage_daily_extra_grant_expands_limit(db_session, test_user):
    db_session.add(
        AIQuotaGrantModel(
            user_id=test_user.id,
            feature=AIFeature.MOCK_INTERVIEW,
            daily_extra_units=7,
            starts_at=datetime.utcnow() - timedelta(days=1),
            ends_at=datetime.utcnow() + timedelta(days=30),
            reason="paid_interview_pack",
        )
    )
    await db_session.commit()

    service = AIUsageService(db_session)
    summary = await service.get_summary(user_id=test_user.id, feature=AIFeature.MOCK_INTERVIEW)

    assert summary.daily_limit == 10
    assert summary.remaining_today == 10


@pytest.mark.asyncio
async def test_ai_usage_counts_legacy_job_analysis_until_ledger_takes_over(db_session, test_user):
    db_session.add_all(
        [
            JobAnalysisModel(user_id=test_user.id, status=JobStatus.COMPLETED, keywords="python"),
            JobAnalysisModel(user_id=test_user.id, status=JobStatus.FAILED, error_message="failed"),
        ]
    )
    await db_session.commit()

    service = AIUsageService(db_session)
    summary = await service.get_summary(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)

    assert summary.used_today == 2
    assert summary.remaining_today == 1
