"""Web of Science Starter API search service."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import httpx

from app.config import settings


logger = logging.getLogger(__name__)
WOS_DEBUG_LOG = Path("wos_debug.log")


class WosSearchService:
    timeout_seconds = 15

    async def search(
        self,
        *,
        query: str,
        limit: int = 5,
        page: int = 1,
    ) -> tuple[list[dict[str, Any]], str | None]:
        if not settings.ENABLE_WOS_SEARCH:
            logger.warning("WoS search skipped: ENABLE_WOS_SEARCH=false.")
            return [], "Web of Science 未启用：ENABLE_WOS_SEARCH=false。"
        if not settings.WOS_API_KEY:
            logger.warning("WoS search skipped: WOS_API_KEY is missing.")
            return [], "Web of Science 未配置：缺少 WOS_API_KEY。"

        max_results = max(1, min(limit, 5))
        params = {
            "db": "WOS",
            "q": self._build_topic_query(query),
            "limit": max_results,
            "page": page,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                response = await client.get(
                    f"{settings.WOS_API_URL.rstrip('/')}/documents",
                    headers={
                        "X-ApiKey": settings.WOS_API_KEY,
                        "Accept": "application/json",
                    },
                    params=params,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            body = exc.response.text if exc.response is not None else ""
            logger.exception("WoS search failed with HTTP status=%s body=%s", status, body[:2000])
            self._write_debug_log({"params": params, "status": status, "body": body}, exc)
            return [], f"Web of Science 检索失败：HTTP {status}。"
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError, httpx.TimeoutException) as exc:
            logger.exception("WoS search request failed: %s", exc)
            self._write_debug_log({"params": params}, exc)
            return [], f"Web of Science 检索失败：{type(exc).__name__}: {exc}"
        except Exception as exc:
            logger.exception("WoS search failed unexpectedly: %s", exc)
            self._write_debug_log({"params": params}, exc)
            return [], f"Web of Science 检索失败：{type(exc).__name__}: {exc}"

        try:
            payload = response.json()
        except Exception as exc:
            logger.exception("WoS search response is not valid JSON: %s", exc)
            self._write_debug_log({"params": params, "raw_response": response.text}, exc)
            return [], "Web of Science 返回结果解析失败：响应不是合法 JSON。"

        raw_items = payload.get("hits")
        if not isinstance(raw_items, list) or not raw_items:
            logger.info("WoS search returned no hits. metadata=%s", payload.get("metadata"))
            return [], "Web of Science 未返回可用学术证据。"

        results: list[dict[str, Any]] = []
        for raw in raw_items[:max_results]:
            if not isinstance(raw, dict):
                continue
            item = self._normalize_item(raw)
            if item:
                results.append(item)

        if not results:
            self._write_debug_log({"params": params, "payload": payload}, ValueError("No normalizable WoS hits"))
            return [], "Web of Science 返回结果中没有可展示的学术证据。"
        return results, None

    def _build_topic_query(self, query: str) -> str:
        cleaned = re.sub(r"\s+", " ", query).strip()
        if re.match(r"^[A-Z]{2,5}\s*=", cleaned):
            return cleaned
        escaped = cleaned.replace('"', r'\"')
        return f'TS=("{escaped}")'

    def _normalize_item(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        title = self._clean_text(raw.get("title"))
        if not title:
            return None

        source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
        identifiers = raw.get("identifiers") if isinstance(raw.get("identifiers"), dict) else {}
        links = raw.get("links") if isinstance(raw.get("links"), dict) else {}

        source_name = self._clean_text(source.get("sourceTitle"))
        year = self._extract_year(source.get("publishYear"))
        published_date = self._build_published_date(source)
        authors = self._extract_authors(raw)
        doi = self._clean_text(identifiers.get("doi"))
        times_cited = self._extract_times_cited(raw)
        external_url = self._clean_text(links.get("record"))
        summary = self._extract_summary(raw)

        # TODO: Starter API does not expose a dedicated abstract field in the official Document model.
        # Keep raw hits in wos_debug.log on parse failures so we can refine mappings after seeing live payloads.
        return {
            "title": title,
            "authors": authors,
            "year": year,
            "published_date": published_date,
            "source_label": "Web of Science",
            "source_name": source_name,
            "doi": doi,
            "external_url": external_url,
            "quote_or_summary": summary or "WoS Starter API 本条记录未返回摘要；请点击来源链接查看原始记录。",
            "times_cited": times_cited,
        }

    def _extract_authors(self, raw: dict[str, Any]) -> list[str]:
        names = raw.get("names") if isinstance(raw.get("names"), dict) else {}
        authors = names.get("authors")
        if not isinstance(authors, list):
            return []
        items: list[str] = []
        for author in authors:
            if isinstance(author, str):
                name = self._clean_text(author)
            elif isinstance(author, dict):
                name = self._clean_text(author.get("displayName") or author.get("wosStandard") or author.get("fullName") or author.get("name"))
            else:
                name = None
            if name and name not in items:
                items.append(name)
            if len(items) >= 10:
                break
        return items

    def _extract_times_cited(self, raw: dict[str, Any]) -> int | None:
        citations = raw.get("citations")
        if not isinstance(citations, list):
            return None
        for citation in citations:
            if not isinstance(citation, dict):
                continue
            count = citation.get("count")
            if isinstance(count, int):
                return count
            if isinstance(count, str) and count.isdigit():
                return int(count)
        return None

    def _extract_summary(self, raw: dict[str, Any]) -> str | None:
        summary = self._clean_text(raw.get("abstract") or raw.get("abstractText") or raw.get("snippet"))
        if summary:
            return summary
        keywords = raw.get("keywords") if isinstance(raw.get("keywords"), dict) else {}
        author_keywords = keywords.get("authorKeywords")
        if isinstance(author_keywords, list) and author_keywords:
            joined = ", ".join(str(item) for item in author_keywords if str(item).strip())
            return f"Author keywords: {joined}" if joined else None
        return None

    def _build_published_date(self, source: dict[str, Any]) -> str | None:
        year = self._extract_year(source.get("publishYear"))
        month = self._clean_text(source.get("publishMonth"))
        if year and month:
            return f"{year} {month}"
        return str(year) if year else None

    def _extract_year(self, value: Any) -> int | None:
        if isinstance(value, int) and 1000 <= value <= 9999:
            return value
        if isinstance(value, str):
            match = re.search(r"\d{4}", value)
            if match:
                year = int(match.group(0))
                return year if 1000 <= year <= 9999 else None
        return None

    def _clean_text(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned or None

    def _write_debug_log(self, payload: dict[str, Any], error: Exception) -> None:
        try:
            with WOS_DEBUG_LOG.open("a", encoding="utf-8") as handle:
                handle.write("\n--- WoS search debug ---\n")
                handle.write(f"error: {type(error).__name__}: {error}\n")
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2))
                handle.write("\n")
        except Exception:
            logger.exception("Failed to write WoS debug log.")


wos_search_service = WosSearchService()
