from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentTask:
    action: str
    payload: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    name = "base"

    def handle(self, command: str):
        raise NotImplementedError

    def execute(self, task: AgentTask | dict | str):
        raise NotImplementedError

    def normalize_task(self, task: AgentTask | dict | str, default_action: str = "handle") -> AgentTask:
        if isinstance(task, AgentTask):
            return task
        if isinstance(task, dict):
            action = str(task.get("action", default_action) or default_action).strip()
            payload = str(task.get("payload", "") or "").strip()
            meta = dict(task.get("meta", {}) or {})
            return AgentTask(action=action, payload=payload, meta=meta)
        return AgentTask(action=default_action, payload=str(task or "").strip(), meta={})
