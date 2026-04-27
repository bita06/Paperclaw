import json
import logging
import re
import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.exceptions import raise_bad_request, raise_forbidden, raise_not_found
from app.models import Researcher, ResearcherAdvisor, User
from app.schemas.agent import (
    AgentEvidenceSourceEnum,
    AgentExternalEvidenceItem,
    AgentLocalEvidenceItem,
    AgentModeEnum,
    AgentQueryResponse,
    AgentSourceStatus,
)
from app.services.semantic_search_service import semantic_search_service
from app.services.web_search_service import web_search_service
from app.services.wos_search_service import wos_search_service
from app.services.zep_session_service import zep_session_service


logger = logging.getLogger(__name__)
MINIMAX_DEBUG_LOG = Path("minimax_debug.log")


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
        session_id: str | None,
    ) -> AgentQueryResponse:
        researcher = await self._get_researcher(db, researcher_id)
        links = await self._get_advisor_links(db, researcher.id)
        if advisor_id and advisor_id not in {link.advisor_id for link in links}:
            raise_forbidden("The selected advisor is not available in the current researcher context")

        zep_user_id = current_user.id
        zep_thread_id = session_id or self._default_session_id(current_user.id, researcher.id, advisor_id)
        conversation_history = await zep_session_service.get_recent_messages(
            user_id=zep_user_id,
            thread_id=zep_thread_id,
        )

        source_status = AgentSourceStatus(local="disabled", wos="disabled", web="disabled")

        local_evidence: list[AgentLocalEvidenceItem] = []
        web_evidence: list[AgentExternalEvidenceItem] = []
        wos_evidence: list[AgentExternalEvidenceItem] = []
        local_task = None
        web_task = None
        wos_task = None

        if include_builtin_library or include_user_uploads:
            local_task = asyncio.create_task(
                self._collect_local_evidence(
                    db,
                    current_user=current_user,
                    researcher=researcher,
                    question=question,
                    top_k=top_k,
                    include_builtin_library=include_builtin_library,
                    include_user_uploads=include_user_uploads,
                    collection_slug=collection_slug,
                )
            )
        else:
            source_status.messages.append("当前未启用任何本地文献来源。")

        if use_web_search:
            source_status.web = "processing"
            web_task = asyncio.create_task(web_search_service.search(query=question, limit=5))

        if use_wos_search:
            source_status.wos = "processing"
            wos_task = asyncio.create_task(wos_search_service.search(query=question, limit=5, page=1))

        tasks = [task for task in (local_task, web_task, wos_task) if task is not None]
        task_results = await asyncio.gather(*tasks) if tasks else []
        result_index = 0
        if local_task:
            local_evidence = task_results[result_index]
            result_index += 1
        if web_task:
            web_results, web_note = task_results[result_index]
            result_index += 1
        else:
            web_results, web_note = [], None
        if wos_task:
            wos_results, wos_note = task_results[result_index]
        else:
            wos_results, wos_note = [], None

        if include_builtin_library or include_user_uploads:
            source_status.local = "ok" if local_evidence else "empty"
            if not local_evidence:
                source_status.messages.append("当前选中的本地来源范围内，未检索到与问题直接相关的文献段落。")

        if use_web_search:
            web_evidence = [self._build_external_evidence(item, AgentEvidenceSourceEnum.WEB) for item in web_results[:5]]
            if web_evidence:
                source_status.web = "ok"
            elif web_note and "未启用" in web_note:
                source_status.web = "disabled"
            elif web_note and ("失败" in web_note or "未配置" in web_note):
                source_status.web = "error"
            else:
                source_status.web = "empty"
            if web_note:
                source_status.messages.append(web_note)

        if use_wos_search:
            wos_evidence = [self._build_external_evidence(item, AgentEvidenceSourceEnum.WOS) for item in wos_results[:5]]
            if wos_evidence:
                source_status.wos = "ok"
            elif wos_note and "未启用" in wos_note:
                source_status.wos = "disabled"
            elif wos_note and ("失败" in wos_note or "未配置" in wos_note):
                source_status.wos = "error"
            else:
                source_status.wos = "empty"
            if wos_note:
                source_status.messages.append(wos_note)

        if not local_evidence and not wos_evidence and not web_evidence:
            response = self._build_insufficient_response(
                mode=mode,
                message="当前启用的来源中没有返回足够证据。请先导入系统内置文献库，或再启用外部来源。",
                source_status=source_status,
            )
            await zep_session_service.append_messages(
                user_id=zep_user_id,
                thread_id=zep_thread_id,
                messages=self._build_history_messages(question, response.direct_answer),
            )
            return response

        response = await self._query_minimax(
            question=question,
            mode=mode,
            researcher=researcher,
            links=links,
            conversation_history=conversation_history,
            local_evidence=local_evidence,
            wos_evidence=wos_evidence,
            web_evidence=web_evidence,
            source_status=source_status,
        )
        if response is None:
            response = self._build_fallback_response(
                mode=mode,
                local_evidence=local_evidence,
                wos_evidence=wos_evidence,
                web_evidence=web_evidence,
                source_status=source_status,
            )

        await zep_session_service.append_messages(
            user_id=zep_user_id,
            thread_id=zep_thread_id,
            messages=self._build_history_messages(question, response.direct_answer),
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

    async def _collect_local_evidence(
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
    ) -> list[AgentLocalEvidenceItem]:
        items = await semantic_search_service.search_chunks(
            db,
            current_user=current_user,
            researcher=researcher,
            query=question,
            include_builtin_library=include_builtin_library,
            include_user_uploads=include_user_uploads,
            collection_slug=collection_slug,
            top_k=top_k,
        )
        return [
            AgentLocalEvidenceItem(
                paper_id=item.paper_id,
                title=item.title,
                authors=item.authors,
                year=item.year,
                section_title=item.section_title,
                quote_or_summary=self._truncate(item.chunk_text, 420),
                source=item.source,
                source_label=item.source_label,
                collection_slug=item.collection_slug,
                page_start=item.page_start,
                page_end=item.page_end,
            )
            for item in items
        ]

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
            times_cited=item.get("times_cited"),
            external_url=item.get("external_url"),
            published_date=item.get("published_date"),
            quote_or_summary=item.get("quote_or_summary") or "",
        )

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
        conversation_history: Sequence[dict[str, str]],
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
            conversation_history=conversation_history,
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
                        "Use built-in local library chunk evidence as the primary basis, then incorporate Web of Science and web search evidence if available. "
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
            raw = self._parse_minimax_json(content)
        except Exception as exc:
            self._write_minimax_debug_log(data, exc)
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
        conversation_history: Sequence[dict[str, str]],
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
            f"Recent conversation history: {json.dumps(list(conversation_history), ensure_ascii=False)}\n"
            f"Question: {question}\n"
            f"Source status: {json.dumps(source_status.model_dump(), ensure_ascii=False)}\n"
            f"Local chunk evidence: {json.dumps([item.model_dump() for item in local_evidence], ensure_ascii=False)}\n"
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
            "- Use local chunk evidence as the primary source whenever available.\n"
            "- Quote or paraphrase only what is supported by the evidence list.\n"
            "- If local evidence is insufficient, say so explicitly.\n"
            "- Use Web of Science as an external academic supplement, not a replacement.\n"
            "- Use web search evidence only as supplementary current public web context.\n"
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
        cleaned = text.strip()
        fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            cleaned = fenced.group(1).strip()

        start = cleaned.find("{")
        if start < 0:
            raise ValueError("MiniMax response does not contain JSON")

        end = self._find_matching_json_object_end(cleaned, start)
        if end is None:
            end = cleaned.rfind("}")
        if end > start:
            return cleaned[start : end + 1]
        raise ValueError("MiniMax response does not contain JSON")

    def _find_matching_json_object_end(self, text: str, start: int) -> int | None:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return index
        return None

    def _parse_minimax_json(self, content: str) -> dict[str, Any]:
        json_block = self._extract_json_block(content)
        payload, _ = json.JSONDecoder(strict=False).raw_decode(json_block)
        if not isinstance(payload, dict):
            raise ValueError("MiniMax JSON payload must be an object")
        return payload

    def _write_minimax_debug_log(self, payload: dict[str, Any], error: Exception) -> None:
        try:
            with MINIMAX_DEBUG_LOG.open("a", encoding="utf-8") as handle:
                handle.write("\n--- MiniMax JSON parse failure ---\n")
                handle.write(f"error: {type(error).__name__}: {error}\n")
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
                handle.write("\n")
        except Exception:
            logger.exception("Failed to write MiniMax debug log.")

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
            limitations.append("Web of Science 本轮未提供稳定可用的外部学术证据，当前回答仍以内置文献库为主。")
        if source_status.web == "error":
            limitations.append("网页搜索调用失败，本轮回答未使用真实网页补充证据。")
        elif source_status.web == "empty":
            limitations.append("网页搜索本轮未返回可用补充证据。")
        if not local_evidence:
            limitations.append("当前选中的本地来源范围内证据较弱，回答更多依赖外部补充。")
        if not limitations:
            limitations = ["当前回答仍受限于本地文献规模与外部检索返回质量。"]

        if not next_steps:
            next_steps = ["补充更多与当前研究问题直接相关的内置文献后再继续追问。"]

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

    def _default_session_id(self, user_id: str, researcher_id: str, advisor_id: str | None) -> str:
        return f"paperclaw-{user_id}-{researcher_id}-{advisor_id or 'default'}"

    def _build_history_messages(self, question: str, answer: str) -> list[dict[str, str]]:
        return [
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ]

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
            next_steps=["先导入系统内置文献库，再重新提问。"],
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
                "可先根据内置文献库 chunk 证据与 WoS 证据梳理论文中的概念界定、文献脉络或研究设计线索。",
            ],
            local_evidence=list(local_evidence),
            wos_evidence=list(wos_evidence),
            web_evidence=list(web_evidence),
            source_status=source_status,
            next_steps=["稍后重试真实问答。", "如本地证据不足，可继续导入内置文献库。"],
            limitations=["当前未能成功调用 Minimax 模型，结构化回答为降级结果。"],
        )


agent_service = AgentService()

