from __future__ import annotations

from datetime import datetime


class PlannerAI:
    def __init__(self, memory, behavior_engine=None):
        self.memory = memory
        self.behavior_engine = behavior_engine

    def handle(self, command):
        normalized = " ".join(str(command).lower().split())
        triggers = {
            "plan my day",
            "plan today",
            "my schedule",
            "today schedule",
            "what is my schedule",
            "what's my schedule",
            "aaj ka schedule",
            "schedule my day",
        }
        if normalized not in triggers:
            return False, ""
        schedule = self.generate_schedule(force=normalized in {"plan my day", "schedule my day", "plan today"})
        return True, self.format_schedule(schedule)

    def generate_schedule(self, force=False):
        daily = self.memory.daily_memory()
        if daily.get("schedule") and not force:
            return list(daily.get("schedule", []))

        profile = self.memory.profile()
        behavior = self.behavior_engine.summary() if self.behavior_engine else {}
        preferred = str(behavior.get("preferred_study_time", "")).strip().lower() or self._default_block()

        subject = str(daily.get("subject") or profile.get("subject") or "Study").strip()
        study_goal = max(1.0, float(daily.get("study_goal_hours") or profile.get("study_goal_hours") or 3))
        schedule = []

        slots = self._slots_for_block(preferred)
        remaining_minutes = int(study_goal * 60)
        block_index = 0
        while remaining_minutes > 0 and block_index < len(slots):
            duration = min(60, remaining_minutes)
            label = f"{subject} revision" if self._exam_countdown(profile, daily) and self._exam_countdown(profile, daily) <= 7 else f"{subject} study"
            schedule.append(
                {
                    "time": slots[block_index],
                    "title": label if block_index == 0 else f"{subject} focus session",
                    "duration_minutes": duration,
                    "category": "study",
                }
            )
            remaining_minutes -= duration
            block_index += 1

        schedule.append({"time": "12:00", "title": "Break", "duration_minutes": 30, "category": "wellbeing"})
        schedule.append({"time": "15:00", "title": "Coding practice", "duration_minutes": 30, "category": "coding"})

        ordered = sorted(schedule, key=lambda item: item.get("time", "99:99"))
        self.memory.set_daily_schedule(ordered)
        self.memory.set_daily_tasks(
            [
                {
                    "title": item["title"],
                    "category": item.get("category", "general"),
                    "status": "pending",
                    "scheduled_for": item.get("time", ""),
                    "duration_minutes": item.get("duration_minutes", 0),
                }
                for item in ordered
            ]
        )
        return ordered

    def format_schedule(self, schedule=None):
        items = schedule if isinstance(schedule, list) else self.generate_schedule()
        name = self._name()
        if not items:
            return f"{name}, aaj ka schedule abhi blank sa hai... bol to plan bana dete hain."
        lines = [f"Morning {name}... aaj ka schedule ye raha:"]
        for item in items[:5]:
            time_slot = str(item.get("time", "")).strip()
            title = str(item.get("title", "")).strip()
            duration = int(item.get("duration_minutes", 0) or 0)
            if time_slot and duration:
                lines.append(f"{time_slot} - {title} ({duration} min)")
            elif time_slot:
                lines.append(f"{time_slot} - {title}")
            else:
                lines.append(title)
        return " ".join(lines)

    def _slots_for_block(self, block):
        mapping = {
            "morning": ["07:30", "10:00", "17:00"],
            "afternoon": ["10:00", "13:30", "18:30"],
            "evening": ["09:30", "16:00", "19:30"],
            "night": ["10:00", "18:30", "21:00"],
        }
        return mapping.get(block, mapping["afternoon"])

    def _default_block(self):
        hour = datetime.now().hour
        if hour < 12:
            return "morning"
        if hour < 17:
            return "afternoon"
        if hour < 21:
            return "evening"
        return "night"

    def _exam_countdown(self, profile, daily):
        exam_date = str(daily.get("exam_date") or profile.get("exam_date") or "").strip()
        if not exam_date:
            return None
        try:
            target = datetime.fromisoformat(exam_date).date()
        except ValueError:
            return None
        return (target - datetime.now().date()).days

    def _name(self):
        return "Boss"
