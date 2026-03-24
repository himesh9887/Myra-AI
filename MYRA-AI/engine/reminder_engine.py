from __future__ import annotations

import re
from datetime import date, datetime, timedelta


class ReminderEngine:
    def __init__(self, memory, behavior_engine=None):
        self.memory = memory
        self.behavior_engine = behavior_engine

    def handle(self, command):
        raw = " ".join(str(command).strip().split())
        normalized = raw.lower()
        if not normalized:
            return False, ""

        feedback_message = self._capture_exam_feedback(raw, normalized)
        if feedback_message:
            return True, feedback_message

        exam_event = self._extract_exam_event(raw, normalized)
        if exam_event:
            self.memory.set_exam_event(
                exam_date=exam_event["exam_date"],
                start_time=exam_event["start_time"],
                end_time=exam_event["end_time"],
            )
            return True, (
                f"Boss, noted. {exam_event['exam_date']} ko tera exam "
                f"{exam_event['start_time']} se {exam_event['end_time']} tak yaad rahega."
            )

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
        exam_message = self._exam_proactive_message(context=context, daily=daily)
        if exam_message:
            return exam_message

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

    def _capture_exam_feedback(self, raw, normalized):
        daily = self.memory.daily_memory()
        if not daily.get("awaiting_exam_feedback"):
            return ""
        if self._looks_like_action_command(normalized):
            return ""
        if len(normalized.split()) > 40:
            return ""
        if self.memory.save_exam_feedback(raw):
            return "Acha Boss... exam feedback bhi yaad rakh liya. Hope theek gaya hoga."
        return ""

    def _extract_exam_event(self, raw, normalized):
        if "exam" not in normalized:
            return {}

        time_match = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*(?:to|-|se)\s*(\d{1,2})(?::(\d{2}))?\b",
            normalized,
            re.IGNORECASE,
        )
        if not time_match:
            return {}

        exam_date = self._resolve_relative_date(normalized)
        if not exam_date:
            return {}

        start_time, end_time = self._normalize_time_range(
            time_match.group(1),
            time_match.group(2),
            time_match.group(3),
            time_match.group(4),
        )
        if not start_time or not end_time:
            return {}

        return {
            "exam_date": exam_date,
            "start_time": start_time,
            "end_time": end_time,
        }

    def _resolve_relative_date(self, normalized):
        today = date.today()
        if "tomorrow" in normalized or "kal" in normalized:
            return str(today + timedelta(days=1))
        if "today" in normalized or "aaj" in normalized:
            return str(today)
        iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", normalized)
        if iso_match:
            return iso_match.group(1)
        return ""

    def _normalize_time_range(self, start_hour, start_minute, end_hour, end_minute):
        try:
            start_hh = int(start_hour)
            start_mm = int(start_minute or 0)
            end_hh = int(end_hour)
            end_mm = int(end_minute or 0)
        except (TypeError, ValueError):
            return "", ""

        if 1 <= end_hh < start_hh <= 12:
            end_hh += 12

        if not (0 <= start_hh <= 23 and 0 <= start_mm <= 59):
            return "", ""
        if not (0 <= end_hh <= 23 and 0 <= end_mm <= 59):
            return "", ""

        return f"{start_hh:02d}:{start_mm:02d}", f"{end_hh:02d}:{end_mm:02d}"

    def _exam_proactive_message(self, context=None, daily=None):
        context = context or {}
        daily = daily or context.get("daily_memory") or self.memory.daily_memory()
        exam_date = str(daily.get("exam_date") or context.get("exam_date") or "").strip()
        subject = str(daily.get("subject") or context.get("subject") or "exam").strip()
        subject_label = f"{subject} " if subject and subject.lower() != "exam" else ""
        exam_start = str(daily.get("exam_start") or "").strip()
        exam_end = str(daily.get("exam_end") or "").strip()
        exam_feedback = str(daily.get("exam_feedback") or "").strip()
        if not exam_date:
            return ""

        now = datetime.now()
        today_key = str(now.date())
        if exam_date != today_key:
            return ""

        if exam_start and exam_end:
            start_dt = self._combine_today(exam_start)
            end_dt = self._combine_today(exam_end)
            if start_dt and end_dt:
                if now < start_dt:
                    return f"Boss yaad hai na... aaj {exam_start} se {exam_end} tera {subject_label}exam hai."
                if start_dt <= now <= end_dt:
                    return "Boss abhi tera exam chal raha hoga... focus kar."
                if now > end_dt and not exam_feedback:
                    self.memory.update_daily_memory({"awaiting_exam_feedback": True}, target_day=today_key)
                    return "Boss exam ho gaya? kaisa gaya?"

        if not exam_feedback:
            return f"Boss yaad hai na... aaj tera {subject_label}exam hai."
        return ""

    def _combine_today(self, time_text):
        try:
            parsed = datetime.strptime(time_text, "%H:%M").time()
        except ValueError:
            return None
        return datetime.combine(date.today(), parsed)

    def _looks_like_action_command(self, normalized):
        return bool(
            re.match(
                r"^(open|close|launch|start|run|play|search|find|google|download|send|call|set|increase|decrease|mute|restart|shutdown|lock|plan|schedule|remind)\b",
                normalized,
            )
        )
