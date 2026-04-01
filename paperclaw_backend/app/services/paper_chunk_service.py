"""Chunk generation utilities for local RAG ingestion."""
from collections.abc import Sequence
import re

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import raise_not_found
from app.models import Paper, PaperChunk, PaperSection


class PaperChunkService:
    chunk_size = 900
    overlap = 120
    boundary_window = 180
    boundary_tokens = ["\n\n", "\n", "。", "！", "？", "；", ". ", "; "]

    def build_chunks_for_section(self, section: PaperSection) -> list[PaperChunk]:
        text = self._normalize_chunk_text(section.section_text or "")
        if not text:
            return []

        chunks: list[PaperChunk] = []
        start = 0
        text_length = len(text)
        chunk_index = 0

        while start < text_length:
            tentative_end = min(text_length, start + self.chunk_size)
            end = self._find_chunk_end(text, start, tentative_end)
            if end <= start:
                end = min(text_length, start + self.chunk_size)
            chunk_text = text[start:end].strip()
            if not chunk_text:
                if end >= text_length:
                    break
                start = max(end, start + 1)
                continue

            local_offset = text[start:end].find(chunk_text)
            local_start = start + (local_offset if local_offset >= 0 else 0)
            local_end = local_start + len(chunk_text)
            absolute_start = section.span_start + local_start if section.span_start is not None else None
            absolute_end = section.span_start + local_end if section.span_start is not None else None

            chunks.append(
                PaperChunk(
                    paper_id=section.paper_id,
                    section_id=section.id,
                    chunk_index=chunk_index,
                    section_title=section.section_name,
                    chunk_text=chunk_text,
                    span_start=absolute_start,
                    span_end=absolute_end,
                )
            )
            chunk_index += 1

            if local_end >= text_length:
                break
            start = max(local_end - self.overlap, start + 1)

        return chunks

    async def rebuild_chunks_for_paper(self, db: AsyncSession, paper_id: str) -> dict[str, int | str]:
        stmt = (
            select(Paper)
            .options(selectinload(Paper.section_contents), selectinload(Paper.chunks))
            .where(Paper.id == paper_id)
        )
        result = await db.execute(stmt)
        paper = result.scalar_one_or_none()
        if paper is None:
            raise_not_found("Paper not found")

        created_chunks = await self._replace_chunks_for_sections(db, paper.section_contents)
        await db.commit()
        return {
            "paper_id": paper.id,
            "processed_sections": len(paper.section_contents),
            "created_chunks": created_chunks,
        }

    async def backfill_chunks(
        self,
        db: AsyncSession,
        *,
        paper_id: str | None = None,
        only_missing: bool = True,
        limit: int = 100,
    ) -> dict[str, int]:
        if paper_id:
            result = await self.rebuild_chunks_for_paper(db, paper_id)
            return {
                "processed_papers": 1,
                "processed_sections": int(result["processed_sections"]),
                "created_chunks": int(result["created_chunks"]),
                "skipped_papers": 0,
            }

        stmt = (
            select(Paper)
            .options(selectinload(Paper.section_contents), selectinload(Paper.chunks))
            .order_by(Paper.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        papers = result.scalars().all()

        processed_papers = 0
        processed_sections = 0
        created_chunks = 0
        skipped_papers = 0

        for paper in papers:
            if not paper.section_contents:
                skipped_papers += 1
                continue
            if only_missing and paper.chunks:
                skipped_papers += 1
                continue
            counts = await self.rebuild_chunks_for_paper(db, paper.id)
            processed_papers += 1
            processed_sections += int(counts["processed_sections"])
            created_chunks += int(counts["created_chunks"])

        return {
            "processed_papers": processed_papers,
            "processed_sections": processed_sections,
            "created_chunks": created_chunks,
            "skipped_papers": skipped_papers,
        }

    async def replace_chunks_for_sections(self, db: AsyncSession, sections: Sequence[PaperSection]) -> int:
        return await self._replace_chunks_for_sections(db, sections)

    async def _replace_chunks_for_sections(self, db: AsyncSession, sections: Sequence[PaperSection]) -> int:
        if not sections:
            return 0

        paper_ids = sorted({section.paper_id for section in sections})
        await db.execute(sa_delete(PaperChunk).where(PaperChunk.paper_id.in_(paper_ids)))
        await db.flush()

        created_chunks = 0
        ordered_sections = sorted(sections, key=lambda item: (item.span_start if item.span_start is not None else 10**12, item.created_at))
        for section in ordered_sections:
            chunks = self.build_chunks_for_section(section)
            if not chunks:
                continue
            db.add_all(chunks)
            created_chunks += len(chunks)

        await db.flush()
        return created_chunks

    def _find_chunk_end(self, text: str, start: int, tentative_end: int) -> int:
        if tentative_end >= len(text):
            return len(text)

        search_start = max(start, tentative_end - self.boundary_window)
        window = text[search_start:tentative_end]
        best_end = tentative_end
        for token in self.boundary_tokens:
            index = window.rfind(token)
            if index >= 0:
                candidate_end = search_start + index + len(token)
                if candidate_end > start:
                    best_end = max(best_end if best_end != tentative_end else 0, candidate_end)
        return best_end if best_end > start else tentative_end

    def _normalize_chunk_text(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()


paper_chunk_service = PaperChunkService()

