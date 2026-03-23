from __future__ import annotations

import re
import webbrowser
from urllib.parse import quote_plus

from engine.ai_brain import ask_ai
from engine.browser_agent import BrowserAgent as LegacyBrowserAgent
from engine.web_control import WebControl

from .base_agent import BaseAgent


class BrowserAgent(BaseAgent):
    name = "browser"

    def __init__(self, browser=None, web=None):
        self.browser = browser or LegacyBrowserAgent()
        self.web = web or WebControl()

    def handle(self, command: str):
        raw = " ".join(str(command).strip().split())
        if not raw:
            return False, ""

        handled, message = self.web.handle(raw)
        if handled:
            return True, message

        handled, message = self.browser.handle(raw)
        if handled:
            return True, message

        normalized = raw.lower()
        if normalized.startswith("open website "):
            return True, self.open_website(raw[len("open website ") :].strip())
        if normalized.startswith("open site "):
            return True, self.open_website(raw[len("open site ") :].strip())
        if normalized.startswith("summarize page "):
            return True, self.summarize_page(raw[len("summarize page ") :].strip())
        return False, ""

    def execute(self, task):
        task = self.normalize_task(task)
        action = task.action.lower()
        payload = task.payload

        if action in {"search", "search_google", "google_search"}:
            return self.search_google(payload)
        if action in {"open", "open_site", "open_website"}:
            return self.open_website(payload)
        if action in {"summarize", "summarize_page"}:
            return self.summarize_page(payload)

        handled, message = self.handle(payload)
        return message if handled else ""

    def search_google(self, query: str):
        query = str(query).strip()
        if not query:
            return "Boss, search query clear nahi hai."
        return self.browser.search(query)

    def open_website(self, target: str):
        value = str(target).strip()
        if not value:
            return "Boss, website target clear nahi hai."

        handled, message = self.web.handle(f"open {value}")
        if handled:
            return message

        site = value if re.match(r"^https?://", value, flags=re.IGNORECASE) else f"https://{value}"
        try:
            webbrowser.open(site, new=0, autoraise=False)
            return f"Boss, website {value} open kar di hai."
        except Exception as exc:
            return f"Boss, website open nahi ho payi. {exc}"

    def summarize_page(self, target: str = ""):
        topic = str(target).strip() or "the current topic"
        prompt = (
            "Summarize this topic for Boss in 3 short casual Hinglish sentences. "
            "Keep it natural and friend-like, not formal. "
            f"Topic or page target: {topic}"
        )
        summary = ask_ai(prompt)
        if not summary:
            return f"Boss, {topic} ke liye short summary abhi ready nahi ho paayi."
        if summary.startswith("LOCAL_FALLBACK::"):
            summary = summary.replace("LOCAL_FALLBACK::", "", 1).strip()
        return f"Boss, short summary for {topic}: {summary}"
