from __future__ import annotations

import queue
import threading
import time

try:
    import pyttsx3
except Exception:  # pragma: no cover
    pyttsx3 = None


class VoiceAlertSystem:
    def __init__(self, config=None):
        self.config = dict(config or {})
        self.enabled = bool(self.config.get("voiceAlertsEnabled", True))
        self.cooldown_seconds = float(self.config.get("voiceCooldownSeconds", 8))
        self.available = pyttsx3 is not None and self.enabled
        self._engine = None
        self._queue = queue.Queue()
        self._last_by_key = {}
        self._worker = None
        self._stop = threading.Event()

        if self.available:
            try:
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", 172)
            except Exception:
                self._engine = None
                self.available = False

        if self.available:
            self._worker = threading.Thread(target=self._run, daemon=True)
            self._worker.start()

    def speak(self, message, key="general"):
        if not self.available:
            return False

        now = time.time()
        last_time = float(self._last_by_key.get(str(key), 0.0))
        if (now - last_time) < self.cooldown_seconds:
            return False

        self._last_by_key[str(key)] = now
        self._queue.put(str(message or "").strip())
        return True

    def close(self):
        self._stop.set()
        if self._worker is not None:
            self._queue.put("")
            self._worker.join(timeout=1.5)

    def _run(self):  # pragma: no cover
        while not self._stop.is_set():
            try:
                message = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if self._stop.is_set():
                return
            clean = str(message or "").strip()
            if not clean:
                continue
            try:
                self._engine.say(clean)
                self._engine.runAndWait()
            except Exception:
                continue
