from __future__ import annotations

from memory.memory_hub import MemoryHub


class MemoryEngine(MemoryHub):
    """Companion memory engine kept as a thin wrapper around MemoryHub."""

    def companion_snapshot(self):
        daily = self.daily_memory()
        return {
            "profile": self.profile(),
            "daily_memory": daily,
            "latest_mood": self.latest_mood(),
            "pending_tasks": self.pending_tasks(),
            "study_goal_hours": daily.get("study_goal_hours", 0),
            "study_progress": daily.get("study_progress", 0),
        }
