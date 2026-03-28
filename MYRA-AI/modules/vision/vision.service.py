from __future__ import annotations

import argparse
import json
import random
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
        self.face_missing_seconds = float(self.config.get("faceMissingSeconds", 3))
        self.face_adjust_seconds = float(self.config.get("faceAdjustSeconds", 2.5))
        self.face_recovery_seconds = float(self.config.get("faceRecoverySeconds", 1.2))
        self.focus_loss_seconds = float(self.config.get("focusLossSeconds", 10))
        self.noise_hold_seconds = float(self.config.get("noiseHoldSeconds", 3))
        self.frame_interval = max(0.5, float(self.config.get("frameIntervalMs", 500)) / 1000.0)
        self.face_warning_repeat_seconds = max(1.5, float(self.config.get("faceWarningRepeatSeconds", 3)))
        self.focus_warning_repeat_seconds = max(2.0, float(self.config.get("focusWarningRepeatSeconds", 8)))
        self.noise_warning_repeat_seconds = max(2.0, float(self.config.get("noiseWarningRepeatSeconds", 8)))
        self.max_noise_level = max(0.1, float(self.config.get("maxNoiseLevel", 0.2)))
        self.camera_warmup_seconds = max(0.0, float(self.config.get("cameraWarmupSeconds", 0.5)))
        self.messages = dict(self.config.get("alertMessages") or {})

        self.face_detected = False
        self.last_face_detected_at = time.time()
        self.last_face_warning_at = 0.0
        self.face_adjust_since = None
        self.face_clear_since = None
        self.focus_away_since = None
        self.noise_since = None
        self.current_warning = "none"
        self.last_noise_level = 0.0
        self.webcam_available = False
        self.microphone_available = False
        self.runtime_message = self._build_runtime_message()
        self._pending_events = []
        self._face_detection_logged = False

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
        self.face_detector.close()
        self.noise_detector.stop()
        self.eye_tracker.close()
        self.voice_alerts.close()

    def status_snapshot(self):
        return {
            "type": "status",
            "active": True,
            "warning": "none",
            "dependencies": self._dependency_status(),
            "supports": self._support_status(self.face_detector.available, False),
            "message": self._build_runtime_message(),
            "previewAvailable": False,
            "faceDetected": False,
            "faceStatus": "detecting" if self.face_detector.available else "unavailable",
        }

    def _build_status_payload(self, now):
        frame = self._read_frame()
        face_result = self.face_detector.detect(frame)
        face_detected = bool(face_result.get("detected"))
        face_properly_visible = bool(face_result.get("properlyVisible"))
        face_guidance = str(face_result.get("guidance") or "").strip()
        self.face_detected = face_detected
        if face_detected:
            self.last_face_detected_at = now
            if not self._face_detection_logged:
                self._face_detection_logged = True
                self._queue_event("Face detection working")
            if self.face_clear_since is None:
                self.face_clear_since = now
        else:
            self.face_clear_since = None

        if face_detected and not face_properly_visible:
            if self.face_adjust_since is None:
                self.face_adjust_since = now
        else:
            self.face_adjust_since = None

        face_recovered = bool(face_properly_visible) and self.face_clear_since is not None and (
            (now - self.face_clear_since) >= self.face_recovery_seconds
        )

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

        face_missing_active = bool(face_result.get("available")) and not face_detected and (now - self.last_face_detected_at) >= self.face_missing_seconds
        face_adjust_active = (
            bool(face_result.get("available"))
            and face_detected
            and not face_properly_visible
            and self.face_adjust_since is not None
            and (now - self.face_adjust_since) >= self.face_adjust_seconds
        )
        focus_warning_active = bool(eye_result.get("available")) and self.focus_away_since is not None and (now - self.focus_away_since) >= self.focus_loss_seconds
        noise_warning_active = bool(noise_result.get("available")) and bool(noise_result.get("started")) and self.noise_since is not None and (now - self.noise_since) >= self.noise_hold_seconds

        next_warning = "none"
        if face_missing_active:
            next_warning = "Face not detected"
        elif face_adjust_active or (face_detected and not face_properly_visible and self.current_warning in {"Face not detected", "Face not clear"}):
            next_warning = "Face not clear"
        elif self.current_warning in {"Face not detected", "Face not clear"} and not face_recovered:
            next_warning = self.current_warning
        elif focus_warning_active:
            next_warning = "User not focused"
        elif noise_warning_active:
            next_warning = "Background noise detected"

        event_message = self._warning_transition_event(next_warning)
        self.current_warning = next_warning

        if next_warning == "Face not detected":
            if self._should_repeat_face_warning(now):
                if self._speak(
                    self._message_variation(
                        self.messages.get(
                            "faceMissing",
                            [
                                "Face detect nahi ho raha, screen ke saamne aao.",
                                "Screen ke saamne aao.",
                                "Himesh, face camera ke saamne rakho.",
                            ],
                        )
                    ),
                    "faceMissing",
                    0.0,
                ):
                    self._queue_event("Face warning triggered")
                    self.last_face_warning_at = now
        elif next_warning == "Face not clear":
            if self._should_repeat_face_warning(now):
                if self._speak(
                    self._compose_face_adjust_message(face_guidance),
                    "faceAdjust",
                    0.0,
                ):
                    self._queue_event("Face warning triggered")
                    self.last_face_warning_at = now
        elif next_warning == "User not focused":
            self.last_face_warning_at = 0.0
            self._speak(
                self._message_variation(
                    self.messages.get(
                        "generalFocus",
                        [
                            "Himesh, focus karo.",
                            "Boss, focus back on the screen.",
                            "Himesh, dhyan screen par rakho.",
                        ],
                    )
                ),
                "focusLost",
                self.focus_warning_repeat_seconds,
            )
        elif next_warning == "Background noise detected":
            self.last_face_warning_at = 0.0
            if self.last_noise_level >= float(self.config.get("noiseThreshold", 0.055)) * 1.8:
                self._speak(
                    self.messages.get("noiseHigh", "Too much disturbance around you."),
                    "noiseHigh",
                    self.noise_warning_repeat_seconds,
                )
            else:
                self._speak(
                    self.messages.get("noiseDetected", "Background noise detected, stay focused."),
                    "noiseDetected",
                    self.noise_warning_repeat_seconds,
                )
        else:
            self.last_face_warning_at = 0.0

        face_status = "unavailable"
        if face_result.get("available"):
            if face_recovered:
                face_status = "detected"
            elif face_missing_active:
                face_status = "missing"
            elif face_detected:
                face_status = "adjust"
            else:
                face_status = "detecting"

        self._queue_event(event_message)

        return {
            "type": "status",
            "active": True,
            "faceDetected": face_detected,
            "faceProperlyVisible": face_properly_visible,
            "faceReady": face_recovered,
            "faceGuidance": face_guidance,
            "faceStatus": face_status,
            "focus": focused,
            "focusStatus": self._focus_status(focused, eye_result.get("available")),
            "noiseLevel": round(self.last_noise_level, 4),
            "noisePercent": round(min(100.0, (self.last_noise_level / self.max_noise_level) * 100.0), 1),
            "noiseAlert": bool(noise_warning_active),
            "noiseStatus": "noisy" if noise_warning_active else ("quiet" if noise_result.get("available") and noise_result.get("started") else "unavailable"),
            "warning": next_warning if next_warning != "none" else "none",
            "event": self._next_event(),
            "focusAwaySeconds": round(0.0 if self.focus_away_since is None else now - self.focus_away_since, 1),
            "faceMissingSeconds": round(0.0 if face_detected else max(0.0, now - self.last_face_detected_at), 1),
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
            return "Warning triggered: Face not detected"
        if next_warning == "Face not clear":
            return "Warning triggered: Face not clear"
        if next_warning == "User not focused":
            return "Warning triggered: User distracted"
        if next_warning == "Background noise detected":
            return "Warning triggered: Background noise detected"
        if previous != "none" and next_warning == "none":
            return "Focus restored"
        return ""

    def _open_camera(self):
        if cv2 is None:
            self.webcam_available = False
            return

        candidate_indexes = [0]
        configured_index = int(self.config.get("cameraIndex", 0))
        if configured_index not in candidate_indexes:
            candidate_indexes.append(configured_index)

        for index in candidate_indexes:
            try:
                camera = cv2.VideoCapture(int(index))
                time.sleep(self.camera_warmup_seconds)
                if not camera.isOpened():
                    camera.release()
                    continue

                # Read a couple of frames after warmup so the first detection pass
                # is not working with a black/unstable frame from the camera driver.
                for _ in range(3):
                    ok, _ = camera.read()
                    if ok:
                        break
                    time.sleep(0.1)

                self.camera = camera
                self.webcam_available = True
                self._queue_event("Camera started")
                return
            except Exception:
                continue

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
            notes.append("MediaPipe face detection unavailable")
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

    def _compose_face_adjust_message(self, guidance):
        base_message = self._message_variation(
            self.messages.get("faceAdjust", "Face is not clear. Please center your face properly.")
        )
        clean_guidance = str(guidance or "").strip().rstrip(".")
        if not clean_guidance:
            return base_message
        return f"{base_message.rstrip('.')} Please {clean_guidance}."

    def _message_variation(self, value):
        if isinstance(value, (list, tuple)):
            choices = [str(item).strip() for item in value if str(item or "").strip()]
            if choices:
                return random.choice(choices)
            return ""
        return str(value or "").strip()

    def _should_repeat_face_warning(self, now):
        return (float(now) - float(self.last_face_warning_at)) >= self.face_warning_repeat_seconds

    def _speak(self, message, key, cooldown_seconds=None):
        return self.voice_alerts.speak(message, key=key, cooldown_seconds=cooldown_seconds)

    def _queue_event(self, message):
        clean = str(message or "").strip()
        if clean:
            self._pending_events.append(clean)

    def _next_event(self):
        if not self._pending_events:
            return ""
        return self._pending_events.pop(0)

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
