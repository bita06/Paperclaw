"""
Advisor Library service layer - handles paper library management for advisors.
"""
from typing import List, Optional, Sequence

from loguru import logger
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import raise_conflict, raise_forbidden, raise_not_found
from app.models import Advisor, AdvisorLibraryPaper, AdvisorSubField, Paper, ResearcherAdvisor
from app.schemas import (
    AdvisorCreate,
    AdvisorLibraryPaperCreate,
    AdvisorLibraryPaperUpdate,
    AdvisorSubFieldCreate,
    AdvisorSubFieldUpdate,
    AdvisorUpdate,
)


class AdvisorLibraryService:
    """Business logic for advisor library paper management."""

    async def add_paper_to_library(
        self,
        db: AsyncSession,
        *,
        advisor_id: str,
        paper_id: str,
        sub_field_id: Optional[str],
        library_tags: List[str],
        notes: Optional[str],
        added_by: str,
        researcher_id: Optional[str] = None,
    ) -> AdvisorLibraryPaper:
        await self._get_advisor(db, advisor_id)
        await self._get_paper(db, paper_id)
        sub_field = await self._validate_sub_field(db, advisor_id, sub_field_id)

        if researcher_id and sub_field is not None:
            await self._ensure_sub_field_authorized(
                db,
                researcher_id=researcher_id,
                advisor_id=advisor_id,
                sub_field=sub_field,
            )

        try:
            library_paper = AdvisorLibraryPaper(
                advisor_id=advisor_id,
                paper_id=paper_id,
                sub_field_id=sub_field_id,
                library_tags=library_tags,
                notes=notes,
                added_by=added_by,
            )
            db.add(library_paper)
            await db.commit()
            await db.refresh(library_paper, attribute_names=["paper", "sub_field"])
            logger.info(f"Added paper {paper_id} to advisor {advisor_id}'s library")
            return library_paper
        except IntegrityError:
            await db.rollback()
            raise_conflict("Paper already exists in this advisor's library")

    async def remove_paper_from_library(
        self,
        db: AsyncSession,
        advisor_id: str,
        paper_id: str,
    ) -> bool:
        stmt = select(AdvisorLibraryPaper).where(
            and_(
                AdvisorLibraryPaper.advisor_id == advisor_id,
                AdvisorLibraryPaper.paper_id == paper_id,
            )
        )
        result = await db.execute(stmt)
        library_paper = result.scalar_one_or_none()

        if not library_paper:
            raise_not_found("Paper not found in this advisor's library")

        await db.delete(library_paper)
        await db.commit()
        logger.info(f"Removed paper {paper_id} from advisor {advisor_id}'s library")
        return True

    async def get_library_paper(
        self,
        db: AsyncSession,
        advisor_id: str,
        paper_id: str,
        researcher_id: Optional[str] = None,
    ) -> AdvisorLibraryPaper:
        stmt = (
            select(AdvisorLibraryPaper)
            .options(
                selectinload(AdvisorLibraryPaper.paper).selectinload(Paper.section_contents),
                selectinload(AdvisorLibraryPaper.sub_field),
            )
            .where(
                and_(
                    AdvisorLibraryPaper.advisor_id == advisor_id,
                    AdvisorLibraryPaper.paper_id == paper_id,
                )
            )
        )
        result = await db.execute(stmt)
        library_paper = result.scalar_one_or_none()

        if not library_paper:
            raise_not_found("Paper not found in this advisor's library")

        if researcher_id and library_paper.sub_field_id:
            await self._ensure_sub_field_authorized_by_id(
                db,
                researcher_id=researcher_id,
                advisor_id=advisor_id,
                sub_field_id=library_paper.sub_field_id,
            )

        return library_paper

    async def list_library_papers(
        self,
        db: AsyncSession,
        advisor_id: str,
        *,
        sub_field_id: Optional[str] = None,
        tag: Optional[str] = None,
        researcher_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[AdvisorLibraryPaper]:
        stmt = (
            select(AdvisorLibraryPaper)
            .where(AdvisorLibraryPaper.advisor_id == advisor_id)
            .options(
                selectinload(AdvisorLibraryPaper.paper).selectinload(Paper.section_contents),
                selectinload(AdvisorLibraryPaper.sub_field),
            )
            .order_by(AdvisorLibraryPaper.added_at.desc())
        )

        if sub_field_id:
            stmt = stmt.where(AdvisorLibraryPaper.sub_field_id == sub_field_id)

        if tag:
            stmt = stmt.where(AdvisorLibraryPaper.library_tags.contains([tag]))

        if researcher_id:
            allowed_sub_field_ids = await self._get_authorized_sub_field_ids(
                db,
                researcher_id=researcher_id,
                advisor_id=advisor_id,
            )
            if allowed_sub_field_ids:
                stmt = stmt.where(
                    or_(
                        AdvisorLibraryPaper.sub_field_id.is_(None),
                        AdvisorLibraryPaper.sub_field_id.in_(allowed_sub_field_ids),
                    )
                )
            else:
                stmt = stmt.where(AdvisorLibraryPaper.sub_field_id.is_(None))

        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def update_library_paper(
        self,
        db: AsyncSession,
        advisor_id: str,
        paper_id: str,
        update_data: AdvisorLibraryPaperUpdate,
    ) -> AdvisorLibraryPaper:
        library_paper = await self.get_library_paper(db, advisor_id, paper_id)

        if update_data.sub_field_id is not None:
            await self._validate_sub_field(db, advisor_id, update_data.sub_field_id)

        update_fields = update_data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(library_paper, field, value)

        await db.commit()
        await db.refresh(library_paper, attribute_names=["paper", "sub_field"])
        logger.info(f"Updated paper {paper_id} in advisor {advisor_id}'s library")
        return library_paper

    async def get_papers_by_tag(
        self,
        db: AsyncSession,
        advisor_id: str,
        tag: str,
        researcher_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[AdvisorLibraryPaper]:
        return await self.list_library_papers(
            db,
            advisor_id,
            tag=tag,
            researcher_id=researcher_id,
            skip=skip,
            limit=limit,
        )

    async def create_sub_field(
        self,
        db: AsyncSession,
        sub_field_in: AdvisorSubFieldCreate,
    ) -> AdvisorSubField:
        try:
            sub_field = AdvisorSubField(**sub_field_in.model_dump())
            db.add(sub_field)
            await db.commit()
            await db.refresh(sub_field)
            logger.info(f"Created sub-field {sub_field_in.field_name} for advisor {sub_field_in.advisor_id}")
            return sub_field
        except IntegrityError:
            await db.rollback()
            raise_conflict("Sub-field with this name already exists for this advisor")

    async def list_sub_fields(
        self,
        db: AsyncSession,
        advisor_id: str,
    ) -> Sequence[AdvisorSubField]:
        stmt = (
            select(AdvisorSubField)
            .where(AdvisorSubField.advisor_id == advisor_id)
            .order_by(AdvisorSubField.display_order)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def update_sub_field(
        self,
        db: AsyncSession,
        sub_field_id: str,
        update_data: AdvisorSubFieldUpdate,
    ) -> AdvisorSubField:
        stmt = select(AdvisorSubField).where(AdvisorSubField.id == sub_field_id)
        result = await db.execute(stmt)
        sub_field = result.scalar_one_or_none()

        if not sub_field:
            raise_not_found("Sub-field not found")

        update_fields = update_data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(sub_field, field, value)

        await db.commit()
        await db.refresh(sub_field)
        logger.info(f"Updated sub-field {sub_field_id}")
        return sub_field

    async def delete_sub_field(
        self,
        db: AsyncSession,
        sub_field_id: str,
    ) -> bool:
        stmt = select(AdvisorSubField).where(AdvisorSubField.id == sub_field_id)
        result = await db.execute(stmt)
        sub_field = result.scalar_one_or_none()

        if not sub_field:
            raise_not_found("Sub-field not found")

        linked_library_paper = await db.execute(
            select(AdvisorLibraryPaper.id).where(AdvisorLibraryPaper.sub_field_id == sub_field_id).limit(1)
        )
        if linked_library_paper.scalar_one_or_none():
            raise_conflict("该子领域仍有关联的导师知识库文献，请先移除或调整文献挂接后再删除。")

        await db.delete(sub_field)
        await db.commit()
        logger.info(f"Deleted sub-field {sub_field_id}")
        return True

    async def create_advisor(
        self,
        db: AsyncSession,
        advisor_in: AdvisorCreate,
    ) -> Advisor:
        try:
            advisor = Advisor(**advisor_in.model_dump())
            db.add(advisor)
            await db.commit()
            await db.refresh(advisor)
            logger.info(f"Created advisor {advisor_in.name} ({advisor_in.email})")
            return advisor
        except IntegrityError:
            await db.rollback()
            raise_conflict("Advisor with this email already exists")

    async def list_advisors(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[Advisor]:
        stmt = select(Advisor).order_by(Advisor.created_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_advisor(
        self,
        db: AsyncSession,
        advisor_id: str,
    ) -> Advisor:
        stmt = select(Advisor).options(selectinload(Advisor.sub_fields)).where(Advisor.id == advisor_id)
        result = await db.execute(stmt)
        advisor = result.scalar_one_or_none()

        if not advisor:
            raise_not_found("Advisor not found")

        return advisor

    async def _get_advisor(
        self,
        db: AsyncSession,
        advisor_id: str,
    ) -> Advisor:
        return await self.get_advisor(db, advisor_id)

    async def _get_paper(
        self,
        db: AsyncSession,
        paper_id: str,
    ) -> Paper:
        stmt = select(Paper).where(Paper.id == paper_id)
        result = await db.execute(stmt)
        paper = result.scalar_one_or_none()
        if not paper:
            raise_not_found("Paper not found")
        return paper

    async def _validate_sub_field(
        self,
        db: AsyncSession,
        advisor_id: str,
        sub_field_id: Optional[str],
    ) -> Optional[AdvisorSubField]:
        if sub_field_id is None:
            return None

        stmt = select(AdvisorSubField).where(
            AdvisorSubField.id == sub_field_id,
            AdvisorSubField.advisor_id == advisor_id,
        )
        result = await db.execute(stmt)
        sub_field = result.scalar_one_or_none()
        if not sub_field:
            raise_not_found("Sub-field not found for this advisor")
        return sub_field

    async def _get_researcher_advisor_link(
        self,
        db: AsyncSession,
        researcher_id: str,
        advisor_id: str,
    ) -> ResearcherAdvisor:
        stmt = select(ResearcherAdvisor).where(
            ResearcherAdvisor.researcher_id == researcher_id,
            ResearcherAdvisor.advisor_id == advisor_id,
        )
        result = await db.execute(stmt)
        link = result.scalar_one_or_none()
        if not link:
            raise_forbidden("Researcher does not have access to this advisor library")
        return link

    async def _get_authorized_sub_field_ids(
        self,
        db: AsyncSession,
        researcher_id: str,
        advisor_id: str,
    ) -> list[str]:
        link = await self._get_researcher_advisor_link(db, researcher_id, advisor_id)
        if not link.sub_fields_access:
            return []

        stmt = select(AdvisorSubField.id).where(
            AdvisorSubField.advisor_id == advisor_id,
            AdvisorSubField.field_name.in_(link.sub_fields_access),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def _ensure_sub_field_authorized(
        self,
        db: AsyncSession,
        *,
        researcher_id: str,
        advisor_id: str,
        sub_field: AdvisorSubField,
    ) -> None:
        link = await self._get_researcher_advisor_link(db, researcher_id, advisor_id)
        if link.sub_fields_access and sub_field.field_name not in link.sub_fields_access:
            raise_forbidden("Advisor cannot access this sub-field in the current researcher context")

    async def _ensure_sub_field_authorized_by_id(
        self,
        db: AsyncSession,
        *,
        researcher_id: str,
        advisor_id: str,
        sub_field_id: str,
    ) -> None:
        sub_field = await self._validate_sub_field(db, advisor_id, sub_field_id)
        if sub_field is not None:
            await self._ensure_sub_field_authorized(
                db,
                researcher_id=researcher_id,
                advisor_id=advisor_id,
                sub_field=sub_field,
            )

    async def update_advisor(
        self,
        db: AsyncSession,
        advisor_id: str,
        update_data: AdvisorUpdate,
    ) -> Advisor:
        advisor = await self.get_advisor(db, advisor_id)

        update_fields = update_data.model_dump(exclude_unset=True)
        for field, value in update_fields.items():
            setattr(advisor, field, value)

        await db.commit()
        await db.refresh(advisor)
        logger.info(f"Updated advisor {advisor_id}")
        return advisor

    async def delete_advisor(
        self,
        db: AsyncSession,
        advisor_id: str,
    ) -> bool:
        advisor = await self.get_advisor(db, advisor_id)

        researcher_link = await db.execute(
            select(ResearcherAdvisor.id).where(ResearcherAdvisor.advisor_id == advisor_id).limit(1)
        )
        if researcher_link.scalar_one_or_none():
            raise_conflict("该导师仍与研究者建立了指导关系，请先解除研究者绑定后再删除。")

        library_paper = await db.execute(
            select(AdvisorLibraryPaper.id).where(AdvisorLibraryPaper.advisor_id == advisor_id).limit(1)
        )
        if library_paper.scalar_one_or_none():
            raise_conflict("该导师仍有关联的导师知识库文献，请先移除知识库文献后再删除。")

        sub_field = await db.execute(
            select(AdvisorSubField.id).where(AdvisorSubField.advisor_id == advisor_id).limit(1)
        )
        if sub_field.scalar_one_or_none():
            raise_conflict("该导师仍配置了子领域，请先删除子领域配置后再删除导师档案。")

        await db.delete(advisor)
        await db.commit()
        logger.info(f"Deleted advisor {advisor_id}")
        return True


advisor_library_service = AdvisorLibraryService()

