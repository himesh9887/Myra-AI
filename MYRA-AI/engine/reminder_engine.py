from __future__ import annotations

import re
from datetime import datetime


class ReminderEngine:
    def __init__(self, memory, behavior_engine=None):
        self.memory = memory
        self.behavior_engine = behavior_engine

    def handle(self, command):
        raw = " ".join(str(command).strip().split())
        normalized = raw.lower()
        if not normalized:
            return False, ""

        remind_match = re.search(r"(?:remind me to|add reminder)\s+(.+)", raw, re.IGNORECASE)
        if remind_match:
            text = remind_match.group(1).strip().strip(".")
            if not text:
                return True, "Reminder text thoda unclear hai."
            self.memory.add_reminder(text)
            self.memory.add_daily_task(text, category="reminder")
            return True, f"Thik hai, maine '{text}' yaad rakh liya."

        task_match = re.search(r"(?:add task|add todo)\s+(.+)", raw, re.IGNORECASE)
        if task_match:
            text = task_match.group(1).strip().strip(".")
            if not text:
                return True, "Task text clear nahi mila."
            self.memory.add_daily_task(text)
            return True, f"{text} ko aaj ke task list me daal diya."

        goal_match = re.search(r"(?:set study goal to|study goal is)\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?)", normalized)
        if goal_match:
            hours = float(goal_match.group(1))
            self.memory.set_study_goal(hours)
            return True, f"Aaj ka study goal {hours:g} hours set kar diya."

        studied_match = re.search(r"(?:i studied for|i studied|study progress is)\s+(\d+(?:\.\d+)?)\s*(hours?|hrs?|minutes?|mins?)", normalized)
        if studied_match:
            value = float(studied_match.group(1))
            unit = studied_match.group(2)
            hours = round(value / 60, 2) if unit.startswith("min") else value
            self.memory.log_study_progress(hours)
            if self.behavior_engine:
                self.behavior_engine.record_study_progress(hours)
            daily = self.memory.daily_memory()
            return True, f"Nice. Aaj ka study progress ab {daily.get('study_progress', 0):g} hours hai."

        progress_queries = {
            "study progress",
            "how much did i study",
            "how much have i studied",
            "my progress",
        }
        if normalized in progress_queries:
            daily = self.memory.daily_memory()
            return True, (
                f"Aaj tumne {daily.get('study_progress', 0):g} out of "
                f"{daily.get('study_goal_hours', 0):g} study hours complete kiye hain."
            )

        pending_queries = {
            "show reminders",
            "show tasks",
            "what's pending today",
            "what is pending today",
            "pending tasks",
        }
        if normalized in pending_queries:
            return True, self.pending_summary()

        done_match = re.search(r"(?:mark|complete|done)\s+(.+)", raw, re.IGNORECASE)
        if done_match:
            text = done_match.group(1).strip().strip(".")
            if self.memory.mark_task_status(text):
                return True, f"{text} ko completed mark kar diya."
            return True, f"Mujhe '{text}' naam ka task nahi mila."

        return False, ""

    def pending_summary(self):
        tasks = self.memory.pending_tasks(limit=5)
        reminders = self.memory.due_today()
        if not tasks and not reminders:
            return "Aaj ke pending tasks clear lag rahe hain."
        items = [item.get("title", "") for item in tasks if item.get("title")]
        items.extend(item.get("text", "") for item in reminders if item.get("text"))
        preview = ", ".join(items[:5])
        return f"Aaj ye pending hai: {preview}"

    def proactive_prompt(self, context=None, snapshot=None):
        context = context or {}
        daily = context.get("daily_memory") or self.memory.daily_memory()
        name = self._name(context)
        pending_tasks = self.memory.pending_tasks(limit=5)

        progress = float(daily.get("study_progress", 0) or 0)
        goal = float(daily.get("study_goal_hours", 0) or 0)
        hour = datetime.now().hour
        if goal > progress and hour >= 18:
            remaining = round(goal - progress, 1)
            return f"{name}, aaj ke study goal me abhi {remaining:g} hour baaki hai... kya 25 minute ka focus sprint maar dein?"

        for item in pending_tasks:
            title = str(item.get("title", "")).strip()
            category = str(item.get("category", "")).strip().lower()
            if category == "coding":
                return f"{name}, aaj coding practice abhi hui nahi lag rahi... kya 20 minute ka session start karu?"
            if title:
                break

        reminder = next((item for item in self.memory.due_today() if item.get("text")), None)
        if reminder:
            return f"{name}, ek chhota reminder hai... {reminder.get('text')}."
        return ""

    def _name(self, context):
        return "Boss"
