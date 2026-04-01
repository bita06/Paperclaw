import json
import logging
import math
import re
from collections.abc import Sequence
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.exceptions import raise_bad_request, raise_forbidden, raise_not_found
from app.models import Researcher, ResearcherAdvisor, User
from app.models.paper import Paper, PaperSection
from app.schemas.agent import (
    AgentEvidenceSourceEnum,
    AgentExternalEvidenceItem,
    AgentLocalEvidenceItem,
    AgentModeEnum,
    AgentQueryResponse,
    AgentSourceStatus,
)
from app.services.local_retrieval_service import local_retrieval_service
from app.services.web_search_service import web_search_service
from app.services.wos_service import wos_service


logger = logging.getLogger(__name__)


class AgentService:
    async def query(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        researcher_id: str | None,
        advisor_id: str | None,
        question: str,
        mode: AgentModeEnum,
        top_k: int,
        include_builtin_library: bool,
        include_user_uploads: bool,
        use_web_search: bool,
        use_wos_search: bool,
        collection_slug: str | None,
    ) -> AgentQueryResponse:
        researcher = await self._get_researcher(db, researcher_id)
        links = await self._get_advisor_links(db, researcher.id)
        if advisor_id and advisor_id not in {link.advisor_id for link in links}:
            raise_forbidden("The selected advisor is not available in the current researcher context")

        source_status = AgentSourceStatus(local="disabled", wos="disabled", web="disabled")

        local_sources_enabled = include_builtin_library or include_user_uploads
        local_evidence: list[AgentLocalEvidenceItem] = []
        if local_sources_enabled:
            local_candidates = await self._collect_local_candidates(
                db,
                current_user=current_user,
                researcher=researcher,
                question=question,
                top_k=top_k,
                include_builtin_library=include_builtin_library,
                include_user_uploads=include_user_uploads,
                collection_slug=collection_slug,
            )
            local_evidence = [self._build_local_evidence(item) for item in local_candidates[:top_k]]
            source_status.local = "ok" if local_evidence else "empty"
            if not local_evidence:
                source_status.messages.append("当前选中的本地来源范围内，未检索到与问题直接相关的文献证据。")
        else:
            source_status.messages.append("当前未启用任何本地文献来源。")

        wos_evidence: list[AgentExternalEvidenceItem] = []
        if use_wos_search:
            source_status.wos = "processing"
            wos_results, wos_note = await wos_service.search_documents(query=question, limit=top_k, page=1)
            if wos_results:
                wos_evidence = [self._build_external_evidence(item, AgentEvidenceSourceEnum.WOS) for item in wos_results[:top_k]]
                source_status.wos = "ok"
            else:
                source_status.wos = "error" if wos_note and "失败" in wos_note else "empty"
            if wos_note:
                source_status.messages.append(wos_note)

        web_evidence: list[AgentExternalEvidenceItem] = []
        if use_web_search:
            web_results, web_note = await web_search_service.search(query=question, limit=top_k)
            web_evidence = [self._build_external_evidence(item, AgentEvidenceSourceEnum.WEB) for item in web_results[:top_k]]
            source_status.web = "placeholder"
            if web_note:
                source_status.messages.append(web_note)

        if not local_evidence and not wos_evidence and not web_evidence:
            return self._build_insufficient_response(
                mode=mode,
                message="当前启用的来源中没有返回足够证据。请先导入内置文献库、上传个人文献，或再启用外部来源。",
                source_status=source_status,
            )

        response = await self._query_minimax(
            question=question,
            mode=mode,
            researcher=researcher,
            links=links,
            local_evidence=local_evidence,
            wos_evidence=wos_evidence,
            web_evidence=web_evidence,
            source_status=source_status,
        )
        if response is None:
            return self._build_fallback_response(
                mode=mode,
                local_evidence=local_evidence,
                wos_evidence=wos_evidence,
                web_evidence=web_evidence,
                source_status=source_status,
            )
        return response

    async def _get_researcher(self, db: AsyncSession, researcher_id: str | None) -> Researcher:
        if not researcher_id:
            raise_bad_request("researcher_id is required for agent query context")
        stmt = select(Researcher).options(selectinload(Researcher.user)).where(Researcher.id == researcher_id)
        result = await db.execute(stmt)
        researcher = result.scalar_one_or_none()
        if not researcher:
            raise_not_found("Researcher not found")
        return researcher

    async def _get_advisor_links(self, db: AsyncSession, researcher_id: str) -> Sequence[ResearcherAdvisor]:
        stmt = (
            select(ResearcherAdvisor)
            .options(selectinload(ResearcherAdvisor.advisor))
            .where(ResearcherAdvisor.researcher_id == researcher_id)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def _collect_local_candidates(
        self,
        db: AsyncSession,
        *,
        current_user: User,
        researcher: Researcher,
        question: str,
        top_k: int,
        include_builtin_library: bool,
        include_user_uploads: bool,
        collection_slug: str | None,
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        limit = max(top_k * 6, 20)

        if include_builtin_library:
            builtin_papers = await local_retrieval_service.list_builtin_papers(
                db,
                collection_slug=collection_slug,
                limit=limit,
            )
            for paper in builtin_papers:
                candidates.extend(
                    self._score_local_paper(
                        question,
                        paper,
                        source=AgentEvidenceSourceEnum.BUILTIN_LIBRARY,
                        source_label="系统内置文献库",
                        collection_slug=paper.collection_slug,
                    )
                )

        if include_user_uploads:
            owner_user_id = researcher.user.id if researcher.user else None
            if current_user.role == "researcher":
                owner_user_id = current_user.id
            uploaded_papers = await local_retrieval_service.list_user_uploaded_papers(
                db,
                owner_user_id=owner_user_id,
                researcher_id=researcher.id,
                limit=limit,
            )
            for paper in uploaded_papers:
                candidates.extend(
                    self._score_local_paper(
                        question,
                        paper,
                        source=AgentEvidenceSourceEnum.USER_UPLOAD,
                        source_label="用户上传文献",
                        collection_slug=None,
                    )
                )

        ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)
        positive = [item for item in ranked if item["score"] > 0]
        chosen = positive[:top_k] if positive else ranked[:top_k]

        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for item in chosen:
            key = (item["paper_id"], item.get("section_title") or "", item["source"].value)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _score_local_paper(
        self,
        question: str,
        paper: Paper,
        *,
        source: AgentEvidenceSourceEnum,
        source_label: str,
        collection_slug: str | None,
    ) -> list[dict[str, Any]]:
        tokens = self._tokenize(question)
        candidates: list[dict[str, Any]] = []

        title_text = paper.title or ""
        abstract_text = paper.abstract or ""
        keyword_text = " ".join(paper.keywords or [])
        full_context = "\n".join(filter(None, [title_text, abstract_text, keyword_text]))
        paper_score = self._score_text(tokens, title_text) * 3 + self._score_text(tokens, abstract_text) * 2 + self._score_text(tokens, keyword_text) * 2
        candidates.append(
            {
                "score": paper_score,
                "paper_id": paper.id,
                "title": paper.title,
                "authors": paper.authors or [],
                "year": paper.year,
                "section_title": "摘要与元数据",
                "quote_or_summary": self._truncate(full_context, 360),
                "source": source,
                "source_label": source_label,
                "collection_slug": collection_slug,
            }
        )

        sections = sorted(
            paper.section_contents or [],
            key=lambda section: (section.span_start if section.span_start is not None else math.inf, section.created_at),
        )
        for section in sections:
            text = section.section_text or ""
            if not text.strip():
                continue
            score = self._score_text(tokens, section.section_name or "") * 2 + self._score_text(tokens, text)
            candidates.append(
                {
                    "score": score,
                    "paper_id": paper.id,
                    "title": paper.title,
                    "authors": paper.authors or [],
                    "year": paper.year,
                    "section_title": section.section_name,
                    "quote_or_summary": self._truncate(text, 360),
                    "source": source,
                    "source_label": source_label,
                    "collection_slug": collection_slug,
                }
            )
        return candidates

    def _build_local_evidence(self, item: dict[str, Any]) -> AgentLocalEvidenceItem:
        return AgentLocalEvidenceItem(
            paper_id=item["paper_id"],
            title=item["title"],
            authors=item["authors"],
            year=item["year"],
            section_title=item["section_title"],
            quote_or_summary=item["quote_or_summary"],
            source=item["source"],
            source_label=item["source_label"],
            collection_slug=item.get("collection_slug"),
        )

    def _build_external_evidence(
        self,
        item: dict[str, Any],
        source: AgentEvidenceSourceEnum,
    ) -> AgentExternalEvidenceItem:
        return AgentExternalEvidenceItem(
            title=item["title"],
            authors=item.get("authors", []),
            year=item.get("year"),
            source=source,
            source_label=item.get("source_label") or ("Web of Science" if source == AgentEvidenceSourceEnum.WOS else "网页搜索"),
            source_name=item.get("source_name"),
            doi=item.get("doi"),
            external_url=item.get("external_url"),
            quote_or_summary=item.get("quote_or_summary") or "",
        )

    def _tokenize(self, text: str) -> list[str]:
        normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower())
        return [token for token in normalized.split() if len(token) >= 2]

    def _score_text(self, tokens: Sequence[str], text: str) -> float:
        haystack = (text or "").lower()
        if not haystack.strip() or not tokens:
            return 0.0
        score = 0.0
        for token in tokens:
            if token in haystack:
                score += 1.0
        return score

    def _truncate(self, text: str, limit: int) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 1].rstrip() + "…"

    async def _query_minimax(
        self,
        *,
        question: str,
        mode: AgentModeEnum,
        researcher: Researcher,
        links: Sequence[ResearcherAdvisor],
        local_evidence: Sequence[AgentLocalEvidenceItem],
        wos_evidence: Sequence[AgentExternalEvidenceItem],
        web_evidence: Sequence[AgentExternalEvidenceItem],
        source_status: AgentSourceStatus,
    ) -> AgentQueryResponse | None:
        if not settings.ENABLE_LLM_FEATURES:
            logger.warning("Agent query fallback: ENABLE_LLM_FEATURES is false; Minimax call skipped.")
            return None
        if not settings.MINIMAX_API_KEY:
            logger.warning("Agent query fallback: MINIMAX_API_KEY is missing; Minimax call skipped.")
            return None

        prompt = self._build_prompt(
            question=question,
            mode=mode,
            researcher=researcher,
            links=links,
            local_evidence=local_evidence,
            wos_evidence=wos_evidence,
            web_evidence=web_evidence,
            source_status=source_status,
        )
        payload = {
            "model": settings.MINIMAX_MODEL,
            "temperature": 0.2,
            "tokens_to_generate": 1400,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a research-task academic assistant for public administration scholars. "
                        "Return strict JSON only. Do not wrap in markdown. "
                        "Use built-in local library and user-uploaded documents as the primary basis, then incorporate Web of Science evidence if available. "
                        "Do not fabricate citations. If evidence is weak, say so clearly."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=settings.MINIMAX_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    settings.MINIMAX_BASE_URL,
                    headers={
                        "Authorization": f"Bearer {settings.MINIMAX_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body_excerpt = exc.response.text[:1000] if exc.response is not None else ""
            logger.exception(
                "Agent query fallback: Minimax HTTP error status=%s body=%s",
                exc.response.status_code if exc.response is not None else "unknown",
                body_excerpt,
            )
            return None
        except Exception:
            logger.exception("Agent query fallback: Minimax request failed before a valid response was received.")
            return None

        data = response.json()
        try:
            content = self._extract_content(data)
            raw = json.loads(self._extract_json_block(content))
        except Exception:
            logger.exception(
                "Agent query fallback: Minimax response parsing failed. Raw response excerpt=%s",
                json.dumps(data, ensure_ascii=False)[:1200],
            )
            return None
        return self._normalize_response(mode, raw, local_evidence, wos_evidence, web_evidence, source_status)

    def _build_prompt(
        self,
        *,
        question: str,
        mode: AgentModeEnum,
        researcher: Researcher,
        links: Sequence[ResearcherAdvisor],
        local_evidence: Sequence[AgentLocalEvidenceItem],
        wos_evidence: Sequence[AgentExternalEvidenceItem],
        web_evidence: Sequence[AgentExternalEvidenceItem],
        source_status: AgentSourceStatus,
    ) -> str:
        advisor_context = [
            {
                "advisor_name": link.advisor.name if link.advisor else link.advisor_id,
                "relationship_type": link.relationship_type,
                "access_level": link.access_level,
                "sub_fields_access": link.sub_fields_access or [],
            }
            for link in links
        ]
        return (
            "Answer the research question using the provided researcher context and evidence.\n"
            f"Mode: {mode.value}\n"
            f"Researcher current_stage: {researcher.current_stage or 'unknown'}\n"
            f"Researcher current_research_question: {researcher.current_research_question or 'not provided'}\n"
            f"Advisor access context: {json.dumps(advisor_context, ensure_ascii=False)}\n"
            f"Question: {question}\n"
            f"Source status: {json.dumps(source_status.model_dump(), ensure_ascii=False)}\n"
            f"Local knowledge evidence: {json.dumps([item.model_dump() for item in local_evidence], ensure_ascii=False)}\n"
            f"Web of Science evidence: {json.dumps([item.model_dump() for item in wos_evidence], ensure_ascii=False)}\n"
            f"Web search evidence: {json.dumps([item.model_dump() for item in web_evidence], ensure_ascii=False)}\n"
            "Return strict JSON with this exact shape:\n"
            "{\n"
            '  "mode": "concept_positioning|literature_review|mechanism_analysis|research_design",\n'
            '  "answer_title": "string",\n'
            '  "direct_answer": "string",\n'
            '  "concept_lineage": ["string"],\n'
            '  "next_steps": ["string"],\n'
            '  "limitations": ["string"]\n'
            "}\n"
            "Rules:\n"
            "- Use local knowledge evidence as the primary source whenever available.\n"
            "- Treat builtin_library and user_upload as different local sources, and respect the evidence source labels.\n"
            "- Use Web of Science as an external academic supplement, not a replacement.\n"
            "- If web search is only a placeholder, acknowledge that in limitations instead of pretending it provided real evidence.\n"
            "- For literature_review mode, concept_lineage should become literature threads.\n"
            "- For mechanism_analysis mode, concept_lineage should become mechanism chain points.\n"
            "- For research_design mode, concept_lineage should become design suggestions.\n"
            "- Return JSON only."
        )

    def _extract_content(self, payload: dict[str, Any]) -> str:
        choices = payload.get("choices") or []
        if not choices:
            raise ValueError("MiniMax response does not contain choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        raise ValueError("MiniMax response content is missing")

    def _extract_json_block(self, text: str) -> str:
        fenced = re.search(r"```json\s*(\{.*\})\s*```", text, flags=re.DOTALL)
        if fenced:
            return fenced.group(1)
        direct = re.search(r"(\{.*\})", text, flags=re.DOTALL)
        if direct:
            return direct.group(1)
        raise ValueError("MiniMax response does not contain JSON")

    def _normalize_response(
        self,
        mode: AgentModeEnum,
        payload: dict[str, Any],
        local_evidence: Sequence[AgentLocalEvidenceItem],
        wos_evidence: Sequence[AgentExternalEvidenceItem],
        web_evidence: Sequence[AgentExternalEvidenceItem],
        source_status: AgentSourceStatus,
    ) -> AgentQueryResponse:
        concept_lineage = self._normalize_string_list(payload.get("concept_lineage"), 6)
        next_steps = self._normalize_string_list(payload.get("next_steps"), 6)
        limitations = self._normalize_string_list(payload.get("limitations"), 6)

        answer_title = self._clean_text(payload.get("answer_title")) or self._default_title(mode)
        direct_answer = self._clean_text(payload.get("direct_answer")) or "当前已基于可用本地证据与外部补充生成初步结构化回答。"

        if source_status.wos in {"error", "empty"} and not any("Web of Science" in item for item in limitations):
            limitations.append("Web of Science 本轮未提供稳定可用的外部学术证据，当前回答仍以内置文献库和用户上传文献为主。")
        if source_status.web == "placeholder":
            limitations.append("网页搜索当前仍为占位能力，本轮回答未使用真实网页检索结果。")
        if not local_evidence:
            limitations.append("当前选中的本地来源范围内证据较弱，回答更多依赖外部补充。")
        if not limitations:
            limitations = ["当前回答仍受限于本地文献规模与外部检索返回质量。"]

        if not next_steps:
            next_steps = ["补充更多与当前研究问题直接相关的内置文献或个人上传文献后再继续追问。"]

        return AgentQueryResponse(
            mode=mode,
            answer_title=answer_title,
            direct_answer=direct_answer,
            concept_lineage=concept_lineage,
            local_evidence=list(local_evidence),
            wos_evidence=list(wos_evidence),
            web_evidence=list(web_evidence),
            source_status=source_status,
            next_steps=next_steps,
            limitations=limitations,
        )

    def _normalize_string_list(self, value: Any, limit: int) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for entry in value:
            cleaned = self._clean_text(entry)
            if cleaned and cleaned not in items:
                items.append(cleaned)
            if len(items) >= limit:
                break
        return items

    def _clean_text(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = re.sub(r"\s+", " ", value).strip()
        return cleaned or None

    def _default_title(self, mode: AgentModeEnum) -> str:
        mapping = {
            AgentModeEnum.CONCEPT_POSITIONING: "概念定位回答",
            AgentModeEnum.LITERATURE_REVIEW: "文献综述回答",
            AgentModeEnum.MECHANISM_ANALYSIS: "机制分析回答",
            AgentModeEnum.RESEARCH_DESIGN: "研究设计回答",
        }
        return mapping[mode]

    def _build_insufficient_response(
        self,
        *,
        mode: AgentModeEnum,
        message: str,
        source_status: AgentSourceStatus | None = None,
    ) -> AgentQueryResponse:
        return AgentQueryResponse(
            mode=mode,
            answer_title=self._default_title(mode),
            direct_answer=message,
            concept_lineage=[],
            local_evidence=[],
            wos_evidence=[],
            web_evidence=[],
            source_status=source_status or AgentSourceStatus(local="empty", wos="disabled", web="disabled"),
            next_steps=["补充内置文献、上传个人文献，或扩大来源范围后重新提问。"],
            limitations=["当前启用的知识来源不足，无法生成高可信度回答。"],
        )

    def _build_fallback_response(
        self,
        *,
        mode: AgentModeEnum,
        local_evidence: Sequence[AgentLocalEvidenceItem],
        wos_evidence: Sequence[AgentExternalEvidenceItem],
        web_evidence: Sequence[AgentExternalEvidenceItem],
        source_status: AgentSourceStatus,
    ) -> AgentQueryResponse:
        return AgentQueryResponse(
            mode=mode,
            answer_title=self._default_title(mode),
            direct_answer="已检索当前启用的本地文献与外部证据，但模型服务暂时不可用。下面先返回最相关的证据，供继续研判。",
            concept_lineage=[
                "当前回答退回到证据摘要模式。",
                "可先根据内置文献、个人上传文献与 WoS 证据梳理论文中的概念界定、文献脉络或研究设计线索。",
            ],
            local_evidence=list(local_evidence),
            wos_evidence=list(wos_evidence),
            web_evidence=list(web_evidence),
            source_status=source_status,
            next_steps=["稍后重试真实问答。", "如本地证据不足，可继续导入内置文献或上传个人文献。"],
            limitations=["当前未能成功调用 Minimax 模型，结构化回答为降级结果。"],
        )


agent_service = AgentService()



