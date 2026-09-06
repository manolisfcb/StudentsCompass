"""A failed course audit must not cost the user a slot.

Upload, evaluation row and text extraction used to run *outside* the block that
returns a reservation: a storage error, an unreadable PDF or a database failure
in the middle left the slot claimed and the evaluation stuck on PENDING. Each
step is failed on purpose here, and after every one of them the same two things
are checked — the slot is back, and the evaluation is in a terminal state.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models.aiUsageModel import AIUsageEventModel, AIUsageStatus
from app.models.resumeCourseEvaluationModel import (
    ResumeCourseEvaluationModel,
    ResumeCourseEvaluationStatus,
)
from app.services.ai.aiBudgetGuard import AIBudgetExhausted
from app.services.ai.aiUsageService import (
    RELEASE_AFTER_ATTEMPT,
    RELEASE_NO_SPEND,
    AIFeature,
    AIUsageService,
)
from app.services.ratelimit.counterStore import reset_counter_store
from app.services.resumes.resumeCourseAuditService import ResumeCourseAuditService

READABLE_CV = ("Experienced Python engineer. " * 20).encode()


class _StubEvaluator:
    """Stands in for Gemini. Never reaches the network (the lane blocks it)."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls = 0

    async def evaluate(self, text: str):
        self.calls += 1
        if self.error is not None:
            raise self.error
        raise AssertionError("no test here expects a successful evaluation")


@pytest.fixture
def audit_service(db_session, monkeypatch):
    """The audit service with storage and text extraction under test control."""

    def _build(*, evaluator, extracted_text=" ".join(["word"] * 60), upload_error=None):
        service = ResumeCourseAuditService(db_session, evaluator=evaluator)

        async def fake_upload(**kwargs):
            if upload_error is not None:
                raise upload_error
            from app.models.resumeModel import ResumeModel

            resume = ResumeModel(
                user_id=kwargs["user_id"],
                storage_file_id="stub-file",
                original_filename=kwargs["file_name"],
                view_url="https://example.invalid/cv",
                folder_id="stub-folder",
            )
            db_session.add(resume)
            await db_session.commit()
            await db_session.refresh(resume)
            return resume, {"view_url": "https://example.invalid/cv"}

        async def fake_extract(file_bytes, *, filename, content_type):
            return extracted_text

        monkeypatch.setattr(service.resume_service, "create_resume_from_upload", fake_upload)
        monkeypatch.setattr(
            "app.services.resumes.resumeCourseAuditService.extract_resume_text_from_bytes",
            fake_extract,
        )
        return service

    return _build


async def _run(service, user_id):
    return await service.upload_and_evaluate_resume(
        user_id=user_id,
        storage_location_id="stub-location",
        file_bytes=READABLE_CV,
        filename="cv.pdf",
        content_type="application/pdf",
    )


async def _ledger(session, user_id):
    result = await session.execute(
        select(AIUsageEventModel)
        .where(AIUsageEventModel.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars())


async def _evaluations(session, user_id):
    result = await session.execute(
        select(ResumeCourseEvaluationModel)
        .where(ResumeCourseEvaluationModel.user_id == user_id)
        .execution_options(populate_existing=True)
    )
    return list(result.scalars())


@pytest.mark.asyncio
async def test_upload_failure_returns_the_slot(db_session, test_user, audit_service):
    await reset_counter_store()
    evaluator = _StubEvaluator()
    service = audit_service(evaluator=evaluator, upload_error=RuntimeError("storage is down"))

    with pytest.raises(RuntimeError):
        await _run(service, test_user.id)

    assert evaluator.calls == 0
    usage = AIUsageService(db_session)
    assert await usage.get_used_today(user_id=test_user.id, feature=AIFeature.RESUME_COURSE_AUDIT) == 0
    ledger = await _ledger(db_session, test_user.id)
    assert [event.status for event in ledger] == [AIUsageStatus.RELEASED]
    assert ledger[0].source == RELEASE_NO_SPEND
    # The upload never produced a resume, so there is no evaluation to close.
    assert await _evaluations(db_session, test_user.id) == []


@pytest.mark.asyncio
async def test_unreadable_cv_returns_the_slot_and_fails_the_evaluation(
    db_session, test_user, audit_service
):
    await reset_counter_store()
    evaluator = _StubEvaluator()
    service = audit_service(evaluator=evaluator, extracted_text="too short")

    with pytest.raises(HTTPException) as exc_info:
        await _run(service, test_user.id)
    assert exc_info.value.status_code == 400

    assert evaluator.calls == 0
    usage = AIUsageService(db_session)
    assert await usage.get_used_today(user_id=test_user.id, feature=AIFeature.RESUME_COURSE_AUDIT) == 0
    assert [event.status for event in await _ledger(db_session, test_user.id)] == [
        AIUsageStatus.RELEASED
    ]
    evaluations = await _evaluations(db_session, test_user.id)
    assert [evaluation.status for evaluation in evaluations] == [
        ResumeCourseEvaluationStatus.FAILED
    ]


@pytest.mark.asyncio
async def test_budget_exhausted_returns_the_slot_without_charging_an_attempt(
    db_session, test_user, audit_service
):
    """Refused before the provider was called: nothing was spent anywhere."""
    await reset_counter_store()
    evaluator = _StubEvaluator(AIBudgetExhausted("daily attempt ceiling reached"))
    service = audit_service(evaluator=evaluator)

    with pytest.raises(HTTPException) as exc_info:
        await _run(service, test_user.id)
    assert exc_info.value.status_code == 503

    usage = AIUsageService(db_session)
    assert await usage.get_used_today(user_id=test_user.id, feature=AIFeature.RESUME_COURSE_AUDIT) == 0
    ledger = await _ledger(db_session, test_user.id)
    assert ledger[0].source == RELEASE_NO_SPEND


@pytest.mark.asyncio
async def test_provider_failure_is_recorded_as_an_attempt_that_cost_nothing_to_the_user(
    db_session, test_user, audit_service
):
    """The provider may well have charged; the user's daily slot still returns.

    The two facts are kept apart in the data: the ledger row says the release
    followed a real attempt, and the global budget guard is what counts that
    attempt against spend.
    """
    await reset_counter_store()
    evaluator = _StubEvaluator(RuntimeError("provider exploded mid-call"))
    service = audit_service(evaluator=evaluator)

    with pytest.raises(HTTPException) as exc_info:
        await _run(service, test_user.id)
    assert exc_info.value.status_code == 502

    assert evaluator.calls == 1
    usage = AIUsageService(db_session)
    assert await usage.get_used_today(user_id=test_user.id, feature=AIFeature.RESUME_COURSE_AUDIT) == 0
    ledger = await _ledger(db_session, test_user.id)
    assert [event.status for event in ledger] == [AIUsageStatus.RELEASED]
    assert ledger[0].source == RELEASE_AFTER_ATTEMPT
    evaluations = await _evaluations(db_session, test_user.id)
    assert [evaluation.status for evaluation in evaluations] == [
        ResumeCourseEvaluationStatus.FAILED
    ]


@pytest.mark.asyncio
async def test_repeated_failures_do_not_use_up_the_daily_allowance(
    db_session, test_user, audit_service
):
    """The whole point: a broken provider must not cost a user their day."""
    await reset_counter_store()
    for _ in range(5):  # more attempts than the daily limit of 3
        service = audit_service(evaluator=_StubEvaluator(RuntimeError("still broken")))
        with pytest.raises(HTTPException):
            await _run(service, test_user.id)

    usage = AIUsageService(db_session)
    summary = await usage.get_summary(user_id=test_user.id, feature=AIFeature.RESUME_COURSE_AUDIT)
    assert summary.used_today == 0
    assert summary.remaining_today == 3
