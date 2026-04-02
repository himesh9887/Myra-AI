from __future__ import annotations

from pydantic import BaseModel, Field

from myra.models.memory import MemoryRecord
from myra.models.profile import UserProfile
from myra.models.task import ParsedTask, TaskRecord


class ChatRequest(BaseModel):
    user_id: str
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    intent: str
    profile: UserProfile
    extracted_task: ParsedTask | None = None
    saved_task: TaskRecord | None = None
    task_created: bool = False
    relevant_memories: list[MemoryRecord] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)

