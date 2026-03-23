from __future__ import annotations

import re


class ObjectDetector:
    def __init__(self, camera_agent):
        self.camera = camera_agent

    def detect(self, prompt="identify this object"):
        if not hasattr(self.camera, "capture_frame"):
            return "Boss, object detection camera layer unavailable hai."
        frame_path, error = self.camera.capture_frame()
        if not frame_path:
            return f"Boss, object detect nahi ho paya. {error or 'Camera unavailable hai.'}"

        caption = ""
        legacy = getattr(self.camera, "_agent", None)
        if legacy and hasattr(legacy, "_caption_image"):
            try:
                caption = legacy._caption_image(frame_path)
            except Exception:
                caption = ""

        if not caption:
            answer, _ = self.camera.analyze_visual_query(prompt)
            return answer

        words = [item for item in re.split(r"[^a-zA-Z0-9]+", caption) if len(item) > 2]
        key_terms = ", ".join(words[:4]) if words else "the visible object"
        return f"Boss, I can see {key_terms} in the frame."
