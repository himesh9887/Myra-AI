from __future__ import annotations

import re


SPELLING_FIXES: tuple[tuple[str, str], ...] = (
    (r"\bkerna\b", "karna"),
    (r"\bkrna\b", "karna"),
    (r"\bkrne\b", "karne"),
    (r"\bkrdo\b", "kar do"),
    (r"\bkrnao\b", "karna"),
    (r"\bkro\b", "karo"),
    (r"\bplz\b", "please"),
    (r"\bpls\b", "please"),
    (r"\byadd\b", "yaad"),
    (r"\byad\b", "yaad"),
    (r"\bserch\b", "search"),
    (r"\bseach\b", "search"),
    (r"\bopne\b", "open"),
    (r"\bopn\b", "open"),
    (r"\bclsoe\b", "close"),
    (r"\bwatsapp\b", "whatsapp"),
    (r"\bwhatsap\b", "whatsapp"),
    (r"\bchat gpt\b", "chatgpt"),
    (r"\bchat-gpt\b", "chatgpt"),
    (r"\byou tube\b", "youtube"),
)

CASUAL_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bzara\b", ""),
    (r"\bplease\b", ""),
    (r"\bna\b", ""),
    (r"\bjaldi se\b", ""),
    (r"\bek baar\b", ""),
    (r"\bthoda\b", ""),
    (r"\bmera liye\b", "mere liye"),
)


class TextNormalizer:
    """Normalizes noisy Hinglish command text before parsing."""

    def normalize(self, text: str) -> str:
        normalized = str(text or "").strip().lower()
        normalized = normalized.replace("&", " and ")
        normalized = re.sub(r"[^\w\s:/.?+-]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()

        for pattern, replacement in SPELLING_FIXES:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        for pattern, replacement in CASUAL_REPLACEMENTS:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

