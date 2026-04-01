"""
Authentication API endpoints.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles
from app.models import User
from app.schemas.auth import (
    CreatePrivilegedUserRequest,
    CurrentUserResponse,
    LoginRequest,
    LogoutResponse,
    RegisterResearcherRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_researcher(
    payload: RegisterResearcherRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await auth_service.register_researcher(db, payload)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    return await auth_service.login(db, payload)


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    _: User = Depends(get_current_user),
) -> LogoutResponse:
    return LogoutResponse(message="Logged out successfully")


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CurrentUserResponse:
    return await auth_service.get_current_user_profile(db, current_user.id)


@router.post("/admin-users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_privileged_user(
    payload: CreatePrivilegedUserRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> UserResponse:
    return await auth_service.create_privileged_user(db, payload)
