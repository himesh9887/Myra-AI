import re

import screen_brightness_control as sbc


class BrightnessControl:
    def handle(self, command):
        normalized = str(command).lower().strip()

        level = self._extract_percent(normalized)
        if level is not None:
            return True, self.set_brightness(level)

        if "increase brightness" in normalized or "brightness up" in normalized:
            return True, self.change_brightness(10)

        if "decrease brightness" in normalized or "brightness down" in normalized:
            return True, self.change_brightness(-10)

        return False, ""

    def set_brightness(self, percent):
        try:
            value = max(0, min(100, int(percent)))
            sbc.set_brightness(value)
            return "Brightness adjusted."
        except Exception as exc:
            return f"Sir ji, brightness set nahi ho payi. {exc}"

    def change_brightness(self, delta):
        try:
            current = sbc.get_brightness()
            if isinstance(current, list):
                current_value = int(current[0])
            else:
                current_value = int(current)
            target = max(0, min(100, current_value + delta))
            sbc.set_brightness(target)
            return "Brightness adjusted."
        except Exception as exc:
            return f"Sir ji, brightness adjust nahi ho payi. {exc}"

    def _extract_percent(self, command):
        patterns = [
            r"brightness\s+(\d{1,3})\s*percent",
            r"brightness\s+(\d{1,3})\s*%",
            r"set brightness(?: to)?\s+(\d{1,3})",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return int(match.group(1))
        return None
