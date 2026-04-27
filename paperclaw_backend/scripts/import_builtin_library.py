from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys
import time

from sqlalchemy import select

from app.config import settings
from app.database import async_session_maker, init_db
from app.models import Paper, PaperSection, PaperSource
from app.services.file_task_service import file_task_service
from app.services.paper_chunk_service import paper_chunk_service


class ImportLogger:
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        self._handle = log_path.open("w", encoding="utf-8")
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")

    def close(self) -> None:
        self._handle.close()

    def log(self, *values: object) -> None:
        message = " ".join(str(value) for value in values)
        try:
            print(message, flush=True)
        except UnicodeEncodeError:
            print(message.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8"), flush=True)
        self._handle.write(f"{message}\n")
        self._handle.flush()


def resolve_default_library_root() -> Path:
    return Path(settings.BUILTIN_LIBRARY_ROOT)


def list_pdf_files(directory: Path) -> list[Path]:
    if not directory.exists() or not directory.is_dir():
        return []
    return sorted(item for item in directory.iterdir() if item.is_file() and item.suffix.lower() == ".pdf")


def discover_collections(library_root: Path, collection_slug: str | None) -> list[Path]:
    root = library_root.resolve()
    root_pdf_count = len(list_pdf_files(root))

    if collection_slug:
        direct_collection = (root / collection_slug).resolve()
        if list_pdf_files(direct_collection):
            return [direct_collection]
        if root_pdf_count and root.name == collection_slug:
            return [root]
        return []

    if root_pdf_count:
        return [root]
    if root.exists() and root.is_dir():
        return [item for item in sorted(root.iterdir()) if item.is_dir() and list_pdf_files(item)]
    return []


def format_seconds(seconds: float) -> str:
    return f"{seconds:.1f}"


def format_minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}"


async def import_builtin_library(
    library_root: Path,
    *,
    collection_slug: str | None = None,
    force: bool = False,
    limit: int | None = None,
    log_path: Path = Path("import.log"),
) -> dict[str, int]:
    imported = 0
    skipped = 0
    failed = 0
    failed_items: list[tuple[str, str]] = []
    logger = ImportLogger(log_path)

    try:
        collections = discover_collections(library_root, collection_slug)
        collection_pdf_counts = {str(collection_dir): len(list_pdf_files(collection_dir)) for collection_dir in collections}
        pdf_count = sum(collection_pdf_counts.values())
        pdf_jobs = [
            (pdf_path, collection_dir.name)
            for collection_dir in collections
            for pdf_path in list_pdf_files(collection_dir)
        ]
        if limit is not None:
            pdf_jobs = pdf_jobs[:limit]
        total_to_process = len(pdf_jobs)
        logger.log(
            "[SCAN]",
            {
                "library_root": str(library_root.resolve()),
                "collection_slug": collection_slug,
                "collections": collection_pdf_counts,
                "pdf_count": pdf_count,
                "force": force,
                "limit": limit,
                "will_process": total_to_process,
                "log_path": str(log_path.resolve()),
            },
        )

        await init_db()
        started_at = time.perf_counter()

        async with async_session_maker() as session:
            for index, (pdf_path, slug) in enumerate(pdf_jobs, start=1):
                item_started_at = time.perf_counter()
                logger.log(f"[{index}/{total_to_process}] 正在导入：{pdf_path.name}")

                try:
                    resolved_path = str(pdf_path.resolve())
                    existing = await session.execute(
                        select(Paper).where(Paper.source == PaperSource.BUILTIN_LIBRARY, Paper.file_path == resolved_path)
                    )
                    existing_papers = list(existing.scalars().all())
                    if existing_papers and not force:
                        skipped += 1
                        elapsed = time.perf_counter() - item_started_at
                        logger.log(f"- 跳过：已存在（耗时 {format_seconds(elapsed)} 秒）")
                        continue
                    if existing_papers:
                        for existing_paper in existing_papers:
                            await session.delete(existing_paper)
                        await session.flush()

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
                            page_start=section.get("page_start"),
                            page_end=section.get("page_end"),
                        )
                        session.add(section_record)
                        section_records.append(section_record)

                    await session.flush()
                    chunk_count = await paper_chunk_service.replace_chunks_for_sections(session, section_records)
                    await session.commit()
                    imported += 1
                    elapsed = time.perf_counter() - item_started_at
                    logger.log(f"✓ 完成（耗时 {format_seconds(elapsed)} 秒，生成 {chunk_count} 个 chunk）")
                except Exception as exc:
                    await session.rollback()
                    failed += 1
                    error_reason = f"{type(exc).__name__}: {exc}"
                    failed_items.append((pdf_path.name, error_reason))
                    elapsed = time.perf_counter() - item_started_at
                    logger.log(f"✗ 失败：{error_reason}（耗时 {format_seconds(elapsed)} 秒）")

        total_elapsed = time.perf_counter() - started_at
        logger.log(f"汇总：成功 {imported} 篇，跳过 {skipped} 篇，失败 {failed} 篇，总耗时 {format_minutes(total_elapsed)} 分钟")
        if failed_items:
            logger.log("失败文件列表：")
            for file_name, error_reason in failed_items:
                logger.log(f"- {file_name}：{error_reason}")

        return {"imported": imported, "skipped": skipped, "failed": failed}
    finally:
        logger.close()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import builtin library PDFs into PaperClaw")
    parser.add_argument("--library-root", default=str(resolve_default_library_root()), help="Root directory of builtin library collections")
    parser.add_argument("--collection-slug", default=None, help="Only import one collection slug")
    parser.add_argument("--force", action="store_true", help="Re-import PDFs even if the same source path already exists")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N PDFs for quick verification")
    parser.add_argument("--log-path", default="import.log", help="Write import progress and failure details to this log file")
    args = parser.parse_args()

    result = await import_builtin_library(
        Path(args.library_root),
        collection_slug=args.collection_slug,
        force=args.force,
        limit=args.limit,
        log_path=Path(args.log_path),
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
