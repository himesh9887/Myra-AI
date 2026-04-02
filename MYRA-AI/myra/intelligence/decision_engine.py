from __future__ import annotations

from datetime import datetime

from myra.core.config import Settings
from myra.core.time import to_zone
from myra.models.profile import UserProfile
from myra.models.task import TaskRecord


class DecisionEngine:
    """Generates helpful suggestions from tasks, timing, and user profile."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def generate_suggestions(
        self,
        *,
        profile: UserProfile,
        upcoming_tasks: list[TaskRecord],
        current_time: datetime,
    ) -> list[str]:
        suggestions: list[str] = []
        local_now = to_zone(current_time, self._settings.timezone)

        if upcoming_tasks:
            next_task = upcoming_tasks[0]
            next_start = to_zone(next_task.start_at, self._settings.timezone)
            hours_left = max((next_start - local_now).total_seconds() / 3600, 0)

            if next_task.task_type == "exam":
                if hours_left <= 6:
                    suggestions.append("You should revise important topics now and keep your essentials ready.")
                else:
                    suggestions.append("You should plan one focused revision session before your exam.")
            elif next_task.task_type == "meeting":
                suggestions.append("You should review the agenda and key points before the meeting starts.")
            elif next_task.task_type == "assignment":
                suggestions.append("You should break the assignment into smaller chunks and start with the hardest part.")

        if local_now.hour >= 23:
            suggestions.append("You should sleep early for better productivity tomorrow.")
        elif 5 <= local_now.hour <= 8:
            suggestions.append("A short morning planning session could make the day feel lighter.")

        if profile.goals:
            suggestions.append(f"Keep moving toward your goal: {profile.goals[0]}.")
        elif profile.preferences:
            suggestions.append(f"You usually enjoy {profile.preferences[0]}, so we can use that to keep you motivated.")

        unique: list[str] = []
        for item in suggestions:
            if item not in unique:
                unique.append(item)
        return unique[:3]

