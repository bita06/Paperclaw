"""
SQLAlchemy Models - Files and Tasks
"""
import enum

from sqlalchemy import JSON, Column, Enum as SQLEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import BaseModel


class FileStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class TaskStatus(str, enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


class StoredFile(BaseModel):
    """Uploaded source file waiting for parsing/indexing."""
    __tablename__ = "stored_files"

    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    content_type = Column(String(100))
    size_bytes = Column(Integer, nullable=False, default=0)
    status = Column(SQLEnum(FileStatus), nullable=False, default=FileStatus.UPLOADED, index=True)
    uploaded_by = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    researcher_id = Column(String(36), ForeignKey("researchers.id"), nullable=True, index=True)
    linked_paper_id = Column(String(36), ForeignKey("papers.id"), nullable=True, index=True)

    uploader = relationship("User")
    researcher = relationship("Researcher")
    linked_paper = relationship("Paper")
    tasks = relationship("ProcessingTask", back_populates="file", cascade="all, delete-orphan")


class ProcessingTask(BaseModel):
    """Generic processing task skeleton for file parsing and future agent runs."""
    __tablename__ = "processing_tasks"

    task_type = Column(String(50), nullable=False, index=True)
    status = Column(SQLEnum(TaskStatus), nullable=False, default=TaskStatus.QUEUED, index=True)
    file_id = Column(String(36), ForeignKey("stored_files.id"), nullable=True, index=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    result = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text)

    file = relationship("StoredFile", back_populates="tasks")
    creator = relationship("User")
