"""
Placeholder web search service for future expansion.
"""
from typing import Any


class WebSearchService:
    async def search(
        self,
        *,
        query: str,
        limit: int = 5,
    ) -> tuple[list[dict[str, Any]], str | None]:
        return [
            {
                "title": "网页搜索暂未启用",
                "authors": [],
                "year": None,
                "source_label": "网页搜索",
                "source_name": "占位说明",
                "doi": None,
                "external_url": None,
                "quote_or_summary": "当前版本尚未接通网页搜索能力。本次回答未使用真实网页公开信息，仅对外部搜索选项做了结构化占位。",
            }
        ], "网页搜索能力将在后续版本接入；当前结果为结构化占位说明。"


web_search_service = WebSearchService()
