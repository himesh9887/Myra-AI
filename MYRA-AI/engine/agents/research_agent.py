from __future__ import annotations

from engine.research_agent import ResearchAgent as LegacyResearchAgent

from .base_agent import BaseAgent


class ResearchAgent(BaseAgent):
    name = "research"

    def __init__(self, research=None):
        self.research = research or LegacyResearchAgent()

    def handle(self, command: str):
        return self.research.handle(command)

    def execute(self, task):
        task = self.normalize_task(task)
        action = task.action.lower()
        payload = task.payload

        if action in {"research", "collect_information", "collect", "analyze"}:
            handled, message = self.research.handle(f"research {payload}")
            return message if handled else ""
        if action in {"summarize", "summarize_results"}:
            handled, message = self.research.handle(f"summarize {payload}")
            return message if handled else ""

        handled, message = self.handle(payload)
        return message if handled else ""
