"""
Authentication service layer.
"""
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.exceptions import raise_conflict, raise_forbidden, raise_not_found, raise_unauthorized
from app.models import Researcher, User
from app.schemas.auth import (
    CreatePrivilegedUserRequest,
    CurrentUserResponse,
    LoginRequest,
    RegisterResearcherRequest,
    TokenResponse,
    UserResponse,
)
from app.security import create_access_token, hash_password, verify_password


class AuthService:
    async def register_researcher(
        self,
        db: AsyncSession,
        payload: RegisterResearcherRequest,
    ) -> TokenResponse:
        password_hash = hash_password(payload.password)
        researcher = Researcher(
            name=payload.name,
            email=payload.email,
            password_hash=password_hash,
            research_group=payload.research_group,
            academic_level=payload.academic_level,
            bio=payload.bio,
        )
        db.add(researcher)
        await db.flush()

        user = User(
            name=payload.name,
            student_id=payload.student_id,
            email=payload.email,
            password_hash=password_hash,
            role="researcher",
            department=payload.department,
            researcher_id=researcher.id,
        )
        db.add(user)

        await self._commit_or_raise_conflict(
            db,
            "A user with the same email or student ID already exists",
        )
        await db.refresh(user)
        await db.refresh(researcher)
        return self._build_token_response(user, researcher)

    async def login(
        self,
        db: AsyncSession,
        payload: LoginRequest,
    ) -> TokenResponse:
        user = await self.get_user_by_identifier(db, payload.identifier)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise_unauthorized("Incorrect account or password")

        if not user.is_active:
            raise_forbidden("This account has been disabled")

        return self._build_token_response(user, user.researcher)

    async def get_current_user_profile(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> CurrentUserResponse:
        user = await self.get_user_by_id(db, user_id)
        return self._build_user_profile(user, user.researcher)

    async def create_privileged_user(
        self,
        db: AsyncSession,
        payload: CreatePrivilegedUserRequest,
    ) -> UserResponse:
        user = User(
            name=payload.name,
            student_id=payload.student_id,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=payload.role,
            department=payload.department,
        )
        db.add(user)
        await self._commit_or_raise_conflict(
            db,
            "A user with the same email or student ID already exists",
        )
        await db.refresh(user)
        return UserResponse.model_validate(user)

    async def ensure_bootstrap_developer_admin(self, db: AsyncSession) -> None:
        if not settings.BOOTSTRAP_DEVELOPER_ADMIN_EMAIL or not settings.BOOTSTRAP_DEVELOPER_ADMIN_PASSWORD:
            return

        existing = await self.get_user_by_identifier(db, settings.BOOTSTRAP_DEVELOPER_ADMIN_EMAIL)
        if existing is not None:
            return

        user = User(
            name=settings.BOOTSTRAP_DEVELOPER_ADMIN_NAME or "Developer Admin",
            email=settings.BOOTSTRAP_DEVELOPER_ADMIN_EMAIL,
            password_hash=hash_password(settings.BOOTSTRAP_DEVELOPER_ADMIN_PASSWORD),
            role="developer_admin",
            department=settings.BOOTSTRAP_DEVELOPER_ADMIN_DEPARTMENT or "PaperClaw",
        )
        db.add(user)
        await db.commit()

    async def get_user_by_identifier(
        self,
        db: AsyncSession,
        identifier: str,
    ) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.researcher))
            .where(or_(User.email == identifier, User.student_id == identifier))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_id(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> User:
        stmt = (
            select(User)
            .options(selectinload(User.researcher))
            .where(User.id == user_id)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise_not_found("User not found")
        return user

    async def _commit_or_raise_conflict(self, db: AsyncSession, detail: str) -> None:
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise_conflict(detail)

    def _build_user_profile(
        self,
        user: User,
        researcher: Researcher | None,
    ) -> CurrentUserResponse:
        return CurrentUserResponse(
            **UserResponse.model_validate(user).model_dump(),
            researcher_name=researcher.name if researcher else None,
        )

    def _build_token_response(
        self,
        user: User,
        researcher: Researcher | None,
    ) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user.id, user.role),
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=self._build_user_profile(user, researcher),
        )


auth_service = AuthService()
