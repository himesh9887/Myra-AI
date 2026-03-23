from __future__ import annotations

from automation.automation_agent import AutomationController
from agents.base_agent import BaseAgent


class AutomationAgent(BaseAgent):
    name = "automation"

    def __init__(self, controller=None):
        self.controller = controller or AutomationController()

    def handle(self, command: str):
        return self.controller.handle(command)

    def execute(self, task):
        task = self.normalize_task(task)
        action = task.action.lower()
        if action in {"macro", "execute_macro"}:
            return self.controller.execute_macro(task.payload)
        return self.controller.execute(task.payload)
