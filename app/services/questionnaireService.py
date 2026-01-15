import json
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.questionnaireModel import UserQuestionnaire
from app.schemas.questionnaireSchema import QuestionnaireRead, QuestionnaireSubmit, QuestionnaireResult
from uuid import UUID

# Path to your JSON file
QUESTIONNAIRE_PATH = Path("app/data/questionnaires/v1/v1.json")

class QuestionnaireService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _load_json(self) -> dict:
        if not QUESTIONNAIRE_PATH.exists():
            raise FileNotFoundError(f"Questionnaire file not found at {QUESTIONNAIRE_PATH}")
        with open(QUESTIONNAIRE_PATH, "r") as f:
            return json.load(f)

    async def get_questionnaire(self) -> QuestionnaireRead:
        data = self._load_json()
        # Pydantic will filter out the 'weights' from options automatically
        return QuestionnaireRead(**data)

    async def submit_questionnaire(self, user_id: UUID, submit: QuestionnaireSubmit) -> QuestionnaireResult:
        data = self._load_json()
        
        # 1. Build a lookup map for weights: question_id -> option_id -> weights
        weight_map = {}
        for q in data.get("questions", []):
            q_id = q["id"]
            weight_map[q_id] = {}
            for opt in q.get("options", []):
                weight_map[q_id][opt["id"]] = opt.get("weights", {})

        # 2. Calculate scores
        scores = {}
        for answer in submit.answers:
            # Get weights for the selected option
            option_weights = weight_map.get(answer.question_id, {}).get(answer.option_id, {})
            
            # Sum up weights for each career
            for career, weight in option_weights.items():
                scores[career] = scores.get(career, 0) + weight

        # 3. Sort careers by score (descending)
        sorted_scores = [
            {"career": k, "score": v} 
            for k, v in sorted(scores.items(), key=lambda item: item[1], reverse=True)
        ]

        # 4. Save to Database
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