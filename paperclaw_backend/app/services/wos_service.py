"""
Web of Science Starter API retrieval service.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class WosService:
    def is_enabled(self) -> bool:
        return bool(settings.WOS_API_KEY)

    async def search_documents(
        self,
        *,
        query: str,
        limit: int = 5,
        page: int = 1,
    ) -> tuple[list[dict[str, Any]], str | None]:
        if not self.is_enabled():
            return [], "Web of Science 未配置，当前仅使用本地知识库回答。"

        params = {
            "db": "WOS",
            "q": query,
            "limit": limit,
            "page": page,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.WOS_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{settings.WOS_BASE_URL.rstrip('/')}/documents",
                    headers={"X-ApiKey": settings.WOS_API_KEY},
                    params=params,
                )
                response.raise_for_status()
        except Exception as error:
            return [], f"Web of Science 检索失败：{error}"

        try:
            payload = response.json()
        except Exception as error:
            return [], f"Web of Science 返回结果解析失败：{error}"

        raw_items = payload.get("hits") or payload.get("documents") or payload.get("records") or []
        results = [item for item in (self._normalize_item(entry) for entry in raw_items) if item]
        if not results:
            return [], "Web of Science 未返回可用学术证据。"
        return results, None

    def _normalize_item(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        title = self._pick_first_text(
            raw.get("title"),
            raw.get("titles"),
            raw.get("documentTitle"),
            raw.get("names", {}).get("title") if isinstance(raw.get("names"), dict) else None,
        )
        if not title:
            return None

        authors = self._extract_authors(raw)
        year = self._extract_year(raw)
        source_name = self._pick_first_text(
            raw.get("source"),
            raw.get("sourceTitle"),
            raw.get("source_name"),
            raw.get("journal"),
        )
        doi = self._extract_doi(raw)
        external_url = self._extract_external_url(raw)
        summary = self._pick_first_text(
            raw.get("snippet"),
            raw.get("summary"),
            raw.get("abstract"),
            raw.get("abstractText"),
            raw.get("description"),
        )

        return {
            "title": title,
            "authors": authors,
            "year": year,
            "source_label": "Web of Science",
            "source_name": source_name,
            "doi": doi,
            "external_url": external_url,
            "quote_or_summary": summary or "WoS 记录未返回摘要片段，请点击外部链接查看原始信息。",
        }

    def _extract_authors(self, raw: dict[str, Any]) -> list[str]:
        authors: list[str] = []
        for candidate in [raw.get("authors"), raw.get("author"), raw.get("names")]:
            if isinstance(candidate, list):
                for item in candidate:
                    if isinstance(item, str) and item.strip() and item.strip() not in authors:
                        authors.append(item.strip())
                    elif isinstance(item, dict):
                        name = self._pick_first_text(item.get("displayName"), item.get("name"), item.get("fullName"))
                        if name and name not in authors:
                            authors.append(name)
            elif isinstance(candidate, dict):
                nested = candidate.get("authors") or candidate.get("author") or candidate.get("items") or []
                if isinstance(nested, list):
                    for item in nested:
                        if isinstance(item, dict):
                            name = self._pick_first_text(item.get("displayName"), item.get("name"), item.get("fullName"))
                            if name and name not in authors:
                                authors.append(name)
        return authors[:10]

    def _extract_year(self, raw: dict[str, Any]) -> int | None:
        for candidate in [
            raw.get("publishYear"),
            raw.get("year"),
            raw.get("publicationYear"),
            raw.get("source", {}).get("publishYear") if isinstance(raw.get("source"), dict) else None,
        ]:
            if isinstance(candidate, int) and 1900 <= candidate <= 2100:
                return candidate
            if isinstance(candidate, str):
                digits = "".join(ch for ch in candidate if ch.isdigit())
                if len(digits) >= 4:
                    year = int(digits[:4])
                    if 1900 <= year <= 2100:
                        return year
        return None

    def _extract_doi(self, raw: dict[str, Any]) -> str | None:
        direct = self._pick_first_text(raw.get("doi"), raw.get("DOI"))
        if direct:
            return direct
        identifiers = raw.get("identifiers") or raw.get("identifier") or []
        if isinstance(identifiers, list):
            for item in identifiers:
                if isinstance(item, dict):
                    kind = str(item.get("type") or item.get("name") or "").lower()
                    if "doi" in kind:
                        value = self._pick_first_text(item.get("value"), item.get("identifier"))
                        if value:
                            return value
        return None

    def _extract_external_url(self, raw: dict[str, Any]) -> str | None:
        links = raw.get("links") or raw.get("link") or []
        if isinstance(links, list):
            for item in links:
                if isinstance(item, dict):
                    value = self._pick_first_text(item.get("url"), item.get("href"), item.get("link"))
                    if value:
                        return value
        return self._pick_first_text(raw.get("url"), raw.get("recordLink"), raw.get("externalUrl"))

    def _pick_first_text(self, *values: Any) -> str | None:
        for value in values:
            if isinstance(value, str):
                cleaned = " ".join(value.split()).strip()
                if cleaned:
                    return cleaned
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        cleaned = " ".join(item.split()).strip()
                        if cleaned:
                            return cleaned
                    elif isinstance(item, dict):
                        cleaned = self._pick_first_text(item.get("value"), item.get("text"), item.get("title"))
                        if cleaned:
                            return cleaned
            if isinstance(value, dict):
                cleaned = self._pick_first_text(value.get("value"), value.get("text"), value.get("title"), value.get("sourceTitle"))
                if cleaned:
                    return cleaned
        return None


wos_service = WosService()
