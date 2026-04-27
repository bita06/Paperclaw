from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class AgentModeEnum(str, Enum):
    CONCEPT_POSITIONING = "concept_positioning"
    LITERATURE_REVIEW = "literature_review"
    MECHANISM_ANALYSIS = "mechanism_analysis"
    RESEARCH_DESIGN = "research_design"


class AgentEvidenceSourceEnum(str, Enum):
    BUILTIN_LIBRARY = "builtin_library"
    USER_UPLOAD = "user_upload"
    WOS = "web_of_science"
    WEB = "web_search"


class AgentQueryRequest(BaseModel):
    question: str = Field(min_length=5, max_length=4000)
    mode: AgentModeEnum = AgentModeEnum.CONCEPT_POSITIONING
    researcher_id: Optional[str] = None
    advisor_id: Optional[str] = None
    include_builtin_library: bool = True
    include_user_uploads: bool = False
    include_web: bool = False
    include_wos: bool = False
    collection_slug: Optional[str] = Field(default=None, max_length=120)
    top_k: int = Field(default=5, ge=1, le=10)
    session_id: Optional[str] = Field(default=None, max_length=120)


class AgentLocalEvidenceItem(BaseModel):
    paper_id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    section_title: Optional[str] = None
    quote_or_summary: str
    source: AgentEvidenceSourceEnum
    source_label: str
    collection_slug: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class AgentExternalEvidenceItem(BaseModel):
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    published_date: Optional[str] = None
    source: AgentEvidenceSourceEnum
    source_label: str
    source_name: Optional[str] = None
    doi: Optional[str] = None
    times_cited: Optional[int] = None
    external_url: Optional[str] = None
    quote_or_summary: str


class AgentSourceStatus(BaseModel):
    local: str = "ok"
    wos: str = "disabled"
    web: str = "disabled"
    messages: List[str] = Field(default_factory=list)


class BuiltinCollectionOption(BaseModel):
    collection_slug: str
    label: str


class SemanticSearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=4000)
    researcher_id: Optional[str] = None
    include_builtin_library: bool = True
    include_user_uploads: bool = False
    collection_slug: Optional[str] = Field(default=None, max_length=120)
    top_k: int = Field(default=8, ge=1, le=20)


class SemanticSearchChunkItem(BaseModel):
    chunk_id: str
    paper_id: str
    title: str
    authors: List[str] = Field(default_factory=list)
    year: Optional[int] = None
    section_title: str
    chunk_text: str
    source: AgentEvidenceSourceEnum
    source_label: str
    collection_slug: Optional[str] = None
    score: float
    vector_score: float = 0.0
    keyword_score: float = 0.0
    page_start: Optional[int] = None
    page_end: Optional[int] = None


class SemanticSearchResponse(BaseModel):
    query: str
    items: List[SemanticSearchChunkItem] = Field(default_factory=list)


class AgentQueryResponse(BaseModel):
    mode: AgentModeEnum
    answer_title: str
    direct_answer: str
    concept_lineage: List[str] = Field(default_factory=list)
    local_evidence: List[AgentLocalEvidenceItem] = Field(default_factory=list)
    wos_evidence: List[AgentExternalEvidenceItem] = Field(default_factory=list)
    web_evidence: List[AgentExternalEvidenceItem] = Field(default_factory=list)
    source_status: AgentSourceStatus = Field(default_factory=AgentSourceStatus)
    next_steps: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
