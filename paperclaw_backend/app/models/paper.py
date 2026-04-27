"""
SQLAlchemy Models - Paper and Library
"""
from datetime import datetime
import enum

from pgvector.utils import from_db, to_db
from sqlalchemy import ARRAY, Boolean, Column, DateTime, Enum as SQLEnum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship
from sqlalchemy.types import UserDefinedType

from app.config import settings
from app.models.base import BaseModel


class AsyncpgVector(UserDefinedType):
    cache_ok = True
    _string = String()

    def __init__(self, dim=None):
        super(UserDefinedType, self).__init__()
        self.dim = dim

    def get_col_spec(self, **kw):
        if self.dim is None:
            return "VECTOR"
        return "VECTOR(%d)" % self.dim

    def bind_processor(self, dialect):
        if getattr(dialect, "driver", None) == "asyncpg":
            def process(value):
                return value
            return process

        def process(value):
            return to_db(value, self.dim)
        return process

    def literal_processor(self, dialect):
        string_literal_processor = self._string._cached_literal_processor(dialect)

        def process(value):
            return string_literal_processor(to_db(value, self.dim))

        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            return from_db(value)
        return process

    class comparator_factory(UserDefinedType.Comparator):
        def l2_distance(self, other):
            return self.op('<->', return_type=Float)(other)

        def max_inner_product(self, other):
            return self.op('<#>', return_type=Float)(other)

        def cosine_distance(self, other):
            return self.op('<=>', return_type=Float)(other)


class PaperSource(str, enum.Enum):
    """Paper source types"""

    UPLOADED = "uploaded"
    BUILTIN_LIBRARY = "builtin_library"
    ADVISOR_LIBRARY = "advisor_library"
    WOS = "wos"
    CNKI = "cnki"
    ARXIV = "arxiv"


class PaperVisibility(str, enum.Enum):
    """Paper visibility control"""

    PUBLIC = "public"
    ADVISOR_ONLY = "advisor_only"
    RESEARCH_GROUP_ONLY = "research_group_only"


PAPER_SOURCE_ENUM = SQLEnum(
    PaperSource,
    name="papersource",
    values_callable=lambda members: [member.value for member in members],
)

PAPER_VISIBILITY_ENUM = SQLEnum(PaperVisibility, name="papervisibility")


class Paper(BaseModel):
    """Academic Paper/Literature"""

    __tablename__ = "papers"

    title = Column(String(500), nullable=False, index=True)
    authors = Column(ARRAY(String), default=[])
    year = Column(Integer)
    venue = Column(String(255))
    doi = Column(String(255), unique=True, nullable=True)
    abstract = Column(Text)
    keywords = Column(ARRAY(String), default=[])

    source = Column(PAPER_SOURCE_ENUM, nullable=False, index=True)
    source_url = Column(String(500))
    collection_slug = Column(String(120), nullable=True, index=True)
    owner_user_id = Column(String(36), nullable=True, index=True)

    full_text = Column(Text)
    file_path = Column(String(500))

    full_text_embedding = Column(ARRAY(Float))
    abstract_embedding = Column(ARRAY(Float))

    indexed = Column(Boolean, default=False, index=True)
    visibility = Column(PAPER_VISIBILITY_ENUM, default=PaperVisibility.PUBLIC)

    concepts = relationship("PaperConcept", back_populates="paper", cascade="all, delete-orphan")
    advisor_libraries = relationship("AdvisorLibraryPaper", back_populates="paper", cascade="all, delete-orphan")
    section_contents = relationship("PaperSection", back_populates="paper", cascade="all, delete-orphan")
    chunks = relationship("PaperChunk", back_populates="paper", cascade="all, delete-orphan")
    reading_history = relationship("ReadingHistory", back_populates="paper")

    def __repr__(self):
        return f"<Paper {self.title}>"


class PaperSection(BaseModel):
    """Paper sections for targeted retrieval"""

    __tablename__ = "paper_sections"

    paper_id = Column(String(36), ForeignKey("papers.id"), nullable=False, index=True)
    section_name = Column(String(100), nullable=False)
    section_text = Column(Text)
    section_embedding = Column(ARRAY(Float))
    concepts = Column(ARRAY(String), default=[])
    span_start = Column(Integer)
    span_end = Column(Integer)
    page_start = Column(Integer)
    page_end = Column(Integer)

    paper = relationship("Paper", back_populates="section_contents")
    chunks = relationship("PaperChunk", back_populates="section", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PaperSection {self.section_name}>"


class PaperChunk(BaseModel):
    """Smaller retrieval unit built from sections for RAG retrieval."""

    __tablename__ = "paper_chunks"

    paper_id = Column(String(36), ForeignKey("papers.id"), nullable=False, index=True)
    section_id = Column(String(36), ForeignKey("paper_sections.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    section_title = Column(String(100), nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_embedding = Column(AsyncpgVector(settings.EMBEDDING_DIMENSION))
    chunk_tsv = Column(TSVECTOR)
    span_start = Column(Integer)
    span_end = Column(Integer)
    page_start = Column(Integer)
    page_end = Column(Integer)

    paper = relationship("Paper", back_populates="chunks")
    section = relationship("PaperSection", back_populates="chunks")

    __table_args__ = (
        Index("ix_paper_chunks_paper_id_chunk_index", "paper_id", "chunk_index"),
        Index("ix_paper_chunks_section_id_chunk_index", "section_id", "chunk_index"),
    )

    def __repr__(self):
        return f"<PaperChunk {self.paper_id}:{self.chunk_index}>"


class PaperConcept(BaseModel):
    """Concepts extracted from papers"""

    __tablename__ = "paper_concepts"

    paper_id = Column(String(36), ForeignKey("papers.id"), nullable=False, index=True)
    concept_name = Column(String(255), nullable=False, index=True)
    definition = Column(Text)
    section = Column(String(100))
    role = Column(String(50))

    span_start = Column(Integer)
    span_end = Column(Integer)
    context_text = Column(Text)

    embedding = Column(ARRAY(Float))

    paper = relationship("Paper", back_populates="concepts")

    __table_args__ = (
        Index("ix_paper_concepts_paper_id_concept_name", "paper_id", "concept_name"),
    )

    def __repr__(self):
        return f"<PaperConcept {self.concept_name}>"


class AdvisorLibraryPaper(BaseModel):
    """Papers in advisor's library with metadata"""

    __tablename__ = "advisor_library_papers"

    advisor_id = Column(String(36), ForeignKey("advisors.id"), nullable=False, index=True)
    paper_id = Column(String(36), ForeignKey("papers.id"), nullable=False, index=True)
    sub_field_id = Column(String(36), ForeignKey("advisor_sub_fields.id"), nullable=True)

    library_tags = Column(ARRAY(String), default=[])
    notes = Column(Text)
    added_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    added_by = Column(String(36), nullable=False)

    advisor = relationship("Advisor", back_populates="library_papers")
    paper = relationship("Paper", back_populates="advisor_libraries")
    sub_field = relationship("AdvisorSubField", back_populates="library_papers")

    __table_args__ = (
        Index("ix_advisor_library_papers_advisor_id_paper_id", "advisor_id", "paper_id", unique=True),
    )

    @property
    def sub_field_name(self):
        return self.sub_field.field_name if self.sub_field else None

    def __repr__(self):
        return f"<AdvisorLibraryPaper {self.paper_id}>"


class ReadingHistory(BaseModel):
    """Track researcher's reading activity"""

    __tablename__ = "reading_history"

    researcher_id = Column(String(36), ForeignKey("researchers.id"), nullable=False, index=True)
    paper_id = Column(String(36), ForeignKey("papers.id"), nullable=False, index=True)

    read_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    usefulness_score = Column(Float, default=0.5)
    research_relevance = Column(String(50))

    concepts_noted = Column(ARRAY(String), default=[])
    notes = Column(Text)

    researcher = relationship("Researcher", back_populates="reading_history")
    paper = relationship("Paper", back_populates="reading_history")

    __table_args__ = (
        Index("ix_reading_history_researcher_id_paper_id", "researcher_id", "paper_id"),
    )

    def __repr__(self):
        return f"<ReadingHistory {self.researcher_id} -> {self.paper_id}>"
