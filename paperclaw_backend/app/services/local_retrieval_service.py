"""Utilities for defining and querying the local retrievable knowledge scope."""
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import AdvisorLibraryPaper, AdvisorSubField, Paper, PaperSource, ResearcherAdvisor, StoredFile
from app.services.advisor_library_service import advisor_library_service


class LocalRetrievalService:
    async def list_retrievable_library_items(
        self,
        db: AsyncSession,
        *,
        researcher_id: str,
        advisor_ids: Sequence[str] | None = None,
        limit_per_advisor: int = 50,
    ) -> list[AdvisorLibraryPaper]:
        links = await self._get_researcher_links(db, researcher_id, advisor_ids)
        items: list[AdvisorLibraryPaper] = []
        for link in links:
            advisor_items = await advisor_library_service.list_library_papers(
                db,
                link.advisor_id,
                researcher_id=researcher_id,
                limit=limit_per_advisor,
            )
            items.extend(advisor_items)
        return items

    async def is_paper_retrievable_for_researcher(
        self,
        db: AsyncSession,
        *,
        researcher_id: str,
        paper_id: str,
        advisor_ids: Sequence[str] | None = None,
    ) -> bool:
        links = await self._get_researcher_links(db, researcher_id, advisor_ids)
        if not links:
            return False

        for link in links:
            allowed_sub_field_ids = await self._get_allowed_sub_field_ids(db, link)
            stmt = select(AdvisorLibraryPaper.id).where(
                AdvisorLibraryPaper.advisor_id == link.advisor_id,
                AdvisorLibraryPaper.paper_id == paper_id,
            )
            if link.sub_fields_access:
                if allowed_sub_field_ids:
                    stmt = stmt.where(
                        (AdvisorLibraryPaper.sub_field_id.is_(None))
                        | (AdvisorLibraryPaper.sub_field_id.in_(allowed_sub_field_ids))
                    )
                else:
                    stmt = stmt.where(AdvisorLibraryPaper.sub_field_id.is_(None))
            else:
                stmt = stmt.where(AdvisorLibraryPaper.sub_field_id.is_(None))
            result = await db.execute(stmt.limit(1))
            if result.scalar_one_or_none() is not None:
                return True
        return False

    async def list_builtin_papers(
        self,
        db: AsyncSession,
        *,
        collection_slug: str | None = None,
        limit: int = 50,
    ) -> list[Paper]:
        stmt = (
            select(Paper)
            .options(selectinload(Paper.section_contents))
            .where(Paper.source == PaperSource.BUILTIN_LIBRARY)
            .order_by(Paper.created_at.desc())
            .limit(limit)
        )
        if collection_slug:
            stmt = stmt.where(Paper.collection_slug == collection_slug)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_builtin_collections(self, db: AsyncSession) -> list[str]:
        stmt = (
            select(Paper.collection_slug)
            .where(Paper.source == PaperSource.BUILTIN_LIBRARY, Paper.collection_slug.is_not(None))
            .distinct()
            .order_by(Paper.collection_slug.asc())
        )
        result = await db.execute(stmt)
        return [value for value in result.scalars().all() if value]

    async def list_user_uploaded_papers(
        self,
        db: AsyncSession,
        *,
        owner_user_id: str | None = None,
        researcher_id: str | None = None,
        limit: int = 50,
    ) -> list[Paper]:
        candidate_ids: set[str] = set()

        if owner_user_id:
            paper_result = await db.execute(
                select(Paper.id).where(Paper.source == PaperSource.UPLOADED, Paper.owner_user_id == owner_user_id).limit(limit)
            )
            candidate_ids.update(paper_result.scalars().all())

        file_stmt = select(StoredFile.linked_paper_id).where(StoredFile.linked_paper_id.is_not(None))
        if owner_user_id and researcher_id:
            file_stmt = file_stmt.where((StoredFile.uploaded_by == owner_user_id) | (StoredFile.researcher_id == researcher_id))
        elif owner_user_id:
            file_stmt = file_stmt.where(StoredFile.uploaded_by == owner_user_id)
        elif researcher_id:
            file_stmt = file_stmt.where(StoredFile.researcher_id == researcher_id)
        else:
            return []

        file_stmt = file_stmt.limit(limit)
        file_result = await db.execute(file_stmt)
        candidate_ids.update([paper_id for paper_id in file_result.scalars().all() if paper_id])

        if not candidate_ids:
            return []

        stmt = (
            select(Paper)
            .options(selectinload(Paper.section_contents))
            .where(Paper.id.in_(sorted(candidate_ids)))
            .order_by(Paper.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_researcher_links(
        self,
        db: AsyncSession,
        researcher_id: str,
        advisor_ids: Sequence[str] | None = None,
    ) -> list[ResearcherAdvisor]:
        stmt = select(ResearcherAdvisor).where(ResearcherAdvisor.researcher_id == researcher_id)
        if advisor_ids:
            stmt = stmt.where(ResearcherAdvisor.advisor_id.in_(list(advisor_ids)))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _get_allowed_sub_field_ids(self, db: AsyncSession, link: ResearcherAdvisor) -> list[str]:
        if not link.sub_fields_access:
            return []
        stmt = select(AdvisorSubField.id).where(
            AdvisorSubField.advisor_id == link.advisor_id,
            AdvisorSubField.field_name.in_(link.sub_fields_access),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


local_retrieval_service = LocalRetrievalService()
