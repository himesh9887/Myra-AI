import os
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path

import pyautogui

try:
    import winreg
except ImportError:  # pragma: no cover
    winreg = None

try:
    import winapps
except ImportError:  # pragma: no cover
    winapps = None


class AppLauncher:
    def __init__(self):
        self.app_index = {}

    def refresh_index(self):
        index = {}
        self._scan_start_menu(index)
        self._scan_program_files(index)
        self._scan_registry(index)
        self._scan_path(index)
        self.app_index = index

    def open_application(self, query):
        normalized = self._normalize_name(query)
        if not normalized:
            return False, "Sir ji, app name clear nahi hai."

        target = self._match_application(normalized)
        if not target:
            self.refresh_index()
            target = self._match_application(normalized)

        if target:
            ok, message = self._launch_target(target, query)
            if ok:
                return True, message

        ok, message = self._launch_direct_command(normalized)
        if ok:
            return True, message

        ok, message = self._launch_from_installed_apps(normalized)
        if ok:
            return True, message

        ok, message = self.windows_search(query)
        if ok:
            return True, message

        ok, message = self.google_search(query)
        if ok:
            return True, message

        return True, "Sir ji, opening application."

    def available_apps(self):
        return sorted(item["display_name"] for item in self.app_index.values())

    def close_application(self, query):
        normalized = self._normalize_name(query)
        if not normalized:
            return False, "Boss, app name clear nahi hai."

        target = self._match_application(normalized)
        image_name = None
        if target and target["kind"] == "path":
            image_name = Path(target["launcher"]).name
        elif target and target["kind"] == "command":
            image_name = Path(target["launcher"][0]).name
        else:
            token = normalized.split()[0]
            image_name = f"{token}.exe"

        try:
            subprocess.run(["taskkill", "/IM", image_name, "/F"], check=False)
        except Exception as exc:
            return False, f"Boss, {query.title()} band nahi ho paya. {exc}"
        return True, f"Boss, {query.title()} close command execute ho gaya hai."

    def kill_process(self, process_name):
        token = self._normalize_name(process_name).split()[0]
        if not token:
            return False, "Sir ji, process name clear nahi hai."
        image_name = token if token.endswith(".exe") else f"{token}.exe"
        try:
            subprocess.run(["taskkill", "/IM", image_name, "/F"], check=False)
        except Exception as exc:
            return False, f"Sir ji, {image_name} kill nahi ho paya. {exc}"
        return True, f"Sir ji, {image_name} kill command execute ho gaya hai."

    def _match_application(self, normalized):
        if normalized in self.app_index:
            return self.app_index[normalized]

        for key, value in self.app_index.items():
            if normalized in key or key in normalized:
                return value
        return None

    def _scan_start_menu(self, index):
        start_menu_dirs = [
            Path(os.environ.get("ProgramData", "")) / "Microsoft/Windows/Start Menu/Programs",
            Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        ]
        for folder in start_menu_dirs:
            if not folder.exists():
                continue
            for shortcut in folder.rglob("*.lnk"):
                name = self._normalize_name(shortcut.stem)
                index.setdefault(
                    name,
                    {
                        "display_name": shortcut.stem,
                        "kind": "path",
                        "launcher": str(shortcut),
                    },
                )

    def _scan_program_files(self, index):
        root_values = [
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.path.join(os.environ.get("LocalAppData", ""), "Programs")
            if os.environ.get("LocalAppData")
            else "",
        ]
        for root_value in root_values:
            if not root_value:
                continue
            root = Path(root_value)
            if not root.exists():
                continue

            for exe in root.rglob("*.exe"):
                try:
                    if len(exe.parts) - len(root.parts) > 3:
                        continue
                except Exception:
                    continue
                name = self._normalize_name(exe.stem)
                index.setdefault(
                    name,
                    {
                        "display_name": exe.stem,
                        "kind": "path",
                        "launcher": str(exe),
                    },
                )

    def _scan_registry(self, index):
        if winreg is None:
            return

        registry_roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        ]

        for hive, path in registry_roots:
            try:
                with winreg.OpenKey(hive, path) as key:
                    total = winreg.QueryInfoKey(key)[0]
                    for item_index in range(total):
                        subkey_name = winreg.EnumKey(key, item_index)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            value, _ = winreg.QueryValueEx(subkey, None)
                            exe_path = Path(value)
                            display_name = exe_path.stem or Path(subkey_name).stem
                            name = self._normalize_name(display_name)
                            index.setdefault(
                                name,
                                {
                                    "display_name": display_name,
                                    "kind": "path",
                                    "launcher": str(exe_path),
                                },
                            )
            except OSError:
                continue

    def _scan_path(self, index):
        for app_name in ["chrome", "code", "notepad", "calc", "taskmgr", "spotify"]:
            resolved = shutil.which(app_name)
            if not resolved:
                continue
            display_name = Path(resolved).stem
            name = self._normalize_name(display_name)
            index.setdefault(
                name,
                {
                    "display_name": display_name,
                    "kind": "command",
                    "launcher": [resolved],
                },
            )

    def _normalize_name(self, value):
        cleaned = value.lower().strip()
        for token in ["(", ")", "-", "_", ".exe", ".lnk"]:
            cleaned = cleaned.replace(token, " ")
        return " ".join(cleaned.split())

    def _launch_target(self, target, query):
        try:
            launcher = target["launcher"]
            if target["kind"] == "path":
                os.startfile(launcher)
            else:
                subprocess.Popen(launcher, shell=False)
            return True, f"Opening {target['display_name']}."
        except Exception as exc:
            return False, f"Sir ji, {query.title()} open nahi ho paya. {exc}"

    def _launch_direct_command(self, normalized):
        tokens = [part for part in normalized.split() if part]
        if not tokens:
            return False, ""

        candidates = []
        first = tokens[0]
        aliases = {
            "vscode": "code",
            "vs": "code",
            "calculator": "calc",
        }
        candidates.append(aliases.get(first, first))
        if normalized.replace(" ", "") != candidates[0]:
            candidates.append(normalized.replace(" ", ""))

        for candidate in candidates:
            resolved = shutil.which(candidate)
            if not resolved:
                continue
            try:
                subprocess.Popen([resolved], shell=False)
                return True, f"Opening {Path(resolved).stem}."
            except Exception:
                continue
        return False, ""

    def _launch_from_installed_apps(self, normalized):
        if winapps is None:
            return False, ""

        try:
            for app in winapps.list_installed():
                name = self._normalize_name(getattr(app, "name", ""))
                if not name:
                    continue
                if normalized in name or name in normalized:
                    return self.windows_search(getattr(app, "name", normalized))
        except Exception:
            return False, ""

        return False, ""

    def windows_search(self, app_name):
        try:
            pyautogui.press("win")
            time.sleep(1)
            pyautogui.write(str(app_name), interval=0.03)
            time.sleep(1)
            pyautogui.press("enter")
            return True, f"Opening {app_name}."
        except Exception:
            return False, ""

    def google_search(self, query):
        try:
            webbrowser.open(
                "https://www.google.com/search?q=" + str(query).strip().replace(" ", "+"),
                new=0,
                autoraise=False,
            )
            return True, "Searching on Google."
        except Exception:
            return False, ""
