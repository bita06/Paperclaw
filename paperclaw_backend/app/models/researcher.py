"""
SQLAlchemy Models - Advisor and Researcher Relationship
"""
from sqlalchemy import ARRAY, Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class Advisor(BaseModel):
    """Advisor/Teacher Account"""
    __tablename__ = "advisors"
    
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    affiliation = Column(String(255))  # 清华大学
    research_areas = Column(ARRAY(String), default=[])  # ['governance', 'policy']
    bio = Column(Text)
    
    # Relationships
    sub_fields = relationship("AdvisorSubField", back_populates="advisor", cascade="all, delete-orphan")
    library_papers = relationship("AdvisorLibraryPaper", back_populates="advisor", cascade="all, delete-orphan")
    researcher_links = relationship("ResearcherAdvisor", back_populates="advisor", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Advisor {self.name} ({self.email})>"


class AdvisorSubField(BaseModel):
    """Research sub-fields within an advisor's library"""
    __tablename__ = "advisor_sub_fields"
    
    advisor_id = Column(String(36), ForeignKey("advisors.id"), nullable=False, index=True)
    field_name = Column(String(255), nullable=False)
    description = Column(Text)
    display_order = Column(Integer, default=0)
    
    # Relationships
    advisor = relationship("Advisor", back_populates="sub_fields")
    library_papers = relationship("AdvisorLibraryPaper", back_populates="sub_field")
    
    __table_args__ = (
        Index("ix_advisor_sub_fields_advisor_id_field_name", "advisor_id", "field_name", unique=True),
    )
    
    def __repr__(self):
        return f"<AdvisorSubField {self.field_name}>"


class Researcher(BaseModel):
    """Researcher/Student Account"""
    __tablename__ = "researchers"
    
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    primary_advisor_id = Column(String(36), ForeignKey("advisors.id"), nullable=True)
    research_group = Column(String(255))
    academic_level = Column(String(50))  # 'PhD', 'Master', 'Bachelor'
    bio = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # Current research task
    current_stage = Column(String(100))  # 'topic_selection', 'literature_review', etc.
    current_research_question = Column(Text)
    
    # Relationships
    user = relationship("User", back_populates="researcher", uselist=False)
    advisor_links = relationship("ResearcherAdvisor", back_populates="researcher", cascade="all, delete-orphan")
    reading_history = relationship("ReadingHistory", back_populates="researcher", cascade="all, delete-orphan")
    research_concepts = relationship("ResearcherConcept", back_populates="researcher", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Researcher {self.name} ({self.email})>"


class ResearcherAdvisor(BaseModel):
    """Many-to-many relationship between researchers and advisors"""
    __tablename__ = "researcher_advisors"
    
    researcher_id = Column(String(36), ForeignKey("researchers.id"), nullable=False, index=True)
    advisor_id = Column(String(36), ForeignKey("advisors.id"), nullable=False, index=True)
    relationship_type = Column(String(50), nullable=False)  # 'primary_advisor', 'co_advisor', 'mentor'
    access_level = Column(String(50), nullable=False, default="full")  # 'full', 'readonly'
    sub_fields_access = Column(ARRAY(String), nullable=False, default=list)
    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    researcher = relationship("Researcher", back_populates="advisor_links")
    advisor = relationship("Advisor", back_populates="researcher_links")
    
    __table_args__ = (
        Index("ix_researcher_advisors_researcher_id_advisor_id", "researcher_id", "advisor_id", unique=True),
    )
    
    def __repr__(self):
        return f"<ResearcherAdvisor {self.researcher_id} -> {self.advisor_id}>"


class ResearcherConcept(BaseModel):
    """Track researcher's understanding of concepts over time"""
    __tablename__ = "researcher_concepts"
    
    researcher_id = Column(String(36), ForeignKey("researchers.id"), nullable=False, index=True)
    concept_name = Column(String(255), nullable=False, index=True)
    definition = Column(Text)
    importance = Column(String(50), default=0.5)  # 0.0-1.0
    encounter_count = Column(Integer, default=1)
    last_encountered = Column(DateTime, default=datetime.utcnow)
    context_embedding = Column(ARRAY(Float))  # For semantic search
    
    # Relationships
    researcher = relationship("Researcher", back_populates="research_concepts")
    
    __table_args__ = (
        Index("ix_researcher_concepts_researcher_id_concept_name", "researcher_id", "concept_name", unique=True),
    )
    
    def __repr__(self):
        return f"<ResearcherConcept {self.concept_name}>"
