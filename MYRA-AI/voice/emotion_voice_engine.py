from __future__ import annotations

from dataclasses import replace

from engine.emotion_engine import EmotionEngine
from engine.emotion_reply_engine import EmotionReplyEngine

from .voice_engine import VoiceEngine


class EmotionVoiceEngine(VoiceEngine):
    def __init__(self, emotion_engine=None):
        super().__init__()
        self.emotion_engine = emotion_engine or EmotionEngine()
        self.emotion_reply_engine = EmotionReplyEngine()
        self._last_emotion = ""

    def prepare_response(self, text, user_text=""):
        signal = self.emotion_engine.detect(user_text) if str(user_text).strip() else None
        prepared = super().prepare_response(text)
        if signal and signal.is_emotional:
            self._last_emotion = signal.emotion
            voice_emotion = self.emotion_reply_engine.voice_emotion_for(signal.emotion)
            return replace(prepared, emotion=voice_emotion)
        return prepared

    def status_snapshot(self):
        payload = super().status_snapshot()
        payload["emotion_voice"] = self._last_emotion or "neutral"
        return payload
