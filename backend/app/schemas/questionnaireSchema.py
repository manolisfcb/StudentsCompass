from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
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