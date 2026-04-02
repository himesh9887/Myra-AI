from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ParsedTask(BaseModel):
    task_type: str
    title: str
    date_label: str
    start_at: datetime
    end_at: datetime | None = None
    confidence: float = 0.0


class TaskRecord(BaseModel):
    id: str | None = None
    user_id: str
    task_type: str
    title: str
    raw_text: str | None = None
    date_label: str
    start_at: datetime
    end_at: datetime | None = None
    reminder_at: datetime | None = None
    reminder_sent_at: datetime | None = None
    status: str = "scheduled"
    source: str = "api"
    created_at: datetime


class TaskCreateRequest(BaseModel):
    user_id: str
    message: str | None = None
    task_type: str | None = None
    title: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    reminder_minutes_before: int | None = None


class TaskResponse(BaseModel):
    task: TaskRecord
    created: bool


class NotificationRecord(BaseModel):
    id: str | None = None
    user_id: str
    task_id: str
    message: str
    created_at: datetime

