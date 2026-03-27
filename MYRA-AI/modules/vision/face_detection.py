from __future__ import annotations

from pathlib import Path

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None


class FaceDetector:
    def __init__(self, config=None):
        self.config = dict(config or {})
        self.available = cv2 is not None
        self._classifier = None

        if self.available:
            cascade_root = getattr(getattr(cv2, "data", None), "haarcascades", "")
            cascade_path = Path(cascade_root) / "haarcascade_frontalface_default.xml"
            if cascade_path.exists():
                self._classifier = cv2.CascadeClassifier(str(cascade_path))
                if self._classifier.empty():
                    self._classifier = None

        self.available = self.available and self._classifier is not None

    def detect(self, frame):
        if not self.available or frame is None:
            return {
                "available": False,
                "detected": False,
                "count": 0,
                "faces": [],
            }

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._classifier.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )
        normalized_faces = [
            {
                "x": int(x),
                "y": int(y),
                "w": int(w),
                "h": int(h),
            }
            for (x, y, w, h) in faces
        ]
        return {
            "available": True,
            "detected": len(normalized_faces) > 0,
            "count": len(normalized_faces),
            "faces": normalized_faces,
        }
