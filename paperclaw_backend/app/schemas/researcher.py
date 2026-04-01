"""
Pydantic Schemas - Researcher
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# === Advisor Schemas ===

class AdvisorSubFieldBase(BaseModel):
    field_name: str
    description: Optional[str] = None
    display_order: int = 0


class AdvisorSubFieldCreate(AdvisorSubFieldBase):
    pass


class AdvisorSubFieldResponse(AdvisorSubFieldBase):
    id: str
    advisor_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AdvisorBase(BaseModel):
    name: str
    email: EmailStr
    affiliation: Optional[str] = None
    research_areas: List[str] = []
    bio: Optional[str] = None


class AdvisorCreate(AdvisorBase):
    password: str


class AdvisorUpdate(BaseModel):
    name: Optional[str] = None
    affiliation: Optional[str] = None
    research_areas: Optional[List[str]] = None
    bio: Optional[str] = None


class AdvisorResponse(AdvisorBase):
    id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AdvisorWithLibraryResponse(AdvisorResponse):
    sub_fields: List[AdvisorSubFieldResponse] = []
    papers_count: int = 0


# === Researcher Schemas ===

class ResearcherAdvisorLink(BaseModel):
    advisor_id: str
    advisor_name: str
    relationship_type: str  # 'primary_advisor', 'co_advisor', 'mentor'
    access_level: str
    sub_fields_access: List[str] = Field(default_factory=list)
    joined_at: datetime


class ResearcherBase(BaseModel):
    name: str
    email: EmailStr
    research_group: Optional[str] = None
    academic_level: Optional[str] = None
    bio: Optional[str] = None


class ResearcherCreate(ResearcherBase):
    password: str
    primary_advisor_id: Optional[str] = None


class ResearcherUpdate(BaseModel):
    name: Optional[str] = None
    research_group: Optional[str] = None
    academic_level: Optional[str] = None
    bio: Optional[str] = None
    current_stage: Optional[str] = None
    current_research_question: Optional[str] = None
    primary_advisor_id: Optional[str] = None


class ResearcherStageUpdate(BaseModel):
    current_stage: str
    current_research_question: Optional[str] = None


class ResearcherResponse(ResearcherBase):
    id: str
    is_active: bool
    current_stage: Optional[str] = None
    current_research_question: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ResearcherWithAdvisorsResponse(ResearcherResponse):
    advisor_links: List[ResearcherAdvisorLink] = Field(default_factory=list)


# === Researcher Advisor Link Schemas ===

class ResearcherAdvisorCreate(BaseModel):
    advisor_id: str
    relationship_type: str = "co_advisor"
    access_level: str = "full"
    sub_fields_access: List[str] = Field(default_factory=list)


class ResearcherPrimaryAdvisorUpdate(BaseModel):
    advisor_id: str


class ResearcherAdvisorUpdate(BaseModel):
    relationship_type: Optional[str] = None
    access_level: Optional[str] = None
    sub_fields_access: Optional[List[str]] = None


# === Researcher Concept Schemas ===

class ResearcherConceptCreate(BaseModel):
    concept_name: str
    definition: Optional[str] = None
    importance: float = 0.5


class ResearcherConceptUpdate(BaseModel):
    definition: Optional[str] = None
    importance: Optional[float] = None


class ResearcherConceptResponse(BaseModel):
    id: str
    researcher_id: str
    concept_name: str
    definition: Optional[str]
    importance: float
    encounter_count: int
    last_encountered: datetime
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
