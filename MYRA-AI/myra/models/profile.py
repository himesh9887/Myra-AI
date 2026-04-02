from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    user_id: str
    name: str | None = None
    preferences: list[str] = Field(default_factory=list)
    habits: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    facts: dict[str, str] = Field(default_factory=dict)
    updated_at: datetime | None = None

