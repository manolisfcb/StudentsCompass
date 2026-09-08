"""The single rule for "is this resume approved?".

The threshold used to be written three times: the evaluator normalised
``pass_status`` against a literal ``8``, application eligibility re-checked both
``pass_status`` and its own ``MIN_APPROVED_RESUME_SCORE``, and the resources hub
checked only ``pass_status``. The third one is why a course lesson could show as
finished for a resume that could not actually be attached to an application.

Nothing here changes the threshold — it stays at 8 — it only stops the rule from
being restated.
"""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resumeCourseEvaluationModel import (
    ResumeCourseEvaluationModel,
    ResumeCourseEvaluationStatus,
)

#: A resume audit passes at 8 out of 10. Deliberately unchanged by this refactor.
RESUME_APPROVAL_MIN_SCORE = 8.0


def is_passing_score(score: float | int | None) -> bool:
    """Whether a raw audit score clears the bar.

    ``None`` is not a pass: an evaluation without a score has not been judged.
    """
    if score is None:
        return False
    return float(score) >= RESUME_APPROVAL_MIN_SCORE


def approved_evaluation_clauses() -> tuple:
    """SQL conditions that select an approved evaluation.

    ``pass_status`` and ``overall_score`` are both required on purpose. They are
    written by the same code path today, but historical rows predate that and a
    stored flag must not be able to outvote the score it was derived from.
    """
    return (
        ResumeCourseEvaluationModel.status == ResumeCourseEvaluationStatus.COMPLETED,
        ResumeCourseEvaluationModel.pass_status.is_(True),
        ResumeCourseEvaluationModel.overall_score >= RESUME_APPROVAL_MIN_SCORE,
    )


async def has_approved_resume(session: AsyncSession, user_id: UUID) -> bool:
    """Does this user hold at least one approved resume evaluation?

    Deleting a resume takes its evaluations with it (ON DELETE CASCADE), so this
    stops being true when the approved CV is removed — which is what both the
    course view and the dashboard must then show.
    """
    result = await session.execute(
        select(ResumeCourseEvaluationModel.id)
        .where(ResumeCourseEvaluationModel.user_id == user_id, *approved_evaluation_clauses())
        .limit(1)
    )
    return result.scalar_one_or_none() is not None
