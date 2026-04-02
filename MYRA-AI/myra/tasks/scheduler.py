from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from myra.core.config import Settings
from myra.core.database import MongoDatabase
from myra.core.time import ensure_utc, to_zone, utc_now
from myra.models.task import NotificationRecord, ParsedTask, TaskRecord

logger = logging.getLogger(__name__)


class TaskService:
    """Stores tasks and exposes reminder-oriented queries."""

    def __init__(self, db: MongoDatabase, settings: Settings) -> None:
        self._settings = settings
        self._tasks = db.db["tasks"]
        self._notifications = db.db["notifications"]

    async def create_from_parsed(
        self,
        *,
        user_id: str,
        parsed_task: ParsedTask,
        raw_text: str,
        source: str = "chat",
        reminder_minutes_before: int | None = None,
    ) -> tuple[TaskRecord, bool]:
        reminder_minutes = reminder_minutes_before or self._settings.default_reminder_lead_minutes
        start_at = ensure_utc(parsed_task.start_at)
        end_at = ensure_utc(parsed_task.end_at) if parsed_task.end_at else None
        reminder_at = start_at - timedelta(minutes=reminder_minutes)

        existing = await self._tasks.find_one(
            {
                "user_id": user_id,
                "task_type": parsed_task.task_type,
                "title": parsed_task.title,
                "start_at": start_at,
                "status": {"$in": ["scheduled", "in_progress"]},
            }
        )
        if existing:
            return self._to_task(existing), False

        payload: dict[str, Any] = {
            "user_id": user_id,
            "task_type": parsed_task.task_type,
            "title": parsed_task.title,
            "raw_text": raw_text,
            "date_label": parsed_task.date_label,
            "start_at": start_at,
            "end_at": end_at,
            "reminder_at": reminder_at,
            "status": "scheduled",
            "source": source,
            "created_at": utc_now(),
        }
        result = await self._tasks.insert_one(payload)
        payload["_id"] = result.inserted_id
        return self._to_task(payload), True

    async def create_structured(
        self,
        *,
        user_id: str,
        task_type: str,
        title: str,
        start_at,
        end_at=None,
        raw_text: str | None = None,
        reminder_minutes_before: int | None = None,
        source: str = "api",
    ) -> tuple[TaskRecord, bool]:
        parsed = ParsedTask(
            task_type=task_type,
            title=title,
            date_label="structured",
            start_at=start_at,
            end_at=end_at,
            confidence=1.0,
        )
        return await self.create_from_parsed(
            user_id=user_id,
            parsed_task=parsed,
            raw_text=raw_text or title,
            reminder_minutes_before=reminder_minutes_before,
            source=source,
        )

    async def get_upcoming_tasks(self, user_id: str, within_hours: int = 24, limit: int = 5) -> list[TaskRecord]:
        now = utc_now()
        end_window = now + timedelta(hours=within_hours)
        cursor = self._tasks.find(
            {
                "user_id": user_id,
                "status": {"$in": ["scheduled", "in_progress"]},
                "start_at": {"$gte": now, "$lte": end_window},
            }
        ).sort("start_at", 1).limit(limit)
        documents = await cursor.to_list(length=limit)
        return [self._to_task(document) for document in documents]

    async def get_due_reminders(self) -> list[TaskRecord]:
        now = utc_now()
        cursor = self._tasks.find(
            {
                "status": "scheduled",
                "reminder_at": {"$lte": now},
                "$or": [
                    {"reminder_sent_at": {"$exists": False}},
                    {"reminder_sent_at": None},
                ],
            }
        ).sort("reminder_at", 1)
        documents = await cursor.to_list(length=50)
        return [self._to_task(document) for document in documents]

    async def mark_reminder_sent(self, task_id: str) -> None:
        await self._tasks.update_one(
            {"_id": self._parse_object_id(task_id)},
            {"$set": {"reminder_sent_at": utc_now()}},
        )

    async def create_notification(self, task: TaskRecord, message: str) -> NotificationRecord:
        payload = {
            "user_id": task.user_id,
            "task_id": task.id,
            "message": message,
            "created_at": utc_now(),
        }
        result = await self._notifications.insert_one(payload)
        return NotificationRecord(
            id=str(result.inserted_id),
            user_id=task.user_id,
            task_id=task.id or "",
            message=message,
            created_at=payload["created_at"],
        )

    @staticmethod
    def _to_task(document: dict[str, Any]) -> TaskRecord:
        return TaskRecord(
            id=str(document.get("_id")),
            user_id=document["user_id"],
            task_type=document["task_type"],
            title=document["title"],
            raw_text=document.get("raw_text"),
            date_label=document.get("date_label", "unspecified"),
            start_at=document["start_at"],
            end_at=document.get("end_at"),
            reminder_at=document.get("reminder_at"),
            reminder_sent_at=document.get("reminder_sent_at"),
            status=document.get("status", "scheduled"),
            source=document.get("source", "api"),
            created_at=document["created_at"],
        )

    @staticmethod
    def _parse_object_id(value: str):
        from bson import ObjectId

        return ObjectId(value)


class TaskSchedulerService:
    """Background job that turns due tasks into reminder notifications."""

    def __init__(self, task_service: TaskService, settings: Settings) -> None:
        self._task_service = task_service
        self._settings = settings
        self._scheduler = AsyncIOScheduler(timezone=settings.timezone)

    async def start(self) -> None:
        if self._scheduler.running:
            return
        self._scheduler.add_job(
            self.scan_due_tasks,
            "interval",
            seconds=self._settings.reminder_poll_seconds,
            id="myra-task-reminders",
            replace_existing=True,
        )
        self._scheduler.start()

    async def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def scan_due_tasks(self) -> None:
        due_tasks = await self._task_service.get_due_reminders()
        for task in due_tasks:
            message = self._build_reminder_message(task)
            await self._task_service.create_notification(task, message)
            if task.id:
                await self._task_service.mark_reminder_sent(task.id)
            logger.info("Reminder created for user=%s task=%s", task.user_id, task.title)

    def _build_reminder_message(self, task: TaskRecord) -> str:
        local_start = to_zone(task.start_at, self._settings.timezone)
        return (
            f"Reminder: your {task.task_type} \"{task.title}\" starts at "
            f"{local_start.strftime('%I:%M %p')} on {local_start.strftime('%d %b %Y')}."
        )

