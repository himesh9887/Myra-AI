from __future__ import annotations

from dataclasses import dataclass

from myra.intelligence.decision_engine import DecisionEngine
from myra.memory.long_term import LongTermMemoryStore
from myra.memory.short_term import ShortTermMemoryStore
from myra.services.chat_service import ChatService
from myra.tasks.parser import TaskParser
from myra.tasks.scheduler import TaskSchedulerService, TaskService
from myra.user.profile import UserProfileService


@dataclass
class ServiceContainer:
    short_term: ShortTermMemoryStore
    long_term: LongTermMemoryStore
    profile_service: UserProfileService
    task_parser: TaskParser
    task_service: TaskService
    scheduler: TaskSchedulerService
    decision_engine: DecisionEngine
    chat_service: ChatService

