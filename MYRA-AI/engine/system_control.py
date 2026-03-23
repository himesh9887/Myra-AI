import ctypes
import os
import re
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pyautogui

try:
    import screen_brightness_control as sbc
except Exception:  # pragma: no cover
    sbc = None


class SystemControl:
    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)

    def volume_up(self):
        pyautogui.press("volumeup")
        return "Boss, volume up ho gaya hai."

    def volume_down(self):
        pyautogui.press("volumedown")
        return "Boss, volume down ho gaya hai."

    def mute_toggle(self):
        pyautogui.press("volumemute")
        return "Boss, mute toggle complete ho gaya hai."

    def set_volume_percent(self, percent):
        try:
            target = int(percent)
        except (TypeError, ValueError):
            return "Boss, volume percentage clear nahi hai."

        target = max(0, min(100, target))

        # Windows volume key steps are coarse, so reset low first and then step up.
        for _ in range(60):
            pyautogui.press("volumedown")
            time.sleep(0.01)

        if target == 0:
            return "Boss, volume 0 percent set ho gaya hai."

        steps = max(0, min(50, round(target / 2)))
        for _ in range(steps):
            pyautogui.press("volumeup")
            time.sleep(0.01)

        return f"Boss, volume {target} percent ke aas paas set ho gaya hai."

    def increase_brightness(self, step=10):
        if sbc is None:
            return "Boss, brightness control ke liye screen_brightness_control install karna padega."
        try:
            current = sbc.get_brightness()
            current_value = int(current[0] if isinstance(current, list) else current)
            sbc.set_brightness(max(0, min(100, current_value + int(step))))
            return "Boss, brightness increase ho gayi hai."
        except Exception as exc:
            return f"Boss, brightness increase nahi ho payi. {exc}"

    def decrease_brightness(self, step=10):
        return self.set_brightness_percent(max(0, self._current_brightness() - int(step)))

    def set_brightness_percent(self, percent):
        if sbc is None:
            return "Boss, brightness control ke liye screen_brightness_control install karna padega."
        try:
            sbc.set_brightness(max(0, min(100, int(percent))))
            return "Boss, brightness set ho gayi hai."
        except Exception as exc:
            return f"Boss, brightness set nahi ho payi. {exc}"

    def extract_volume_percent(self, command):
        patterns = [
            r"volume\s+(\d{1,3})\s*%",
            r"volume\s+ko\s+(\d{1,3})\s*%",
            r"volume\s+(\d{1,3})\s*percent",
            r"volume\s+ko\s+(\d{1,3})\s*percent",
            r"set volume(?: to)?\s+(\d{1,3})",
            r"make volume\s+(\d{1,3})",
            r"volume\s+ko\s+(\d{1,3})\s*(?:%|percent)?\s*(?:karna|kar do|kardo|kar dena)?",
            r"volume\s+(\d{1,3})\s*(?:%|percent)?\s*(?:kr do|kar do|kardo|krde|kar dena)?",
            r"awaz\s+(\d{1,3})\s*(?:%|percent)?\s*(?:kr do|kar do|kardo|krde|kar dena)?",
            r"sound\s+(\d{1,3})\s*(?:%|percent)?\s*(?:kr do|kar do|kardo|krde|kar dena)?",
            r"(\d{1,3})\s*%\s*(?:volume|sound|awaz)",
            r"(\d{1,3})\s*percent\s*(?:volume|sound|awaz)",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return int(match.group(1))
        return None

    def extract_brightness_percent(self, command):
        patterns = [
            r"brightness\s+(\d{1,3})\s*%",
            r"brightness\s+(\d{1,3})\s*percent",
            r"brightness\s+ko\s+(\d{1,3})\s*(?:%|percent)?\s*(?:kar do|kr do|kardo|krde|kar dena)?",
            r"brightness\s+(\d{1,3})\s*(?:%|percent)?\s*(?:kar do|kr do|kardo|krde|kar dena)?",
            r"screen brightness\s+(\d{1,3})",
            r"light\s+(\d{1,3})\s*(?:%|percent)?",
            r"(\d{1,3})\s*%\s*brightness",
            r"(\d{1,3})\s*percent\s*brightness",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return int(match.group(1))
        return None

    def take_screenshot(self):
        target = self.base_dir / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        image = pyautogui.screenshot()
        image.save(target)
        return f"Boss, screenshot save ho gaya hai as {target.name}."

    def lock_system(self):
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=False)
        return "Boss, system lock command execute ho gaya hai."

    def shutdown(self):
        subprocess.run(["shutdown", "/s", "/t", "5"], check=False)
        return "Boss, system shutdown 5 seconds me hoga."

    def restart(self):
        subprocess.run(["shutdown", "/r", "/t", "5"], check=False)
        return "Boss, system restart 5 seconds me hoga."

    def sleep_mode(self):
        ctypes.windll.powrprof.SetSuspendState(False, True, False)
        return "Boss, system sleep mode me ja raha hai."

    def battery_status(self):
        try:
            import psutil
        except ImportError:
            return "Boss, battery check ke liye psutil install karna padega."

        battery = psutil.sensors_battery()
        if battery is None:
            return "Boss, battery information available nahi hai."

        state = "charging" if battery.power_plugged else "not charging"
        return f"Boss, battery {int(battery.percent)} percent hai and system is {state}."

    def wifi_status(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2).close()
            return "Boss, WiFi ya internet connection active hai."
        except OSError:
            return "Boss, WiFi ya internet connection currently unavailable hai."

    def cpu_usage(self):
        try:
            import psutil
        except ImportError:
            return "Boss, CPU usage ke liye psutil install karna padega."
        value = psutil.cpu_percent(interval=0.4)
        return f"Boss, CPU usage {value:.0f} percent hai."

    def ram_usage(self):
        try:
            import psutil
        except ImportError:
            return "Boss, RAM usage ke liye psutil install karna padega."
        memory = psutil.virtual_memory()
        return f"Boss, RAM usage {memory.percent:.0f} percent hai."

    def disk_usage(self):
        try:
            import psutil
        except ImportError:
            return "Boss, disk usage ke liye psutil install karna padega."
        disk = psutil.disk_usage(str(Path.home().anchor or "C:\\"))
        return f"Boss, disk usage {disk.percent:.0f} percent hai."

    def system_status(self):
        parts = [
            self.cpu_usage(),
            self.ram_usage(),
            self.battery_status(),
            self.network_status(),
        ]
        return " ".join(parts)

    def _current_brightness(self):
        if sbc is None:
            return 50
        try:
            current = sbc.get_brightness()
            return int(current[0] if isinstance(current, list) else current)
        except Exception:
            return 50

    def network_status(self):
        return self.wifi_status()

    def internet_speed(self):
        try:
            import speedtest
        except ImportError:
            return "Boss, speed check ke liye speedtest-cli install karna padega."

        try:
            tester = speedtest.Speedtest()
            download = tester.download() / 1_000_000
            upload = tester.upload() / 1_000_000
            return f"Boss, download {download:.1f} Mbps aur upload {upload:.1f} Mbps hai."
        except Exception as exc:
            return f"Boss, internet speed check fail ho gaya. {exc}"

    def date_time_status(self):
        now = datetime.now()
        return f"Boss, abhi {now:%I:%M %p} ho raha hai aur aaj {now:%A, %d %B %Y} hai."

    def open_task_manager(self):
        subprocess.Popen(["taskmgr.exe"])
        return "Boss, Task Manager open ho gaya hai."

    def open_settings(self):
        os.startfile("ms-settings:")
        return "Boss, Windows Settings open ho gayi hai."

    def switch_window(self):
        pyautogui.hotkey("alt", "tab")
        return "Boss, window switch ho gaya hai."

    def minimize_current_window(self):
        pyautogui.hotkey("win", "down")
        return "Boss, current window minimize command execute ho gaya hai."

    def maximize_current_window(self):
        pyautogui.hotkey("win", "up")
        return "Boss, current window maximize command execute ho gaya hai."

    def open_known_folder(self, folder_name):
        mapping = {
            "desktop": Path.home() / "Desktop",
            "downloads": Path.home() / "Downloads",
            "documents": Path.home() / "Documents",
        }
        target = mapping.get(folder_name.lower())
        if not target or not target.exists():
            return "Boss, yeh folder available nahi hai."
        try:
            os.startfile(str(target))
            return f"Boss, {folder_name.title()} folder open ho gaya hai."
        except PermissionError:
            return f"Boss, {folder_name.title()} folder access nahi ho pa raha."
        except OSError as exc:
            return f"Boss, {folder_name.title()} folder open nahi ho paya. {exc}"
