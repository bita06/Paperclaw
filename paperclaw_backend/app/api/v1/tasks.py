"""
Task API endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas.file_task import TaskResponse
from app.services.file_task_service import file_task_service

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    return await file_task_service.get_task(db, task_id, current_user)
