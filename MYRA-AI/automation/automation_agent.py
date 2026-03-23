from __future__ import annotations

from engine.automation import DesktopAutomation


class AutomationController:
    def __init__(self):
        self.desktop = DesktopAutomation()

    def handle(self, command):
        handled, message = self.desktop.handle(command)
        return handled, message

    def execute(self, task):
        payload = task if isinstance(task, str) else str(task.get("payload", "") or task.get("goal", "")).strip()
        handled, message = self.handle(payload)
        return message if handled else "Boss, automation command clear nahi hai."

    def execute_macro(self, macro_name: str):
        macros = {
            "switch_window": "press hotkey alt tab",
            "copy_paste": "press hotkey ctrl c",
        }
        payload = macros.get(str(macro_name).strip().lower(), "")
        if not payload:
            return "Boss, macro available nahi hai."
        handled, message = self.handle(payload)
        return message if handled else "Boss, macro run nahi ho paya."
