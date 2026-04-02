from __future__ import annotations

import asyncio
from collections import defaultdict, deque

from myra.models.memory import MemoryRecord


class ShortTermMemoryStore:
    """Keeps a rolling in-memory window for active sessions."""

    def __init__(self, limit: int = 24) -> None:
        self._limit = limit
        self._sessions: dict[str, deque[MemoryRecord]] = defaultdict(lambda: deque(maxlen=self._limit))
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(user_id: str, session_id: str | None) -> str:
        return f"{user_id}:{session_id or 'default'}"

    async def append(self, record: MemoryRecord) -> None:
        async with self._lock:
            self._sessions[self._key(record.user_id, record.session_id)].append(record)

    async def get_session(self, user_id: str, session_id: str | None) -> list[MemoryRecord]:
        async with self._lock:
            return list(self._sessions[self._key(user_id, session_id)])

    async def get_recent_for_user(self, user_id: str, limit: int = 10) -> list[MemoryRecord]:
        async with self._lock:
            aggregated: list[MemoryRecord] = []
            prefix = f"{user_id}:"
            for key, items in self._sessions.items():
                if key.startswith(prefix):
                    aggregated.extend(list(items))

        aggregated.sort(key=lambda item: item.timestamp, reverse=True)
        return aggregated[:limit]

