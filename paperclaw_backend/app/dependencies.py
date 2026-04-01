"""
FastAPI dependencies for auth and authorization.
"""
from collections.abc import AsyncGenerator, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker
from app.exceptions import raise_forbidden, raise_unauthorized
from app.models import User
from app.security import decode_access_token, is_jwt_error
from app.services.auth_service import auth_service

bearer_scheme = HTTPBearer(auto_error=False)
PRIVILEGED_ROLES = {"admin", "developer_admin"}


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise_unauthorized("Authentication required")

    try:
        payload = decode_access_token(credentials.credentials)
    except Exception as error:
        if is_jwt_error(error):
            raise_unauthorized("Invalid or expired token")
        raise

    user_id = payload.get("sub")
    if not user_id:
        raise_unauthorized("Invalid token payload")

    user = await auth_service.get_user_by_id(db, user_id)
    if not user.is_active:
        raise_forbidden("This account has been disabled")
    return user


def require_roles(*roles: str) -> Callable[..., User]:
    async def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise_forbidden("You do not have permission to access this resource")
        return current_user

    return dependency


def is_privileged(user: User) -> bool:
    return user.role in PRIVILEGED_ROLES


def resolve_researcher_context(user: User, researcher_id: str | None = None) -> str | None:
    if is_privileged(user):
        return researcher_id

    if user.role != "researcher":
        raise_forbidden("This account cannot access researcher context")

    if not user.researcher_id:
        raise_forbidden("Researcher account is not linked to a researcher profile")

    if researcher_id and researcher_id != user.researcher_id:
        raise_forbidden("Researcher accounts can only access their own context")

    return user.researcher_id


def ensure_researcher_access(user: User, researcher_id: str) -> None:
    if is_privileged(user):
        return

    if user.role != "researcher" or user.researcher_id != researcher_id:
        raise_forbidden("Researcher accounts can only access their own profile")
