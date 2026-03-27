from __future__ import annotations

import atexit
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


class NetControlBridge:
    def __init__(self, base_dir, host: str = "127.0.0.1", port: int = 5127):
        self.base_dir = Path(base_dir)
        self.host = host
        self.port = int(port)
        self.server_script = self.base_dir / "netcontrol_server.js"
        self._process = None
        self.awaiting_study_unlock = False
        self.awaiting_study_duration = False
        self.study_mode_active = False
        self.study_pending_action = ""
        atexit.register(self.shutdown)

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def ensure_server(self, timeout_seconds: float = 6.0) -> bool:
        if self._server_ready():
            return True

        if not self.server_script.exists():
            return False

        if self._process is None or self._process.poll() is not None:
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            environment = os.environ.copy()
            environment.setdefault("MYRA_NETCONTROL_HOST", self.host)
            environment.setdefault("MYRA_NETCONTROL_PORT", str(self.port))
            try:
                self._process = subprocess.Popen(
                    ["node", str(self.server_script)],
                    cwd=str(self.base_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=creationflags,
                    env=environment,
                )
            except OSError:
                return False

        deadline = time.time() + max(1.0, float(timeout_seconds))
        while time.time() < deadline:
            if self._server_ready():
                return True
            time.sleep(0.2)
        return False

    def handle_command(self, command: str):
        normalized = " ".join(str(command or "").strip().split())
        if not normalized:
            return False, ""

        if not self.ensure_server():
            return False, "Boss, NetControl backend start nahi ho pa raha."

        try:
            payload = self.request("POST", "/api/netcontrol/command", {"command": normalized})
        except Exception as exc:  # pragma: no cover
            return False, f"Boss, NetControl se baat nahi ho pa rahi. {exc}"

        open_url = str(payload.get("openUrl", "")).strip()
        if open_url:
            webbrowser.open(open_url, new=0, autoraise=False)

        return bool(payload.get("handled", False)), str(payload.get("message", "")).strip()

    def open_dashboard(self):
        if not self.ensure_server():
            return False, "Boss, dashboard ke liye NetControl server ready nahi ho pa raha."
        url = f"{self.base_url}/dashboard/netcontrol"
        webbrowser.open(url, new=0, autoraise=False)
        return True, "Boss, NetControl dashboard browser me ready hai."

    def status_snapshot(self, refresh: bool = True):
        if refresh and self.ensure_server():
            try:
                return self.request("GET", "/api/netcontrol/status", timeout=1.5)
            except Exception:
                pass
        return {
            "studyMode": self.study_mode_active,
            "studyUnlockPending": self.awaiting_study_unlock,
            "studyDurationPending": self.awaiting_study_duration,
            "pendingAction": self.study_pending_action,
        }

    def add_log(self, message: str):
        text = str(message or "").strip()
        if not text or not self.ensure_server():
            return {}
        try:
            return self.request("POST", "/api/netcontrol/log", {"message": text}, timeout=1.5)
        except Exception:
            return {}

    def request(self, method: str, route: str, payload=None, timeout: float = 3.0):
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.base_url}{route}",
            data=body,
            headers=headers,
            method=str(method).upper(),
        )

        try:
            with urllib.request.urlopen(request, timeout=max(0.5, float(timeout))) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            try:
                payload = json.loads(raw) if raw else {}
            except ValueError as parse_error:
                raise RuntimeError(raw or str(exc)) from parse_error
            self._sync_state(payload)
            message = payload.get("error") or payload.get("message") or str(exc)
            raise RuntimeError(message) from exc

        payload = json.loads(raw) if raw else {}
        self._sync_state(payload)
        return payload

    def should_claim_input(self, command: str) -> bool:
        normalized = " ".join(str(command or "").strip().split()).lower()
        if not normalized:
            return False
        if self.awaiting_study_duration and self.looks_like_duration(command):
            return True
        if self.awaiting_study_unlock and self.looks_like_passcode(command):
            return True
        return "study mode" in normalized or "study mood" in normalized

    def looks_like_duration(self, command: str) -> bool:
        normalized = " ".join(str(command or "").strip().split()).lower()
        if not normalized:
            return False
        if normalized.isdigit():
            return True
        return bool(re.search(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr|h|minutes?|mins?|min|m)\b", normalized))

    def looks_like_passcode(self, command: str) -> bool:
        normalized = " ".join(str(command or "").strip().split()).lower()
        if not normalized:
            return False
        return normalized.isdigit() or normalized.startswith("passcode ")

    def shutdown(self):
        if self._process is None:
            return
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:  # pragma: no cover
                self._process.kill()
        self._process = None

    def _server_ready(self) -> bool:
        try:
            self.request("GET", "/api/netcontrol/status", timeout=1.0)
            return True
        except Exception:
            return False

    def _sync_state(self, payload):
        if not isinstance(payload, dict):
            return
        self.awaiting_study_unlock = bool(payload.get("studyUnlockPending", payload.get("requiresPasscode", False)))
        self.awaiting_study_duration = bool(payload.get("studyDurationPending", payload.get("requiresDuration", False)))
        self.study_mode_active = bool(payload.get("studyMode", False))
        self.study_pending_action = str(payload.get("pendingAction", "") or "").strip()
