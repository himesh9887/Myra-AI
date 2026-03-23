from __future__ import annotations

from engine.download_agent import DownloadAgent as LegacyDownloadAgent

from .base_agent import BaseAgent


class DownloadAgent(BaseAgent):
    name = "download"

    def __init__(self, download=None):
        self.download = download or LegacyDownloadAgent()

    def handle(self, command: str):
        return self.download.handle(command)

    def execute(self, task):
        task = self.normalize_task(task)
        action = task.action.lower()
        payload = task.payload

        if action in {"download", "download_file", "download_url"}:
            return self.download_file(payload)
        if action in {"download_search_result", "download_search", "search_download"}:
            return self.download_search_result(payload)

        handled, message = self.handle(payload)
        return message if handled else ""

    def download_file(self, url: str):
        return self.download.download_url(url)

    def download_search_result(self, query: str):
        return self.download.search_download(query)
