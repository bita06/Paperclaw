"""
User authentication models.
"""
from sqlalchemy import Boolean, Column, ForeignKey, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class User(BaseModel):
    """Platform login account."""

    __tablename__ = "users"

    name = Column(String(255), nullable=False)
    student_id = Column(String(64), unique=True, nullable=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="researcher", index=True)
    department = Column(String(255), nullable=True)
    auth_provider = Column(String(50), nullable=False, default="local")
    is_active = Column(Boolean, nullable=False, default=True)
    researcher_id = Column(String(36), ForeignKey("researchers.id"), nullable=True, unique=True)

    researcher = relationship("Researcher", back_populates="user", uselist=False)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"
