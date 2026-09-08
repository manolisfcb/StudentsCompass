from datetime import datetime, timedelta

import pytest

from app.models.aiUsageModel import AIQuotaGrantModel
from app.models.jobAnalysisModel import JobAnalysisModel, JobStatus
from app.services.ai.aiUsageService import AIFeature, AIUsageService


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
async def test_legacy_rows_no_longer_count_by_themselves(db_session, test_user):
    """The ledger is the authority now; a bare legacy count is not a charge.

    Before reconciliation the quota read was ``max(ledger, legacy_count)``, which
    charged for every ``job_analysis`` row — including the ones whose slot had
    been explicitly released (a cache hit, an unreadable CV). Those rows are
    still history, but only a ledger entry is a charge.
    """
    db_session.add_all(
        [
            JobAnalysisModel(user_id=test_user.id, status=JobStatus.COMPLETED, keywords="python"),
            JobAnalysisModel(user_id=test_user.id, status=JobStatus.FAILED, error_message="failed"),
        ]
    )
    await db_session.commit()

    service = AIUsageService(db_session)
    summary = await service.get_summary(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)

    assert summary.used_today == 0
    assert summary.remaining_today == 3


@pytest.mark.asyncio
async def test_parity_reports_legacy_rows_missing_from_the_ledger(db_session, test_user):
    """The evidence the backfill migration produces, re-runnable at any time."""
    analysed = JobAnalysisModel(user_id=test_user.id, status=JobStatus.COMPLETED, keywords="python")
    db_session.add(analysed)
    await db_session.commit()

    service = AIUsageService(db_session)
    gaps = await service.legacy_parity_gaps(feature=AIFeature.CV_JOB_SEARCH, user_id=test_user.id)
    assert [gap["reference_id"] for gap in gaps] == [analysed.id]

    # Reconciling that row by identity — what the migration does — closes the gap
    # and makes the same historical attempt count exactly once.
    await service.record_usage(
        user_id=test_user.id,
        feature=AIFeature.CV_JOB_SEARCH,
        source="legacy_backfill",
        reference_type="job_analysis",
        reference_id=analysed.id,
    )
    await db_session.commit()

    assert await service.legacy_parity_gaps(feature=AIFeature.CV_JOB_SEARCH, user_id=test_user.id) == []
    summary = await service.get_summary(user_id=test_user.id, feature=AIFeature.CV_JOB_SEARCH)
    assert summary.used_today == 1
