from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MemoryRecord(BaseModel):
    id: str | None = None
    user_id: str
    session_id: str | None = None
    role: str
    message: str
    timestamp: datetime
    intent: str
    keywords: list[str] = Field(default_factory=list)
    relevance_score: float | None = None


class MemoryResponse(BaseModel):
    user_id: str
    short_term: list[MemoryRecord] = Field(default_factory=list)
    recent: list[MemoryRecord] = Field(default_factory=list)
    relevant: list[MemoryRecord] = Field(default_factory=list)
