import logging
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.questionnaireModel import UserQuestionnaire
from app.models.userModel import User
from app.schemas.questionnaireSchema import QuestionnaireRead, QuestionnaireSubmit, QuestionnaireResult
from app.services.accounts.questionnaireCatalog import (
    CURRENT_QUESTIONNAIRE_PATH,
    QuestionnaireVersionNotFound,
    load_current_definition,
    load_definition_for_version,
)
from uuid import UUID

LOGGER = logging.getLogger(__name__)

# Kept as a module attribute because tests and older callers refer to it.
QUESTIONNAIRE_PATH = CURRENT_QUESTIONNAIRE_PATH

#: Question kinds that accept exactly one answer. Every question in every
#: shipped definition is currently ``single``; an unknown kind is refused rather
#: than guessed at, so adding one is a deliberate change here.
SINGLE_ANSWER_KINDS = {"single"}


class QuestionnaireService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _load_json(self) -> dict:
        return load_current_definition()

    async def get_questionnaire(self) -> QuestionnaireRead:
        data = self._load_json()
        # Pydantic will filter out the 'weights' from options automatically
        return QuestionnaireRead(**data)

    @staticmethod
    def _index_definition(data: dict) -> tuple[dict, dict]:
        """``(question_id -> kind, question_id -> option_id -> weights)``."""
        kinds: dict[str, str] = {}
        weights: dict[str, dict[str, dict]] = {}
        for question in data.get("questions", []):
            question_id = question["id"]
            kinds[question_id] = question.get("kind", "single")
            weights[question_id] = {
                option["id"]: option.get("weights", {})
                for option in question.get("options", [])
            }
        return kinds, weights

    @classmethod
    def _validate_answers(cls, submit: QuestionnaireSubmit, data: dict) -> None:
        """Refuse an answer set the definition cannot account for.

        Scoring used to look every answer up with ``.get(...,{})`` and add
        whatever came back, so three distinct defects were all silent:

        * a ``question_id`` that does not exist contributed zero and looked like
          a legitimate answer;
        * an ``option_id`` from a different question did the same;
        * the same question answered twice was **counted twice**, which is a
          way to inflate a career score by repeating one answer.

        Each is a 422 with the offending ids named, so a broken client is told
        what is wrong instead of quietly receiving a wrong result.
        """
        kinds, weights = cls._index_definition(data)

        unknown_questions: list[str] = []
        unknown_options: list[str] = []
        seen: dict[str, int] = {}

        for answer in submit.answers:
            if answer.question_id not in weights:
                unknown_questions.append(answer.question_id)
                continue
            if answer.option_id not in weights[answer.question_id]:
                unknown_options.append(f"{answer.question_id}:{answer.option_id}")
            seen[answer.question_id] = seen.get(answer.question_id, 0) + 1

        duplicated = sorted(
            question_id
            for question_id, count in seen.items()
            if count > 1 and kinds.get(question_id) in SINGLE_ANSWER_KINDS
        )
        unsupported_kinds = sorted(
            {
                kinds[answer.question_id]
                for answer in submit.answers
                if answer.question_id in kinds
                and kinds[answer.question_id] not in SINGLE_ANSWER_KINDS
            }
        )

        problems: list[str] = []
        if unknown_questions:
            problems.append(f"unknown question ids: {', '.join(sorted(set(unknown_questions)))}")
        if unknown_options:
            problems.append(f"options that do not belong to their question: {', '.join(sorted(set(unknown_options)))}")
        if duplicated:
            problems.append(f"questions answered more than once: {', '.join(duplicated)}")
        if unsupported_kinds:
            problems.append(f"unsupported question kinds: {', '.join(unsupported_kinds)}")

        if problems:
            raise HTTPException(
                status_code=422,
                detail=(
                    "The submitted answers do not match questionnaire version "
                    f"{data.get('version', 'unknown')}: " + "; ".join(problems)
                ),
            )

    async def submit_questionnaire(self, user_id: UUID, submit: QuestionnaireSubmit) -> QuestionnaireResult:
        data = self._load_json()
        self._validate_answers(submit, data)

        _kinds, weight_map = self._index_definition(data)

        # Unanswered questions are allowed and simply score nothing. That is the
        # behaviour the endpoint has always had, stated here rather than left to
        # be inferred, and pinned by
        # ``test_a_partial_submission_is_accepted_and_scores_only_what_it_answered``.
        scores: dict[str, int] = {}
        for answer in submit.answers:
            for career, weight in weight_map[answer.question_id][answer.option_id].items():
                scores[career] = scores.get(career, 0) + weight

        # Sort careers by score (descending). Unchanged, including the tie order.
        sorted_scores = [
            {"career": k, "score": v}
            for k, v in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        ]

        user_questionnaire = UserQuestionnaire(
            user_id=user_id,
            version=data.get("version", "unknown"),
            answers=[a.model_dump() for a in submit.answers],
            results=sorted_scores
        )
        self.session.add(user_questionnaire)
        await self.session.commit()
        await self.session.refresh(user_questionnaire)

        return QuestionnaireResult(
            id=user_questionnaire.id,
            version=user_questionnaire.version,
            top_careers=sorted_scores,
            created_at=user_questionnaire.created_at
        )

    async def get_user_questionnaire_profile(self, user: User) -> dict:
        result = await self.session.execute(
            select(UserQuestionnaire)
            .where(UserQuestionnaire.user_id == user.id)
            .order_by(UserQuestionnaire.created_at.desc())
            .limit(1)
        )
        user_questionnaire = result.scalar_one_or_none()

        if not user_questionnaire:
            raise HTTPException(status_code=404, detail="No questionnaire responses found")

        # The definition the answers were given under, not whatever is current.
        # Rendering a v1 answer set against the v3 questions showed option ids
        # that no longer exist next to questions the user never saw.
        stored_version = user_questionnaire.version
        try:
            definition = load_definition_for_version(stored_version)
            questionnaire = QuestionnaireRead(**definition)
            questionnaire_available = True
        except QuestionnaireVersionNotFound:
            # The answers and results are still the user's own record and are
            # returned; what is missing is the questions they were asked, and
            # saying so is better than substituting different ones.
            LOGGER.warning(
                "Questionnaire definition %s is no longer on disk; profile for user %s "
                "is returned without it.",
                stored_version,
                user.id,
            )
            questionnaire = None
            questionnaire_available = False

        return {
            "user_id": str(user.id),
            "user_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split("@")[0],
            "user_email": user.email,
            "created_at": user_questionnaire.created_at.isoformat(),
            "version": stored_version,
            "answers": user_questionnaire.answers,
            "results": user_questionnaire.results,
            "questionnaire": questionnaire,
            "questionnaire_definition_available": questionnaire_available,
        }
