"""
SQLAlchemy Models - Base Class
"""
from datetime import datetime
from uuid import uuid4
from sqlalchemy import Column, DateTime, String
from sqlalchemy.orm import declarative_mixin
from app.database import Base


@declarative_mixin
class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


@declarative_mixin
class IdMixin:
    """Mixin for id field"""
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))


class BaseModel(Base, IdMixin, TimestampMixin):
    """Base model class for all models"""
    __abstract__ = True
