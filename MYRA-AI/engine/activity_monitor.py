from __future__ import annotations

import csv
import ctypes
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from io import StringIO


@dataclass
class ActivitySnapshot:
    active_app: str = ""
    active_title: str = ""
    category: str = "idle"
    open_apps: tuple[str, ...] = ()
    minutes_in_focus: int = 0
    delta_seconds: int = 0

    def as_dict(self):
        return {
            "active_app": self.active_app,
            "active_title": self.active_title,
            "category": self.category,
            "open_apps": list(self.open_apps),
            "minutes_in_focus": self.minutes_in_focus,
            "delta_seconds": self.delta_seconds,
        }


class ActivityMonitor:
    def __init__(self, memory=None, behavior_engine=None):
        self.memory = memory
        self.behavior_engine = behavior_engine
        self._last_signature = ""
        self._last_focus_started = time.monotonic()
        self._last_polled = time.monotonic()
        self._last_snapshot = ActivitySnapshot()

    def poll(self):
        active_title = self._active_window_title()
        open_apps = self._running_apps()
        active_app, category = self._classify_activity(active_title, open_apps)

        now = time.monotonic()
        delta_seconds = int(max(0, now - self._last_polled))
        self._last_polled = now

        signature = f"{active_app}|{active_title}"
        if signature != self._last_signature:
            self._last_signature = signature
            self._last_focus_started = now

        minutes_in_focus = int(max(0, now - self._last_focus_started) // 60)
        snapshot = ActivitySnapshot(
            active_app=active_app,
            active_title=active_title,
            category=category,
            open_apps=tuple(open_apps),
            minutes_in_focus=minutes_in_focus,
            delta_seconds=delta_seconds,
        )
        self._last_snapshot = snapshot
        return snapshot

    def last_snapshot(self):
        return self._last_snapshot

    def handle(self, command):
        normalized = " ".join(str(command).lower().split())
        queries = {
            "what apps are open",
            "activity status",
            "what am i doing",
            "what is running",
            "show activity",
        }
        if normalized not in queries:
            return False, ""
        snapshot = self.poll()
        return True, self.describe(snapshot)

    def describe(self, snapshot=None):
        snap = snapshot or self._last_snapshot or self.poll()
        if not snap.active_app and not snap.open_apps:
            return "Abhi koi clear active app detect nahi ho raha."
        open_preview = ", ".join(list(snap.open_apps)[:5]) if snap.open_apps else "kuch selected apps"
        if snap.active_app:
            return f"Abhi {snap.active_app} active lag raha hai. Open apps me {open_preview} dikh rahe hain."
        return f"Open apps me {open_preview} dikh rahe hain."

    def build_intervention(self, context=None, snapshot=None):
        context = context or {}
        snap = snapshot or self._last_snapshot or self.poll()
        if snap.category not in {"entertainment", "social_media", "game"}:
            return ""

        daily = context.get("daily_memory") or {}
        goal = float(daily.get("study_goal_hours", 0) or 0)
        progress = float(daily.get("study_progress", 0) or 0)
        if goal and progress >= goal:
            return ""

        exam_days = self._days_until_exam(context)
        threshold = 30 if exam_days in {0, 1} else 40
        if snap.minutes_in_focus < threshold:
            return ""

        name = self._name(context)
        subject = str(context.get("subject") or daily.get("subject") or "exam").strip()
        label = snap.active_app.title() if snap.active_app else "entertainment"
        options = [
            f"{name} tum {snap.minutes_in_focus} minutes se {label} me ho. Kya 20 minute study karna chahoge?",
            f"{name} ek suggestion hai. Abhi 30 min study kar lo, phir bina tension {label} dekh lena.",
            f"{name} ek honest question. Tum sach me busy ho ya bas procrastinate kar rahe ho?",
        ]
        if exam_days == 1:
            options.insert(0, f"{name} tum {snap.minutes_in_focus} minutes se {label} dekh rahe ho. Kal {subject} ka exam hai. Kya 20 minute revision karein?")
            options.append("Warning, exam mode active hai. Netflix temporarily banned.")
        return options[int(time.time()) % len(options)]

    def _classify_activity(self, active_title, open_apps):
        title = str(active_title or "").lower()
        open_set = {self._normalize(app) for app in open_apps}

        if "youtube" in title:
            return "youtube", "entertainment"
        if "netflix" in title:
            return "netflix", "entertainment"
        if any(token in title for token in ("instagram", "facebook", "twitter", "reel", "shorts")):
            return "social media", "social_media"
        if any(token in title for token in ("visual studio code", "cursor", "pycharm")):
            return "vscode", "coding"
        if any(token in title for token in ("github", "stack overflow", "documentation", "notebook", "jupyter")):
            return "browser", "productive"
        if any(token in title for token in ("chrome", "edge", "firefox", "brave")):
            return "browser", "browser"

        if any(app in open_set for app in {"valorant", "steam", "epicgameslauncher", "robloxplayerbeta", "leagueclient"}):
            return "game", "game"
        if "code" in open_set or "vscode" in open_set:
            return "vscode", "coding"
        if "netflix" in open_set:
            return "netflix", "entertainment"
        if "chrome" in open_set or "edge" in open_set or "firefox" in open_set:
            return "browser", "browser"
        return "", "idle"

    def _running_apps(self):
        try:
            result = subprocess.run(
                ["tasklist", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return []

        if not result.stdout:
            return []

        rows = csv.reader(StringIO(result.stdout))
        apps = []
        for row in rows:
            if not row:
                continue
            image_name = row[0].strip().strip('"')
            stem = image_name.rsplit(".", 1)[0]
            normalized = self._normalize(stem)
            if normalized and normalized not in apps:
                apps.append(normalized)
        return apps

    def _active_window_title(self):
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return ""
            length = user32.GetWindowTextLengthW(hwnd)
            if length <= 0:
                return ""
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            return buffer.value.strip()
        except Exception:
            return ""

    def _days_until_exam(self, context):
        exam_date = str(context.get("exam_date") or (context.get("daily_memory") or {}).get("exam_date") or "").strip()
        if not exam_date:
            return None
        try:
            target = datetime.fromisoformat(exam_date).date()
        except Exception:
            return None
        return (target - datetime.now().date()).days

    def _name(self, context):
        return "Boss"

    def _normalize(self, value):
        aliases = {
            "code": "vscode",
            "msedge": "edge",
            "chrome": "chrome",
        }
        normalized = " ".join(str(value).strip().lower().split())
        return aliases.get(normalized, normalized)
