"""Pydantic Schemas - Paper"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class PaperSourceEnum(str, Enum):
    UPLOADED = "uploaded"
    ADVISOR_LIBRARY = "advisor_library"
    WOS = "wos"
    CNKI = "cnki"
    ARXIV = "arxiv"


class PaperVisibilityEnum(str, Enum):
    PUBLIC = "public"
    ADVISOR_ONLY = "advisor_only"
    RESEARCH_GROUP_ONLY = "research_group_only"


class PaperConceptBase(BaseModel):
    concept_name: str
    definition: Optional[str] = None
    section: Optional[str] = None
    role: Optional[str] = None
    context_text: Optional[str] = None


class PaperConceptResponse(PaperConceptBase):
    id: str
    paper_id: str
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaperSectionBase(BaseModel):
    section_name: str
    section_text: Optional[str] = None
    concepts: List[str] = Field(default_factory=list)


class PaperSectionResponse(PaperSectionBase):
    id: str
    paper_id: str
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaperChunkBase(BaseModel):
    section_title: str
    chunk_text: str


class PaperChunkResponse(PaperChunkBase):
    id: str
    paper_id: str
    section_id: str
    chunk_index: int
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaperBase(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)


class PaperCreate(PaperBase):
    source: PaperSourceEnum = PaperSourceEnum.UPLOADED
    source_url: Optional[str] = None
    full_text: Optional[str] = None
    file_path: Optional[str] = None


class PaperUpdate(BaseModel):
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[List[str]] = None
    source: Optional[PaperSourceEnum] = None
    source_url: Optional[str] = None
    full_text: Optional[str] = None
    file_path: Optional[str] = None
    indexed: Optional[bool] = None
    visibility: Optional[PaperVisibilityEnum] = None


class PaperResponse(PaperBase):
    id: str
    source: PaperSourceEnum
    source_url: Optional[str] = None
    indexed: bool
    visibility: PaperVisibilityEnum
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaperDetailResponse(PaperResponse):
    full_text: Optional[str] = None
    file_path: Optional[str] = None
    concepts: List[PaperConceptResponse] = Field(default_factory=list)
    sections: List[PaperSectionResponse] = Field(default_factory=list)


class ChunkBackfillResponse(BaseModel):
    processed_papers: int
    processed_sections: int
    created_chunks: int
    skipped_papers: int = 0


class AdvisorLibraryPaperCreate(BaseModel):
    paper_id: str
    sub_field_id: Optional[str] = None
    library_tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class AdvisorLibraryPaperUpdate(BaseModel):
    sub_field_id: Optional[str] = None
    library_tags: Optional[List[str]] = None
    notes: Optional[str] = None


class AdvisorLibraryPaperResponse(BaseModel):
    id: str
    advisor_id: str
    paper_id: str
    sub_field_id: Optional[str]
    sub_field_name: Optional[str] = None
    library_tags: List[str]
    notes: Optional[str]
    added_at: datetime

    class Config:
        from_attributes = True


class AdvisorLibraryPaperWithPaperResponse(AdvisorLibraryPaperResponse):
    paper: PaperResponse


class PaperUploadResponse(BaseModel):
    paper: PaperResponse
    advisor_links: List[AdvisorLibraryPaperResponse] = Field(default_factory=list)


class ReadingHistoryCreate(BaseModel):
    paper_id: str
    usefulness_score: float = Field(0.5, ge=0.0, le=1.0)
    research_relevance: Optional[str] = None
    concepts_noted: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class ReadingHistoryUpdate(BaseModel):
    usefulness_score: Optional[float] = None
    research_relevance: Optional[str] = None
    concepts_noted: Optional[List[str]] = None
    notes: Optional[str] = None


class ReadingHistoryResponse(BaseModel):
    id: str
    researcher_id: str
    paper_id: str
    read_at: datetime
    usefulness_score: float
    research_relevance: Optional[str]
    concepts_noted: List[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ReadingHistoryWithPaperResponse(ReadingHistoryResponse):
    paper: PaperResponse
