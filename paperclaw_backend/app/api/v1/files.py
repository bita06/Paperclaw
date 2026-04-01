"""
Files API endpoints.
"""
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, resolve_researcher_context
from app.models import User
from app.schemas.file_task import FileHistoryItemResponse, FileStatusResponse, FileUploadAcceptedResponse
from app.services.file_task_service import file_task_service

router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/upload", response_model=FileUploadAcceptedResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    researcher_id: str | None = Form(default=None, description="Optional researcher context for privileged users"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileUploadAcceptedResponse:
    researcher_context = resolve_researcher_context(current_user, researcher_id)
    return await file_task_service.upload_file(
        db,
        file=file,
        current_user=current_user,
        researcher_id=researcher_context,
    )


@router.get("/history", response_model=list[FileHistoryItemResponse])
async def list_file_history(
    researcher_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[FileHistoryItemResponse]:
    researcher_context = resolve_researcher_context(current_user, researcher_id)
    return await file_task_service.list_file_history(
        db,
        current_user=current_user,
        researcher_id=researcher_context,
        limit=limit,
    )


@router.get("/{file_id}/status", response_model=FileStatusResponse)
async def get_file_status(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileStatusResponse:
    return await file_task_service.get_file_status(db, file_id, current_user)
