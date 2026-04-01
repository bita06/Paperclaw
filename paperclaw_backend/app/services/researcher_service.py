"""
Researcher service layer.
"""
from typing import Sequence

from datetime import datetime

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import raise_conflict, raise_not_found
from app.models import Advisor, Researcher, ResearcherAdvisor, User
from app.security import hash_password
from app.schemas import (
    ResearcherAdvisorLink,
    ResearcherAdvisorCreate,
    ResearcherAdvisorUpdate,
    ResearcherCreate,
    ResearcherPrimaryAdvisorUpdate,
    ResearcherStageUpdate,
    ResearcherUpdate,
)


class ResearcherService:
    """Business logic for researcher CRUD operations."""

    async def create_researcher(
        self,
        db: AsyncSession,
        researcher_in: ResearcherCreate,
    ) -> Researcher:
        create_data = researcher_in.model_dump()
        password = create_data.pop("password")

        password_hash = hash_password(password)
        researcher = Researcher(
            **create_data,
            password_hash=password_hash,
        )
        db.add(researcher)
        await db.flush()
        db.add(
            User(
                name=researcher.name,
                email=researcher.email,
                password_hash=password_hash,
                role="researcher",
                researcher_id=researcher.id,
            )
        )
        await self._commit_or_raise_conflict(db, "Researcher with this email already exists")
        await db.refresh(researcher)
        return researcher

    async def list_researchers(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> Sequence[Researcher]:
        stmt = (
            select(Researcher)
            .order_by(Researcher.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_researcher(
        self,
        db: AsyncSession,
        researcher_id: str,
    ) -> Researcher:
        stmt = select(Researcher).where(Researcher.id == researcher_id)
        result = await db.execute(stmt)
        researcher = result.scalar_one_or_none()
        if researcher is None:
            raise_not_found("Researcher not found")
        return researcher

    async def update_researcher(
        self,
        db: AsyncSession,
        researcher_id: str,
        update_data: ResearcherUpdate,
    ) -> Researcher:
        researcher = await self.get_researcher(db, researcher_id)
        for field, value in update_data.model_dump(exclude_unset=True).items():
            setattr(researcher, field, value)

        await self._commit_or_raise_conflict(db, "Researcher with this email already exists")
        await db.refresh(researcher)
        return researcher

    async def update_research_stage(
        self,
        db: AsyncSession,
        researcher_id: str,
        stage_data: ResearcherStageUpdate,
    ) -> Researcher:
        researcher = await self.get_researcher(db, researcher_id)
        researcher.current_stage = stage_data.current_stage

        if stage_data.current_research_question is not None:
            researcher.current_research_question = stage_data.current_research_question

        await db.commit()
        await db.refresh(researcher)
        return researcher

    async def delete_researcher(
        self,
        db: AsyncSession,
        researcher_id: str,
    ) -> None:
        researcher = await self.get_researcher(db, researcher_id)
        await db.delete(researcher)
        await db.commit()

    async def assign_primary_advisor(
        self,
        db: AsyncSession,
        researcher_id: str,
        advisor_data: ResearcherPrimaryAdvisorUpdate,
    ) -> ResearcherAdvisorLink:
        researcher = await self.get_researcher(db, researcher_id)
        advisor = await self._get_advisor(db, advisor_data.advisor_id)
        researcher_advisor = await self._upsert_advisor_link(
            db,
            researcher=researcher,
            advisor=advisor,
            relationship_type="primary_advisor",
            access_level="full",
            sub_fields_access=self._default_sub_fields_access(advisor),
        )
        await self._commit_or_raise_conflict(db, "Researcher already has this advisor relationship")
        await db.refresh(researcher_advisor)
        return self._build_advisor_link(researcher_advisor, advisor)

    async def assign_advisor(
        self,
        db: AsyncSession,
        researcher_id: str,
        advisor_data: ResearcherAdvisorCreate,
    ) -> ResearcherAdvisorLink:
        researcher = await self.get_researcher(db, researcher_id)
        advisor = await self._get_advisor(db, advisor_data.advisor_id)
        if "sub_fields_access" in advisor_data.model_fields_set:
            sub_fields_access = self._resolve_sub_fields_access(advisor, advisor_data.sub_fields_access)
        else:
            sub_fields_access = self._default_sub_fields_access(advisor)
        researcher_advisor = await self._upsert_advisor_link(
            db,
            researcher=researcher,
            advisor=advisor,
            relationship_type=advisor_data.relationship_type,
            access_level=advisor_data.access_level,
            sub_fields_access=sub_fields_access,
        )
        await self._commit_or_raise_conflict(db, "Researcher already has this advisor relationship")
        await db.refresh(researcher_advisor)
        return self._build_advisor_link(researcher_advisor, advisor)

    async def get_primary_advisor(
        self,
        db: AsyncSession,
        researcher_id: str,
    ) -> ResearcherAdvisorLink:
        researcher = await self.get_researcher(db, researcher_id)
        if not researcher.primary_advisor_id:
            raise_not_found("Researcher does not have a primary advisor")

        advisor = await self._get_advisor(db, researcher.primary_advisor_id)
        stmt = select(ResearcherAdvisor).where(
            ResearcherAdvisor.researcher_id == researcher_id,
            ResearcherAdvisor.advisor_id == advisor.id,
        )
        result = await db.execute(stmt)
        researcher_advisor = result.scalar_one_or_none()

        if researcher_advisor is None:
            researcher_advisor = ResearcherAdvisor(
                researcher_id=researcher_id,
                advisor_id=advisor.id,
                relationship_type="primary_advisor",
                access_level="full",
                sub_fields_access=self._default_sub_fields_access(advisor),
                joined_at=datetime.utcnow(),
            )

        return self._build_advisor_link(researcher_advisor, advisor)

    async def list_advisors(
        self,
        db: AsyncSession,
        researcher_id: str,
    ) -> list[ResearcherAdvisorLink]:
        await self.get_researcher(db, researcher_id)
        stmt = (
            select(ResearcherAdvisor, Advisor)
            .join(Advisor, Advisor.id == ResearcherAdvisor.advisor_id)
            .where(ResearcherAdvisor.researcher_id == researcher_id)
            .order_by(
                desc(ResearcherAdvisor.relationship_type == "primary_advisor"),
                ResearcherAdvisor.joined_at.desc(),
            )
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [self._build_advisor_link(link, advisor) for link, advisor in rows]

    async def get_advisor_relationship(
        self,
        db: AsyncSession,
        researcher_id: str,
        advisor_id: str,
    ) -> ResearcherAdvisorLink:
        await self.get_researcher(db, researcher_id)
        advisor = await self._get_advisor(db, advisor_id)
        researcher_advisor = await self._get_researcher_advisor_link(db, researcher_id, advisor_id)
        return self._build_advisor_link(researcher_advisor, advisor)

    async def remove_primary_advisor(
        self,
        db: AsyncSession,
        researcher_id: str,
    ) -> None:
        researcher = await self.get_researcher(db, researcher_id)
        if not researcher.primary_advisor_id:
            raise_not_found("Researcher does not have a primary advisor")

        advisor_id = researcher.primary_advisor_id
        researcher.primary_advisor_id = None
        await self._delete_primary_advisor_link(db, researcher_id, advisor_id)
        await db.commit()

    async def update_advisor_relationship(
        self,
        db: AsyncSession,
        researcher_id: str,
        advisor_id: str,
        update_data: ResearcherAdvisorUpdate,
    ) -> ResearcherAdvisorLink:
        researcher = await self.get_researcher(db, researcher_id)
        advisor = await self._get_advisor(db, advisor_id)
        researcher_advisor = await self._get_researcher_advisor_link(db, researcher_id, advisor_id)

        relationship_type = update_data.relationship_type or researcher_advisor.relationship_type
        access_level = update_data.access_level or researcher_advisor.access_level
        sub_fields_access = (
            self._resolve_sub_fields_access(advisor, update_data.sub_fields_access)
            if update_data.sub_fields_access is not None
            else researcher_advisor.sub_fields_access
        )

        researcher_advisor = await self._upsert_advisor_link(
            db,
            researcher=researcher,
            advisor=advisor,
            relationship_type=relationship_type,
            access_level=access_level,
            sub_fields_access=sub_fields_access,
        )
        await db.commit()
        await db.refresh(researcher_advisor)
        return self._build_advisor_link(researcher_advisor, advisor)

    async def remove_advisor(
        self,
        db: AsyncSession,
        researcher_id: str,
        advisor_id: str,
    ) -> None:
        researcher = await self.get_researcher(db, researcher_id)
        await self._get_advisor(db, advisor_id)
        stmt = select(ResearcherAdvisor).where(
            ResearcherAdvisor.researcher_id == researcher_id,
            ResearcherAdvisor.advisor_id == advisor_id,
        )
        result = await db.execute(stmt)
        researcher_advisor = result.scalar_one_or_none()
        if researcher_advisor is None:
            raise_not_found("Researcher is not linked to this advisor")

        if researcher.primary_advisor_id == advisor_id:
            researcher.primary_advisor_id = None

        await db.delete(researcher_advisor)
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

    async def _get_advisor(
        self,
        db: AsyncSession,
        advisor_id: str,
    ) -> Advisor:
        stmt = (
            select(Advisor)
            .options(selectinload(Advisor.sub_fields))
            .where(Advisor.id == advisor_id)
        )
        result = await db.execute(stmt)
        advisor = result.scalar_one_or_none()
        if advisor is None:
            raise_not_found("Advisor not found")
        return advisor

    async def _delete_primary_advisor_link(
        self,
        db: AsyncSession,
        researcher_id: str,
        advisor_id: str,
    ) -> None:
        stmt = select(ResearcherAdvisor).where(
            ResearcherAdvisor.researcher_id == researcher_id,
            ResearcherAdvisor.advisor_id == advisor_id,
            ResearcherAdvisor.relationship_type == "primary_advisor",
        )
        result = await db.execute(stmt)
        researcher_advisor = result.scalar_one_or_none()
        if researcher_advisor is not None:
            await db.delete(researcher_advisor)

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
        researcher_advisor = result.scalar_one_or_none()
        if researcher_advisor is None:
            raise_not_found("Researcher is not linked to this advisor")
        return researcher_advisor

    async def _upsert_advisor_link(
        self,
        db: AsyncSession,
        *,
        researcher: Researcher,
        advisor: Advisor,
        relationship_type: str,
        access_level: str,
        sub_fields_access: list[str],
    ) -> ResearcherAdvisor:
        if (
            relationship_type == "primary_advisor"
            and researcher.primary_advisor_id
            and researcher.primary_advisor_id != advisor.id
        ):
            await self._delete_primary_advisor_link(db, researcher.id, researcher.primary_advisor_id)

        stmt = select(ResearcherAdvisor).where(
            ResearcherAdvisor.researcher_id == researcher.id,
            ResearcherAdvisor.advisor_id == advisor.id,
        )
        result = await db.execute(stmt)
        researcher_advisor = result.scalar_one_or_none()

        if researcher_advisor is None:
            researcher_advisor = ResearcherAdvisor(
                researcher_id=researcher.id,
                advisor_id=advisor.id,
                relationship_type=relationship_type,
                access_level=access_level,
                sub_fields_access=sub_fields_access,
            )
            db.add(researcher_advisor)
        else:
            researcher_advisor.relationship_type = relationship_type
            researcher_advisor.access_level = access_level
            researcher_advisor.sub_fields_access = sub_fields_access

        if relationship_type == "primary_advisor":
            researcher.primary_advisor_id = advisor.id
        elif researcher.primary_advisor_id == advisor.id:
            researcher.primary_advisor_id = None

        return researcher_advisor

    def _build_advisor_link(
        self,
        researcher_advisor: ResearcherAdvisor,
        advisor: Advisor,
    ) -> ResearcherAdvisorLink:
        return ResearcherAdvisorLink(
            advisor_id=advisor.id,
            advisor_name=advisor.name,
            relationship_type=researcher_advisor.relationship_type,
            access_level=researcher_advisor.access_level,
            sub_fields_access=researcher_advisor.sub_fields_access or [],
            joined_at=researcher_advisor.joined_at,
        )

    def _default_sub_fields_access(
        self,
        advisor: Advisor,
    ) -> list[str]:
        return [sub_field.field_name for sub_field in advisor.sub_fields]

    def _resolve_sub_fields_access(
        self,
        advisor: Advisor,
        sub_fields_access: list[str],
    ) -> list[str]:
        if not sub_fields_access:
            return []

        available_sub_fields = {sub_field.field_name for sub_field in advisor.sub_fields}
        invalid_sub_fields = sorted(set(sub_fields_access) - available_sub_fields)
        if invalid_sub_fields:
            raise_conflict(
                "Invalid sub_fields_access values: "
                + ", ".join(invalid_sub_fields)
            )

        return list(dict.fromkeys(sub_fields_access))


researcher_service = ResearcherService()

