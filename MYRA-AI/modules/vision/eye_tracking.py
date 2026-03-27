from __future__ import annotations

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

try:
    import mediapipe as mp
except Exception:  # pragma: no cover
    mp = None


class EyeTracker:
    LEFT_EYE = {
        "left_corner": 33,
        "right_corner": 133,
        "top": 159,
        "bottom": 145,
        "iris": (469, 470, 471, 472),
    }
    RIGHT_EYE = {
        "left_corner": 362,
        "right_corner": 263,
        "top": 386,
        "bottom": 374,
        "iris": (474, 475, 476, 477),
    }

    def __init__(self, config=None):
        self.config = dict(config or {})
        self.focus_center_min = float(self.config.get("focusCenterMin", 0.22))
        self.focus_center_max = float(self.config.get("focusCenterMax", 0.78))
        self.available = cv2 is not None and mp is not None
        self._mesh = None

        if self.available:
            try:
                self._mesh = mp.solutions.face_mesh.FaceMesh(
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5,
                )
            except Exception:
                self._mesh = None
                self.available = False

    def analyze(self, frame):
        if not self.available or self._mesh is None or frame is None:
            return {
                "available": False,
                "focused": None,
                "gaze": "unavailable",
                "scores": {},
            }

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._mesh.process(rgb)
        if not result.multi_face_landmarks:
            return {
                "available": True,
                "focused": None,
                "gaze": "no-face",
                "scores": {},
            }

        landmarks = result.multi_face_landmarks[0].landmark
        frame_height, frame_width = frame.shape[:2]

        left_ratio = self._eye_center_ratio(landmarks, self.LEFT_EYE, frame_width, frame_height)
        right_ratio = self._eye_center_ratio(landmarks, self.RIGHT_EYE, frame_width, frame_height)
        horizontal = (left_ratio["horizontal"] + right_ratio["horizontal"]) / 2.0
        vertical = (left_ratio["vertical"] + right_ratio["vertical"]) / 2.0

        focused = (
            self.focus_center_min <= horizontal <= self.focus_center_max
            and self.focus_center_min <= vertical <= self.focus_center_max
        )
        gaze = "center"
        if horizontal < self.focus_center_min:
            gaze = "left"
        elif horizontal > self.focus_center_max:
            gaze = "right"
        elif vertical < self.focus_center_min:
            gaze = "up"
        elif vertical > self.focus_center_max:
            gaze = "down"

        return {
            "available": True,
            "focused": focused,
            "gaze": gaze,
            "scores": {
                "horizontal": round(horizontal, 3),
                "vertical": round(vertical, 3),
            },
        }

    def close(self):
        if self._mesh is not None:
            try:
                self._mesh.close()
            except Exception:
                pass
            self._mesh = None

    def _eye_center_ratio(self, landmarks, eye_map, frame_width, frame_height):
        left_corner = self._point(landmarks[eye_map["left_corner"]], frame_width, frame_height)
        right_corner = self._point(landmarks[eye_map["right_corner"]], frame_width, frame_height)
        top_point = self._point(landmarks[eye_map["top"]], frame_width, frame_height)
        bottom_point = self._point(landmarks[eye_map["bottom"]], frame_width, frame_height)
        iris_points = [self._point(landmarks[index], frame_width, frame_height) for index in eye_map["iris"]]

        iris_x = sum(point[0] for point in iris_points) / max(1, len(iris_points))
        iris_y = sum(point[1] for point in iris_points) / max(1, len(iris_points))

        min_x = min(left_corner[0], right_corner[0])
        max_x = max(left_corner[0], right_corner[0])
        min_y = min(top_point[1], bottom_point[1])
        max_y = max(top_point[1], bottom_point[1])

        eye_width = max(1.0, max_x - min_x)
        eye_height = max(1.0, max_y - min_y)

        return {
          "horizontal": (iris_x - min_x) / eye_width,
          "vertical": (iris_y - min_y) / eye_height,
        }

    @staticmethod
    def _point(landmark, frame_width, frame_height):
        return (
            float(landmark.x) * float(frame_width),
            float(landmark.y) * float(frame_height),
        )
