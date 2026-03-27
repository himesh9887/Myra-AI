from __future__ import annotations

from engine.netcontrol_bridge import NetControlBridge

from .base_agent import BaseAgent


class NetControlAgent(BaseAgent):
    name = "netcontrol"

    def __init__(self, base_dir, bridge=None):
        self.bridge = bridge or NetControlBridge(base_dir)

    def handle(self, command: str):
        raw = " ".join(str(command).strip().split())
        normalized = raw.lower()
        if not normalized or not self.should_claim_input(normalized):
            return False, ""
        return self.bridge.handle_command(raw)

    def execute(self, task):
        task = self.normalize_task(task)
        action = task.action.lower()
        payload = task.payload

        if action == "open_dashboard":
            handled, message = self.bridge.open_dashboard()
            return message if handled else ""

        if action == "status":
            handled, message = self.bridge.handle_command("check network")
            return message if handled else ""

        if action in {"handle", "command", "run"}:
            handled, message = self.handle(payload)
            return message if handled else ""

        handled, message = self.handle(payload or action.replace("_", " "))
        return message if handled else ""

    def should_claim_input(self, command: str) -> bool:
        normalized = " ".join(str(command).strip().split()).lower()
        if self.bridge.should_claim_input(normalized):
            return True
        return self._looks_like_netcontrol(normalized)

    def _looks_like_netcontrol(self, normalized: str) -> bool:
        if normalized == "show logs":
            return True
        if normalized.startswith("block site "):
            return True
        if "focus mode" in normalized:
            return True
        if "vision monitor" in normalized or "vision monitoring" in normalized:
            return True
        if "study mode" in normalized or "study mood" in normalized:
            return True
        if "netcontrol" in normalized:
            return True
        if normalized in {"internet on", "internet off"}:
            return True
        return any(
            token in normalized
            for token in (
                "check network",
                "network status",
                "internet status",
                "internet speed",
                "wifi status",
                "scan wifi",
                "wifi scan",
                "network ping",
            )
        )
