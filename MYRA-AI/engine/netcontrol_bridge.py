from __future__ import annotations

import atexit
import json
import os
import re
import socket
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
        self.study_state_path = self.base_dir / "modules" / "studymode" / "state.json"
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
            payload = self.request(
                "POST",
                "/api/netcontrol/command",
                {"command": normalized},
                timeout=self._command_timeout_seconds(normalized),
            )
        except Exception as exc:  # pragma: no cover
            recovered = self._recover_command_timeout(normalized, exc)
            if recovered:
                return recovered
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
        local_state = self._load_local_study_state()
        if local_state:
            self._sync_state(local_state)
            return local_state
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
        if "study mode" in normalized or "study mood" in normalized:
            return True

        duration_like = self.looks_like_duration(command)
        passcode_like = self.looks_like_passcode(command)
        unlock_like = normalized == "unlock"

        # Refresh live study state before we discard short follow-up replies like
        # "1234" or "10 minutes". These often arrive after the pending prompt was
        # opened from another surface (dashboard button, previous session, etc.).
        if (duration_like or passcode_like or unlock_like) and not (
            self.awaiting_study_duration or self.awaiting_study_unlock
        ):
            self.status_snapshot(refresh=True)

        if self.awaiting_study_duration and duration_like:
            return True
        if self.awaiting_study_unlock and (passcode_like or unlock_like):
            return True
        return False

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

    def _load_local_study_state(self):
        if not self.study_state_path.exists():
            return {}
        try:
            payload = json.loads(self.study_state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(payload, dict):
            return {}

        pending_action = str(payload.get("pendingAction", "") or "").strip()
        payload["studyMode"] = bool(payload.get("studyMode", False))
        payload["studyUnlockPending"] = pending_action == "await_passcode"
        payload["studyDurationPending"] = pending_action == "await_duration"
        payload["pendingAction"] = pending_action
        payload["pendingPrompt"] = str(payload.get("pendingPrompt", "") or "").strip()
        return payload

    def _command_timeout_seconds(self, command: str) -> float:
        normalized = " ".join(str(command or "").strip().split()).lower()
        if not normalized:
            return 5.0
        if "study mode" in normalized or "study mood" in normalized:
            return 20.0
        if self.looks_like_duration(normalized) or self.looks_like_passcode(normalized) or normalized == "unlock":
            return 20.0
        if "vision monitor" in normalized or "vision monitoring" in normalized:
            return 12.0
        return 6.0

    def _recover_command_timeout(self, command: str, error):
        message = str(error or "").strip().lower()
        if "timed out" not in message and not isinstance(error, socket.timeout):
            return None

        state = self.status_snapshot(refresh=False)
        if not isinstance(state, dict):
            return None

        normalized = " ".join(str(command or "").strip().split()).lower()
        pending_action = str(state.get("pendingAction", "") or "").strip()
        remaining = str(state.get("remainingLabel", "") or "").strip()

        if ("study mode on" in normalized or "study mode" in normalized) and pending_action == "await_duration":
            return True, state.get("pendingPrompt") or "Enter duration (e.g., 2 hours, 30 minutes)"

        if self.looks_like_duration(normalized) and state.get("studyMode") and not pending_action:
            timer_text = remaining or "the selected duration"
            return True, f"Study mode activated. Timer {timer_text} ke liye start ho gaya."

        if ("study mode off" in normalized or normalized == "unlock") and pending_action == "await_passcode":
            return True, state.get("pendingPrompt") or "Enter passcode to unlock"

        if self.looks_like_passcode(normalized) and not state.get("studyMode") and not pending_action:
            return True, "Study mode disabled. Full access restored."

        return None
