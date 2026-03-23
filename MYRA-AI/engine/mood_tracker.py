from __future__ import annotations

from engine.emotion_engine import EmotionEngine, EmotionSignal


class MoodTracker:
    def __init__(self, memory, emotion_engine=None):
        self.memory = memory
        self.emotion_engine = emotion_engine or EmotionEngine()

    def track(self, text, source="text"):
        signal = self.emotion_engine.detect(text)
        if signal and signal.is_emotional:
            self.memory.log_mood(signal.emotion, signal.intensity, source=source, note=text)
        return signal

    def latest_mood(self):
        if hasattr(self.memory, "latest_mood"):
            return self.memory.latest_mood()
        return {}

    def mood_history(self):
        if hasattr(self.memory, "mood_history"):
            return self.memory.mood_history(limit=None)
        return {}
