import json
from datetime import date
from pathlib import Path


class MemoryEngine:
    def __init__(self, storage_path):
        self.storage_path = Path(storage_path)
        self.data = self._load()

    def set_user_name(self, name):
        cleaned = str(name).strip()
        if not cleaned:
            return False
        self.data["user_name"] = cleaned
        self._save()
        return True

    def user_name(self):
        return self.data.get("user_name") or "Sir"

    def save_note(self, text):
        cleaned = str(text).strip()
        if not cleaned:
            return False
        self.data.setdefault("notes", []).append(
            {
                "text": cleaned,
                "created_on": str(date.today()),
            }
        )
        self._save()
        return True

    def notes(self):
        return list(self.data.get("notes", []))

    def reminders(self):
        return list(self.data.get("reminders", []))

    def remember_fact(self, text):
        cleaned = str(text).strip()
        if not cleaned:
            return False
        self.data.setdefault("facts", []).append(
            {
                "text": cleaned,
                "created_on": str(date.today()),
            }
        )
        self._save()
        return True

    def facts(self):
        return list(self.data.get("facts", []))

    def add_reminder(self, text, due_on=None):
        cleaned = str(text).strip()
        if not cleaned:
            return False
        self.data.setdefault("reminders", []).append(
            {
                "text": cleaned,
                "due_on": due_on or str(date.today()),
            }
        )
        self._save()
        return True

    def due_today(self):
        today = str(date.today())
        reminders = self.data.get("reminders", [])
        return [item for item in reminders if item.get("due_on") == today]

    def _load(self):
        if not self.storage_path.exists():
            return self._default_data()

        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return self._default_data()

        if not isinstance(payload, dict):
            return self._default_data()

        base = self._default_data()
        base.update(payload)
        base["notes"] = list(base.get("notes", []))
        base["reminders"] = list(base.get("reminders", []))
        base["facts"] = list(base.get("facts", []))
        return base

    def _save(self):
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )

    def _default_data(self):
        return {
            "user_name": "",
            "notes": [],
            "reminders": [],
            "facts": [],
        }
