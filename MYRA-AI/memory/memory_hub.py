from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path


class MemoryHub:
    def __init__(self, storage_root):
        root = Path(storage_root)
        self.storage_dir = root if root.suffix.lower() != ".json" else root.parent
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.profile_path = self.storage_dir / "user_profile.json"
        self.conversation_path = self.storage_dir / "conversation_memory.json"
        self.usage_path = self.storage_dir / "usage_stats.json"
        self.task_history_path = self.storage_dir / "task_history.json"
        self.daily_memory_path = self.storage_dir / "daily_memory.json"
        self.mood_history_path = self.storage_dir / "mood_history.json"
        self.emotion_history_path = self.storage_dir / "emotion_history.json"
        self.snapshot_path = self.storage_dir / "myra_memory.json"

        self.profile_data = self._merge(self._default_profile(), self._load_json(self.profile_path, {}))
        self.conversation_data = self._load_list(self.conversation_path)
        self.usage_data = self._merge_usage(self._default_usage(), self._load_json(self.usage_path, {}))
        self.task_data = self._load_list(self.task_history_path)
        self.daily_data = self._merge_daily_store(self._default_daily_store(), self._load_json(self.daily_memory_path, {}))
        self.mood_data = self._load_mood_history()
        self.emotion_history_data = self._load_emotion_history()

        self._sync_favorite_app()
        self._ensure_today_entry()
        self._sync_behavior_profile()
        self._flush_all()

    def set_user_name(self, name):
        cleaned = str(name).strip()
        if not cleaned:
            return False
        self.profile_data["user_name"] = cleaned
        self.profile_data["name"] = cleaned
        self._save_profile()
        return True

    def user_name(self):
        return self.profile_data.get("name") or self.profile_data.get("user_name") or "Boss"

    def set_profile(self, profile):
        if not isinstance(profile, dict):
            return False

        defaults = self._default_profile()
        for key in defaults:
            if key not in profile:
                continue
            value = profile[key]
            if key in {"interests", "projects", "frequent_apps"}:
                self.profile_data[key] = self._dedupe_list(value)
            elif key in {"facts", "notes", "reminders"}:
                self.profile_data[key] = list(value) if isinstance(value, list) else []
            elif key == "preferences":
                self.profile_data[key] = dict(value) if isinstance(value, dict) else {}
            elif key == "behavior_profile":
                self.profile_data[key] = self._merge_behavior_profile(self._default_behavior_profile(), value)
            elif key == "conversation_history":
                self.conversation_data = list(value) if isinstance(value, list) else []
            elif key in {"study_goal_hours", "study_progress"}:
                self.profile_data[key] = self._coerce_hours(value, defaults[key])
            else:
                self.profile_data[key] = value

        if self.profile_data.get("name") and not self.profile_data.get("user_name"):
            self.profile_data["user_name"] = self.profile_data["name"]
        if self.profile_data.get("user_name") and not self.profile_data.get("name"):
            self.profile_data["name"] = self.profile_data["user_name"]

        self._sync_favorite_app()
        self._ensure_today_entry()
        self._sync_behavior_profile()
        self._flush_all()
        return True

    def profile(self):
        payload = dict(self.profile_data)
        payload["conversation_history"] = list(self.conversation_data[-50:])
        payload["study_progress"] = self.daily_memory().get("study_progress", payload.get("study_progress", 0))
        payload["study_goal_hours"] = self.daily_memory().get("study_goal_hours", payload.get("study_goal_hours", 0))
        payload["latest_mood"] = self.latest_mood()
        payload["emotion_history"] = self.emotion_history()
        return payload

    def usage(self):
        return {
            "most_used_apps": dict(self.usage_data.get("most_used_apps", {})),
            "frequent_commands": dict(self.usage_data.get("frequent_commands", {})),
            "user_habits": dict(self.usage_data.get("user_habits", {})),
        }

    def full_memory_snapshot(self):
        return {
            "profile": self.profile(),
            "daily_memory": self.daily_memory(),
            "conversation_history": self.recent_conversations(limit=80),
            "usage": self.usage(),
            "task_history": self.task_history(limit=100),
            "mood_history": self.mood_history(limit=None),
            "emotion_history": self.emotion_history(),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }

    def add_interest(self, interest):
        cleaned = str(interest).strip()
        if not cleaned:
            return False
        interests = self.profile_data.setdefault("interests", [])
        if cleaned.lower() not in [item.lower() for item in interests]:
            interests.append(cleaned)
            self._save_profile()
        return True

    def add_project(self, project):
        cleaned = str(project).strip()
        if not cleaned:
            return False
        projects = self.profile_data.setdefault("projects", [])
        if cleaned.lower() not in [item.lower() for item in projects]:
            projects.append(cleaned)
        self.profile_data["current_project"] = cleaned
        self._save_profile()
        return True

    def set_preference(self, key, value):
        cleaned_key = str(key).strip().lower().replace(" ", "_")
        cleaned_value = str(value).strip()
        if not cleaned_key or not cleaned_value:
            return False
        self.profile_data.setdefault("preferences", {})[cleaned_key] = cleaned_value
        self._save_profile()
        return True

    def add_frequent_app(self, app_name):
        cleaned = self._normalize_token(app_name)
        if not cleaned:
            return False
        apps = self.profile_data.setdefault("frequent_apps", [])
        if cleaned not in [self._normalize_token(item) for item in apps]:
            apps.append(cleaned)
            self._sync_favorite_app()
            self._save_profile()
        return True

    def save_note(self, text):
        cleaned = str(text).strip()
        if not cleaned:
            return False
        self.profile_data.setdefault("notes", []).append({"text": cleaned, "created_on": str(date.today())})
        self._save_profile()
        return True

    def notes(self):
        return list(self.profile_data.get("notes", []))

    def reminders(self):
        return list(self.profile_data.get("reminders", []))

    def remember_fact(self, text):
        cleaned = str(text).strip()
        if not cleaned:
            return False
        facts = self.profile_data.setdefault("facts", [])
        if cleaned.lower() not in [str(item.get("text", "")).lower() for item in facts]:
            facts.append({"text": cleaned, "created_on": str(date.today())})
            self._save_profile()
        return True

    def facts(self):
        return list(self.profile_data.get("facts", []))

    def add_reminder(self, text, due_on=None):
        cleaned = str(text).strip()
        if not cleaned:
            return False
        reminder = {
            "text": cleaned,
            "due_on": due_on or str(date.today()),
            "status": "pending",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.profile_data.setdefault("reminders", []).append(reminder)
        self._save_profile()
        return True

    def set_relationship_status(self, status, note=""):
        cleaned = str(status).strip().lower()
        if not cleaned:
            return False
        self.profile_data["relationship_status"] = cleaned
        if note:
            self.remember_fact(str(note).strip())
        self._save_profile()
        return True

    def set_emotional_state(self, state, note=""):
        cleaned = str(state).strip().lower()
        if not cleaned:
            return False
        self.profile_data["emotional_state"] = cleaned
        self._save_profile()
        if cleaned in {"happy", "excited", "motivated", "sad", "tired", "angry", "bored", "confused", "stressed"}:
            self.log_mood(cleaned, source="memory", note=note)
        return True

    def set_exam_event(self, exam_date=None, start_time="", end_time="", subject=""):
        normalized_date = str(exam_date).strip() if exam_date else ""
        cleaned_subject = str(subject).strip()
        cleaned_start = str(start_time).strip()
        cleaned_end = str(end_time).strip()
        target_day = self.day_key(normalized_date or None)

        if not normalized_date and not cleaned_subject and not cleaned_start and not cleaned_end:
            return False

        if normalized_date:
            self.profile_data["exam_date"] = normalized_date
        if cleaned_subject:
            self.profile_data["subject"] = cleaned_subject

        entry = self.daily_data.setdefault("days", {}).setdefault(target_day, self._default_daily_entry(target_day))
        entry["exam_date"] = normalized_date or entry.get("exam_date") or target_day
        if cleaned_subject:
            entry["subject"] = cleaned_subject
        if cleaned_start:
            entry["exam_start"] = cleaned_start
        if cleaned_end:
            entry["exam_end"] = cleaned_end
        entry.setdefault("exam_feedback", "")
        entry.setdefault("awaiting_exam_feedback", False)
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._save_profile()
        self._save_daily_memory()
        return True

    def save_exam_feedback(self, feedback, target_day=None):
        cleaned = " ".join(str(feedback).strip().split())
        if not cleaned:
            return False
        day = self.day_key(target_day or self.profile_data.get("exam_date") or None)
        entry = self.daily_data.setdefault("days", {}).setdefault(day, self._default_daily_entry(day))
        entry["exam_feedback"] = cleaned
        entry["awaiting_exam_feedback"] = False
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.profile_data["latest_exam_feedback"] = cleaned
        self._save_profile()
        self._save_daily_memory()
        return True

    def due_today(self):
        today = str(date.today())
        reminders = self.profile_data.get("reminders", [])
        return [
            item
            for item in reminders
            if item.get("due_on") == today and str(item.get("status", "pending")).lower() != "completed"
        ]

    def log_conversation(self, user_text, myra_reply=""):
        user_message = str(user_text).strip()
        assistant_message = str(myra_reply).strip()
        if not user_message and not assistant_message:
            return False
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "user": user_message,
            "assistant": assistant_message,
        }
        self.conversation_data.append(entry)
        self.conversation_data = self.conversation_data[-80:]
        self._save_conversations()
        return True

    def recent_conversations(self, limit=10):
        return list(self.conversation_data[-max(1, int(limit)) :])

    def track_command(self, raw_command, category="general"):
        command = " ".join(str(raw_command).strip().split()).lower()
        if not command:
            return False
        commands = self.usage_data.setdefault("frequent_commands", {})
        commands[command] = int(commands.get(command, 0)) + 1

        habits = self.usage_data.setdefault("user_habits", self._default_usage()["user_habits"])
        habits["last_command"] = command
        habits["last_category"] = str(category or "general")
        habits["last_active_at"] = datetime.now().isoformat(timespec="seconds")
        self._save_usage()
        return True

    def track_app_usage(self, app_name):
        normalized = self._normalize_token(app_name)
        if not normalized:
            return False

        apps = self.usage_data.setdefault("most_used_apps", {})
        apps[normalized] = int(apps.get(normalized, 0)) + 1
        self.add_frequent_app(normalized)

        habits = self.usage_data.setdefault("user_habits", self._default_usage()["user_habits"])
        habits["last_app_opened"] = normalized
        habits["last_active_at"] = datetime.now().isoformat(timespec="seconds")
        if normalized in {"code", "vscode", "visual studio code", "cursor", "pycharm"}:
            habits["last_coding_activity"] = datetime.now().isoformat(timespec="seconds")
        self._sync_favorite_app()
        self._save_usage()
        return True

    def learn_from_text(self, raw_text):
        raw = " ".join(str(raw_text).strip().split())
        normalized = raw.lower()
        if not normalized:
            return False

        learned = False
        if normalized.startswith("i like "):
            learned = self.add_interest(raw[7:].strip()) or learned
        if normalized.startswith("my name is "):
            learned = self.set_user_name(raw[11:].strip()) or learned
        if normalized.startswith("i use "):
            learned = self.add_frequent_app(raw[6:].strip()) or learned
        if normalized.startswith("i prefer "):
            preference = raw[9:].strip()
            learned = self.set_preference("general_preference", preference) or learned
            learned = self.remember_fact(f"I prefer {preference}") or learned
        learning_match = re.match(r"^(?:i am|i m|i'm)\s+learning\s+(.+)$", raw, re.IGNORECASE)
        if learning_match:
            skill = learning_match.group(1).strip().strip(".")
            learned = self.set_preference("learning", skill) or learned
            learned = self.add_interest(skill) or learned
            learned = self.remember_fact(f"You are learning {skill}") or learned
        project_match = re.match(r"^(?:my project is|i am working on|i'm working on|i am building|i'm building)\s+(.+)$", raw, re.IGNORECASE)
        if project_match:
            project = project_match.group(1).strip().strip(".")
            learned = self.add_project(project) or learned
        goal_match = re.match(r"^(?:my goal is|my goal is to|i want to|i wanna)\s+(.+)$", raw, re.IGNORECASE)
        if goal_match:
            goal = goal_match.group(1).strip().strip(".")
            learned = self.set_preference("goal", goal) or learned
            learned = self.remember_fact(f"Your goal is {goal}") or learned
        if re.search(r"\b(?:gf|girlfriend|relationship)\b", normalized) and re.search(
            r"\b(?:dhokha|cheat(?:ed)?|betray(?:ed|al)?|break(?: ?up)?|left me|heartbroken)\b",
            normalized,
        ):
            learned = self.set_relationship_status("broken", note=raw) or learned
            learned = self.set_emotional_state("sad", note=raw) or learned
        elif re.search(r"\b(?:relationship|gf|girlfriend)\b", normalized) and re.search(
            r"\b(?:complicated|messy|not good|toxic)\b",
            normalized,
        ):
            learned = self.set_relationship_status("complicated", note=raw) or learned
        return learned

    def suggestion(self):
        favorite_app = self.profile_data.get("favorite_app", "")
        last_command = str(self.usage_data.get("user_habits", {}).get("last_command", ""))
        if favorite_app and any(token in last_command for token in ["code", "coding", "project", "python"]):
            display = "VS Code" if favorite_app in {"vscode", "code"} else favorite_app.title()
            return f"Boss, want me to open {display}?"
        return ""

    def top_apps(self, limit=3):
        apps = self.usage_data.get("most_used_apps", {})
        return [name for name, _ in Counter(apps).most_common(limit)]

    def frequent_commands(self, limit=5):
        commands = self.usage_data.get("frequent_commands", {})
        return [name for name, _ in Counter(commands).most_common(limit)]

    def log_task(self, goal, steps, outcome, status="completed", agent="", model=""):
        entry = {
            "goal": str(goal).strip(),
            "status": str(status or "completed").strip(),
            "agent": str(agent).strip(),
            "model": str(model).strip(),
            "outcome": str(outcome).strip(),
            "steps": list(steps) if isinstance(steps, list) else [],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.task_data.append(entry)
        self.task_data = self.task_data[-100:]
        self._save_tasks()
        return True

    def task_history(self, limit=20):
        return list(self.task_data[-max(1, int(limit)) :])

    def day_key(self, target_day=None):
        return str(target_day or date.today())

    def daily_memory(self, target_day=None):
        day = self.day_key(target_day)
        days = self.daily_data.setdefault("days", {})
        if day not in days:
            if day == str(date.today()):
                self._ensure_today_entry()
            else:
                days[day] = self._default_daily_entry(day)
        entry = dict(days[day])
        entry["schedule"] = list(entry.get("schedule", []))
        entry["tasks"] = list(entry.get("tasks", []))
        entry["activity_log"] = list(entry.get("activity_log", []))
        entry["activity_summary"] = dict(entry.get("activity_summary", {}))
        return entry

    def update_daily_memory(self, updates=None, target_day=None, **kwargs):
        payload = dict(updates) if isinstance(updates, dict) else {}
        payload.update(kwargs)
        day = self.day_key(target_day)
        if day == str(date.today()):
            self._ensure_today_entry()
        entry = self.daily_data.setdefault("days", {}).setdefault(day, self._default_daily_entry(day))

        for key, value in payload.items():
            if key == "schedule":
                entry[key] = self._normalize_schedule(value)
            elif key == "tasks":
                entry[key] = self._normalize_tasks(value)
            elif key == "activity_log":
                entry[key] = list(value) if isinstance(value, list) else []
            elif key == "activity_summary":
                entry[key] = self._merge_activity_summary(value)
            elif key in {"study_goal_hours", "study_progress"}:
                fallback = entry.get(key, 0)
                entry[key] = self._coerce_hours(value, fallback)
            else:
                entry[key] = value

        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.daily_data["current_date"] = day
        self._trim_day_history()
        if day == str(date.today()):
            self._sync_profile_from_daily()
        self._save_daily_memory()
        return self.daily_memory(day)

    def set_exam_details(self, exam_date=None, subject=None):
        changed = False
        if exam_date:
            self.profile_data["exam_date"] = str(exam_date).strip()
            changed = True
        if subject:
            self.profile_data["subject"] = str(subject).strip()
            changed = True
        if not changed:
            return False

        self._ensure_today_entry()
        today = self.day_key()
        entry = self.daily_data["days"][today]
        entry["exam_date"] = self.profile_data.get("exam_date", "")
        entry["subject"] = self.profile_data.get("subject", "")
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._save_profile()
        self._save_daily_memory()
        return True

    def set_study_goal(self, hours):
        goal = self._coerce_hours(hours, None)
        if goal is None:
            return False
        self.profile_data["study_goal_hours"] = goal
        self._ensure_today_entry()
        today = self.day_key()
        self.daily_data["days"][today]["study_goal_hours"] = goal
        self.daily_data["days"][today]["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self._save_profile()
        self._save_daily_memory()
        return True

    def log_study_progress(self, hours, source="manual", mode="add"):
        delta = self._coerce_hours(hours, None)
        if delta is None:
            return {}

        self._ensure_today_entry()
        today = self.day_key()
        entry = self.daily_data["days"][today]
        current = self._coerce_hours(entry.get("study_progress", 0), 0)
        progress = delta if mode == "set" else current + delta
        entry["study_progress"] = round(max(0.0, progress), 2)
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        entry.setdefault("checkins", []).append(
            {
                "type": "study_progress",
                "source": str(source or "manual"),
                "hours": round(delta, 2),
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self.profile_data["study_progress"] = entry["study_progress"]
        self._save_profile()
        self._save_daily_memory()
        return self.daily_memory()

    def set_study_progress(self, hours, source="manual"):
        return self.log_study_progress(hours, source=source, mode="set")

    def set_daily_schedule(self, schedule, target_day=None):
        normalized = self._normalize_schedule(schedule)
        day = self.day_key(target_day)
        self.update_daily_memory({"schedule": normalized}, target_day=day)
        if normalized and not self.daily_memory(day).get("tasks"):
            tasks = []
            for item in normalized:
                tasks.append(
                    {
                        "title": item.get("title", ""),
                        "category": item.get("category", "general"),
                        "status": "pending",
                        "scheduled_for": item.get("time", ""),
                        "duration_minutes": item.get("duration_minutes", 0),
                    }
                )
            self.set_daily_tasks(tasks, target_day=day)
        return self.daily_memory(day).get("schedule", [])

    def set_daily_tasks(self, tasks, target_day=None):
        normalized = self._normalize_tasks(tasks)
        self.update_daily_memory({"tasks": normalized}, target_day=target_day)
        return self.daily_memory(target_day).get("tasks", [])

    def add_daily_task(self, title, category="general", scheduled_for="", duration_minutes=0, status="pending"):
        cleaned = str(title).strip()
        if not cleaned:
            return False

        day = self.day_key()
        entry = self.daily_data.setdefault("days", {}).setdefault(day, self._default_daily_entry(day))
        tasks = self._normalize_tasks(entry.get("tasks", []))
        if cleaned.lower() in [str(item.get("title", "")).lower() for item in tasks]:
            return False

        tasks.append(
            {
                "title": cleaned,
                "category": str(category or "general").strip().lower(),
                "status": str(status or "pending").strip().lower(),
                "scheduled_for": str(scheduled_for or "").strip(),
                "duration_minutes": int(duration_minutes or 0),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self.update_daily_memory({"tasks": tasks}, target_day=day)
        return True

    def mark_task_status(self, title, status="completed"):
        cleaned = str(title).strip().lower()
        if not cleaned:
            return False

        changed = False
        day = self.day_key()
        entry = self.daily_data.setdefault("days", {}).setdefault(day, self._default_daily_entry(day))
        tasks = self._normalize_tasks(entry.get("tasks", []))
        for item in tasks:
            if cleaned in str(item.get("title", "")).lower():
                item["status"] = str(status or "completed").strip().lower()
                item["updated_at"] = datetime.now().isoformat(timespec="seconds")
                changed = True
        if changed:
            self.update_daily_memory({"tasks": tasks}, target_day=day)
        return changed

    def pending_tasks(self, limit=10):
        tasks = self.daily_memory().get("tasks", [])
        pending = [item for item in tasks if str(item.get("status", "pending")).lower() != "completed"]
        return pending[: max(1, int(limit))]

    def record_activity_snapshot(self, snapshot):
        if not isinstance(snapshot, dict):
            return False

        day = self.day_key()
        entry = self.daily_data.setdefault("days", {}).setdefault(day, self._default_daily_entry(day))
        activity_summary = self._merge_activity_summary(entry.get("activity_summary", {}))

        category = str(snapshot.get("category", "")).strip().lower()
        active_app = self._normalize_token(snapshot.get("active_app", ""))
        delta_seconds = int(snapshot.get("delta_seconds", 0) or 0)
        delta_minutes = round(max(0, delta_seconds) / 60, 2)

        if active_app:
            entry["last_active_app"] = active_app
            self.track_app_usage(active_app)
        entry["last_window_title"] = str(snapshot.get("active_title", "")).strip()
        if delta_minutes > 0:
            if category in {"coding", "productive", "study"}:
                activity_summary["productive_minutes"] += delta_minutes
            if category in {"entertainment", "social_media", "game"}:
                activity_summary["entertainment_minutes"] += delta_minutes
            if category == "study":
                activity_summary["study_minutes"] += delta_minutes
            if category == "coding":
                activity_summary["coding_minutes"] += delta_minutes

        log_entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "active_app": active_app,
            "active_title": entry.get("last_window_title", ""),
            "category": category,
            "minutes_in_focus": int(snapshot.get("minutes_in_focus", 0) or 0),
            "detected_apps": list(snapshot.get("open_apps", []))[:12],
        }
        if delta_seconds > 0:
            log_entry["delta_seconds"] = delta_seconds

        activity_log = list(entry.get("activity_log", []))
        if log_entry["active_app"] or log_entry["active_title"]:
            activity_log.append(log_entry)

        entry["activity_log"] = activity_log[-120:]
        entry["activity_summary"] = activity_summary
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")

        habits = self.usage_data.setdefault("user_habits", self._default_usage()["user_habits"])
        if active_app:
            habits["last_app_opened"] = active_app
        habits["last_active_at"] = datetime.now().isoformat(timespec="seconds")
        if category == "coding":
            habits["last_coding_activity"] = datetime.now().isoformat(timespec="seconds")

        self._save_usage()
        self._save_daily_memory()
        return True

    def log_mood(self, emotion, intensity="normal", source="text", note=""):
        cleaned_emotion = str(emotion).strip().lower()
        if not cleaned_emotion:
            return False
        day = self.day_key()
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "emotion": cleaned_emotion,
            "intensity": str(intensity or "normal").strip().lower(),
            "source": str(source or "text").strip().lower(),
            "note": str(note or "").strip(),
        }
        self.mood_data[day] = cleaned_emotion
        today_entry = self.daily_data.setdefault("days", {}).setdefault(day, self._default_daily_entry(day))
        today_entry["current_mood"] = cleaned_emotion
        today_entry.setdefault("checkins", []).append(
            {
                "type": "mood",
                "emotion": cleaned_emotion,
                "intensity": entry["intensity"],
                "timestamp": entry["timestamp"],
            }
        )
        today_entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.emotion_history_data[day] = cleaned_emotion

        self._save_daily_memory()
        self._save_mood_history()
        self._save_emotion_history()
        return True

    def mood_history(self, limit=30):
        if limit is None:
            return dict(self.mood_data)
        keep = sorted(self.mood_data.keys())[-max(1, int(limit)) :]
        return {day: self.mood_data[day] for day in keep}

    def emotion_history(self):
        return dict(self.emotion_history_data)

    def latest_mood(self):
        if not self.mood_data:
            return {}
        latest_day = sorted(self.mood_data.keys())[-1]
        return {
            "date": latest_day,
            "emotion": self.mood_data.get(latest_day, ""),
        }

    def behavior_profile(self):
        return dict(self.profile_data.get("behavior_profile", self._default_behavior_profile()))

    def update_behavior_profile(self, updates):
        if not isinstance(updates, dict):
            return self.behavior_profile()
        current = self._merge_behavior_profile(self._default_behavior_profile(), self.profile_data.get("behavior_profile", {}))
        current = self._merge_behavior_profile(current, updates)
        self.profile_data["behavior_profile"] = current
        self._save_profile()
        return dict(current)

    def dashboard_snapshot(self):
        daily = self.daily_memory()
        latest_mood = self.latest_mood()
        return {
            "memory_status": "SYNCED",
            "conversation_count": len(self.conversation_data),
            "task_count": len(self.task_data),
            "favorite_app": self.profile_data.get("favorite_app", ""),
            "top_apps": self.top_apps(),
            "study_goal_hours": daily.get("study_goal_hours", 0),
            "study_progress": daily.get("study_progress", 0),
            "latest_mood": latest_mood.get("emotion", ""),
        }

    def _flush_all(self):
        self._save_profile()
        self._save_conversations()
        self._save_usage()
        self._save_tasks()
        self._save_daily_memory()
        self._save_mood_history()
        self._save_emotion_history()

    def _save_profile(self):
        self.profile_path.write_text(json.dumps(self.profile_data, indent=2, ensure_ascii=True), encoding="utf-8")
        self._save_companion_memory()

    def _save_conversations(self):
        self.conversation_path.write_text(json.dumps(self.conversation_data, indent=2, ensure_ascii=True), encoding="utf-8")
        self._save_companion_memory()

    def _save_usage(self):
        self.usage_path.write_text(json.dumps(self.usage_data, indent=2, ensure_ascii=True), encoding="utf-8")
        self._save_companion_memory()

    def _save_tasks(self):
        self.task_history_path.write_text(json.dumps(self.task_data, indent=2, ensure_ascii=True), encoding="utf-8")
        self._save_companion_memory()

    def _save_daily_memory(self):
        self.daily_memory_path.write_text(json.dumps(self.daily_data, indent=2, ensure_ascii=True), encoding="utf-8")
        self._save_companion_memory()

    def _save_mood_history(self):
        self.mood_history_path.write_text(json.dumps(self.mood_data, indent=2, ensure_ascii=True), encoding="utf-8")
        self._save_companion_memory()

    def _save_emotion_history(self):
        self.emotion_history_path.write_text(
            json.dumps(self.emotion_history_data, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        self._save_companion_memory()

    def _save_companion_memory(self):
        payload = self.full_memory_snapshot()
        self.snapshot_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")

    def _load_json(self, path, default):
        if not path.exists():
            return default
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return default
        return payload

    def _load_list(self, path):
        payload = self._load_json(path, [])
        return payload if isinstance(payload, list) else []

    def _load_emotion_history(self):
        payload = self._load_json(self.emotion_history_path, {})
        return dict(payload) if isinstance(payload, dict) else {}

    def _load_mood_history(self):
        payload = self._load_json(self.mood_history_path, {})
        if isinstance(payload, dict):
            return {str(day): str(emotion).strip().lower() for day, emotion in payload.items() if str(emotion).strip()}
        if isinstance(payload, list):
            summary = {}
            for item in payload:
                if not isinstance(item, dict):
                    continue
                timestamp = str(item.get("timestamp", "")).strip()
                emotion = str(item.get("emotion", "")).strip().lower()
                if not timestamp or not emotion:
                    continue
                summary[timestamp[:10]] = emotion
            return summary
        return {}

    def _merge(self, base, payload):
        if not isinstance(payload, dict):
            return dict(base)
        merged = dict(base)
        merged.update(payload)
        merged["interests"] = self._dedupe_list(merged.get("interests", []))
        merged["projects"] = self._dedupe_list(merged.get("projects", []))
        merged["frequent_apps"] = self._dedupe_list(merged.get("frequent_apps", []))
        merged["facts"] = list(merged.get("facts", []))
        merged["notes"] = list(merged.get("notes", []))
        merged["reminders"] = list(merged.get("reminders", []))
        merged["preferences"] = dict(merged.get("preferences", {}))
        merged["behavior_profile"] = self._merge_behavior_profile(
            self._default_behavior_profile(),
            merged.get("behavior_profile", {}),
        )
        merged["study_goal_hours"] = self._coerce_hours(merged.get("study_goal_hours", base.get("study_goal_hours", 3)), 3)
        merged["study_progress"] = self._coerce_hours(merged.get("study_progress", base.get("study_progress", 0)), 0)
        if merged.get("name") and not merged.get("user_name"):
            merged["user_name"] = merged["name"]
        if merged.get("user_name") and not merged.get("name"):
            merged["name"] = merged["user_name"]
        return merged

    def _merge_usage(self, base, payload):
        if not isinstance(payload, dict):
            return dict(base)
        merged = dict(base)
        merged.update(payload)
        merged["most_used_apps"] = dict(merged.get("most_used_apps", {}))
        merged["frequent_commands"] = dict(merged.get("frequent_commands", {}))
        user_habits = dict(base.get("user_habits", {}))
        user_habits.update(dict(merged.get("user_habits", {})))
        merged["user_habits"] = user_habits
        return merged

    def _merge_daily_store(self, base, payload):
        if not isinstance(payload, dict):
            return dict(base)
        merged = {"current_date": str(payload.get("current_date", "")), "days": {}}
        raw_days = payload.get("days", {})
        if isinstance(raw_days, dict):
            for day, item in raw_days.items():
                day_key = str(day).strip()
                if not day_key or not isinstance(item, dict):
                    continue
                merged["days"][day_key] = self._merge_daily_entry(day_key, item)
        return merged

    def _merge_daily_entry(self, day_key, payload):
        entry = self._default_daily_entry(day_key)
        if isinstance(payload, dict):
            entry.update(payload)
        entry["schedule"] = self._normalize_schedule(entry.get("schedule", []))
        entry["tasks"] = self._normalize_tasks(entry.get("tasks", []))
        entry["activity_log"] = list(entry.get("activity_log", []))[-120:]
        entry["activity_summary"] = self._merge_activity_summary(entry.get("activity_summary", {}))
        entry["study_goal_hours"] = self._coerce_hours(
            entry.get("study_goal_hours", self.profile_data.get("study_goal_hours", 3)),
            self.profile_data.get("study_goal_hours", 3),
        )
        entry["study_progress"] = self._coerce_hours(entry.get("study_progress", 0), 0)
        return entry

    def _ensure_today_entry(self):
        today = self.day_key()
        days = self.daily_data.setdefault("days", {})
        current = days.get(today, {})
        days[today] = self._merge_daily_entry(today, current)
        self.daily_data["current_date"] = today
        self._trim_day_history()
        self._sync_profile_from_daily()
        return days[today]

    def _sync_profile_from_daily(self):
        today = self.day_key()
        daily = self.daily_data.setdefault("days", {}).setdefault(today, self._default_daily_entry(today))
        self.profile_data["study_goal_hours"] = self._coerce_hours(daily.get("study_goal_hours", 3), 3)
        self.profile_data["study_progress"] = self._coerce_hours(daily.get("study_progress", 0), 0)
        if daily.get("subject"):
            self.profile_data["subject"] = daily.get("subject", "")
        elif self.profile_data.get("subject"):
            daily["subject"] = self.profile_data.get("subject", "")
        if daily.get("exam_date"):
            self.profile_data["exam_date"] = daily.get("exam_date", "")
        elif self.profile_data.get("exam_date"):
            daily["exam_date"] = self.profile_data.get("exam_date", "")

    def _trim_day_history(self):
        days = self.daily_data.setdefault("days", {})
        keep = sorted(days.keys())[-30:]
        self.daily_data["days"] = {day: days[day] for day in keep}

    def _sync_behavior_profile(self):
        profile = self._merge_behavior_profile(
            self._default_behavior_profile(),
            self.profile_data.get("behavior_profile", {}),
        )
        if not profile.get("frequent_apps"):
            profile["frequent_apps"] = self.top_apps(limit=5)
        self.profile_data["behavior_profile"] = profile

    def _sync_favorite_app(self):
        usage_apps = self.usage_data.get("most_used_apps", {})
        if usage_apps:
            self.profile_data["favorite_app"] = max(usage_apps, key=usage_apps.get)
            return
        frequent = self.profile_data.get("frequent_apps", [])
        self.profile_data["favorite_app"] = frequent[0] if frequent else ""

    def _default_profile(self):
        return {
            "name": "",
            "user_name": "",
            "course": "",
            "semester": "",
            "field": "",
            "interests": [],
            "current_project": "",
            "goal": "",
            "projects": [],
            "preferences": {},
            "frequent_apps": [],
            "favorite_app": "",
            "facts": [],
            "notes": [],
            "reminders": [],
            "conversation_history": [],
            "exam_date": "",
            "subject": "",
            "relationship_status": "",
            "emotional_state": "",
            "latest_exam_feedback": "",
            "study_goal_hours": 3,
            "study_progress": 0,
            "behavior_profile": self._default_behavior_profile(),
        }

    def _default_usage(self):
        return {
            "most_used_apps": {},
            "frequent_commands": {},
            "user_habits": {
                "last_command": "",
                "last_category": "",
                "last_active_at": "",
                "last_app_opened": "",
                "last_coding_activity": "",
            },
        }

    def _default_behavior_profile(self):
        return {
            "preferred_study_time": "",
            "coding_schedule": "",
            "sleep_time": "",
            "frequent_apps": [],
            "app_minutes": {},
            "study_windows": {},
            "coding_windows": {},
            "night_activity_count": 0,
        }

    def _default_daily_store(self):
        return {"current_date": "", "days": {}}

    def _default_daily_entry(self, day_key):
        now = datetime.now().isoformat(timespec="seconds")
        current_mood = ""
        mood_data = getattr(self, "mood_data", [])
        if isinstance(mood_data, dict) and mood_data:
            latest_day = sorted(mood_data.keys())[-1]
            current_mood = str(mood_data.get(latest_day, "")).strip()
        return {
            "date": day_key,
            "subject": self.profile_data.get("subject", ""),
            "exam_date": self.profile_data.get("exam_date", ""),
            "exam_start": "",
            "exam_end": "",
            "exam_feedback": "",
            "awaiting_exam_feedback": False,
            "study_goal_hours": self._coerce_hours(self.profile_data.get("study_goal_hours", 3), 3),
            "study_progress": self._coerce_hours(self.profile_data.get("study_progress", 0), 0),
            "focus_mode": "study",
            "schedule": [],
            "tasks": [],
            "checkins": [],
            "activity_log": [],
            "activity_summary": self._merge_activity_summary({}),
            "current_mood": current_mood,
            "last_active_app": "",
            "last_window_title": "",
            "created_at": now,
            "updated_at": now,
        }

    def _merge_behavior_profile(self, base, payload):
        merged = dict(base)
        if isinstance(payload, dict):
            merged.update(payload)
        merged["frequent_apps"] = self._dedupe_list(merged.get("frequent_apps", []))
        merged["app_minutes"] = dict(merged.get("app_minutes", {}))
        merged["study_windows"] = dict(merged.get("study_windows", {}))
        merged["coding_windows"] = dict(merged.get("coding_windows", {}))
        merged["night_activity_count"] = int(merged.get("night_activity_count", 0) or 0)
        return merged

    def _merge_activity_summary(self, payload):
        summary = {
            "productive_minutes": 0.0,
            "entertainment_minutes": 0.0,
            "study_minutes": 0.0,
            "coding_minutes": 0.0,
        }
        if isinstance(payload, dict):
            for key in summary:
                value = payload.get(key, summary[key])
                try:
                    summary[key] = round(float(value), 2)
                except (TypeError, ValueError):
                    summary[key] = 0.0
        return summary

    def _normalize_schedule(self, schedule):
        normalized = []
        source = schedule if isinstance(schedule, list) else []
        for item in source:
            if isinstance(item, dict):
                title = str(item.get("title", "")).strip()
                if not title:
                    continue
                normalized.append(
                    {
                        "time": str(item.get("time", "")).strip(),
                        "title": title,
                        "duration_minutes": int(item.get("duration_minutes", 0) or 0),
                        "category": str(item.get("category", "general")).strip().lower() or "general",
                    }
                )
                continue
            text = str(item).strip()
            if text:
                normalized.append({"time": "", "title": text, "duration_minutes": 0, "category": "general"})
        return normalized

    def _normalize_tasks(self, tasks):
        normalized = []
        source = tasks if isinstance(tasks, list) else []
        for item in source:
            if isinstance(item, dict):
                title = str(item.get("title", "")).strip()
                if not title:
                    continue
                normalized.append(
                    {
                        "title": title,
                        "category": str(item.get("category", "general")).strip().lower() or "general",
                        "status": str(item.get("status", "pending")).strip().lower() or "pending",
                        "scheduled_for": str(item.get("scheduled_for", "")).strip(),
                        "duration_minutes": int(item.get("duration_minutes", 0) or 0),
                        "created_at": str(item.get("created_at", "")).strip(),
                        "updated_at": str(item.get("updated_at", "")).strip(),
                    }
                )
                continue
            text = str(item).strip()
            if text:
                normalized.append(
                    {
                        "title": text,
                        "category": "general",
                        "status": "pending",
                        "scheduled_for": "",
                        "duration_minutes": 0,
                        "created_at": "",
                        "updated_at": "",
                    }
                )
        return normalized

    def _dedupe_list(self, values):
        seen = set()
        result = []
        source = values if isinstance(values, list) else []
        for value in source:
            item = str(value).strip()
            if not item:
                continue
            key = item.lower()
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    def _coerce_hours(self, value, fallback):
        try:
            parsed = round(float(value), 2)
        except (TypeError, ValueError):
            return fallback
        return max(0.0, parsed)

    def _normalize_token(self, value):
        text = " ".join(str(value).strip().lower().split())
        aliases = {
            "vs code": "vscode",
            "visual studio code": "vscode",
            "microsoft edge": "edge",
            "google chrome": "chrome",
        }
        return aliases.get(text, text)
