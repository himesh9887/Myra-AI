from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

try:
    import pyautogui
except Exception:  # pragma: no cover
    pyautogui = None

from engine.activity_monitor import ActivityMonitor
from engine.ai_brain import OPENROUTER_API_KEY, OPENROUTER_MODEL
from engine.openrouter_client import OpenRouterClient
from engine.runtime_config import DEFAULT_SCREEN_ANALYSIS_PROMPT, load_runtime_env

load_runtime_env()


class ScreenAwareness:
    def __init__(self, base_dir, activity_monitor: ActivityMonitor | None = None):
        self.base_dir = Path(base_dir)
        self.capture_dir = self.base_dir / "captures"
        self.capture_dir.mkdir(exist_ok=True)
        self.activity_monitor = activity_monitor or ActivityMonitor()
        vision_model = str(os.getenv("OPENROUTER_VISION_MODEL") or OPENROUTER_MODEL or "openai/gpt-4o-mini").strip()
        self.client = OpenRouterClient(api_key=OPENROUTER_API_KEY, model=vision_model, timeout=30.0)
        self._last_summary = ""
        self._last_capture = ""
        self._last_error = ""

    def handle(self, command):
        if not self.is_screen_query(command):
            return False, ""
        summary, _ = self.describe_screen(command)
        return True, summary

    def is_screen_query(self, text):
        normalized = self._normalize(text)
        if not normalized:
            return False

        blocked = {
            "screenshot",
            "screen shot",
            "screen capture",
            "take screenshot",
            "capture screen",
        }
        if any(token in normalized for token in blocked):
            return False

        phrases = (
            "what is on my screen",
            "what s on my screen",
            "whats on my screen",
            "what is on screen",
            "what s on screen",
            "screen par kya chal raha hai",
            "screen pe kya chal raha hai",
            "screen pr kya chal raha hai",
            "screen par kya chal rha hai",
            "screen pe kya chal rha hai",
            "screen pr kya chal rha hai",
            "screen par kya hai",
            "screen pe kya hai",
            "screen pr kya hai",
            "display par kya hai",
            "display pe kya hai",
            "meri screen dekho",
            "my screen dekho",
            "screen check karo",
            "screen analyze karo",
            "analyze my screen",
            "analyze screen",
            "current screen summary",
            "abhi screen par kya chal raha hai",
            "abhi screen pe kya chal raha hai",
        )
        return any(phrase in normalized for phrase in phrases)

    def describe_screen(self, command=""):
        snapshot = self.activity_monitor.poll() if self.activity_monitor else None
        screenshot_path, screenshot_error = self.capture_screen()

        vision_summary = ""
        if screenshot_path and self.client.available():
            vision_summary = self._analyze_with_openrouter(command, screenshot_path, snapshot)

        local_summary = self._build_local_summary(snapshot)
        summary = vision_summary or local_summary

        if not summary and screenshot_error:
            summary = f"Boss, current screen capture nahi ho paya. {screenshot_error}"
        elif not summary:
            summary = "Boss, screen ka clear summary abhi nahi nikal paayi."

        if screenshot_path and Path(screenshot_path).exists():
            summary = f"{summary} Reference capture {Path(screenshot_path).name} me save hai."

        self._last_summary = summary
        self._last_capture = str(screenshot_path or "")
        self._last_error = str(screenshot_error or "")
        return summary, screenshot_path

    def capture_screen(self, target_path=None):
        if pyautogui is None:
            return "", "pyautogui available nahi hai."

        target = Path(target_path) if target_path else self.capture_dir / f"screen_{datetime.now():%Y%m%d_%H%M%S}.png"
        try:
            image = pyautogui.screenshot()
            image.save(target)
            return str(target), ""
        except Exception as exc:
            return "", str(exc)

    def status_snapshot(self):
        return {
            "last_summary": self._last_summary,
            "last_capture": self._last_capture,
            "last_error": self._last_error,
            "vision_enabled": self.client.available(),
        }

    def _analyze_with_openrouter(self, command, screenshot_path, snapshot):
        app_name = getattr(snapshot, "active_app", "") if snapshot else ""
        window_title = getattr(snapshot, "active_title", "") if snapshot else ""
        open_apps = ", ".join(list(getattr(snapshot, "open_apps", ()) or [])[:6])

        user_prompt = (
            f"User request: {str(command).strip() or 'Tell me what is on my current screen.'}\n"
            f"Active app hint: {app_name or 'unknown'}\n"
            f"Active window title: {window_title or 'unknown'}\n"
            f"Open apps hint: {open_apps or 'unknown'}\n"
            "Describe what is clearly visible on the current Windows screen. "
            "Mention readable text only when it is actually readable. "
            "If the screenshot is unclear, say that honestly. "
            "Keep it to 2-4 short sentences in casual Hinglish."
        )

        payload = self.client.chat_with_image(
            text_prompt=user_prompt,
            image_path=screenshot_path,
            system_prompt=DEFAULT_SCREEN_ANALYSIS_PROMPT,
            temperature=0.2,
            max_tokens=220,
        )
        text = self.client.extract_text(payload)
        return " ".join(text.split())

    def _build_local_summary(self, snapshot):
        if snapshot is None:
            return ""

        active_app = str(getattr(snapshot, "active_app", "") or "").strip()
        active_title = str(getattr(snapshot, "active_title", "") or "").strip()
        open_apps = list(getattr(snapshot, "open_apps", ()) or [])

        open_preview = ", ".join(open_apps[:5])
        if active_title and active_app:
            return (
                f"Boss, abhi {active_app} active lag raha hai aur front window `{active_title}` dikh rahi hai. "
                f"Background me {open_preview or 'kuch aur apps'} khule hue lag rahe hain."
            )
        if active_title:
            return f"Boss, front par `{active_title}` wali window dikh rahi hai."
        if active_app:
            return f"Boss, abhi active app {active_app} lag rahi hai."
        if open_preview:
            return f"Boss, open apps me {open_preview} dikh rahe hain."
        return ""

    def _normalize(self, text):
        normalized = str(text).lower().strip()
        normalized = re.sub(r"[^\w\s']", " ", normalized)
        return " ".join(normalized.split())
