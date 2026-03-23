from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EmotionSignal:
    emotion: str = ""
    intensity: str = "normal"
    matches: tuple[str, ...] = ()
    confidence: float = 0.0

    @property
    def is_emotional(self) -> bool:
        return bool(self.emotion)


class EmotionEngine:
    def __init__(self) -> None:
        self._priority = {
            "stressed": 9,
            "sad": 8,
            "confused": 7,
            "tired": 6,
            "angry": 5,
            "bored": 4,
            "excited": 3,
            "motivated": 2,
            "happy": 1,
        }
        self._patterns = {
            "happy": (
                r"\bhappy\b",
                r"\bglad\b",
                r"\bfeel good\b",
                r"\bfeel great\b",
                r"\bgreat day\b",
                r"\bmood mast\b",
            ),
            "excited": (
                r"\bexcited\b",
                r"\bpumped\b",
                r"\bhyped\b",
                r"\bcan t wait\b",
                r"\bso ready\b",
            ),
            "motivated": (
                r"\bmotivated\b",
                r"\bfocused\b",
                r"\bdetermined\b",
                r"\blet s do this\b",
                r"\bready to grind\b",
                r"\bready to work\b",
            ),
            "sad": (
                r"\bsad\b",
                r"\bfeel low\b",
                r"\bdown\b",
                r"\bupset\b",
                r"\bheartbroken\b",
                r"\bquiet\b",
            ),
            "tired": (
                r"\btired\b",
                r"\bsleepy\b",
                r"\bexhausted\b",
                r"\bdrained\b",
                r"\bworn out\b",
                r"\bburn(?:ed|t) out\b",
                r"\bthak(?:\s+gaya|\s+gayi)?\b",
            ),
            "angry": (
                r"\bangry\b",
                r"\bmad\b",
                r"\bfurious\b",
                r"\bannoyed\b",
                r"\bfrustrated\b",
                r"\birritated\b",
            ),
            "bored": (
                r"\bbored\b",
                r"\bboring\b",
                r"\bdull\b",
                r"\bmann nahin lag raha\b",
            ),
            "confused": (
                r"\bconfused\b",
                r"\bnot sure\b",
                r"\bstuck\b",
                r"\blost\b",
                r"\bdon t understand\b",
                r"\bsamajh nahi aa\b",
            ),
            "stressed": (
                r"\bstressed\b",
                r"\banxious\b",
                r"\boverwhelmed\b",
                r"\btense\b",
                r"\btension\b",
                r"\bunder pressure\b",
                r"\bpanic\b",
            ),
        }
        self._emotion_words = set(self._patterns)
        self._action_starters = (
            "open",
            "close",
            "launch",
            "start",
            "run",
            "play",
            "search",
            "find",
            "google",
            "youtube",
            "send",
            "call",
            "download",
            "increase",
            "decrease",
            "mute",
            "shutdown",
            "restart",
            "sleep",
            "lock",
            "set",
            "switch",
            "maximize",
            "minimize",
            "take",
            "show",
            "scan",
        )

    def detect(self, text: str) -> EmotionSignal:
        normalized = self._normalize(text)
        if not normalized:
            return EmotionSignal()

        has_frame = self._has_emotional_frame(normalized)
        if self._looks_like_action_command(normalized) and not has_frame:
            return EmotionSignal()
        if not has_frame and not self._looks_like_emotion_checkin(normalized):
            return EmotionSignal()

        scores = {}
        matches = {}
        for emotion, patterns in self._patterns.items():
            for pattern in patterns:
                found = [item.group(0).strip() for item in re.finditer(pattern, normalized, flags=re.IGNORECASE)]
                if not found:
                    continue
                scores[emotion] = scores.get(emotion, 0) + len(found)
                matches.setdefault(emotion, []).extend(found)

        if not scores:
            return EmotionSignal()

        emotion = max(scores, key=lambda key: (scores[key], self._priority.get(key, 0)))
        confidence = min(0.99, 0.45 + (scores[emotion] * 0.18) + (0.15 if has_frame else 0.0))
        return EmotionSignal(
            emotion=emotion,
            intensity=self._estimate_intensity(normalized, emotion, scores[emotion]),
            matches=tuple(dict.fromkeys(matches.get(emotion, []))),
            confidence=round(confidence, 2),
        )

    def has_emotion(self, text: str) -> bool:
        return self.detect(text).is_emotional

    def dominant_emotion(self, text: str) -> str:
        return self.detect(text).emotion

    def _normalize(self, text: str) -> str:
        normalized = str(text).lower().strip()
        replacements = {
            "i'm": "im",
            "i am": "im",
            "feeling": "feel",
            "kind of": "",
            "sort of": "",
            "can't": "can t",
        }
        for source, target in replacements.items():
            normalized = normalized.replace(source, target)
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        return " ".join(normalized.split())

    def _has_emotional_frame(self, normalized: str) -> bool:
        if normalized in self._emotion_words:
            return True
        tokens = normalized.split()
        if tokens and tokens[-1] in self._emotion_words:
            return True
        return bool(
            re.search(
                r"\b(?:im|i feel|feel|feels|been|so|very|really|super|extremely|little|bit|today|lately)\b",
                normalized,
            )
        )

    def _looks_like_action_command(self, normalized: str) -> bool:
        if normalized in self._emotion_words:
            return False
        return any(normalized.startswith(starter + " ") or normalized == starter for starter in self._action_starters)

    def _looks_like_emotion_checkin(self, normalized: str) -> bool:
        tokens = normalized.split()
        if not tokens:
            return False
        allowed_tokens = self._emotion_words | {
            "and",
            "but",
            "feel",
            "feeling",
            "im",
            "very",
            "really",
            "so",
            "too",
            "a",
            "bit",
            "little",
            "today",
            "lately",
            "now",
        }
        return len(tokens) <= 6 and all(token in allowed_tokens for token in tokens)

    def _estimate_intensity(self, normalized: str, emotion: str, score: int) -> str:
        strong_terms = {"very", "really", "too", "so", "super", "extremely", "totally"}
        if score > 1 or any(term in normalized.split() for term in strong_terms):
            return "high"
        if emotion in {"angry", "stressed", "sad"} and any(
            token in normalized for token in ("furious", "overwhelmed", "heartbroken", "panic", "burned out", "burnt out")
        ):
            return "high"
        return "normal"
