from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

try:
    import mediapipe  # noqa: F401
except Exception:  # pragma: no cover
    mediapipe = None

try:
    import numpy  # noqa: F401
except Exception:  # pragma: no cover
    numpy = None

try:
    import sounddevice  # noqa: F401
except Exception:  # pragma: no cover
    sounddevice = None

try:
    import pyttsx3  # noqa: F401
except Exception:  # pragma: no cover
    pyttsx3 = None

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from face_detection import FaceDetector
from eye_tracking import EyeTracker
from noise_detection import NoiseDetector
from voice_alert import VoiceAlertSystem


class VisionMonitorService:
    def __init__(self, config_path: Path):
        self.config_path = Path(config_path)
        self.config = self._load_config(self.config_path)
        self.running = True
        self.camera = None
        self.face_detector = FaceDetector(self.config)
        self.eye_tracker = EyeTracker(self.config)
        self.noise_detector = NoiseDetector(self.config)
        self.voice_alerts = VoiceAlertSystem(self.config)
        self.face_missing_seconds = float(self.config.get("faceMissingSeconds", 6))
        self.focus_loss_seconds = float(self.config.get("focusLossSeconds", 10))
        self.noise_hold_seconds = float(self.config.get("noiseHoldSeconds", 3))
        self.frame_interval = max(0.1, float(self.config.get("frameIntervalMs", 350)) / 1000.0)
        self.max_noise_level = max(0.1, float(self.config.get("maxNoiseLevel", 0.2)))
        self.messages = dict(self.config.get("alertMessages") or {})

        self.last_face_seen_at = time.time()
        self.focus_away_since = None
        self.noise_since = None
        self.current_warning = "none"
        self.last_noise_level = 0.0
        self.webcam_available = False
        self.microphone_available = False
        self.runtime_message = self._build_runtime_message()

    def run(self):
        self._open_camera()
        noise_status = self.noise_detector.start()
        self.microphone_available = bool(noise_status.get("started"))

        while self.running:
            loop_started_at = time.time()
            payload = self._build_status_payload(loop_started_at)
            self._emit(payload)
            time.sleep(max(0.02, self.frame_interval - (time.time() - loop_started_at)))

        self.close()

    def close(self):
        self.running = False
        if self.camera is not None:
            try:
                self.camera.release()
            except Exception:
                pass
            self.camera = None
        self.noise_detector.stop()
        self.eye_tracker.close()
        self.voice_alerts.close()

    def status_snapshot(self):
        return {
            "type": "status",
            "active": True,
            "warning": "none",
            "dependencies": self._dependency_status(),
            "supports": self._support_status(False, False),
            "message": self._build_runtime_message(),
            "previewAvailable": False,
        }

    def _build_status_payload(self, now):
        frame = self._read_frame()
        face_result = self.face_detector.detect(frame)
        face_detected = bool(face_result.get("detected"))
        if face_detected:
            self.last_face_seen_at = now

        eye_result = self.eye_tracker.analyze(frame if face_detected else None)
        focused = eye_result.get("focused")

        if face_detected and focused is False:
            if self.focus_away_since is None:
                self.focus_away_since = now
        else:
            self.focus_away_since = None

        noise_result = self.noise_detector.snapshot()
        self.last_noise_level = float(noise_result.get("level") or 0.0)
        if bool(noise_result.get("alert")):
            if self.noise_since is None:
                self.noise_since = now
        else:
            self.noise_since = None

        face_missing_active = bool(face_result.get("available")) and (now - self.last_face_seen_at) >= self.face_missing_seconds
        focus_warning_active = bool(eye_result.get("available")) and self.focus_away_since is not None and (now - self.focus_away_since) >= self.focus_loss_seconds
        noise_warning_active = bool(noise_result.get("available")) and bool(noise_result.get("started")) and self.noise_since is not None and (now - self.noise_since) >= self.noise_hold_seconds

        next_warning = "none"
        if face_missing_active:
            next_warning = "Face not detected"
        elif focus_warning_active:
            next_warning = "User not focused"
        elif noise_warning_active:
            next_warning = "Background noise detected"

        event_message = self._warning_transition_event(next_warning)
        self.current_warning = next_warning

        if next_warning == "Face not detected":
            self._speak(self.messages.get("faceMissing", "Face not detected, please come back."), "faceMissing")
        elif next_warning == "User not focused":
            self._speak(self.messages.get("generalFocus", "Himesh, focus bro."), "focusLost")
        elif next_warning == "Background noise detected":
            if self.last_noise_level >= float(self.config.get("noiseThreshold", 0.055)) * 1.8:
                self._speak(self.messages.get("noiseHigh", "Too much disturbance around you."), "noiseHigh")
            else:
                self._speak(self.messages.get("noiseDetected", "Background noise detected, stay focused."), "noiseDetected")

        return {
            "type": "status",
            "active": True,
            "faceDetected": face_detected,
            "faceStatus": "detected" if face_detected else ("missing" if face_result.get("available") else "unavailable"),
            "focus": focused,
            "focusStatus": self._focus_status(focused, eye_result.get("available")),
            "noiseLevel": round(self.last_noise_level, 4),
            "noisePercent": round(min(100.0, (self.last_noise_level / self.max_noise_level) * 100.0), 1),
            "noiseAlert": bool(noise_warning_active),
            "noiseStatus": "noisy" if noise_warning_active else ("quiet" if noise_result.get("available") and noise_result.get("started") else "unavailable"),
            "warning": next_warning if next_warning != "none" else "none",
            "event": event_message,
            "focusAwaySeconds": round(0.0 if self.focus_away_since is None else now - self.focus_away_since, 1),
            "faceMissingSeconds": round(max(0.0, now - self.last_face_seen_at), 1),
            "dependencies": self._dependency_status(),
            "supports": self._support_status(face_result.get("available"), bool(noise_result.get("started"))),
            "webcamAvailable": self.webcam_available,
            "microphoneAvailable": bool(noise_result.get("started")),
            "voiceAlertsEnabled": bool(self.voice_alerts.available),
            "message": self.runtime_message if next_warning == "none" else next_warning,
            "previewAvailable": False,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    def _warning_transition_event(self, next_warning):
        previous = self.current_warning
        if next_warning == previous:
            return ""
        if next_warning == "Face not detected":
            return "Face not detected"
        if next_warning == "User not focused":
            return "User distracted"
        if next_warning == "Background noise detected":
            return "Background noise detected"
        if previous != "none" and next_warning == "none":
            return "Focus restored"
        return ""

    def _open_camera(self):
        if cv2 is None:
            self.webcam_available = False
            return

        try:
            if sys.platform == "win32":
                camera = cv2.VideoCapture(int(self.config.get("cameraIndex", 0)), cv2.CAP_DSHOW)
            else:
                camera = cv2.VideoCapture(int(self.config.get("cameraIndex", 0)))
            if not camera.isOpened():
                camera.release()
                self.webcam_available = False
                return
            self.camera = camera
            self.webcam_available = True
        except Exception:
            self.camera = None
            self.webcam_available = False

    def _read_frame(self):
        if self.camera is None:
            return None
        try:
            ok, frame = self.camera.read()
        except Exception:
            return None
        if not ok:
            return None
        return frame

    def _support_status(self, face_available, microphone_started):
        return {
            "faceDetection": bool(face_available),
            "eyeTracking": bool(self.eye_tracker.available),
            "noiseDetection": bool(microphone_started),
            "voiceAlerts": bool(self.voice_alerts.available),
        }

    def _dependency_status(self):
        return {
            "opencv": cv2 is not None,
            "mediapipe": mediapipe is not None,
            "numpy": numpy is not None,
            "sounddevice": sounddevice is not None,
            "pyttsx3": pyttsx3 is not None,
        }

    def _build_runtime_message(self):
        notes = []
        if not self.face_detector.available:
            notes.append("face detection unavailable")
        if not self.eye_tracker.available:
            notes.append("MediaPipe not installed")
        if not self.noise_detector.available:
            notes.append("sounddevice not installed")
        if not self.voice_alerts.available:
            notes.append("voice alerts unavailable")
        if not notes:
            return "Vision monitoring ready"
        return "Fallback mode: " + ", ".join(notes)

    def _focus_status(self, focused, available):
        if not available:
            return "unavailable"
        if focused is True:
            return "focused"
        if focused is False:
            return "distracted"
        return "unknown"

    def _speak(self, message, key):
        self.voice_alerts.speak(message, key=key)

    @staticmethod
    def _load_config(config_path):
        payload = {}
        try:
            payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _emit(payload):
        print(json.dumps(payload, ensure_ascii=True), flush=True)


def parse_args():
    parser = argparse.ArgumentParser(description="MYRA Study Mode Vision Monitor")
    parser.add_argument("--config", default=str(CURRENT_DIR / "config.json"))
    parser.add_argument("--self-check", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    service = VisionMonitorService(Path(args.config))

    def stop_service(signum=None, frame=None):  # pragma: no cover
        service.close()

    signal.signal(signal.SIGINT, stop_service)
    signal.signal(signal.SIGTERM, stop_service)

    if args.self_check:
      VisionMonitorService._emit(service.status_snapshot())
      service.close()
      return 0

    try:
        service.run()
        return 0
    except Exception as exc:  # pragma: no cover
        VisionMonitorService._emit({
            "type": "error",
            "active": False,
            "warning": "Vision monitor error",
            "event": "",
            "message": str(exc),
        })
        service.close()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
