from __future__ import annotations

from math import sqrt
from typing import Any

from myra.core.config import Settings
from myra.core.database import MongoDatabase
from myra.core.time import utc_now
from myra.models.memory import MemoryRecord
from myra.utils.text import extract_keywords, keyword_overlap_score

try:
    from openai import AsyncOpenAI
except ImportError:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore[assignment]


class LongTermMemoryStore:
    """Persists user memories and retrieves relevant context."""

    def __init__(self, db: MongoDatabase, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._collection = db.db["memories"]
        self._client = None

        if settings.use_embeddings and settings.openai_api_key and AsyncOpenAI is not None:
            self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def store_message(
        self,
        *,
        user_id: str,
        session_id: str | None,
        role: str,
        message: str,
        intent: str,
    ) -> MemoryRecord:
        timestamp = utc_now()
        keywords = extract_keywords(message)
        embedding = await self._embed_text(message)

        payload: dict[str, Any] = {
            "user_id": user_id,
            "session_id": session_id,
            "role": role,
            "message": message,
            "timestamp": timestamp,
            "intent": intent,
            "keywords": keywords,
        }
        if embedding is not None:
            payload["embedding"] = embedding

        result = await self._collection.insert_one(payload)
        return MemoryRecord(
            id=str(result.inserted_id),
            user_id=user_id,
            session_id=session_id,
            role=role,
            message=message,
            timestamp=timestamp,
            intent=intent,
            keywords=keywords,
        )

    async def get_recent(self, user_id: str, limit: int = 10) -> list[MemoryRecord]:
        cursor = self._collection.find({"user_id": user_id}).sort("timestamp", -1).limit(limit)
        documents = await cursor.to_list(length=limit)
        return [self._to_record(document) for document in documents]

    async def retrieve_relevant(self, user_id: str, query: str, limit: int = 5) -> list[MemoryRecord]:
        candidate_limit = max(limit * 8, self._settings.relevance_window)
        cursor = self._collection.find({"user_id": user_id}).sort("timestamp", -1).limit(candidate_limit)
        documents = await cursor.to_list(length=candidate_limit)
        if not documents:
            return []

        query_keywords = extract_keywords(query)
        query_embedding = await self._embed_text(query) if self._client else None
        now = utc_now()
        scored: list[MemoryRecord] = []

        for document in documents:
            record = self._to_record(document)
            score = keyword_overlap_score(query_keywords, record.keywords)

            age_hours = max((now - record.timestamp).total_seconds() / 3600, 0.0)
            score += 0.15 / (1 + age_hours / 12)

            if query_embedding is not None and document.get("embedding"):
                score += self._cosine_similarity(query_embedding, document["embedding"])

            if score > 0:
                record.relevance_score = round(score, 4)
                scored.append(record)

        scored.sort(key=lambda item: ((item.relevance_score or 0.0), item.timestamp), reverse=True)
        return scored[:limit]

    async def _embed_text(self, text: str) -> list[float] | None:
        if self._client is None:
            return None

        try:
            response = await self._client.embeddings.create(
                model=self._settings.openai_embedding_model,
                input=text,
            )
        except Exception:
            return None

        data = getattr(response, "data", None) or []
        if not data:
            return None
        return list(data[0].embedding)

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0

        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = sqrt(sum(a * a for a in left))
        right_norm = sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)

    @staticmethod
    def _to_record(document: dict[str, Any]) -> MemoryRecord:
        return MemoryRecord(
            id=str(document.get("_id")),
            user_id=document["user_id"],
            session_id=document.get("session_id"),
            role=document["role"],
            message=document["message"],
            timestamp=document["timestamp"],
            intent=document.get("intent", "general"),
            keywords=document.get("keywords", []),
        )

