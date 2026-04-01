"""
Advisor Library API endpoints.
"""
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, require_roles, resolve_researcher_context
from app.models import User
from app.schemas import (
    AdvisorCreate,
    AdvisorDetailResponse,
    AdvisorLibraryPaperCreate,
    AdvisorLibraryPaperResponse,
    AdvisorLibraryPaperUpdate,
    AdvisorLibraryPaperWithPaperResponse,
    AdvisorResponse,
    AdvisorSubFieldCreate,
    AdvisorSubFieldResponse,
    AdvisorSubFieldUpdate,
    AdvisorUpdate,
)
from app.services.advisor_library_service import advisor_library_service

router = APIRouter(prefix="/advisors", tags=["Advisors"])


@router.post("", response_model=AdvisorResponse, status_code=status.HTTP_201_CREATED)
async def create_advisor(
    advisor_data: AdvisorCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> AdvisorResponse:
    advisor = await advisor_library_service.create_advisor(db, advisor_data)
    return AdvisorResponse.model_validate(advisor)


@router.get("", response_model=List[AdvisorResponse])
async def list_advisors(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> List[AdvisorResponse]:
    advisors = await advisor_library_service.list_advisors(db, skip=skip, limit=limit)
    return [AdvisorResponse.model_validate(advisor) for advisor in advisors]


@router.get("/{advisor_id}", response_model=AdvisorDetailResponse)
async def get_advisor(
    advisor_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AdvisorDetailResponse:
    advisor = await advisor_library_service.get_advisor(db, advisor_id)
    return AdvisorDetailResponse.model_validate(advisor)


@router.put("/{advisor_id}", response_model=AdvisorResponse)
async def update_advisor(
    advisor_id: str,
    advisor_data: AdvisorUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> AdvisorResponse:
    advisor = await advisor_library_service.update_advisor(db, advisor_id, advisor_data)
    return AdvisorResponse.model_validate(advisor)


@router.delete("/{advisor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_advisor(
    advisor_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
):
    await advisor_library_service.delete_advisor(db, advisor_id)


@router.post("/{advisor_id}/sub-fields", response_model=AdvisorSubFieldResponse, status_code=status.HTTP_201_CREATED)
async def create_sub_field(
    advisor_id: str,
    sub_field_data: AdvisorSubFieldCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> AdvisorSubFieldResponse:
    sub_field_data.advisor_id = advisor_id
    sub_field = await advisor_library_service.create_sub_field(db, sub_field_data)
    return AdvisorSubFieldResponse.model_validate(sub_field)


@router.get("/{advisor_id}/sub-fields", response_model=List[AdvisorSubFieldResponse])
async def list_sub_fields(
    advisor_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> List[AdvisorSubFieldResponse]:
    sub_fields = await advisor_library_service.list_sub_fields(db, advisor_id)
    return [AdvisorSubFieldResponse.model_validate(sf) for sf in sub_fields]


@router.put("/sub-fields/{sub_field_id}", response_model=AdvisorSubFieldResponse)
async def update_sub_field(
    sub_field_id: str,
    sub_field_data: AdvisorSubFieldUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> AdvisorSubFieldResponse:
    sub_field = await advisor_library_service.update_sub_field(db, sub_field_id, sub_field_data)
    return AdvisorSubFieldResponse.model_validate(sub_field)


@router.delete("/sub-fields/{sub_field_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sub_field(
    sub_field_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
):
    await advisor_library_service.delete_sub_field(db, sub_field_id)


@router.post("/{advisor_id}/papers", response_model=AdvisorLibraryPaperResponse, status_code=status.HTTP_201_CREATED)
async def add_paper_to_library(
    advisor_id: str,
    paper_data: AdvisorLibraryPaperCreate,
    db: AsyncSession = Depends(get_db),
    researcher_id: str | None = Query(default=None, description="Optional researcher context for sub-field authorization"),
    current_user: User = Depends(require_roles("admin", "developer_admin")),
) -> AdvisorLibraryPaperResponse:
    researcher_context = resolve_researcher_context(current_user, researcher_id)
    library_paper = await advisor_library_service.add_paper_to_library(
        db,
        advisor_id=advisor_id,
        paper_id=paper_data.paper_id,
        sub_field_id=paper_data.sub_field_id,
        library_tags=paper_data.library_tags,
        notes=paper_data.notes,
        added_by=current_user.id,
        researcher_id=researcher_context,
    )
    return AdvisorLibraryPaperResponse.model_validate(library_paper)


@router.get("/{advisor_id}/papers", response_model=List[AdvisorLibraryPaperWithPaperResponse])
async def list_library_papers(
    advisor_id: str,
    sub_field_id: str | None = Query(default=None, description="Optional filter by sub-field"),
    tag: str | None = Query(default=None, description="Optional filter by library tag"),
    researcher_id: str | None = Query(default=None, description="Optional researcher context for sub-field authorization"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AdvisorLibraryPaperWithPaperResponse]:
    researcher_context = resolve_researcher_context(current_user, researcher_id)
    library_papers = await advisor_library_service.list_library_papers(
        db,
        advisor_id,
        sub_field_id=sub_field_id,
        tag=tag,
        researcher_id=researcher_context,
        skip=skip,
        limit=limit,
    )
    return [AdvisorLibraryPaperWithPaperResponse.model_validate(lp) for lp in library_papers]


@router.get("/{advisor_id}/papers/tag/{tag}", response_model=List[AdvisorLibraryPaperWithPaperResponse])
async def get_papers_by_tag(
    advisor_id: str,
    tag: str,
    researcher_id: str | None = Query(default=None, description="Optional researcher context for sub-field authorization"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AdvisorLibraryPaperWithPaperResponse]:
    researcher_context = resolve_researcher_context(current_user, researcher_id)
    library_papers = await advisor_library_service.get_papers_by_tag(
        db,
        advisor_id,
        tag,
        researcher_id=researcher_context,
        skip=skip,
        limit=limit,
    )
    return [AdvisorLibraryPaperWithPaperResponse.model_validate(lp) for lp in library_papers]


@router.get("/{advisor_id}/papers/{paper_id}", response_model=AdvisorLibraryPaperWithPaperResponse)
async def get_library_paper(
    advisor_id: str,
    paper_id: str,
    researcher_id: str | None = Query(default=None, description="Optional researcher context for sub-field authorization"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdvisorLibraryPaperWithPaperResponse:
    researcher_context = resolve_researcher_context(current_user, researcher_id)
    library_paper = await advisor_library_service.get_library_paper(
        db,
        advisor_id,
        paper_id,
        researcher_id=researcher_context,
    )
    return AdvisorLibraryPaperWithPaperResponse.model_validate(library_paper)


@router.put("/{advisor_id}/papers/{paper_id}", response_model=AdvisorLibraryPaperResponse)
async def update_library_paper(
    advisor_id: str,
    paper_id: str,
    update_data: AdvisorLibraryPaperUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> AdvisorLibraryPaperResponse:
    library_paper = await advisor_library_service.update_library_paper(db, advisor_id, paper_id, update_data)
    return AdvisorLibraryPaperResponse.model_validate(library_paper)


@router.delete("/{advisor_id}/papers/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_paper_from_library(
    advisor_id: str,
    paper_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
):
    await advisor_library_service.remove_paper_from_library(db, advisor_id, paper_id)
