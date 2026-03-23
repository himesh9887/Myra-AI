from __future__ import annotations

import re

from engine.app_launcher import AppLauncher
from engine.system_control import SystemControl

from .base_agent import BaseAgent


class SystemAgent(BaseAgent):
    name = "system"

    def __init__(self, base_dir, system=None, apps=None):
        self.system = system or SystemControl(base_dir)
        self.apps = apps or AppLauncher()

    def handle(self, command: str):
        raw = " ".join(str(command).strip().split())
        normalized = raw.lower()
        if not normalized:
            return False, ""

        volume_percent = self.system.extract_volume_percent(normalized)
        if volume_percent is not None:
            return True, self.system.set_volume_percent(volume_percent)

        brightness_percent = self.system.extract_brightness_percent(normalized)
        if brightness_percent is not None:
            return True, self.system.set_brightness_percent(brightness_percent)

        if normalized.startswith(("open ", "launch ", "start ", "run ")):
            target = re.sub(r"^(open|launch|start|run)\s+", "", raw, flags=re.IGNORECASE).strip()
            _, message = self.apps.open_application(target)
            return True, message

        if normalized.startswith(("close ", "terminate ")):
            target = re.sub(r"^(close|terminate)\s+", "", raw, flags=re.IGNORECASE).strip()
            _, message = self.apps.close_application(target)
            return True, message

        mapping = [
            (["volume up", "increase volume"], self.system.volume_up),
            (["volume down", "decrease volume"], self.system.volume_down),
            (["mute", "silent"], self.system.mute_toggle),
            (["brightness up", "increase brightness"], self.system.increase_brightness),
            (["brightness down", "decrease brightness"], self.system.decrease_brightness),
            (["screenshot", "screen capture"], self.system.take_screenshot),
            (["shutdown", "shut down"], self.system.shutdown),
            (["restart", "reboot"], self.system.restart),
            (["sleep", "sleep mode"], self.system.sleep_mode),
            (["lock", "lock screen"], self.system.lock_system),
            (["battery"], self.system.battery_status),
            (["cpu"], self.system.cpu_usage),
            (["ram", "memory"], self.system.ram_usage),
            (["disk", "storage"], self.system.disk_usage),
            (["task manager"], self.system.open_task_manager),
            (["settings"], self.system.open_settings),
            (["switch window"], self.system.switch_window),
            (["minimize window"], self.system.minimize_current_window),
            (["maximize window", "full screen"], self.system.maximize_current_window),
        ]
        for tokens, action in mapping:
            if any(token in normalized for token in tokens):
                return True, action()
        return False, ""

    def execute(self, task):
        task = self.normalize_task(task)
        action = task.action.lower()
        payload = task.payload

        direct_actions = {
            "volume_up": self.system.volume_up,
            "volume_down": self.system.volume_down,
            "mute": self.system.mute_toggle,
            "increase_brightness": self.system.increase_brightness,
            "decrease_brightness": self.system.decrease_brightness,
            "screenshot": self.system.take_screenshot,
            "shutdown": self.system.shutdown,
            "restart": self.system.restart,
            "sleep": self.system.sleep_mode,
            "lock": self.system.lock_system,
            "battery": self.system.battery_status,
            "cpu": self.system.cpu_usage,
            "ram": self.system.ram_usage,
            "disk": self.system.disk_usage,
            "task_manager": self.system.open_task_manager,
            "settings": self.system.open_settings,
            "switch_window": self.system.switch_window,
            "minimize_window": self.system.minimize_current_window,
            "maximize_window": self.system.maximize_current_window,
        }
        if action in direct_actions:
            return direct_actions[action]()
        if action == "set_volume":
            return self.system.set_volume_percent(payload)
        if action == "set_brightness":
            return self.system.set_brightness_percent(payload)
        if action == "open_app":
            _, message = self.apps.open_application(payload)
            return message
        if action == "close_app":
            _, message = self.apps.close_application(payload)
            return message

        handled, message = self.handle(payload)
        return message if handled else ""
