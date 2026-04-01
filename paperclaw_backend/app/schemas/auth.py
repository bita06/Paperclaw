"""
Authentication schemas.
"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


UserRole = Literal["researcher", "admin", "developer_admin"]


class RegisterResearcherRequest(BaseModel):
    name: str
    student_id: str
    email: EmailStr
    password: str = Field(min_length=8)
    department: str | None = None
    research_group: str | None = None
    academic_level: str | None = None
    bio: str | None = None


class LoginRequest(BaseModel):
    identifier: str
    password: str


class LogoutResponse(BaseModel):
    message: str


class CreatePrivilegedUserRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    role: Literal["admin", "developer_admin"]
    student_id: str | None = None
    department: str | None = None


class UserResponse(BaseModel):
    id: str
    name: str
    student_id: str | None = None
    email: EmailStr
    role: UserRole
    department: str | None = None
    auth_provider: str
    is_active: bool
    researcher_id: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CurrentUserResponse(UserResponse):
    researcher_name: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: CurrentUserResponse
