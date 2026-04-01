"""
Pydantic Schemas - Advisor Library and Papers
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# === AdvisorLibraryPaper Schemas ===

class AdvisorLibraryPaperBase(BaseModel):
    """Base schema for advisor library papers"""
    library_tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class AdvisorLibraryPaperCreate(AdvisorLibraryPaperBase):
    """Schema for creating advisor library paper relationship"""
    advisor_id: Optional[str] = None
    paper_id: str
    sub_field_id: Optional[str] = None


class AdvisorLibraryPaperUpdate(BaseModel):
    """Schema for updating advisor library paper"""
    library_tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class AdvisorLibraryPaperResponse(AdvisorLibraryPaperBase):
    """Response schema for advisor library paper"""
    id: str
    advisor_id: str
    paper_id: str
    sub_field_id: Optional[str] = None
    sub_field_name: Optional[str] = None
    added_at: datetime
    added_by: str

    class Config:
        from_attributes = True


# === AdvisorSubField Schemas ===

class AdvisorSubFieldBase(BaseModel):
    """Base schema for advisor sub-field"""
    field_name: str
    description: Optional[str] = None
    display_order: int = 0


class AdvisorSubFieldCreate(AdvisorSubFieldBase):
    """Schema for creating advisor sub-field"""
    advisor_id: str


class AdvisorSubFieldUpdate(BaseModel):
    """Schema for updating advisor sub-field"""
    field_name: Optional[str] = None
    description: Optional[str] = None
    display_order: Optional[int] = None


class AdvisorSubFieldResponse(AdvisorSubFieldBase):
    """Response schema for advisor sub-field"""
    id: str
    advisor_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# === Advisor Schemas ===

class AdvisorBase(BaseModel):
    """Base schema for advisor"""
    name: str
    email: str
    affiliation: Optional[str] = None
    research_areas: List[str] = Field(default_factory=list)
    bio: Optional[str] = None


class AdvisorCreate(AdvisorBase):
    """Schema for creating advisor"""
    pass


class AdvisorUpdate(BaseModel):
    """Schema for updating advisor"""
    name: Optional[str] = None
    email: Optional[str] = None
    affiliation: Optional[str] = None
    research_areas: List[str] = Field(default_factory=list)
    bio: Optional[str] = None


class AdvisorResponse(AdvisorBase):
    """Response schema for advisor"""
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AdvisorDetailResponse(AdvisorResponse):
    """Detailed response schema for advisor including sub-fields"""
    sub_fields: List[AdvisorSubFieldResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True
