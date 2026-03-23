from __future__ import annotations

from engine.vision_agent import VisionAgent as LegacyVisionAgent


class CameraAgent:
    def __init__(self, base_dir):
        self._agent = LegacyVisionAgent(base_dir)

    def __getattr__(self, item):
        return getattr(self._agent, item)

    def status_snapshot(self):
        return {
            "preview_active": self._agent.is_preview_running(),
            "latest_frame": str(getattr(self._agent, "_latest_preview_path", "")),
        }
