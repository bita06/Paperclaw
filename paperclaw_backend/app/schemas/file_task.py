"""
Pydantic Schemas - Files and Tasks
"""
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class FileStatusEnum(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    ERROR = "error"


class TaskStatusEnum(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCESS = "success"
    ERROR = "error"


class FileUploadAcceptedResponse(BaseModel):
    file_id: str
    task_id: str
    status: str = "uploaded"


class TaskResultResponse(BaseModel):
    file_id: str | None = None
    paper_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    sections_count: int = 0
    section_titles: list[str] = Field(default_factory=list)


class KnowledgeStatusSummary(BaseModel):
    uploaded: bool = False
    parsing: bool = False
    parse_success: bool = False
    parse_error: bool = False
    paper_generated: bool = False
    researcher_context_bound: bool = False
    in_researcher_knowledge_base: bool = False
    awaiting_knowledge_base_entry: bool = False
    agent_ready: bool = False
    summary_text: str = ""


class TaskResponse(BaseModel):
    id: str
    task_type: str
    status: TaskStatusEnum
    file_id: str | None = None
    created_by: str
    result: TaskResultResponse = Field(default_factory=TaskResultResponse)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileStatusResponse(BaseModel):
    file_id: str
    file_status: FileStatusEnum
    latest_task: TaskResponse | None = None
    linked_paper_id: str | None = None
    knowledge_status: KnowledgeStatusSummary


class FileHistoryItemResponse(BaseModel):
    file_id: str
    original_name: str
    content_type: str | None = None
    size_bytes: int
    file_status: FileStatusEnum
    researcher_id: str | None = None
    linked_paper_id: str | None = None
    created_at: datetime
    updated_at: datetime
    latest_task: TaskResponse | None = None
    knowledge_status: KnowledgeStatusSummary


class FileUploadContext(BaseModel):
    researcher_id: str | None = None
