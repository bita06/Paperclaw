"""Paper API endpoints."""
import json
from typing import List

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_roles, resolve_researcher_context
from app.exceptions import raise_bad_request
from app.models import User
from app.schemas import (
    ChunkBackfillResponse,
    PaperCreate,
    PaperDetailResponse,
    PaperResponse,
    PaperUpdate,
    PaperUploadResponse,
)
from app.services import paper_chunk_service, paper_service

router = APIRouter(prefix="/papers", tags=["Papers"])


@router.post("/", response_model=PaperResponse, status_code=status.HTTP_201_CREATED)
async def create_paper(
    paper_data: PaperCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> PaperResponse:
    paper = await paper_service.create_paper(db, paper_data)
    return PaperResponse.model_validate(paper)


@router.post("/upload", response_model=PaperUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_paper(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    authors: str | None = Form(default=None, description="JSON array of author names"),
    year: int | None = Form(default=None),
    venue: str | None = Form(default=None),
    doi: str | None = Form(default=None),
    abstract: str | None = Form(default=None),
    keywords: str | None = Form(default=None, description="JSON array of keywords"),
    advisor_ids: str | None = Form(default=None, description="JSON array of advisor IDs"),
    sub_field_ids: str | None = Form(default=None, description="JSON array of sub-field IDs"),
    library_tags: str | None = Form(default=None, description="JSON array of library tags"),
    notes: str | None = Form(default=None),
    researcher_id: str | None = Form(default=None, description="Optional researcher context for sub-field authorization"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "developer_admin")),
) -> PaperUploadResponse:
    researcher_context = resolve_researcher_context(current_user, researcher_id)
    return await paper_service.upload_paper(
        db,
        file=file,
        title=title,
        authors=_parse_json_list(authors, "authors"),
        year=year,
        venue=venue,
        doi=doi,
        abstract=abstract,
        keywords=_parse_json_list(keywords, "keywords"),
        advisor_ids=_parse_json_list(advisor_ids, "advisor_ids"),
        sub_field_ids=_parse_json_list(sub_field_ids, "sub_field_ids"),
        library_tags=_parse_json_list(library_tags, "library_tags"),
        notes=notes,
        researcher_id=researcher_context,
        added_by=current_user.id,
    )


@router.post("/chunks/backfill", response_model=ChunkBackfillResponse)
async def backfill_paper_chunks(
    paper_id: str | None = Query(default=None),
    only_missing: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> ChunkBackfillResponse:
    result = await paper_chunk_service.backfill_chunks(
        db,
        paper_id=paper_id,
        only_missing=only_missing,
        limit=limit,
    )
    return ChunkBackfillResponse(**result)


@router.get("/", response_model=List[PaperResponse])
async def list_papers(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> List[PaperResponse]:
    papers = await paper_service.list_papers(db, skip=skip, limit=limit)
    return [PaperResponse.model_validate(paper) for paper in papers]


@router.get("/{paper_id}", response_model=PaperDetailResponse)
async def get_paper(
    paper_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> PaperDetailResponse:
    return await paper_service.get_paper_detail(db, paper_id)


@router.put("/{paper_id}", response_model=PaperResponse)
async def update_paper(
    paper_id: str,
    paper_data: PaperUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> PaperResponse:
    paper = await paper_service.update_paper(db, paper_id, paper_data)
    return PaperResponse.model_validate(paper)


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper(
    paper_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles("admin", "developer_admin")),
) -> Response:
    await paper_service.delete_paper(db, paper_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _parse_json_list(raw_value: str | None, field_name: str) -> list[str]:
    if not raw_value:
        return []

    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        raise_bad_request(f"{field_name} must be a valid JSON array")

    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise_bad_request(f"{field_name} must be a JSON array of strings")

    return parsed
