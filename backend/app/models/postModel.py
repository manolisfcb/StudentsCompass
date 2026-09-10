
from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from app.db_types import UUID
from sqlalchemy.orm import relationship
from app.db import Base
from datetime import datetime
import uuid

class PostModel(Base):
    __tablename__ = "posts"
    __table_args__ = (
        # The feed page's exact order. The table had no index on created_at at
        # all, so every read of the global feed sorted the whole table; with the
        # keyset page it would still sort, because a page ordered by
        # (created_at, id) cannot be answered by an index on created_at alone.
        Index("ix_posts_created_at_id", "created_at", "id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    caption = Column(String(255), nullable=False)
    url = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    user = relationship("User", back_populates="post")



