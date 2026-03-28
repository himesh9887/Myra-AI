from __future__ import annotations

from pathlib import Path

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

try:
    import mediapipe as mp
except Exception:  # pragma: no cover
    mp = None


class FaceDetector:
    def __init__(self, config=None):
        self.config = dict(config or {})
        self.available = cv2 is not None
        self._classifier = None
        self._detector = None
        self.backend = "unavailable"
        self.min_face_area_ratio = max(0.01, float(self.config.get("minFaceAreaRatio", 0.035)))
        self.face_center_tolerance = min(0.45, max(0.08, float(self.config.get("faceCenterTolerance", 0.24))))
        self.face_edge_margin_ratio = min(0.2, max(0.0, float(self.config.get("faceEdgeMarginRatio", 0.04))))
        self.min_detection_confidence = min(0.99, max(0.1, float(self.config.get("faceDetectionConfidence", 0.7))))

        if self.available and mp is not None:
            try:
                self._detector = mp.solutions.face_detection.FaceDetection(
                    model_selection=0,
                    min_detection_confidence=self.min_detection_confidence,
                )
                self.backend = "mediapipe"
            except Exception:
                self._detector = None

        if self.available and self._detector is None:
            cascade_root = getattr(getattr(cv2, "data", None), "haarcascades", "")
            cascade_path = Path(cascade_root) / "haarcascade_frontalface_default.xml"
            if cascade_path.exists():
                self._classifier = cv2.CascadeClassifier(str(cascade_path))
                if self._classifier.empty():
                    self._classifier = None
                else:
                    self.backend = "haar"

        self.available = self.available and (self._detector is not None or self._classifier is not None)

    def detect(self, frame):
        if not self.available or frame is None:
            return {
                "available": False,
                "detected": False,
                "count": 0,
                "faces": [],
                "properlyVisible": False,
                "primaryFace": None,
                "guidance": "",
                "backend": self.backend,
            }

        frame_height, frame_width = frame.shape[:2]
        normalized_faces = self._detect_faces(frame)
        primary_face = max(
            normalized_faces,
            key=lambda item: int(item["w"]) * int(item["h"]),
            default=None,
        )
        area_ratio = 0.0
        centered = False
        inside_frame = False
        guidance = ""

        if primary_face and frame_width > 0 and frame_height > 0:
            x = int(primary_face["x"])
            y = int(primary_face["y"])
            w = int(primary_face["w"])
            h = int(primary_face["h"])
            center_x = (x + (w / 2.0)) / float(frame_width)
            center_y = (y + (h / 2.0)) / float(frame_height)
            edge_margin_x = frame_width * self.face_edge_margin_ratio
            edge_margin_y = frame_height * self.face_edge_margin_ratio
            area_ratio = (w * h) / float(frame_width * frame_height)
            centered = (
                abs(center_x - 0.5) <= self.face_center_tolerance
                and abs(center_y - 0.5) <= self.face_center_tolerance
            )
            inside_frame = (
                x >= edge_margin_x
                and y >= edge_margin_y
                and (x + w) <= (frame_width - edge_margin_x)
                and (y + h) <= (frame_height - edge_margin_y)
            )

            guidance_parts = []
            if area_ratio < self.min_face_area_ratio:
                guidance_parts.append("move closer to the camera")
            if not centered:
                guidance_parts.append("keep your face in the center")
            if not inside_frame:
                guidance_parts.append("show your full face inside the frame")
            guidance = ", ".join(guidance_parts)

        properly_visible = bool(primary_face) and area_ratio >= self.min_face_area_ratio and centered and inside_frame
        return {
            "available": True,
            "detected": len(normalized_faces) > 0,
            "count": len(normalized_faces),
            "faces": normalized_faces,
            "properlyVisible": properly_visible,
            "primaryFace": primary_face,
            "guidance": guidance,
            "backend": self.backend,
        }

    def close(self):
        detector = self._detector
        self._detector = None
        if detector is not None and hasattr(detector, "close"):
            try:
                detector.close()
            except Exception:
                pass

    def _detect_faces(self, frame):
        if self._detector is not None:
            return self._detect_with_mediapipe(frame)
        return self._detect_with_haar(frame)

    def _detect_with_mediapipe(self, frame):
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._detector.process(rgb_frame)
        detections = getattr(result, "detections", None) or []
        frame_height, frame_width = frame.shape[:2]
        faces = []

        for detection in detections:
            location = getattr(detection, "location_data", None)
            relative_box = getattr(location, "relative_bounding_box", None)
            if relative_box is None:
                continue

            x = max(0, int(relative_box.xmin * frame_width))
            y = max(0, int(relative_box.ymin * frame_height))
            w = int(relative_box.width * frame_width)
            h = int(relative_box.height * frame_height)
            if w <= 0 or h <= 0:
                continue

            x2 = min(frame_width, x + w)
            y2 = min(frame_height, y + h)
            faces.append({
                "x": int(x),
                "y": int(y),
                "w": int(max(0, x2 - x)),
                "h": int(max(0, y2 - y)),
            })

        return faces

    def _detect_with_haar(self, frame):
        if self._classifier is None:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._classifier.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
        )
        return [
            {
                "x": int(x),
                "y": int(y),
                "w": int(w),
                "h": int(h),
            }
            for (x, y, w, h) in faces
        ]
