from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


class ConversationMemory:
    def __init__(self, storage_root, memory=None):
        root = Path(storage_root)
        self.storage_dir = root if root.suffix.lower() != ".json" else root.parent
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.storage_dir / "conversation_history.json"
        self.memory = memory
        self.data = self._load()
        self._save()

    def snapshot(self):
        return {
            "last_topic": str(self.data.get("last_topic", "")).strip(),
            "recent_messages": list(self.data.get("recent_messages", [])),
            "last_emotion": str(self.data.get("last_emotion", "")).strip(),
            "last_updated": str(self.data.get("last_updated", "")).strip(),
        }

    def remember_turn(self, user_text, assistant_text="", emotion=""):
        user_message = " ".join(str(user_text).strip().split())
        assistant_message = " ".join(str(assistant_text).strip().split())
        if not user_message and not assistant_message:
            return False

        recent = list(self.data.get("recent_messages", []))
        if user_message:
            recent.append(user_message)
        if assistant_message:
            recent.append(assistant_message)
        self.data["recent_messages"] = recent[-12:]

        topic = self._infer_topic(user_message or assistant_message)
        if topic:
            self.data["last_topic"] = topic
        if emotion:
            self.data["last_emotion"] = str(emotion).strip().lower()
        self.data["last_updated"] = datetime.now().isoformat(timespec="seconds")
        self._save()
        return True

    def follow_up_prompt(self, context=None):
        context = context or {}
        topic = str(self.data.get("last_topic", "")).strip().lower()
        latest_emotion = str(self.data.get("last_emotion", "")).strip().lower()
        subject = str(context.get("subject") or (context.get("daily_memory") or {}).get("subject") or "").strip()

        if "exam" in topic or "revision" in topic:
            if subject:
                return f"Boss, {subject} exam ki preparation kaisi chal rahi hai?"
            return "Boss, exam ki preparation kaisi chal rahi hai?"
        if "coding" in topic or "project" in topic:
            return "Boss, coding practice kaisi chal rahi hai?"
        if latest_emotion in {"stressed", "sad", "tired"}:
            return "Boss, ab thoda better feel kar rahe ho?"
        return ""

    def _infer_topic(self, text):
        normalized = " ".join(str(text).lower().split())
        if not normalized:
            return ""

        subject = ""
        if self.memory and hasattr(self.memory, "profile"):
            profile = self.memory.profile()
            subject = str(profile.get("subject", "")).strip()

        if any(token in normalized for token in ("exam", "revision", "test", "paper")):
            if subject:
                return f"{subject} exam"
            return "exam preparation"
        if any(token in normalized for token in ("study", "topic", "data structure", "dsa")):
            return f"{subject or 'study'} revision".strip()
        if any(token in normalized for token in ("code", "coding", "project", "bug", "python")):
            return "coding practice"
        if any(token in normalized for token in ("sad", "stressed", "tired", "happy", "excited", "bored")):
            return "emotional check-in"
        if any(token in normalized for token in ("youtube", "music", "song")):
            return "music break"
        return ""

    def _load(self):
        default = {
            "last_topic": "",
            "recent_messages": [],
            "last_emotion": "",
            "last_updated": "",
        }
        if not self.path.exists():
            return default
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return default
        if not isinstance(payload, dict):
            return default
        default.update(payload)
        default["recent_messages"] = [str(item).strip() for item in default.get("recent_messages", []) if str(item).strip()]
        return default

    def _save(self):
        self.path.write_text(json.dumps(self.data, indent=2, ensure_ascii=True), encoding="utf-8")
