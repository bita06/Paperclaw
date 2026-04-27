"""MiniMax embedding service for vector indexing and semantic retrieval."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

import httpx

from app.config import settings


logger = logging.getLogger(__name__)
EmbeddingPurpose = Literal["query", "db"]


class EmbeddingService:
    """Thin MiniMax embedding wrapper using the project's existing API key."""

    max_retries = 3

    def is_enabled(self) -> bool:
        return bool(settings.MINIMAX_API_KEY)

    async def embed_text(self, text: str | None, *, purpose: EmbeddingPurpose = "query") -> list[float] | None:
        if not text or not text.strip():
            return None
        if not self.is_enabled():
            logger.warning("Embedding skipped: MINIMAX_API_KEY is missing.")
            return None

        payload = {
            "model": settings.MINIMAX_EMBEDDING_MODEL,
            "texts": [text],
            "type": purpose,
        }

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.MINIMAX_TIMEOUT_SECONDS, trust_env=False) as client:
                    response = await client.post(
                        settings.MINIMAX_EMBEDDING_URL,
                        headers={
                            "Authorization": f"Bearer {settings.MINIMAX_API_KEY}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
                    response.raise_for_status()

                response_payload = response.json()
                self._raise_on_business_error(response_payload)
                return self._extract_embedding(response_payload)
            except httpx.HTTPStatusError as exc:
                body_excerpt = exc.response.text[:1000] if exc.response is not None else ""
                logger.exception(
                    "MiniMax embedding request failed with HTTP status=%s body=%s",
                    exc.response.status_code if exc.response is not None else "unknown",
                    body_excerpt,
                )
                return None
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError) as exc:
                last_error = exc
                logger.warning(
                    "MiniMax embedding transient error on attempt %s/%s: %s",
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    await asyncio.sleep(1.2 * attempt)
                    continue
                logger.exception("MiniMax embedding request failed after retries.")
                return None
            except Exception as exc:
                last_error = exc
                logger.exception(
                    "MiniMax embedding response parsing failed. Raw response excerpt=%s",
                    response.text[:1200] if 'response' in locals() else '',
                )
                return None

        if last_error is not None:
            logger.exception("MiniMax embedding failed with unexpected terminal error: %s", last_error)
        return None

    def _raise_on_business_error(self, payload: dict[str, Any]) -> None:
        base_resp = payload.get("base_resp")
        if not isinstance(base_resp, dict):
            return

        status_code = base_resp.get("status_code")
        if status_code in (None, 0):
            return

        status_msg = base_resp.get("status_msg") or "unknown MiniMax embedding error"
        raise ValueError(f"MiniMax embedding business error: code={status_code}, message={status_msg}")

    def _extract_embedding(self, payload: dict[str, Any]) -> list[float]:
        vectors = payload.get("vectors")
        if isinstance(vectors, list) and vectors:
            first = vectors[0]
            if isinstance(first, list):
                return self._normalize_embedding(first)
            if isinstance(first, dict) and isinstance(first.get("embedding"), list):
                return self._normalize_embedding(first["embedding"])

        data = payload.get("data")
        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict) and isinstance(first.get("embedding"), list):
                return self._normalize_embedding(first["embedding"])

        if isinstance(payload.get("embedding"), list):
            return self._normalize_embedding(payload["embedding"])

        raise ValueError("MiniMax embedding response does not contain a supported embedding field")

    def _normalize_embedding(self, embedding: list[Any]) -> list[float]:
        normalized = [float(value) for value in embedding]
        if len(normalized) != settings.EMBEDDING_DIMENSION:
            raise ValueError(
                f"MiniMax embedding dimension mismatch: expected {settings.EMBEDDING_DIMENSION}, got {len(normalized)}"
            )
        return normalized


embedding_service = EmbeddingService()
