"""
Researchers API endpoints.
"""
from typing import List

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import ensure_researcher_access, get_current_user, require_roles
from app.models import User
from app.schemas import (
    ResearcherAdvisorLink,
    ResearcherAdvisorCreate,
    ResearcherAdvisorUpdate,
    ResearcherCreate,
    ResearcherPrimaryAdvisorUpdate,
    ResearcherResponse,
    ResearcherStageUpdate,
    ResearcherUpdate,
)
from app.services import researcher_service

router = APIRouter(prefix="/researchers", tags=["Researchers"])


@router.get("/", response_model=List[ResearcherResponse])
async def list_researchers(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ResearcherResponse]:
    if current_user.role == "researcher":
        ensure_researcher_access(current_user, current_user.researcher_id or "")
        researcher = await researcher_service.get_researcher(db, current_user.researcher_id)
        return [ResearcherResponse.model_validate(researcher)]

    researchers = await researcher_service.list_researchers(db, skip=skip, limit=limit)
    return [ResearcherResponse.model_validate(researcher) for researcher in researchers]


@router.post("/", response_model=ResearcherResponse, status_code=status.HTTP_201_CREATED)
async def create_researcher(
    researcher_data: ResearcherCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> ResearcherResponse:
    researcher = await researcher_service.create_researcher(db, researcher_data)
    return ResearcherResponse.model_validate(researcher)


@router.get("/{researcher_id}", response_model=ResearcherResponse)
async def get_researcher(
    researcher_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResearcherResponse:
    ensure_researcher_access(current_user, researcher_id)
    researcher = await researcher_service.get_researcher(db, researcher_id)
    return ResearcherResponse.model_validate(researcher)


@router.put("/{researcher_id}", response_model=ResearcherResponse)
async def update_researcher(
    researcher_id: str,
    researcher_data: ResearcherUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResearcherResponse:
    ensure_researcher_access(current_user, researcher_id)
    researcher = await researcher_service.update_researcher(db, researcher_id, researcher_data)
    return ResearcherResponse.model_validate(researcher)


@router.put("/{researcher_id}/stage", response_model=ResearcherResponse)
async def update_research_stage(
    researcher_id: str,
    stage_data: ResearcherStageUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResearcherResponse:
    ensure_researcher_access(current_user, researcher_id)
    researcher = await researcher_service.update_research_stage(db, researcher_id, stage_data)
    return ResearcherResponse.model_validate(researcher)


@router.put("/{researcher_id}/advisor", response_model=ResearcherAdvisorLink)
async def assign_primary_advisor(
    researcher_id: str,
    advisor_data: ResearcherPrimaryAdvisorUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> ResearcherAdvisorLink:
    return await researcher_service.assign_primary_advisor(db, researcher_id, advisor_data)


@router.get("/{researcher_id}/advisor", response_model=ResearcherAdvisorLink)
async def get_primary_advisor(
    researcher_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResearcherAdvisorLink:
    ensure_researcher_access(current_user, researcher_id)
    return await researcher_service.get_primary_advisor(db, researcher_id)


@router.post("/{researcher_id}/advisors", response_model=ResearcherAdvisorLink, status_code=status.HTTP_201_CREATED)
async def assign_advisor(
    researcher_id: str,
    advisor_data: ResearcherAdvisorCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> ResearcherAdvisorLink:
    return await researcher_service.assign_advisor(db, researcher_id, advisor_data)


@router.get("/{researcher_id}/advisors", response_model=List[ResearcherAdvisorLink])
async def list_advisors(
    researcher_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ResearcherAdvisorLink]:
    ensure_researcher_access(current_user, researcher_id)
    return await researcher_service.list_advisors(db, researcher_id)


@router.get("/{researcher_id}/advisors/{advisor_id}", response_model=ResearcherAdvisorLink)
async def get_advisor_relationship(
    researcher_id: str,
    advisor_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResearcherAdvisorLink:
    ensure_researcher_access(current_user, researcher_id)
    return await researcher_service.get_advisor_relationship(db, researcher_id, advisor_id)


@router.put("/{researcher_id}/advisors/{advisor_id}", response_model=ResearcherAdvisorLink)
async def update_advisor_relationship(
    researcher_id: str,
    advisor_id: str,
    advisor_data: ResearcherAdvisorUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> ResearcherAdvisorLink:
    return await researcher_service.update_advisor_relationship(
        db,
        researcher_id,
        advisor_id,
        advisor_data,
    )


@router.delete("/{researcher_id}/advisor", status_code=status.HTTP_204_NO_CONTENT)
async def remove_primary_advisor(
    researcher_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> Response:
    await researcher_service.remove_primary_advisor(db, researcher_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{researcher_id}/advisors/{advisor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_advisor(
    researcher_id: str,
    advisor_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> Response:
    await researcher_service.remove_advisor(db, researcher_id, advisor_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{researcher_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_researcher(
    researcher_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> Response:
    await researcher_service.delete_researcher(db, researcher_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
