from __future__ import annotations

import queue
import random
import threading
import time

try:
    import pyttsx3
except Exception:  # pragma: no cover
    pyttsx3 = None

try:
    import winsound
except Exception:  # pragma: no cover
    winsound = None


class VoiceAlertSystem:
    def __init__(self, config=None):
        self.config = dict(config or {})
        self.enabled = bool(self.config.get("voiceAlertsEnabled", True))
        self.cooldown_seconds = float(self.config.get("voiceCooldownSeconds", 8))
        self.available = bool(self.enabled)
        self._engine = None
        self._beep_fallback = False
        self._queue = queue.Queue()
        self._last_by_key = {}
        self._worker = None
        self._stop = threading.Event()

        if self.available and pyttsx3 is not None:
            try:
                self._engine = pyttsx3.init()
                self._engine.setProperty("rate", int(self.config.get("voiceRate", 170)))
                self._engine.setProperty("volume", float(self.config.get("voiceVolume", 1.0)))
                voices = list(self._engine.getProperty("voices") or [])
                preferred_voice = None
                if len(voices) > 1:
                    preferred_voice = voices[1]
                elif voices:
                    preferred_voice = voices[0]
                if preferred_voice is not None and getattr(preferred_voice, "id", ""):
                    self._engine.setProperty("voice", preferred_voice.id)
            except Exception:
                self._engine = None
                self._beep_fallback = winsound is not None
        elif self.available and winsound is not None:
            self._beep_fallback = True

        if self._engine is None and not self._beep_fallback:
            self.available = False

        if self.available:
            self._worker = threading.Thread(target=self._run, daemon=True)
            self._worker.start()

    def speak(self, message, key="general", cooldown_seconds=None):
        if not self.available:
            return False

        now = time.time()
        cooldown = self.cooldown_seconds if cooldown_seconds is None else max(0.0, float(cooldown_seconds))
        last_time = float(self._last_by_key.get(str(key), 0.0))
        if (now - last_time) < cooldown:
            return False

        clean_message = self._pick_message(message)
        if not clean_message and not self._beep_fallback:
            return False

        self._last_by_key[str(key)] = now
        self._queue.put((clean_message, str(key)))
        return True

    def close(self):
        self._stop.set()
        if self._worker is not None:
            self._queue.put("")
            self._worker.join(timeout=1.5)

    def _run(self):  # pragma: no cover
        while not self._stop.is_set():
            try:
                payload = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if self._stop.is_set():
                return
            if isinstance(payload, tuple):
                clean, key = payload
            else:
                clean, key = str(payload or "").strip(), "general"
            if not clean and not self._beep_fallback:
                continue
            try:
                if self._engine is not None:
                    self._engine.say(clean)
                    self._engine.runAndWait()
                elif self._beep_fallback:
                    self._beep(str(key or "general"))
            except Exception:
                continue

    def _pick_message(self, message):
        if isinstance(message, (list, tuple)):
            choices = [str(item or "").strip() for item in message if str(item or "").strip()]
            if choices:
                return random.choice(choices)
            return ""
        return str(message or "").strip()

    def _beep(self, key):  # pragma: no cover
        if winsound is None:
            return
        patterns = {
            "faceMissing": [(1200, 180), (1200, 180)],
            "faceAdjust": [(1000, 140), (1000, 140)],
            "focusLost": [(900, 220)],
            "noiseDetected": [(850, 120), (850, 120), (850, 120)],
            "noiseHigh": [(700, 180), (700, 180), (700, 180)],
        }
        sequence = patterns.get(str(key or ""), [(900, 140)])
        for frequency, duration in sequence:
            winsound.Beep(int(frequency), int(duration))
            time.sleep(0.05)
