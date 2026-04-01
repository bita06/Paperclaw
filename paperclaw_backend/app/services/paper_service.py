"""
Paper service layer.
"""
import re
from pathlib import Path
from typing import Sequence

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import raise_conflict, raise_not_found
from app.models import Paper
from app.schemas import (
    PaperConceptResponse,
    PaperCreate,
    PaperDetailResponse,
    PaperResponse,
    PaperSectionResponse,
    PaperUpdate,
)
from app.schemas.paper import PaperUploadResponse
from app.schemas.advisor_library import AdvisorLibraryPaperResponse
from app.services.advisor_library_service import advisor_library_service


class PaperService:
    """Business logic for paper CRUD operations."""

    upload_root = Path(__file__).resolve().parents[3] / "paper_uploads" / "papers"

    async def create_paper(
        self,
        db: AsyncSession,
        paper_in: PaperCreate,
    ) -> Paper:
        paper = Paper(**paper_in.model_dump())
        db.add(paper)
        await self._commit_or_raise_conflict(db, "Paper with the same DOI already exists")
        await db.refresh(paper)
        return paper

    async def upload_paper(
        self,
        db: AsyncSession,
        *,
        file: UploadFile,
        title: str | None = None,
        authors: list[str] | None = None,
        year: int | None = None,
        venue: str | None = None,
        doi: str | None = None,
        abstract: str | None = None,
        keywords: list[str] | None = None,
        advisor_ids: list[str] | None = None,
        sub_field_ids: list[str] | None = None,
        library_tags: list[str] | None = None,
        notes: str | None = None,
        researcher_id: str | None = None,
        added_by: str = "upload_api",
    ) -> PaperUploadResponse:
        saved_path = await self._save_upload(file)
        paper = Paper(
            title=title or self._infer_title(file.filename or saved_path.name),
            authors=authors or [],
            year=year,
            venue=venue,
            doi=doi,
            abstract=abstract,
            keywords=keywords or [],
            source="uploaded",
            full_text=None,
            file_path=str(saved_path),
        )
        db.add(paper)
        await self._commit_or_raise_conflict(db, "Paper with the same DOI already exists")
        await db.refresh(paper)

        advisor_links: list[AdvisorLibraryPaperResponse] = []
        if advisor_ids:
            normalized_sub_field_ids = sub_field_ids or []
            if normalized_sub_field_ids and len(normalized_sub_field_ids) not in {1, len(advisor_ids)}:
                raise_conflict("sub_field_ids must be empty, a single value, or match advisor_ids length")

            for index, advisor_id in enumerate(advisor_ids):
                sub_field_id = None
                if normalized_sub_field_ids:
                    sub_field_id = normalized_sub_field_ids[index if len(normalized_sub_field_ids) > 1 else 0]

                library_paper = await advisor_library_service.add_paper_to_library(
                    db,
                    advisor_id=advisor_id,
                    paper_id=paper.id,
                    sub_field_id=sub_field_id,
                    library_tags=library_tags or [],
                    notes=notes,
                    added_by=added_by,
                    researcher_id=researcher_id,
                )
                advisor_links.append(AdvisorLibraryPaperResponse.model_validate(library_paper))

        return PaperUploadResponse(
            paper=PaperResponse.model_validate(paper),
            advisor_links=advisor_links,
        )

    async def list_papers(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[Paper]:
        stmt = (
            select(Paper)
            .order_by(Paper.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_paper(
        self,
        db: AsyncSession,
        paper_id: str,
    ) -> Paper:
        stmt = select(Paper).where(Paper.id == paper_id)
        result = await db.execute(stmt)
        paper = result.scalar_one_or_none()
        if paper is None:
            raise_not_found("Paper not found")
        return paper

    async def get_paper_detail(
        self,
        db: AsyncSession,
        paper_id: str,
    ) -> PaperDetailResponse:
        stmt = (
            select(Paper)
            .options(
                selectinload(Paper.concepts),
                selectinload(Paper.section_contents),
            )
            .where(Paper.id == paper_id)
        )
        result = await db.execute(stmt)
        paper = result.scalar_one_or_none()
        if paper is None:
            raise_not_found("Paper not found")
        return self._build_paper_detail_response(paper)

    async def update_paper(
        self,
        db: AsyncSession,
        paper_id: str,
        paper_in: PaperUpdate,
    ) -> Paper:
        paper = await self.get_paper(db, paper_id)
        update_data = paper_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(paper, field, value)

        await self._commit_or_raise_conflict(db, "Paper with the same DOI already exists")
        await db.refresh(paper)
        return paper

    async def delete_paper(
        self,
        db: AsyncSession,
        paper_id: str,
    ) -> None:
        paper = await self.get_paper(db, paper_id)
        await db.delete(paper)
        await db.commit()

    async def _commit_or_raise_conflict(
        self,
        db: AsyncSession,
        detail: str,
    ) -> None:
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            raise_conflict(detail)

    def _build_paper_detail_response(self, paper: Paper) -> PaperDetailResponse:
        return PaperDetailResponse(
            **PaperResponse.model_validate(paper).model_dump(),
            full_text=paper.full_text,
            file_path=paper.file_path,
            concepts=[
                PaperConceptResponse.model_validate(concept)
                for concept in paper.concepts
            ],
            sections=[
                PaperSectionResponse.model_validate(section)
                for section in paper.section_contents
            ],
        )

    async def _save_upload(self, file: UploadFile) -> Path:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in {".pdf", ".doc", ".docx"}:
            raise_conflict("Only PDF, DOC, and DOCX uploads are supported")

        self.upload_root.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(file.filename or "paper").name)
        target = self.upload_root / safe_name
        counter = 1
        while target.exists():
            target = self.upload_root / f"{target.stem}_{counter}{target.suffix}"
            counter += 1

        target.write_bytes(await file.read())
        await file.close()
        return target

    def _infer_title(self, filename: str) -> str:
        stem = Path(filename).stem
        normalized = re.sub(r"[_-]+", " ", stem).strip()
        return normalized or "Untitled Paper"


paper_service = PaperService()

