from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from uuid import UUID
from datetime import datetime

# --- Read Models (Output to Frontend) ---

class OptionRead(BaseModel):
    id: str
    label: str
    # We intentionally exclude 'weights' here so the frontend doesn't see them

class QuestionRead(BaseModel):
    id: str
    title: str
    subtitle: Optional[str] = None
    kind: str
    options: List[OptionRead]

class QuestionnaireRead(BaseModel):
    version: str
    title: str
    questions: List[QuestionRead]

# --- Write Models (Input from Frontend) ---

class AnswerCreate(BaseModel):
    question_id: str
    option_id: str

class QuestionnaireSubmit(BaseModel):
    answers: List[AnswerCreate]

# --- Result Models ---

class CareerScore(BaseModel):
    career: str
    score: int

class QuestionnaireResult(BaseModel):
    id: UUID
    version: str
    top_careers: List[CareerScore]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class QuestionnaireProfileRead(BaseModel):
    """`GET /questionnaire/profile` (TASK-047): typed so the profile screen
    does not read this shape out of `unknown`. Not part of the §5.2 path
    rename — the path is unchanged, only the response gets a model."""

    user_id: str
    user_name: str
    user_email: str
    created_at: str
    version: str
    answers: List[AnswerCreate]
    results: List[CareerScore]
    #: `None` when the definition that produced `results` is no longer on
    #: disk (a retired questionnaire version); `results`/`answers` are still
    #: the user's own record even then.
    questionnaire: Optional[QuestionnaireRead] = None
    questionnaire_definition_available: bool