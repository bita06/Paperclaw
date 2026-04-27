from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import fitz
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_maker, init_db
from app.models import Paper, PaperChunk, PaperSection
from app.services.file_task_service import file_task_service
from app.services.paper_chunk_service import paper_chunk_service


async def _rebuild_one_paper(
    db: AsyncSession,
    paper: Paper,
    *,
    diagnose: bool = False,
) -> tuple[int, int, int]:
    parsed = await file_task_service._extract_pdf_insights(Path(paper.file_path), Path(paper.file_path).name)
    parsed_sections = parsed["sections"]

    if diagnose:
        document = fitz.open(str(paper.file_path))
        print(f"[诊断] PyMuPDF 提取的总页数: {document.page_count}")
        document.close()
        for idx, parsed_section in enumerate(parsed_sections[:3], start=1):
            print(
                f"[诊断] section {idx}: "
                f"title={parsed_section.get('title')!r}, "
                f"page_start={parsed_section.get('page_start')}, "
                f"page_end={parsed_section.get('page_end')}"
            )

    section_records: list[PaperSection] = []
    for parsed_section in parsed_sections:
        section_record = PaperSection(
            paper_id=paper.id,
            section_name=(parsed_section.get("title") or "Untitled Section")[:100],
            section_text=parsed_section.get("text"),
            concepts=[],
            span_start=parsed_section.get("span_start"),
            span_end=parsed_section.get("span_end"),
            page_start=parsed_section.get("page_start"),
            page_end=parsed_section.get("page_end"),
        )
        db.add(section_record)
        section_records.append(section_record)

    await db.flush()
    created_chunks = await paper_chunk_service.replace_chunks_for_sections(db, section_records)

    chunk_rows = await db.execute(
        select(PaperChunk)
        .where(PaperChunk.paper_id == paper.id)
        .order_by(PaperChunk.chunk_index.asc())
    )
    rebuilt_chunks = chunk_rows.scalars().all()

    if diagnose:
        for idx, chunk in enumerate(rebuilt_chunks[:3], start=1):
            print(
                f"[诊断] chunk {idx}: "
                f"page_start={chunk.page_start}, "
                f"page_end={chunk.page_end}"
            )

    chunks_with_pages = sum(1 for chunk in rebuilt_chunks if chunk.page_start is not None or chunk.page_end is not None)
    chunks_with_embeddings = sum(1 for chunk in rebuilt_chunks if chunk.chunk_embedding is not None)
    return created_chunks, chunks_with_pages, chunks_with_embeddings


async def rebuild_chunks(limit: int | None = None) -> dict[str, int]:
    await init_db()

    async with async_session_maker() as db:
        stmt = (
            select(Paper)
            .where(Paper.file_path.is_not(None))
            .order_by(Paper.created_at.asc())
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await db.execute(stmt)
        papers = [paper for paper in result.scalars().all() if paper.file_path]
        paper_ids = [paper.id for paper in papers]

        if paper_ids:
            await db.execute(delete(PaperChunk).where(PaperChunk.paper_id.in_(paper_ids)))
            await db.execute(delete(PaperSection).where(PaperSection.paper_id.in_(paper_ids)))
            await db.commit()

        total_papers = len(papers)
        total_chunks = 0
        total_chunks_with_pages = 0
        total_chunks_with_embeddings = 0

        for index, paper in enumerate(papers, start=1):
            print(f"正在处理第 {index}/{total_papers} 篇：{paper.title}")
            created_chunks, chunks_with_pages, chunks_with_embeddings = await _rebuild_one_paper(
                db,
                paper,
                diagnose=(index == 1),
            )
            await db.commit()
            total_chunks += created_chunks
            total_chunks_with_pages += chunks_with_pages
            total_chunks_with_embeddings += chunks_with_embeddings
            print(f"已生成 {created_chunks} 个 chunk")

        db_chunks = await db.scalar(
            select(func.count()).select_from(PaperChunk).where(PaperChunk.paper_id.in_(paper_ids))
        )
        db_chunks_with_pages = await db.scalar(
            select(func.count()).select_from(PaperChunk).where(
                PaperChunk.paper_id.in_(paper_ids),
                (PaperChunk.page_start.is_not(None)) | (PaperChunk.page_end.is_not(None)),
            )
        )
        db_chunks_with_embeddings = await db.scalar(
            select(func.count()).select_from(PaperChunk).where(
                PaperChunk.paper_id.in_(paper_ids),
                PaperChunk.chunk_embedding.is_not(None),
            )
        )

        summary = {
            "total_chunks": int(db_chunks or total_chunks),
            "chunks_with_pages": int(db_chunks_with_pages or total_chunks_with_pages),
            "chunks_with_embeddings": int(db_chunks_with_embeddings or total_chunks_with_embeddings),
        }
        print(
            "重建完成："
            f"总共生成 {summary['total_chunks']} 个 chunk，"
            f"{summary['chunks_with_pages']} 个有页码，"
            f"{summary['chunks_with_embeddings']} 个有 embedding"
        )
        return summary


async def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild paper_sections and paper_chunks using structured PyMuPDF parsing")
    parser.add_argument("--limit", type=int, default=None, help="Only rebuild the first N papers")
    args = parser.parse_args()
    await rebuild_chunks(limit=args.limit)


if __name__ == "__main__":
    asyncio.run(main())
