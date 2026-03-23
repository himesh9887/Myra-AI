from __future__ import annotations

import re

from engine.app_launcher import AppLauncher

from .base_agent import BaseAgent


class AppAgent(BaseAgent):
    name = "app"

    def __init__(self, apps=None):
        self.apps = apps or AppLauncher()

    def handle(self, command: str):
        raw = " ".join(str(command).strip().split())
        normalized = raw.lower()
        if not normalized:
            return False, ""

        if normalized.startswith(("open ", "launch ", "start ", "run ")):
            target = re.sub(r"^(open|launch|start|run)\s+", "", raw, flags=re.IGNORECASE).strip()
            _, message = self.apps.open_application(target)
            return True, message

        if normalized.startswith(("close ", "terminate ")):
            target = re.sub(r"^(close|terminate)\s+", "", raw, flags=re.IGNORECASE).strip()
            _, message = self.apps.close_application(target)
            return True, message

        return False, ""

    def execute(self, task):
        task = self.normalize_task(task)
        action = task.action.lower()
        payload = task.payload

        if action in {"open", "open_app", "launch_app"}:
            _, message = self.apps.open_application(payload)
            return message
        if action in {"close", "close_app", "terminate_app"}:
            _, message = self.apps.close_application(payload)
            return message

        handled, message = self.handle(payload)
        return message if handled else ""
