from sqlalchemy import Column, String, ForeignKey, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db import Base
import uuid
from datetime import datetime

class UserQuestionnaire(Base):
    __tablename__ = "user_questionnaires"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    version = Column(String, nullable=False)
    
    # Stores the list of answers: [{"question_id": "...", "option_id": "..."}]
    answers = Column(JSON, nullable=False)
    
    # Stores the calculated scores: [{"career": "...", "score": 10}]
    results = Column(JSON, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="questionnaires")