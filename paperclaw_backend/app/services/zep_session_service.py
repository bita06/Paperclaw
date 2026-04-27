"""Zep thread/session wrapper for multi-turn conversation memory."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


class ZepSessionService:
    async def get_recent_messages(self, *, user_id: str, thread_id: str, lastn: int | None = None) -> list[dict[str, str]]:
        if not self.is_enabled():
            return []

        await self._ensure_user(user_id=user_id)
        await self._ensure_thread(user_id=user_id, thread_id=thread_id)

        try:
            async with httpx.AsyncClient(timeout=settings.ZEP_TIMEOUT_SECONDS) as client:
                response = await client.get(
                    f"{settings.ZEP_API_BASE_URL.rstrip('/')}/threads/{thread_id}/messages",
                    headers=self._headers(),
                    params={"lastn": lastn or settings.ZEP_LASTN_MESSAGES},
                )
                response.raise_for_status()
        except Exception:
            logger.exception("Zep memory read failed for thread_id=%s", thread_id)
            return []

        payload = response.json()
        messages = payload.get("messages") or []
        normalized: list[dict[str, str]] = []
        for message in messages:
            role = message.get("role")
            content = message.get("content")
            if isinstance(role, str) and isinstance(content, str) and content.strip():
                normalized.append({"role": role, "content": content.strip()})
        return normalized

    async def append_messages(self, *, user_id: str, thread_id: str, messages: list[dict[str, str]]) -> None:
        if not self.is_enabled() or not messages:
            return

        await self._ensure_user(user_id=user_id)
        await self._ensure_thread(user_id=user_id, thread_id=thread_id)

        try:
            async with httpx.AsyncClient(timeout=settings.ZEP_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{settings.ZEP_API_BASE_URL.rstrip('/')}/threads/{thread_id}/messages",
                    headers=self._headers(),
                    json={
                        "messages": messages,
                        "return_context": False,
                    },
                )
                response.raise_for_status()
        except Exception:
            logger.exception("Zep memory write failed for thread_id=%s", thread_id)

    def is_enabled(self) -> bool:
        return bool(settings.ENABLE_ZEP_MEMORY and settings.ZEP_API_KEY)

    async def _ensure_user(self, *, user_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=settings.ZEP_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{settings.ZEP_API_BASE_URL.rstrip('/')}/users",
                    headers=self._headers(),
                    json={"user_id": user_id},
                )
                if response.status_code not in {200, 201, 409}:
                    response.raise_for_status()
        except Exception:
            logger.exception("Zep ensure_user failed for user_id=%s", user_id)

    async def _ensure_thread(self, *, user_id: str, thread_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=settings.ZEP_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    f"{settings.ZEP_API_BASE_URL.rstrip('/')}/threads",
                    headers=self._headers(),
                    json={"thread_id": thread_id, "user_id": user_id},
                )
                if response.status_code not in {200, 201, 409}:
                    response.raise_for_status()
        except Exception:
            logger.exception("Zep ensure_thread failed for thread_id=%s", thread_id)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.ZEP_API_KEY}",
            "x-api-key": settings.ZEP_API_KEY,
            "Content-Type": "application/json",
        }


zep_session_service = ZepSessionService()
