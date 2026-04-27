"""Tavily-backed web search service."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


class WebSearchService:
    timeout_seconds = 10

    async def search(
        self,
        *,
        query: str,
        limit: int = 5,
    ) -> tuple[list[dict[str, Any]], str | None]:
        if not settings.ENABLE_WEB_SEARCH:
            logger.warning("Tavily web search skipped: ENABLE_WEB_SEARCH=false.")
            return [], "网页搜索未启用：ENABLE_WEB_SEARCH=false。"
        if not settings.TAVILY_API_KEY:
            logger.warning("Tavily web search skipped: TAVILY_API_KEY is missing.")
            return [], "网页搜索未配置：缺少 TAVILY_API_KEY。"

        max_results = max(1, min(limit, 5))
        payload = {
            "query": query,
            "search_depth": "basic",
            "include_answer": False,
            "include_raw_content": False,
            "max_results": max_results,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False) as client:
                response = await client.post(
                    settings.TAVILY_SEARCH_URL,
                    headers={
                        "Authorization": f"Bearer {settings.TAVILY_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            body_excerpt = exc.response.text[:1000] if exc.response is not None else ""
            logger.exception(
                "Tavily web search failed with HTTP status=%s body=%s",
                exc.response.status_code if exc.response is not None else "unknown",
                body_excerpt,
            )
            return [], f"网页搜索失败：Tavily HTTP {exc.response.status_code if exc.response is not None else 'unknown'}。"
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError, httpx.TimeoutException) as exc:
            logger.exception("Tavily web search request failed: %s", exc)
            return [], f"网页搜索失败：{type(exc).__name__}: {exc}"
        except Exception as exc:
            logger.exception("Tavily web search failed unexpectedly: %s", exc)
            return [], f"网页搜索失败：{type(exc).__name__}: {exc}"

        try:
            data = response.json()
        except Exception as exc:
            logger.exception("Tavily web search response is not valid JSON: %s", exc)
            return [], "网页搜索失败：Tavily 返回了无法解析的 JSON。"

        results = data.get("results")
        if not isinstance(results, list) or not results:
            return [], "网页搜索未返回相关结果。"

        items: list[dict[str, Any]] = []
        for result in results[:max_results]:
            if not isinstance(result, dict):
                continue
            title = self._clean_text(result.get("title")) or "未命名网页"
            url = self._clean_text(result.get("url"))
            summary = self._clean_text(result.get("content")) or self._clean_text(result.get("raw_content")) or ""
            published_date = self._clean_text(result.get("published_date"))
            if not url and not summary:
                continue
            items.append(
                {
                    "title": title,
                    "authors": [],
                    "year": self._extract_year(published_date),
                    "source_label": "网页搜索",
                    "source_name": self._source_name_from_url(url),
                    "doi": None,
                    "external_url": url,
                    "quote_or_summary": summary,
                    "published_date": published_date,
                }
            )

        if not items:
            return [], "网页搜索未返回可展示的结果。"
        return items, None

    def _clean_text(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        cleaned = " ".join(value.split()).strip()
        return cleaned or None

    def _extract_year(self, published_date: str | None) -> int | None:
        if not published_date or len(published_date) < 4:
            return None
        try:
            year = int(published_date[:4])
        except ValueError:
            return None
        return year if 1000 <= year <= 9999 else None

    def _source_name_from_url(self, url: str | None) -> str | None:
        if not url:
            return None
        without_scheme = url.split("://", 1)[-1]
        host = without_scheme.split("/", 1)[0]
        return host or None


web_search_service = WebSearchService()
