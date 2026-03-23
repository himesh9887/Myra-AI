from __future__ import annotations

from engine.voice_engine import PreparedSpeech
from engine.voice_engine import VoiceEngine as LegacyVoiceEngine


class VoiceEngine:
    def __init__(self):
        self._engine = LegacyVoiceEngine()

    def prepare_response(self, text):
        return self._engine.prepare_response(text)

    def speak(self, text):
        return self._engine.speak(text)

    def status_snapshot(self):
        provider = "ElevenLabs" if getattr(self._engine, "api_key", "") else "Edge TTS"
        return {
            "provider": provider,
            "voice": getattr(self._engine, "voice_id", ""),
            "fallback_voice": getattr(self._engine, "edge_voice", ""),
        }

    @property
    def prepared_type(self):
        return PreparedSpeech
