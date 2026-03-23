from __future__ import annotations

from engine.web_control import WebControl
from engine.youtube_agent import YouTubeAgent as LegacyYouTubeAgent

from .base_agent import BaseAgent


class YouTubeAgent(BaseAgent):
    name = "youtube"

    def __init__(self, youtube=None, web=None):
        self.youtube = youtube or LegacyYouTubeAgent()
        self.web = web or WebControl()

    def handle(self, command: str):
        return self.youtube.handle(command)

    def execute(self, task):
        task = self.normalize_task(task)
        action = task.action.lower()
        payload = task.payload

        if action in {"search_youtube", "search"}:
            return self.search_youtube(payload)
        if action in {"play", "play_video"}:
            return self.play_video(payload)
        if action in {"open", "open_youtube"}:
            handled, message = self.web.handle("open youtube")
            return message if handled else "Boss, YouTube open nahi ho paya."

        handled, message = self.handle(payload)
        return message if handled else ""

    def search_youtube(self, video: str):
        query = str(video).strip()
        if not query:
            return "Boss, YouTube search query clear nahi hai."
        handled, message = self.web.handle(f"youtube search {query}")
        return message if handled else f"Boss, {query} ke liye YouTube search open nahi ho paya."

    def play_video(self, video: str):
        query = str(video).strip()
        if not query:
            return "Boss, YouTube par kya play karna hai?"
        handled, message = self.youtube.handle(f"play {query}")
        return message if handled else self.search_youtube(query)
