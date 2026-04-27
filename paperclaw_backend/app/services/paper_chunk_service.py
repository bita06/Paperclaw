"""Chunk generation utilities for local RAG ingestion."""
from collections.abc import Sequence
import math
import re

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import raise_not_found
from app.models import Paper, PaperChunk, PaperSection
from app.services.embedding_service import embedding_service


class PaperChunkService:
    max_tokens = 512
    overlap_chars = 100
    max_chars_hard = 2200
    sentence_boundary_pattern = re.compile(r"(?<=[。！？；.!?;])\s+")
    token_pattern = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")

    async def build_chunks_for_section(self, section: PaperSection) -> list[PaperChunk]:
        text = self._normalize_chunk_text(section.section_text or "")
        if not text:
            return []

        semantic_segments = self._split_semantic_segments(text)
        chunks: list[PaperChunk] = []
        cursor = 0

        for chunk_index, chunk_text in enumerate(self._assemble_chunks(semantic_segments)):
            found_at = text.find(chunk_text, cursor)
            if found_at < 0:
                found_at = text.find(chunk_text)
            local_start = found_at if found_at >= 0 else None
            local_end = (local_start + len(chunk_text)) if local_start is not None else None
            absolute_start = section.span_start + local_start if section.span_start is not None and local_start is not None else None
            absolute_end = section.span_start + local_end if section.span_start is not None and local_end is not None else None
            if local_end is not None:
                cursor = max(cursor, local_end - self.overlap_chars)

            chunks.append(
                PaperChunk(
                    paper_id=section.paper_id,
                    section_id=section.id,
                    chunk_index=chunk_index,
                    section_title=section.section_name,
                    chunk_text=chunk_text,
                    chunk_embedding=await embedding_service.embed_text(chunk_text, purpose="db"),
                    span_start=absolute_start,
                    span_end=absolute_end,
                    page_start=section.page_start,
                    page_end=section.page_end,
                )
            )

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
        ordered_sections = sorted(
            sections,
            key=lambda item: (
                item.page_start if item.page_start is not None else 10**12,
                item.span_start if item.span_start is not None else 10**12,
                item.created_at,
            ),
        )
        for section in ordered_sections:
            chunks = await self.build_chunks_for_section(section)
            if not chunks:
                continue
            db.add_all(chunks)
            created_chunks += len(chunks)

        await db.flush()
        return created_chunks

    def _split_semantic_segments(self, text: str) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
        segments: list[str] = []
        for paragraph in paragraphs or [text]:
            if self._estimate_tokens(paragraph) <= self.max_tokens and len(paragraph) <= self.max_chars_hard:
                segments.append(paragraph)
                continue
            segments.extend(self._split_long_paragraph(paragraph))
        return segments

    def _split_long_paragraph(self, paragraph: str) -> list[str]:
        sentences = [part.strip() for part in self.sentence_boundary_pattern.split(paragraph) if part.strip()]
        if not sentences:
            return self._split_hard(paragraph)

        pieces: list[str] = []
        buffer = ""
        for sentence in sentences:
            candidate = sentence if not buffer else f"{buffer} {sentence}".strip()
            if self._estimate_tokens(candidate) <= self.max_tokens and len(candidate) <= self.max_chars_hard:
                buffer = candidate
                continue
            if buffer:
                pieces.append(buffer)
                overlap = buffer[-self.overlap_chars :].strip()
                buffer = f"{overlap} {sentence}".strip() if overlap else sentence
                if self._estimate_tokens(buffer) <= self.max_tokens and len(buffer) <= self.max_chars_hard:
                    continue
            else:
                buffer = sentence

            if self._estimate_tokens(buffer) > self.max_tokens or len(buffer) > self.max_chars_hard:
                pieces.extend(self._split_hard(buffer))
                buffer = ""

        if buffer:
            pieces.append(buffer)
        return pieces

    def _assemble_chunks(self, segments: list[str]) -> list[str]:
        chunks: list[str] = []
        buffer = ""
        for segment in segments:
            candidate = segment if not buffer else f"{buffer}\n\n{segment}".strip()
            if self._estimate_tokens(candidate) <= self.max_tokens and len(candidate) <= self.max_chars_hard:
                buffer = candidate
                continue
            if buffer:
                chunks.append(buffer)
                overlap = buffer[-self.overlap_chars :].strip()
                buffer = f"{overlap}\n\n{segment}".strip() if overlap else segment
                if self._estimate_tokens(buffer) <= self.max_tokens and len(buffer) <= self.max_chars_hard:
                    continue
            else:
                buffer = segment

            if self._estimate_tokens(buffer) > self.max_tokens or len(buffer) > self.max_chars_hard:
                split_parts = self._split_long_paragraph(buffer)
                chunks.extend(split_parts[:-1])
                buffer = split_parts[-1] if split_parts else ""

        if buffer:
            chunks.append(buffer)
        return [chunk for chunk in chunks if chunk.strip()]

    def _split_hard(self, text: str) -> list[str]:
        step = max(1, self.max_chars_hard - self.overlap_chars)
        pieces: list[str] = []
        start = 0
        while start < len(text):
            end = min(len(text), start + self.max_chars_hard)
            if end < len(text):
                pivot = text.rfind("。", start, end)
                if pivot < 0:
                    pivot = text.rfind(". ", start, end)
                    if pivot >= 0:
                        pivot += 1
                if pivot > start + 200:
                    end = pivot + 1
            piece = text[start:end].strip()
            if piece:
                pieces.append(piece)
            if end >= len(text):
                break
            start = max(end - self.overlap_chars, start + step)
        return pieces

    def _estimate_tokens(self, text: str) -> int:
        token_count = len(self.token_pattern.findall(text))
        if token_count:
            return token_count
        return math.ceil(len(text) / 4)

    def _normalize_chunk_text(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n")
        normalized = re.sub(r"[ \t]+", " ", normalized)
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()


paper_chunk_service = PaperChunkService()
