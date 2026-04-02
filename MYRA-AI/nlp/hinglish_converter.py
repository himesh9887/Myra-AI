from __future__ import annotations

import re


CONNECTOR_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\baur\b", "and"),
    (r"\bphir\b", "then"),
    (r"\bfir\b", "then"),
    (r"\buske baad\b", "then"),
    (r"\bthen\b", "then"),
)

PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bkhol do\b", "open"),
    (r"\bkhol de\b", "open"),
    (r"\bkholna\b", "open"),
    (r"\bkholo\b", "open"),
    (r"\bkhol\b", "open"),
    (r"\bopen karo\b", "open"),
    (r"\bopen karna\b", "open"),
    (r"\bopen kar\b", "open"),
    (r"\bband karo\b", "close"),
    (r"\bband karna\b", "close"),
    (r"\bband kar\b", "close"),
    (r"\bsearch karo\b", "search"),
    (r"\bsearch karna\b", "search"),
    (r"\bsearch kar\b", "search"),
    (r"\bdhoondo\b", "search"),
    (r"\bdhundho\b", "search"),
    (r"\bdhundo\b", "search"),
    (r"\bfind karo\b", "search"),
    (r"\bchalao\b", "play"),
    (r"\bplay karo\b", "play"),
    (r"\bplay karna\b", "play"),
    (r"\bplay kar\b", "play"),
)

FILLERS = {
    "do",
    "de",
    "dena",
    "denaa",
    "zara",
    "please",
}


class HinglishConverter:
    """Converts normalized Hinglish commands into structured English phrases."""

    def convert(self, text: str) -> str:
        converted = f" {str(text or '').strip().lower()} "

        for pattern, replacement in CONNECTOR_REPLACEMENTS:
            converted = re.sub(pattern, f" {replacement} ", converted, flags=re.IGNORECASE)

        for pattern, replacement in PHRASE_REPLACEMENTS:
            converted = re.sub(pattern, f" {replacement} ", converted, flags=re.IGNORECASE)

        converted = re.sub(r"\s+", " ", converted).strip()
        segments = [self._rewrite_segment(segment) for segment in self._split_connectors(converted)]
        return self._rejoin_segments(segments, converted)

    def _rewrite_segment(self, segment: str) -> str:
        text = " ".join(word for word in segment.split() if word not in FILLERS).strip()
        if not text:
            return ""

        if re.match(r"^(open|close|search|play|go to)\b", text):
            return self._cleanup_tail(text)

        patterns = (
            (r"^(?P<object>.+?)\s+open$", "open {object}"),
            (r"^(?P<object>.+?)\s+close$", "close {object}"),
            (r"^(?P<object>.+?)\s+play$", "play {object}"),
            (r"^(?P<object>.+?)\s+search$", "search {object}"),
            (r"^(?P<object>.+?)\s+google search$", "search {object}"),
        )
        for pattern, template in patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if match:
                obj = self._cleanup_tail(match.group("object"))
                return template.format(object=obj).strip()

        return self._cleanup_tail(text)

    def _cleanup_tail(self, value: str) -> str:
        cleaned = re.sub(r"\b(karna|karne|karo|kar)\b", "", value, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _split_connectors(self, text: str) -> list[str]:
        return [part.strip() for part in re.split(r"\b(?:and|then)\b", text) if part.strip()]

    def _rejoin_segments(self, segments: list[str], original_text: str) -> str:
        connectors = re.findall(r"\b(?:and|then)\b", original_text)
        if not connectors or len(segments) <= 1:
            return segments[0] if segments else ""

        rebuilt: list[str] = []
        for index, segment in enumerate(segments):
            rebuilt.append(segment)
            if index < len(connectors):
                rebuilt.append(connectors[index])
        return " ".join(item for item in rebuilt if item).strip()

