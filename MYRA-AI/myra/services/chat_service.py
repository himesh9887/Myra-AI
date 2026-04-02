from __future__ import annotations

import re
from datetime import datetime, timedelta

from myra.core.config import Settings
from myra.core.time import now_in_zone, to_zone
from myra.intelligence.decision_engine import DecisionEngine
from myra.memory.long_term import LongTermMemoryStore
from myra.memory.short_term import ShortTermMemoryStore
from myra.models.chat import ChatRequest, ChatResponse
from myra.models.memory import MemoryRecord
from myra.models.profile import UserProfile
from myra.models.task import ParsedTask, TaskRecord
from myra.tasks.parser import TaskParser
from myra.tasks.scheduler import TaskService
from myra.user.profile import UserProfileService
from myra.utils.text import compact_text


class ChatService:
    """Coordinates memory, personalization, tasks, and suggestions."""

    def __init__(
        self,
        *,
        settings: Settings,
        short_term: ShortTermMemoryStore,
        long_term: LongTermMemoryStore,
        profile_service: UserProfileService,
        task_parser: TaskParser,
        task_service: TaskService,
        decision_engine: DecisionEngine,
    ) -> None:
        self._settings = settings
        self._short_term = short_term
        self._long_term = long_term
        self._profile_service = profile_service
        self._task_parser = task_parser
        self._task_service = task_service
        self._decision_engine = decision_engine

    async def handle_chat(self, request: ChatRequest) -> ChatResponse:
        session_id = request.session_id or "default"
        reference_time = now_in_zone(self._settings.timezone)

        parsed_task = self._task_parser.parse(request.message, reference_time)
        intent = self._infer_intent(request.message, parsed_task)
        profile = await self._profile_service.update_from_message(request.user_id, request.message)
        relevant_memories = await self._long_term.retrieve_relevant(request.user_id, request.message, limit=5)

        saved_task: TaskRecord | None = None
        task_created = False
        if parsed_task is not None:
            saved_task, task_created = await self._task_service.create_from_parsed(
                user_id=request.user_id,
                parsed_task=parsed_task,
                raw_text=request.message,
                source="chat",
            )

        upcoming_tasks = await self._task_service.get_upcoming_tasks(request.user_id, within_hours=24, limit=3)
        suggestions = self._decision_engine.generate_suggestions(
            profile=profile,
            upcoming_tasks=upcoming_tasks,
            current_time=reference_time,
        )

        response_text = self._build_response(
            user_message=request.message,
            profile=profile,
            parsed_task=parsed_task,
            saved_task=saved_task,
            task_created=task_created,
            relevant_memories=relevant_memories,
            upcoming_tasks=upcoming_tasks,
            suggestions=suggestions,
            current_time=reference_time,
        )

        user_record = await self._long_term.store_message(
            user_id=request.user_id,
            session_id=session_id,
            role="user",
            message=request.message,
            intent=intent,
        )
        assistant_record = await self._long_term.store_message(
            user_id=request.user_id,
            session_id=session_id,
            role="assistant",
            message=response_text,
            intent="assistant_response",
        )

        await self._short_term.append(user_record)
        await self._short_term.append(assistant_record)

        return ChatResponse(
            response=response_text,
            intent=intent,
            profile=profile,
            extracted_task=parsed_task,
            saved_task=saved_task,
            task_created=task_created,
            relevant_memories=relevant_memories,
            suggestions=suggestions,
        )

    @staticmethod
    def _infer_intent(message: str, parsed_task: ParsedTask | None) -> str:
        lowered = message.lower()
        if parsed_task is not None:
            return f"task:{parsed_task.task_type}"
        if "my name is" in lowered or "mera naam" in lowered:
            return "profile_update"
        if any(token in lowered for token in ["?", "what", "how", "when", "why"]):
            return "question"
        if re.search(r"\b(hi|hello|hey|namaste)\b", lowered):
            return "greeting"
        return "general"

    def _build_response(
        self,
        *,
        user_message: str,
        profile: UserProfile,
        parsed_task: ParsedTask | None,
        saved_task: TaskRecord | None,
        task_created: bool,
        relevant_memories: list[MemoryRecord],
        upcoming_tasks: list[TaskRecord],
        suggestions: list[str],
        current_time: datetime,
    ) -> str:
        parts: list[str] = []
        name = profile.name
        lowered = user_message.lower().strip()

        if name and ("my name is" in lowered or "mera naam" in lowered):
            parts.append(f"Got it, {name}! I'll remember your name.")
        elif parsed_task and saved_task:
            parts.append(self._task_acknowledgement(name, saved_task, task_created))
        else:
            proactive = self._proactive_task_message(name, upcoming_tasks, current_time)
            if proactive:
                parts.append(proactive)

        if not parts and relevant_memories:
            memory = relevant_memories[0]
            parts.append(f"I remember you mentioned: {compact_text(memory.message)}")

        if not parts:
            if name:
                parts.append(f"{name}, I'm tracking your context and I'm ready to help.")
            else:
                parts.append("I'm tracking your context and I'm ready to help.")

        if suggestions:
            parts.append(suggestions[0])

        return " ".join(parts)

    def _task_acknowledgement(self, name: str | None, task: TaskRecord, created: bool) -> str:
        local_start = to_zone(task.start_at, self._settings.timezone)
        task_when = local_start.strftime("%d %b %Y at %I:%M %p")
        prefix = f"{name}, " if name else ""
        if created:
            return f"{prefix}I've saved your {task.task_type} for {task_when}."
        return f"{prefix}I already have your {task.task_type} for {task_when} in memory."

    def _proactive_task_message(
        self,
        name: str | None,
        upcoming_tasks: list[TaskRecord],
        current_time: datetime,
    ) -> str | None:
        if not upcoming_tasks:
            return None

        next_task = upcoming_tasks[0]
        local_now = to_zone(current_time, self._settings.timezone)
        local_start = to_zone(next_task.start_at, self._settings.timezone)
        time_diff = local_start - local_now
        prefix = f"{name}, " if name else ""

        if time_diff <= timedelta(hours=24):
            if next_task.task_type == "exam":
                if local_start.date() == local_now.date():
                    return f"{prefix}aaj tera exam hai at {local_start.strftime('%I:%M %p')}. Best of luck!"
                return f"{prefix}you have an exam tomorrow at {local_start.strftime('%I:%M %p')}. Let's stay ready."

            return (
                f"{prefix}your next {next_task.task_type} is at {local_start.strftime('%I:%M %p')} "
                f"on {local_start.strftime('%d %b')}."
            )

        return None
