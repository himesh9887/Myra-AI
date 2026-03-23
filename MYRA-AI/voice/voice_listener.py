from __future__ import annotations

from engine.listener import VoiceListener as LegacyVoiceListener


class VoiceListener:
    def __init__(self, language="en-IN"):
        self._listener = LegacyVoiceListener(language=language)

    def listen_once(self):
        return self._listener.listen_once()

    @property
    def language(self):
        return self._listener.language
