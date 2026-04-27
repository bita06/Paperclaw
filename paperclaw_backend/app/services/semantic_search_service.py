"""Hybrid retrieval over PaperChunk using pgvector + PostgreSQL FTS + RRF."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Paper, PaperChunk, PaperSource, Researcher, User
from app.schemas.agent import AgentEvidenceSourceEnum, SemanticSearchChunkItem
from app.services.embedding_service import embedding_service


@dataclass
class RetrievalCandidate:
    item: SemanticSearchChunkItem
    vector_rank: int | None = None
    keyword_rank: int | None = None
    vector_score: float = 0.0
    keyword_score: float = 0.0


class SemanticSearchService:
    rrf_k = 60
    recall_multiplier = 4

    async def search_chunks(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        researcher: Researcher,
        query: str,
        include_builtin_library: bool,
        include_user_uploads: bool,
        collection_slug: str | None,
        top_k: int,
    ) -> list[SemanticSearchChunkItem]:
        if not query.strip():
            return []

        query_embedding = await embedding_service.embed_text(query, purpose="query")
        if not query_embedding:
            return []

        recall_limit = max(top_k * self.recall_multiplier, top_k)
        vector_items = await self._vector_recall(
            db,
            query_embedding=query_embedding,
            current_user=current_user,
            researcher=researcher,
            include_builtin_library=include_builtin_library,
            include_user_uploads=include_user_uploads,
            collection_slug=collection_slug,
            limit=recall_limit,
        )
        keyword_items = await self._keyword_recall(
            db,
            query=query,
            current_user=current_user,
            researcher=researcher,
            include_builtin_library=include_builtin_library,
            include_user_uploads=include_user_uploads,
            collection_slug=collection_slug,
            limit=recall_limit,
        )
        return self._fuse_with_rrf(vector_items, keyword_items, top_k)

    async def _vector_recall(
        self,
        db: AsyncSession,
        *,
        query_embedding: list[float],
        current_user: User,
        researcher: Researcher,
        include_builtin_library: bool,
        include_user_uploads: bool,
        collection_slug: str | None,
        limit: int,
    ) -> list[SemanticSearchChunkItem]:
        stmt = (
            select(
                PaperChunk,
                Paper,
                (1 - PaperChunk.chunk_embedding.cosine_distance(query_embedding)).label("vector_score"),
            )
            .join(Paper, Paper.id == PaperChunk.paper_id)
            .where(PaperChunk.chunk_embedding.is_not(None))
        )
        stmt = self._apply_source_filters(
            stmt,
            current_user=current_user,
            researcher=researcher,
            include_builtin_library=include_builtin_library,
            include_user_uploads=include_user_uploads,
            collection_slug=collection_slug,
        )
        stmt = stmt.order_by(PaperChunk.chunk_embedding.cosine_distance(query_embedding)).limit(limit)

        result = await db.execute(stmt)
        items: list[SemanticSearchChunkItem] = []
        for chunk, paper, vector_score in result.all():
            source, source_label = self._map_source(paper.source)
            items.append(
                SemanticSearchChunkItem(
                    chunk_id=chunk.id,
                    paper_id=paper.id,
                    title=paper.title,
                    authors=paper.authors or [],
                    year=paper.year,
                    section_title=chunk.section_title,
                    chunk_text=chunk.chunk_text,
                    source=source,
                    source_label=source_label,
                    collection_slug=paper.collection_slug,
                    score=round(float(vector_score or 0.0), 6),
                    vector_score=round(float(vector_score or 0.0), 6),
                    keyword_score=0.0,
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                )
            )
        return items

    async def _keyword_recall(
        self,
        db: AsyncSession,
        *,
        query: str,
        current_user: User,
        researcher: Researcher,
        include_builtin_library: bool,
        include_user_uploads: bool,
        collection_slug: str | None,
        limit: int,
    ) -> list[SemanticSearchChunkItem]:
        ts_query = func.websearch_to_tsquery("simple", query)
        rank_expr = func.ts_rank_cd(PaperChunk.chunk_tsv, ts_query)
        stmt = (
            select(PaperChunk, Paper, rank_expr.label("keyword_score"))
            .join(Paper, Paper.id == PaperChunk.paper_id)
            .where(PaperChunk.chunk_tsv.is_not(None))
            .where(PaperChunk.chunk_tsv.op("@@")(ts_query))
        )
        stmt = self._apply_source_filters(
            stmt,
            current_user=current_user,
            researcher=researcher,
            include_builtin_library=include_builtin_library,
            include_user_uploads=include_user_uploads,
            collection_slug=collection_slug,
        )
        stmt = stmt.order_by(rank_expr.desc()).limit(limit)

        result = await db.execute(stmt)
        items: list[SemanticSearchChunkItem] = []
        for chunk, paper, keyword_score in result.all():
            source, source_label = self._map_source(paper.source)
            items.append(
                SemanticSearchChunkItem(
                    chunk_id=chunk.id,
                    paper_id=paper.id,
                    title=paper.title,
                    authors=paper.authors or [],
                    year=paper.year,
                    section_title=chunk.section_title,
                    chunk_text=chunk.chunk_text,
                    source=source,
                    source_label=source_label,
                    collection_slug=paper.collection_slug,
                    score=round(float(keyword_score or 0.0), 6),
                    vector_score=0.0,
                    keyword_score=round(float(keyword_score or 0.0), 6),
                    page_start=chunk.page_start,
                    page_end=chunk.page_end,
                )
            )
        return items

    def _fuse_with_rrf(
        self,
        vector_items: list[SemanticSearchChunkItem],
        keyword_items: list[SemanticSearchChunkItem],
        top_k: int,
    ) -> list[SemanticSearchChunkItem]:
        merged: dict[str, RetrievalCandidate] = {}

        for rank, item in enumerate(vector_items, start=1):
            candidate = merged.setdefault(item.chunk_id, RetrievalCandidate(item=item))
            candidate.vector_rank = rank
            candidate.vector_score = item.vector_score

        for rank, item in enumerate(keyword_items, start=1):
            candidate = merged.setdefault(item.chunk_id, RetrievalCandidate(item=item))
            candidate.keyword_rank = rank
            candidate.keyword_score = item.keyword_score
            if not candidate.item.authors and item.authors:
                candidate.item.authors = item.authors
            if candidate.item.year is None:
                candidate.item.year = item.year

        ranked: list[SemanticSearchChunkItem] = []
        for candidate in merged.values():
            fused_score = 0.0
            if candidate.vector_rank is not None:
                fused_score += 1.0 / (self.rrf_k + candidate.vector_rank)
            if candidate.keyword_rank is not None:
                fused_score += 1.0 / (self.rrf_k + candidate.keyword_rank)
            candidate.item.score = round(fused_score, 6)
            candidate.item.vector_score = round(candidate.vector_score, 6)
            candidate.item.keyword_score = round(candidate.keyword_score, 6)
            ranked.append(candidate.item)

        ranked.sort(
            key=lambda item: (
                item.score,
                item.vector_score,
                item.keyword_score,
            ),
            reverse=True,
        )
        return ranked[:top_k]

    def _apply_source_filters(
        self,
        stmt: Select,
        *,
        current_user: User,
        researcher: Researcher,
        include_builtin_library: bool,
        include_user_uploads: bool,
        collection_slug: str | None,
    ) -> Select:
        predicates = []
        if include_builtin_library:
            builtin_stmt = (Paper.source == PaperSource.BUILTIN_LIBRARY)
            if collection_slug:
                builtin_stmt = builtin_stmt & (Paper.collection_slug == collection_slug)
            predicates.append(builtin_stmt)

        if include_user_uploads:
            owner_user_id = researcher.user.id if researcher.user else None
            if current_user.role == "researcher":
                owner_user_id = current_user.id
            if owner_user_id:
                predicates.append((Paper.source == PaperSource.UPLOADED) & (Paper.owner_user_id == owner_user_id))

        if not predicates:
            return stmt.where(False)
        return stmt.where(or_(*predicates))

    def _map_source(self, source: PaperSource) -> tuple[AgentEvidenceSourceEnum, str]:
        if source == PaperSource.BUILTIN_LIBRARY:
            return AgentEvidenceSourceEnum.BUILTIN_LIBRARY, "系统内置文献库"
        return AgentEvidenceSourceEnum.USER_UPLOAD, "用户上传文献"


semantic_search_service = SemanticSearchService()
