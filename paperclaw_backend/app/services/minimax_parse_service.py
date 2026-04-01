"""
MiniMax-backed document parse enhancement.
"""
import json
import re
from typing import Any

import httpx

from app.config import settings


class MiniMaxParseService:
    def is_enabled(self) -> bool:
        return bool(settings.ENABLE_LLM_FEATURES and settings.MINIMAX_API_KEY)

    async def enhance_document_parse(
        self,
        *,
        file_type: str,
        filename: str,
        full_text: str,
        heuristic_metadata: dict[str, Any],
        heuristic_section_titles: list[str],
    ) -> dict[str, Any] | None:
        if not self.is_enabled():
            return None

        excerpt = full_text[:24000]
        payload = {
            "model": settings.MINIMAX_MODEL,
            "temperature": 0.1,
            "tokens_to_generate": 1200,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract academic paper metadata and section titles. "
                        "Return strict JSON only. Do not wrap in markdown. "
                        "If a field cannot be determined reliably, use null or an empty list."
                    ),
                },
                {
                    "role": "user",
                    "content": self._build_prompt(
                        file_type=file_type,
                        filename=filename,
                        heuristic_metadata=heuristic_metadata,
                        heuristic_section_titles=heuristic_section_titles,
                        excerpt=excerpt,
                    ),
                },
            ],
        }

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

        data = response.json()
        content = self._extract_content(data)
        parsed = json.loads(self._extract_json_block(content))
        return self._normalize_payload(parsed)

    def _build_prompt(
        self,
        *,
        file_type: str,
        filename: str,
        heuristic_metadata: dict[str, Any],
        heuristic_section_titles: list[str],
        excerpt: str,
    ) -> str:
        return (
            "Extract academic paper metadata and section titles from the following document excerpt.\n"
            "File type: " + file_type + "\n"
            "Filename: " + filename + "\n"
            "Heuristic metadata: " + json.dumps(heuristic_metadata, ensure_ascii=False) + "\n"
            "Heuristic section titles: " + json.dumps(heuristic_section_titles, ensure_ascii=False) + "\n"
            "Return JSON with this exact shape:\n"
            "{\n"
            '  "metadata": {"title": string|null, "authors": string[], "year": number|null, "abstract": string|null, "keywords": string[]},\n'
            '  "section_titles": string[]\n'
            "}\n"
            "Rules:\n"
            "- Prefer information directly supported by the text.\n"
            "- Keep authors as clean person names only.\n"
            "- section_titles should be ordered as they appear in the paper.\n"
            "- Do not invent a year, abstract, or keywords if unsupported.\n"
            "- Return JSON only.\n\n"
            "Document excerpt:\n"
            f"{excerpt}"
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

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = payload.get("metadata") or {}
        title = self._clean_optional_text(metadata.get("title"))
        abstract = self._clean_optional_text(metadata.get("abstract"), limit=4000)
        authors = self._normalize_text_list(metadata.get("authors"), limit=10)
        keywords = self._normalize_text_list(metadata.get("keywords"), limit=12)
        year = self._normalize_year(metadata.get("year"))
        section_titles = self._normalize_text_list(payload.get("section_titles"), limit=30)
        return {
            "metadata": {
                "title": title,
                "authors": authors,
                "year": year,
                "abstract": abstract,
                "keywords": keywords,
            },
            "section_titles": section_titles,
        }

    def _clean_optional_text(self, value: Any, *, limit: int = 3000) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = re.sub(r"\s+", " ", value).strip()
        return cleaned[:limit] if cleaned else None

    def _normalize_text_list(self, value: Any, *, limit: int) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for entry in value:
            cleaned = self._clean_optional_text(entry, limit=120)
            if cleaned and cleaned not in items:
                items.append(cleaned)
            if len(items) >= limit:
                break
        return items

    def _normalize_year(self, value: Any) -> int | None:
        if isinstance(value, int) and 1900 <= value <= 2100:
            return value
        if isinstance(value, str):
            match = re.search(r"(19|20)\d{2}", value)
            if match:
                year = int(match.group(0))
                if 1900 <= year <= 2100:
                    return year
        return None


minimax_parse_service = MiniMaxParseService()
