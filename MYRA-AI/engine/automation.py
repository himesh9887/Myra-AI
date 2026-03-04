import re
import time

import pyautogui

try:
    import pygetwindow as gw
except ImportError:  # pragma: no cover
    gw = None

try:
    import pyperclip
except ImportError:  # pragma: no cover
    pyperclip = None


class DesktopAutomation:
    def handle(self, command):
        normalized = command.lower().strip()

        move_match = re.search(r"(?:move mouse to|mouse to)\s+(\d+)\s*(?:,|\s)\s*(\d+)", normalized)
        if move_match:
            return True, self.move_mouse(int(move_match.group(1)), int(move_match.group(2)))

        drag_match = re.search(r"(?:drag mouse to|drag to)\s+(\d+)\s*(?:,|\s)\s*(\d+)", normalized)
        if drag_match:
            return True, self.drag_mouse(int(drag_match.group(1)), int(drag_match.group(2)))

        scroll_match = re.search(r"scroll\s+(up|down)(?:\s+(\d+))?", normalized)
        if scroll_match:
            direction = scroll_match.group(1)
            amount = int(scroll_match.group(2) or 500)
            return True, self.scroll(direction, amount)

        hotkey_match = re.search(r"(?:press hotkey|shortcut|press shortcut)\s+(.+)", normalized)
        if hotkey_match:
            return True, self.press_hotkey(hotkey_match.group(1))

        press_match = re.search(r"(?:press key|press)\s+([a-z0-9]+)", normalized)
        if press_match:
            return True, self.press_key(press_match.group(1))

        type_match = re.search(r"(?:type text|type)\s+(.+)", command, re.IGNORECASE)
        if type_match:
            return True, self.type_text(type_match.group(1))

        if "right click" in normalized:
            return True, self.click("right")
        if "double click" in normalized:
            return True, self.click("double")
        if "left click" in normalized or normalized == "click":
            return True, self.click("left")

        if "copy" == normalized or "copy that" in normalized:
            return True, self.copy()
        if "paste" == normalized or "paste here" in normalized:
            return True, self.paste()

        if "mouse position" in normalized or "cursor position" in normalized:
            return True, self.mouse_position()

        if "list windows" in normalized or "show open windows" in normalized:
            return True, self.list_windows()

        activate_match = re.search(r"(?:activate|focus|switch to)\s+window\s+(.+)", normalized)
        if activate_match:
            return True, self.activate_window(activate_match.group(1))

        close_match = re.search(r"(?:close)\s+window\s+(.+)", normalized)
        if close_match:
            return True, self.close_window(close_match.group(1))

        resize_match = re.search(
            r"(?:resize)\s+window\s+(.+?)\s+(?:to)\s+(\d+)\s*(?:x|by)\s*(\d+)",
            normalized,
        )
        if resize_match:
            return True, self.resize_window(
                resize_match.group(1),
                int(resize_match.group(2)),
                int(resize_match.group(3)),
            )

        return False, ""

    def move_mouse(self, x, y):
        pyautogui.moveTo(x, y, duration=0.25)
        return f"Sir ji, mouse {x}, {y} position par aa gaya hai."

    def drag_mouse(self, x, y):
        pyautogui.dragTo(x, y, duration=0.4, button="left")
        return f"Sir ji, drag and drop {x}, {y} tak complete ho gaya hai."

    def scroll(self, direction, amount):
        delta = amount if direction == "up" else -amount
        pyautogui.scroll(delta)
        return f"Sir ji, scroll {direction} command execute ho gaya hai."

    def click(self, button):
        if button == "double":
            pyautogui.doubleClick()
            return "Sir ji, double click complete ho gaya hai."
        pyautogui.click(button=button)
        return f"Sir ji, {button} click complete ho gaya hai."

    def type_text(self, text):
        payload = text.strip().strip('"').strip("'")
        if not payload:
            return "Sir ji, type karne ke liye text clear nahi hai."
        pyautogui.write(payload, interval=0.02)
        return "Sir ji, text type ho gaya hai."

    def press_hotkey(self, expression):
        keys = [self._normalize_key(part) for part in re.split(r"[\s+]+", expression) if part.strip()]
        if not keys:
            return "Sir ji, hotkey clear nahi hai."
        pyautogui.hotkey(*keys)
        return f"Sir ji, {' + '.join(keys)} shortcut execute ho gaya hai."

    def press_key(self, key_name):
        key = self._normalize_key(key_name)
        pyautogui.press(key)
        return f"Sir ji, {key} key press ho gayi hai."

    def copy(self):
        pyautogui.hotkey("ctrl", "c")
        return "Sir ji, copy shortcut execute ho gaya hai."

    def paste(self):
        pyautogui.hotkey("ctrl", "v")
        return "Sir ji, paste shortcut execute ho gaya hai."

    def mouse_position(self):
        x, y = pyautogui.position()
        return f"Sir ji, current cursor position {x}, {y} hai."

    def list_windows(self):
        if gw is None:
            return "Sir ji, open window detection ke liye pygetwindow install karna padega."
        titles = [title.strip() for title in gw.getAllTitles() if title and title.strip()]
        if not titles:
            return "Sir ji, abhi koi titled window detect nahi hui."
        preview = " | ".join(titles[:5])
        return f"Sir ji, active windows: {preview}"

    def activate_window(self, title):
        window = self._match_window(title)
        if not window:
            return f"Sir ji, {title} window mujhe nahi mili."
        try:
            if window.isMinimized:
                window.restore()
                time.sleep(0.1)
            window.activate()
            return f"Sir ji, {window.title} window focus me aa gayi hai."
        except Exception as exc:
            return f"Sir ji, window activate nahi ho payi. {exc}"

    def close_window(self, title):
        window = self._match_window(title)
        if not window:
            return f"Sir ji, {title} window mujhe nahi mili."
        try:
            window.close()
            return f"Sir ji, {window.title} window close command execute ho gaya hai."
        except Exception as exc:
            return f"Sir ji, window close nahi ho payi. {exc}"

    def resize_window(self, title, width, height):
        window = self._match_window(title)
        if not window:
            return f"Sir ji, {title} window mujhe nahi mili."
        try:
            window.resizeTo(width, height)
            return f"Sir ji, {window.title} window resize ho gayi hai."
        except Exception as exc:
            return f"Sir ji, window resize nahi ho payi. {exc}"

    def clipboard_text(self):
        if pyperclip is None:
            return ""
        try:
            return pyperclip.paste()
        except Exception:
            return ""

    def _match_window(self, title):
        if gw is None:
            return None
        query = title.strip().lower()
        for window in gw.getAllWindows():
            label = getattr(window, "title", "").strip()
            if label and query in label.lower():
                return window
        return None

    def _normalize_key(self, key_name):
        mapping = {
            "control": "ctrl",
            "return": "enter",
            "escape": "esc",
            "windows": "win",
            "command": "win",
        }
        return mapping.get(key_name.strip().lower(), key_name.strip().lower())
