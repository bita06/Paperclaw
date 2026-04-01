from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import traceback

from sqlalchemy import select

from app.database import async_session_maker, init_db
from app.models import Paper, PaperSection, PaperSource
from app.services.file_task_service import file_task_service
from app.services.paper_chunk_service import paper_chunk_service


MAX_ERROR_SAMPLES = 10


def resolve_default_library_root() -> Path:
    base_root = Path(__file__).resolve().parents[2]
    candidates = [
        base_root / "Paperclaw" / "data" / "builtin_library",
        base_root / "data" / "builtin_library",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


async def import_builtin_library(library_root: Path, *, collection_slug: str | None = None, force: bool = False) -> dict[str, int]:
    await init_db()

    imported = 0
    skipped = 0
    failed = 0
    printed_error_samples = 0

    if collection_slug:
        collections = [library_root / collection_slug]
    else:
        collections = [item for item in library_root.iterdir() if item.is_dir()] if library_root.exists() else []

    async with async_session_maker() as session:
        for collection_dir in collections:
            slug = collection_dir.name
            for pdf_path in sorted(collection_dir.glob("*.pdf")):
                resolved_path = str(pdf_path.resolve())
                existing = await session.execute(
                    select(Paper.id).where(Paper.source == PaperSource.BUILTIN_LIBRARY, Paper.file_path == resolved_path).limit(1)
                )
                if existing.scalar_one_or_none() and not force:
                    skipped += 1
                    continue

                try:
                    parsed = await file_task_service._extract_pdf_insights(pdf_path, pdf_path.name)
                    metadata = parsed["metadata"]
                    sections = parsed["sections"]

                    paper = Paper(
                        title=metadata.get("title") or pdf_path.stem,
                        authors=metadata.get("authors") or [],
                        year=metadata.get("year"),
                        abstract=metadata.get("abstract"),
                        keywords=metadata.get("keywords") or [],
                        source=PaperSource.BUILTIN_LIBRARY,
                        collection_slug=slug,
                        full_text=parsed["full_text"] or None,
                        file_path=resolved_path,
                        indexed=False,
                    )
                    session.add(paper)
                    await session.flush()

                    section_records: list[PaperSection] = []
                    for section in sections:
                        section_record = PaperSection(
                            paper_id=paper.id,
                            section_name=section["title"][:100],
                            section_text=section["text"] or None,
                            concepts=[],
                            span_start=section.get("span_start"),
                            span_end=section.get("span_end"),
                        )
                        session.add(section_record)
                        section_records.append(section_record)

                    await session.flush()
                    await paper_chunk_service.replace_chunks_for_sections(session, section_records)
                    await session.commit()
                    imported += 1
                except Exception as exc:
                    await session.rollback()
                    failed += 1
                    if printed_error_samples < MAX_ERROR_SAMPLES:
                        printed_error_samples += 1
                        print(f"[FAILED] {pdf_path}")
                        print(f"         {type(exc).__name__}: {exc}")
                        print("         traceback (last 5 lines):")
                        tb_lines = traceback.format_exc().strip().splitlines()
                        for line in tb_lines[-5:]:
                            print(f"         {line}")
                        print()

    return {"imported": imported, "skipped": skipped, "failed": failed}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import builtin library PDFs into PaperClaw")
    parser.add_argument("--library-root", default=str(resolve_default_library_root()), help="Root directory of builtin library collections")
    parser.add_argument("--collection-slug", default=None, help="Only import one collection slug")
    parser.add_argument("--force", action="store_true", help="Re-import PDFs even if the same source path already exists")
    args = parser.parse_args()

    result = await import_builtin_library(
        Path(args.library_root),
        collection_slug=args.collection_slug,
        force=args.force,
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
