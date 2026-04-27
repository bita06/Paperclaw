"""
Service layer for files and processing tasks.
"""
import re
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

import fitz
from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.exceptions import raise_bad_request, raise_forbidden, raise_not_found
from app.models import (
    FileStatus,
    Paper,
    PaperSection,
    PaperSource,
    ProcessingTask,
    StoredFile,
    TaskStatus,
    User,
)
from app.schemas.file_task import (
    FileHistoryItemResponse,
    FileStatusResponse,
    FileUploadAcceptedResponse,
    KnowledgeStatusSummary,
    TaskResponse,
    TaskResultResponse,
)
from app.services.local_retrieval_service import local_retrieval_service
from app.services.minimax_parse_service import minimax_parse_service
from app.services.paper_chunk_service import paper_chunk_service
from app.services.paper_service import paper_service


class FileTaskService:
    upload_root = Path(settings.STORAGE_ROOT) / "files"
    heading_number_pattern = re.compile(r"^(?:\d+(?:\.\d+){0,3}|[IVXLC]+)[\.)]?\s+")
    known_headings = {
        "abstract": "Abstract",
        "introduction": "Introduction",
        "background": "Background",
        "literature review": "Literature Review",
        "theoretical framework": "Theoretical Framework",
        "conceptual framework": "Conceptual Framework",
        "method": "Method",
        "methods": "Methods",
        "methodology": "Methodology",
        "data": "Data",
        "results": "Results",
        "findings": "Findings",
        "discussion": "Discussion",
        "conclusion": "Conclusion",
        "conclusions": "Conclusions",
        "references": "References",
        "appendix": "Appendix",
    }

    async def upload_file(
        self,
        db: AsyncSession,
        *,
        file: UploadFile,
        current_user: User,
        researcher_id: str | None = None,
    ) -> FileUploadAcceptedResponse:
        self._validate_upload(file)
        saved_path = await self._save_upload(file)
        try:
            size_bytes = saved_path.stat().st_size

            stored_file = StoredFile(
                original_name=file.filename or saved_path.name,
                stored_name=saved_path.name,
                file_path=str(saved_path),
                content_type=file.content_type,
                size_bytes=size_bytes,
                status=FileStatus.UPLOADED,
                uploaded_by=current_user.id,
                researcher_id=researcher_id,
            )
            task = ProcessingTask(
                task_type="file_parse",
                status=TaskStatus.QUEUED,
                created_by=current_user.id,
                result={},
            )
            stored_file.tasks.append(task)
            db.add(stored_file)
            await db.commit()
            await db.refresh(stored_file)
            await db.refresh(task)
        except Exception:
            await db.rollback()
            if saved_path.exists():
                saved_path.unlink(missing_ok=True)
            raise

        await self._parse_pdf_mvp(db, stored_file.id, task.id)

        return FileUploadAcceptedResponse(file_id=stored_file.id, task_id=task.id)

    async def get_task(self, db: AsyncSession, task_id: str, current_user: User) -> TaskResponse:
        task = await self._get_task(db, task_id)
        self._ensure_task_access(task, current_user)
        return self._build_task_response(task)

    async def get_file_status(self, db: AsyncSession, file_id: str, current_user: User) -> FileStatusResponse:
        stored_file = await self._get_file(db, file_id)
        self._ensure_file_access(stored_file, current_user)
        latest_task = stored_file.tasks[0] if stored_file.tasks else None
        return FileStatusResponse(
            file_id=stored_file.id,
            file_status=stored_file.status,
            latest_task=self._build_task_response(latest_task) if latest_task else None,
            linked_paper_id=stored_file.linked_paper_id,
            knowledge_status=await self._build_knowledge_status(db, stored_file, latest_task),
        )

    async def list_file_history(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        researcher_id: str | None = None,
        limit: int = 20,
    ) -> list[FileHistoryItemResponse]:
        stmt = (
            select(StoredFile)
            .options(selectinload(StoredFile.tasks))
            .order_by(StoredFile.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        stored_files = list(result.scalars().all())

        history_items: list[FileHistoryItemResponse] = []
        for stored_file in stored_files:
            if not self._can_access_file(stored_file, current_user):
                continue
            if researcher_id and stored_file.researcher_id != researcher_id:
                continue
            stored_file.tasks.sort(key=lambda item: item.created_at, reverse=True)
            latest_task = stored_file.tasks[0] if stored_file.tasks else None
            history_items.append(
                FileHistoryItemResponse(
                    file_id=stored_file.id,
                    original_name=stored_file.original_name,
                    content_type=stored_file.content_type,
                    size_bytes=stored_file.size_bytes,
                    file_status=stored_file.status,
                    researcher_id=stored_file.researcher_id,
                    linked_paper_id=stored_file.linked_paper_id,
                    created_at=stored_file.created_at,
                    updated_at=stored_file.updated_at,
                    latest_task=self._build_task_response(latest_task) if latest_task else None,
                    knowledge_status=await self._build_knowledge_status(db, stored_file, latest_task),
                )
            )

        return history_items

    async def _parse_pdf_mvp(self, db: AsyncSession, file_id: str, task_id: str) -> None:
        task = await self._get_task(db, task_id)
        stored_file = task.file
        if stored_file is None or stored_file.id != file_id:
            raise_not_found("Stored file not found")

        try:
            task.status = TaskStatus.PROCESSING
            stored_file.status = FileStatus.PROCESSING
            await db.commit()

            parsed = await self._extract_pdf_insights(Path(stored_file.file_path), stored_file.original_name)
            metadata = parsed["metadata"]
            sections = parsed["sections"]

            paper = Paper(
                title=metadata.get("title") or paper_service._infer_title(stored_file.original_name),
                authors=metadata.get("authors") or [],
                year=metadata.get("year"),
                abstract=metadata.get("abstract"),
                keywords=metadata.get("keywords") or [],
                source=PaperSource.UPLOADED,
                owner_user_id=stored_file.uploaded_by,
                full_text=parsed["full_text"] or None,
                file_path=stored_file.file_path,
                indexed=False,
            )
            db.add(paper)
            await db.flush()

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
                db.add(section_record)
                section_records.append(section_record)

            await db.flush()
            await paper_chunk_service.replace_chunks_for_sections(db, section_records)

            stored_file.linked_paper_id = paper.id
            stored_file.status = FileStatus.READY
            task.status = TaskStatus.SUCCESS
            task.error_message = None
            task.result = {
                "file_id": stored_file.id,
                "paper_id": paper.id,
                "metadata": metadata,
                "sections_count": len(sections),
                "section_titles": [section["title"] for section in sections],
            }
            await db.commit()
        except Exception as exc:
            await db.rollback()
            task = await self._get_task(db, task_id)
            stored_file = task.file
            if stored_file is None:
                raise
            stored_file.status = FileStatus.ERROR
            task.status = TaskStatus.ERROR
            task.error_message = str(exc)
            task.result = {
                "file_id": stored_file.id,
                "paper_id": None,
                "metadata": {},
                "sections_count": 0,
                "section_titles": [],
            }
            await db.commit()

    async def _extract_pdf_insights(self, file_path: Path, original_name: str) -> dict[str, Any]:
        document = fitz.open(str(file_path))
        page_chunks, full_text = self._extract_document_chunks(document)
        if not full_text:
            raise ValueError("No extractable text found in PDF")

        first_page_text = "\n".join(chunk["text"] for chunk in page_chunks if chunk["page"] == 1)[:4000]
        metadata = self._extract_metadata(document.metadata or {}, first_page_text, full_text, original_name)
        sections = self._build_structured_sections(page_chunks, full_text)
        if not sections:
            sections = self._attach_page_ranges(
                self._with_section_spans(full_text, self._split_sections(full_text)),
                page_chunks,
            )
        if metadata.get("abstract") is None:
            abstract_section = next((section for section in sections if section["title"].lower() == "abstract"), None)
            if abstract_section:
                metadata["abstract"] = abstract_section["text"][:3000] or None

        enhancement = await minimax_parse_service.enhance_document_parse(
            file_type="pdf",
            filename=original_name,
            full_text=full_text,
            heuristic_metadata=metadata,
            heuristic_section_titles=[section["title"] for section in sections],
        )
        if enhancement:
            metadata = self._merge_metadata(metadata, enhancement.get("metadata") or {})
            llm_section_titles = enhancement.get("section_titles") or []
            if llm_section_titles:
                sections = self._attach_page_ranges(
                    self._with_section_spans(full_text, self._split_sections(full_text, preferred_titles=llm_section_titles)),
                    page_chunks,
                )
                if metadata.get("abstract") is None:
                    abstract_section = next((section for section in sections if section["title"].lower() == "abstract"), None)
                    if abstract_section:
                        metadata["abstract"] = abstract_section["text"][:3000] or None

        document.close()

        return {
            "full_text": full_text,
            "metadata": metadata,
            "sections": sections,
        }

    def _merge_metadata(self, heuristic_metadata: dict[str, Any], enhanced_metadata: dict[str, Any]) -> dict[str, Any]:
        merged = dict(heuristic_metadata)
        for key in ["title", "abstract"]:
            value = enhanced_metadata.get(key)
            if isinstance(value, str) and value.strip():
                merged[key] = value.strip()
        if isinstance(enhanced_metadata.get("authors"), list) and enhanced_metadata["authors"]:
            merged["authors"] = enhanced_metadata["authors"]
        if isinstance(enhanced_metadata.get("keywords"), list):
            merged["keywords"] = enhanced_metadata["keywords"]
        if enhanced_metadata.get("year"):
            merged["year"] = enhanced_metadata["year"]
        return merged

    def _extract_metadata(
        self,
        reader_metadata: dict[str, Any],
        first_page_text: str,
        full_text: str,
        original_name: str,
    ) -> dict[str, Any]:
        title = self._extract_title(self._safe_metadata_attr(reader_metadata, "title"), first_page_text, original_name)
        authors = self._extract_authors(self._safe_metadata_attr(reader_metadata, "author"), first_page_text, title)
        year = self._extract_year(self._safe_metadata_attr(reader_metadata, "creation_date"), first_page_text, full_text)
        abstract = self._extract_abstract(full_text)
        return {
            "title": title,
            "authors": authors,
            "year": year,
            "abstract": abstract,
            "keywords": [],
        }

    def _safe_metadata_attr(self, metadata: Any, attr_name: str) -> Any:
        try:
            if isinstance(metadata, dict):
                direct = metadata.get(attr_name)
                if direct is not None:
                    return direct
                alias_map = {
                    "title": {"title"},
                    "author": {"author"},
                    "creation_date": {"creationDate", "creation_date"},
                }
                for alias in alias_map.get(attr_name, set()):
                    if alias in metadata:
                        return metadata[alias]
                return None
            return getattr(metadata, attr_name, None)
        except Exception:
            return None

    def _extract_title(self, metadata_title: str | None, first_page_text: str, original_name: str) -> str:
        if metadata_title:
            normalized_metadata_title = self._normalize_text(metadata_title)
            if 8 <= len(normalized_metadata_title) <= 300 and normalized_metadata_title.lower() != "untitled":
                return normalized_metadata_title

        for line in self._candidate_lines(first_page_text, limit=12):
            lowered = line.lower().rstrip(":")
            if lowered in {"abstract", "introduction"}:
                break
            if 12 <= len(line) <= 240 and "@" not in line and not self._looks_like_affiliation(line):
                return line

        return paper_service._infer_title(original_name)

    def _extract_authors(self, metadata_author: str | None, first_page_text: str, title: str) -> list[str]:
        metadata_authors = self._split_authors(metadata_author)
        if metadata_authors:
            return metadata_authors

        lines = self._candidate_lines(first_page_text, limit=18)
        collected: list[str] = []
        title_found = False
        for line in lines:
            if not title_found:
                if line == title:
                    title_found = True
                continue
            lowered = line.lower().rstrip(":")
            if lowered in {"abstract", "introduction"}:
                break
            if self._looks_like_affiliation(line) or "@" in line:
                continue
            if 2 <= len(line.split()) <= 12:
                collected.append(line)
            if len(collected) >= 2:
                break

        return self._split_authors(", ".join(collected))

    def _split_authors(self, raw_value: str | None) -> list[str]:
        if not raw_value:
            return []
        cleaned = self._normalize_text(raw_value)
        cleaned = re.sub(r"\b(and|&)\b", ",", cleaned, flags=re.IGNORECASE)
        candidates = [part.strip() for part in re.split(r"[,;]", cleaned) if part.strip()]
        authors: list[str] = []
        for candidate in candidates:
            normalized = re.sub(r"\s*\d+$", "", candidate).strip("*??0123456789 ")
            if not normalized or self._looks_like_affiliation(normalized) or "@" in normalized:
                continue
            word_count = len(normalized.split())
            if 1 <= word_count <= 5 and len(normalized) <= 80:
                authors.append(normalized)
        return authors[:8]

    def _extract_year(self, metadata_creation_date: Any, first_page_text: str, full_text: str) -> int | None:
        if metadata_creation_date:
            metadata_year_match = re.search(r"(19|20)\d{2}", str(metadata_creation_date))
            if metadata_year_match:
                return int(metadata_year_match.group(0))

        search_window = f"{first_page_text}\n{full_text[:2000]}"
        current_year = datetime.utcnow().year + 1
        for match in re.finditer(r"\b(19\d{2}|20\d{2})\b", search_window):
            year = int(match.group(0))
            if 1900 <= year <= current_year:
                return year
        return None

    def _extract_abstract(self, full_text: str) -> str | None:
        match = re.search(
            r"(?is)\babstract\b\s*[:\-]?\s*(.+?)(?=\n\s*(?:keywords?|1\s*[\.)]?\s*introduction|introduction|background|literature review|methodology|methods|data|references)\b)",
            full_text,
        )
        if not match:
            return None
        abstract = self._normalize_text(match.group(1))
        return abstract[:3000] if abstract else None

    def _split_sections(self, full_text: str, preferred_titles: list[str] | None = None) -> list[dict[str, str]]:
        lines = [self._normalize_text(line) for line in full_text.splitlines()]
        sections: list[dict[str, str]] = []
        current_title: str | None = None
        buffer: list[str] = []
        normalized_preferred = {
            self._normalize_heading_key(title): title
            for title in (preferred_titles or [])
            if self._normalize_heading_key(title)
        }

        for line in lines:
            if not line:
                continue
            heading = self._normalize_heading(line, normalized_preferred)
            if heading:
                if current_title and buffer:
                    sections.append({"title": current_title, "text": "\n".join(buffer).strip()})
                    buffer = []
                elif not current_title and buffer:
                    sections.append({"title": "Front Matter", "text": "\n".join(buffer).strip()})
                    buffer = []
                current_title = heading
                continue
            buffer.append(line)

        if current_title and buffer:
            sections.append({"title": current_title, "text": "\n".join(buffer).strip()})
        elif not sections and full_text.strip():
            sections.append({"title": "Full Text", "text": full_text.strip()})

        deduped: list[dict[str, str]] = []
        seen: dict[str, int] = {}
        for section in sections:
            title = section["title"]
            seen[title] = seen.get(title, 0) + 1
            normalized_title = title if seen[title] == 1 else f"{title} {seen[title]}"
            deduped.append({"title": normalized_title, "text": section["text"]})
        return deduped

    def _with_section_spans(self, full_text: str, sections: list[dict[str, str]]) -> list[dict[str, Any]]:
        annotated: list[dict[str, Any]] = []
        cursor = 0
        for section in sections:
            section_text = section.get("text") or ""
            span_start = None
            span_end = None
            if section_text:
                found_at = full_text.find(section_text, cursor)
                if found_at >= 0:
                    span_start = found_at
                    span_end = found_at + len(section_text)
                    cursor = span_end
            annotated.append(
                {
                    "title": section["title"],
                    "text": section_text,
                    "span_start": span_start,
                    "span_end": span_end,
                }
            )
        return annotated

    def _normalize_heading(self, line: str, preferred_titles: dict[str, str] | None = None) -> str | None:
        stripped = line.strip().strip(":")
        lowered = stripped.lower()
        if lowered in self.known_headings:
            return self.known_headings[lowered]

        if preferred_titles:
            direct_key = self._normalize_heading_key(stripped)
            if direct_key in preferred_titles:
                return preferred_titles[direct_key]

        numbered_match = re.match(r"^(?:\d+(?:\.\d+)*|[IVXLC]+)[\.)]?\s+(.+)$", stripped)
        if numbered_match:
            candidate = numbered_match.group(1).strip().strip(":")
            normalized_candidate = candidate.lower()
            if normalized_candidate in self.known_headings:
                return self.known_headings[normalized_candidate]
            if preferred_titles:
                preferred_key = self._normalize_heading_key(candidate)
                if preferred_key in preferred_titles:
                    return preferred_titles[preferred_key]
            if 2 <= len(candidate.split()) <= 8 and len(candidate) <= 80:
                return candidate.title()

        if stripped.isupper() and 1 <= len(stripped.split()) <= 6 and len(stripped) <= 80:
            return stripped.title()

        return None

    def _extract_document_chunks(self, document: fitz.Document) -> tuple[list[dict[str, Any]], str]:
        page_chunks: list[dict[str, Any]] = []
        full_text_parts: list[str] = []
        offset = 0
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            page_dict = page.get_text("dict")
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                lines = block.get("lines") or []
                line_texts: list[str] = []
                font_sizes: list[float] = []
                flags: list[int] = []
                for line in lines:
                    spans = line.get("spans") or []
                    span_text = "".join((span.get("text") or "") for span in spans)
                    normalized_line = self._normalize_text(span_text)
                    if not normalized_line:
                        continue
                    line_texts.append(normalized_line)
                    font_sizes.extend(float(span.get("size") or 0.0) for span in spans if span.get("size"))
                    flags.extend(int(span.get("flags") or 0) for span in spans)
                block_text = "\n".join(line_texts).strip()
                if not block_text:
                    continue
                avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 0.0
                is_bold = any(flag & 16 for flag in flags)
                block_start = offset
                block_end = block_start + len(block_text)
                page_chunks.append(
                    {
                        "page": page_index + 1,
                        "text": block_text,
                        "avg_font_size": avg_font_size,
                        "is_bold": is_bold,
                        "span_start": block_start,
                        "span_end": block_end,
                    }
                )
                full_text_parts.append(block_text)
                offset = block_end + 2
        return page_chunks, "\n\n".join(full_text_parts).strip()

    def _build_structured_sections(self, page_chunks: Iterable[dict[str, Any]], full_text: str) -> list[dict[str, Any]]:
        chunk_list = list(page_chunks)
        if not chunk_list:
            return []

        font_sizes = [chunk["avg_font_size"] for chunk in chunk_list if chunk.get("avg_font_size")]
        median_font = sorted(font_sizes)[len(font_sizes) // 2] if font_sizes else 11.0

        sections: list[dict[str, Any]] = []
        current_title = "Front Matter"
        current_texts: list[str] = []
        current_page_start = chunk_list[0]["page"]
        current_page_end = chunk_list[0]["page"]

        for chunk in chunk_list:
            text = chunk["text"]
            if self._looks_like_heading_block(text, chunk, median_font):
                if current_texts:
                    sections.append(
                        self._finalize_section(full_text, current_title, current_texts, current_page_start, current_page_end)
                    )
                current_title = self._clean_section_title(text)
                current_texts = []
                current_page_start = chunk["page"]
                current_page_end = chunk["page"]
                continue

            current_texts.append(text)
            current_page_end = chunk["page"]

        if current_texts:
            sections.append(self._finalize_section(full_text, current_title, current_texts, current_page_start, current_page_end))

        return [section for section in sections if section["text"]]

    def _looks_like_heading_block(self, text: str, chunk: dict[str, Any], median_font: float) -> bool:
        normalized = self._normalize_text(text)
        lowered_key = self._normalize_heading_key(normalized)
        if lowered_key in self.known_headings:
            return True
        if self.heading_number_pattern.match(normalized) and len(normalized) <= 120:
            return True
        if "\n" in normalized:
            return False
        word_count = len(normalized.split())
        bigger_font = float(chunk.get("avg_font_size") or 0.0) >= median_font * 1.12
        if bigger_font and word_count <= 14 and len(normalized) <= 120:
            return True
        if chunk.get("is_bold") and word_count <= 10 and len(normalized) <= 100:
            return True
        if normalized.isupper() and word_count <= 10 and len(normalized) <= 100:
            return True
        return False

    def _clean_section_title(self, value: str) -> str:
        normalized = self._normalize_text(value).strip(":")
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized[:100] or "Untitled Section"

    def _finalize_section(
        self,
        full_text: str,
        title: str,
        texts: list[str],
        page_start: int,
        page_end: int,
    ) -> dict[str, Any]:
        body = "\n\n".join(texts).strip()
        span_start = full_text.find(body) if body else None
        span_end = span_start + len(body) if span_start is not None and span_start >= 0 else None
        return {
            "title": title[:100],
            "text": body,
            "span_start": span_start if span_start is not None and span_start >= 0 else None,
            "span_end": span_end,
            "page_start": page_start,
            "page_end": page_end,
        }

    def _attach_page_ranges(self, sections: list[dict[str, Any]], page_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not sections or not page_chunks:
            return sections

        page_ranges: dict[int, tuple[int, int]] = {}
        page_texts: dict[int, str] = {}
        for chunk in page_chunks:
            page = chunk["page"]
            start = chunk.get("span_start")
            end = chunk.get("span_end")
            if start is None or end is None:
                page_texts[page] = f"{page_texts.get(page, '')}\n{chunk.get('text', '')}".strip()
                continue
            current = page_ranges.get(page)
            if current is None:
                page_ranges[page] = (start, end)
            else:
                page_ranges[page] = (min(current[0], start), max(current[1], end))
            page_texts[page] = f"{page_texts.get(page, '')}\n{chunk.get('text', '')}".strip()

        for section in sections:
            span_start = section.get("span_start")
            span_end = section.get("span_end")
            pages: list[int] = []
            if span_start is not None and span_end is not None:
                pages = [
                    page
                    for page, (page_start, page_end) in page_ranges.items()
                    if not (span_end < page_start or span_start > page_end)
                ]
            if not pages:
                pages = self._infer_pages_from_text(section.get("text") or "", page_texts)
            section["page_start"] = min(pages) if pages else None
            section["page_end"] = max(pages) if pages else None
        return sections

    def _infer_pages_from_text(self, section_text: str, page_texts: dict[int, str]) -> list[int]:
        normalized_section = self._normalize_text(section_text)
        if not normalized_section:
            return []

        start_snippet = normalized_section[:160].strip()
        end_snippet = normalized_section[-160:].strip() if len(normalized_section) > 160 else start_snippet
        matched_pages: list[int] = []

        for page, text in page_texts.items():
            normalized_page = self._normalize_text(text)
            if not normalized_page:
                continue
            if start_snippet and start_snippet in normalized_page:
                matched_pages.append(page)
                continue
            if end_snippet and end_snippet in normalized_page:
                matched_pages.append(page)
                continue

        if matched_pages:
            return matched_pages

        first_words = " ".join(normalized_section.split()[:12]).strip()
        if not first_words:
            return []
        for page, text in page_texts.items():
            normalized_page = self._normalize_text(text)
            if first_words and first_words in normalized_page:
                matched_pages.append(page)
        return matched_pages

    def _normalize_heading_key(self, value: str | None) -> str:
        if not value:
            return ""
        cleaned = self._normalize_text(value).lower().strip(":")
        cleaned = re.sub(r"^(?:\d+(?:\.\d+)*|[ivxlc]+)[\.)]?\s+", "", cleaned)
        return cleaned

    def _candidate_lines(self, text: str, limit: int = 12) -> list[str]:
        lines: list[str] = []
        for raw_line in text.splitlines():
            normalized = self._normalize_text(raw_line)
            if normalized:
                lines.append(normalized)
            if len(lines) >= limit:
                break
        return lines

    def _looks_like_affiliation(self, value: str) -> bool:
        lowered = value.lower()
        affiliation_markers = [
            "university",
            "college",
            "department",
            "school",
            "institute",
            "faculty",
            "laboratory",
            "centre",
            "center",
        ]
        return any(marker in lowered for marker in affiliation_markers)

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"[ \t]+", " ", text.replace("\x00", " ")).strip()

    async def _get_task(self, db: AsyncSession, task_id: str) -> ProcessingTask:
        stmt = (
            select(ProcessingTask)
            .options(selectinload(ProcessingTask.file))
            .where(ProcessingTask.id == task_id)
        )
        result = await db.execute(stmt)
        task = result.scalar_one_or_none()
        if task is None:
            raise_not_found("Task not found")
        return task

    async def _get_file(self, db: AsyncSession, file_id: str) -> StoredFile:
        stmt = (
            select(StoredFile)
            .options(selectinload(StoredFile.tasks))
            .where(StoredFile.id == file_id)
        )
        result = await db.execute(stmt)
        stored_file = result.scalar_one_or_none()
        if stored_file is None:
            raise_not_found("File not found")
        stored_file.tasks.sort(key=lambda item: item.created_at, reverse=True)
        return stored_file

    def _validate_upload(self, file: UploadFile) -> None:
        suffix = Path(file.filename or "").suffix.lower()
        if suffix != ".pdf":
            raise_bad_request("Only PDF uploads are supported in this MVP")

    async def _save_upload(self, file: UploadFile) -> Path:
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

    def _can_access_file(self, stored_file: StoredFile, current_user: User) -> bool:
        if current_user.role in {"admin", "developer_admin"}:
            return True
        if current_user.role != "researcher":
            return False
        if stored_file.researcher_id:
            return stored_file.researcher_id == current_user.researcher_id
        return stored_file.uploaded_by == current_user.id

    def _ensure_file_access(self, stored_file: StoredFile, current_user: User) -> None:
        if self._can_access_file(stored_file, current_user):
            return
        if current_user.role != "researcher":
            raise_forbidden("This account cannot access uploaded files")
        raise_forbidden("You do not have permission to access this file")

    def _ensure_task_access(self, task: ProcessingTask, current_user: User) -> None:
        if current_user.role in {"admin", "developer_admin"}:
            return
        if task.file is None:
            raise_forbidden("Task is not associated with a file")
        self._ensure_file_access(task.file, current_user)

    async def _build_knowledge_status(
        self,
        db: AsyncSession,
        stored_file: StoredFile,
        latest_task: ProcessingTask | None,
    ) -> KnowledgeStatusSummary:
        uploaded = True
        parsing = stored_file.status == FileStatus.PROCESSING or (latest_task is not None and latest_task.status in {TaskStatus.QUEUED, TaskStatus.PROCESSING})
        parse_success = latest_task is not None and latest_task.status == TaskStatus.SUCCESS
        parse_error = stored_file.status == FileStatus.ERROR or (latest_task is not None and latest_task.status == TaskStatus.ERROR)
        paper_generated = bool(stored_file.linked_paper_id or (latest_task and latest_task.result and latest_task.result.get("paper_id")))
        researcher_context_bound = bool(stored_file.researcher_id)

        in_researcher_knowledge_base = False
        if researcher_context_bound and stored_file.linked_paper_id:
            in_researcher_knowledge_base = await local_retrieval_service.is_paper_retrievable_for_researcher(
                db,
                researcher_id=stored_file.researcher_id,
                paper_id=stored_file.linked_paper_id,
            )

        awaiting_knowledge_base_entry = bool(parse_success and paper_generated and not in_researcher_knowledge_base)
        agent_ready = bool(in_researcher_knowledge_base)

        if parse_error:
            summary_text = "解析失败，尚未进入研究者知识库。"
        elif parsing:
            summary_text = "文件已上传，系统正在解析。"
        elif in_researcher_knowledge_base:
            summary_text = "文献已完成解析，并已纳入当前研究者权限范围内的可检索知识库，可供后续 Agent 检索。"
        elif parse_success and paper_generated and researcher_context_bound:
            summary_text = "文献已完成解析并绑定研究者上下文，但尚未挂接到 researcher 当前可检索的导师知识库。"
        elif awaiting_knowledge_base_entry:
            summary_text = "文献已完成解析并生成 Paper，但尚未进入研究者可检索知识库。"
        elif paper_generated:
            summary_text = "文献已生成 Paper 记录，但知识库关联仍未完成。"
        else:
            summary_text = "文件已上传，等待进一步处理。"

        return KnowledgeStatusSummary(
            uploaded=uploaded,
            parsing=parsing,
            parse_success=parse_success,
            parse_error=parse_error,
            paper_generated=paper_generated,
            researcher_context_bound=researcher_context_bound,
            in_researcher_knowledge_base=in_researcher_knowledge_base,
            awaiting_knowledge_base_entry=awaiting_knowledge_base_entry,
            agent_ready=agent_ready,
            summary_text=summary_text,
        )

    def _build_task_response(self, task: ProcessingTask) -> TaskResponse:
        task_result = task.result or {}
        return TaskResponse(
            id=task.id,
            task_type=task.task_type,
            status=task.status,
            file_id=task.file_id,
            created_by=task.created_by,
            result=TaskResultResponse(
                file_id=task_result.get("file_id"),
                paper_id=task_result.get("paper_id"),
                metadata=task_result.get("metadata") or {},
                sections_count=task_result.get("sections_count") or 0,
                section_titles=task_result.get("section_titles") or [],
            ),
            error_message=task.error_message,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


file_task_service = FileTaskService()










