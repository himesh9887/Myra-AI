from __future__ import annotations

import re
from dataclasses import dataclass, field


HINGLISH_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bkaise\b", "how"),
    (r"\bkya\b", "what"),
    (r"\bkyu\b", "why"),
    (r"\bkyon\b", "why"),
    (r"\bkab\b", "when"),
    (r"\bkaun\b", "who"),
    (r"\baaj\b", "today"),
    (r"\bkal\b", "tomorrow"),
    (r"\bparso\b", "day after tomorrow"),
    (r"\bmausam\b", "weather"),
    (r"\bkhabar\b", "news"),
    (r"\bdaam\b", "price"),
    (r"\brate\b", "price"),
    (r"\bnaya\b", "new"),
    (r"\bbest\b", "best"),
    (r"\bnearby\b", "nearby"),
    (r"\bpaas\b", "near"),
    (r"\bpass\b", "near"),
    (r"\brecipe\b", "recipe"),
    (r"\breview\b", "review"),
    (r"\bcompare\b", "compare"),
    (r"\bvs\b", "vs"),
)

STOPWORDS = {
    "a",
    "an",
    "aur",
    "batao",
    "batana",
    "bhi",
    "hai",
    "hain",
    "he",
    "hi",
    "i",
    "info",
    "information",
    "ka",
    "ke",
    "ki",
    "kr",
    "kro",
    "me",
    "mera",
    "meri",
    "mujhe",
    "of",
    "please",
    "plz",
    "sirf",
    "the",
    "to",
    "zara",
}


@dataclass(slots=True)
class SearchQuery:
    raw_query: str
    normalized_query: str
    optimized_query: str
    intent: str
    keywords: list[str] = field(default_factory=list)


class QueryBuilder:
    """Converts a user query into a provider-friendly search query."""

    def build(self, query: str) -> SearchQuery:
        normalized = self._normalize(query)
        translated = self._translate_hinglish(normalized)
        intent = self._detect_intent(translated)
        optimized = self._optimize_query(translated, intent)
        keywords = self._extract_keywords(optimized)

        return SearchQuery(
            raw_query=str(query).strip(),
            normalized_query=translated,
            optimized_query=optimized,
            intent=intent,
            keywords=keywords,
        )

    def _normalize(self, query: str) -> str:
        cleaned = str(query).strip().lower()
        cleaned = re.sub(r"[^\w\s:/.-]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    def _translate_hinglish(self, text: str) -> str:
        translated = f" {text} "
        for pattern, replacement in HINGLISH_REPLACEMENTS:
            translated = re.sub(pattern, replacement, translated, flags=re.IGNORECASE)
        translated = re.sub(r"\s+", " ", translated)
        return translated.strip()

    def _detect_intent(self, text: str) -> str:
        if any(token in text for token in ("latest", "today", "news", "headlines", "recent")):
            return "news"
        if any(token in text for token in ("weather", "forecast", "temperature", "rain")):
            return "weather"
        if any(token in text for token in ("price", "stock", "rate", "cost")):
            return "price"
        if any(token in text for token in ("review", "best", "top", "compare", "vs")):
            return "research"
        if any(token in text for token in ("near", "nearby", "location", "where")):
            return "local"
        return "general"

    def _optimize_query(self, text: str, intent: str) -> str:
        tokens = [token for token in text.split() if token not in STOPWORDS]
        compact = " ".join(tokens).strip()

        if intent == "weather":
            return self._optimize_weather(compact)
        if intent == "news":
            return self._append_if_missing(compact, "latest news")
        if intent == "price":
            return self._append_if_missing(compact, "latest price")
        if intent == "research":
            return self._optimize_research(compact)
        if intent == "local":
            return self._append_if_missing(compact, "near me")
        return compact or text

    def _optimize_weather(self, text: str) -> str:
        base = text
        if "forecast" not in base and "weather" in base:
            base = base.replace("weather", "weather forecast")
        if "weather" not in base:
            base = f"{base} weather forecast".strip()
        return re.sub(r"\s+", " ", base).strip()

    def _optimize_research(self, text: str) -> str:
        if "best" in text or "top" in text:
            return self._append_if_missing(text, "2026")
        if "compare" in text or "vs" in text:
            return self._append_if_missing(text, "comparison")
        return text

    def _append_if_missing(self, text: str, suffix: str) -> str:
        lowered = text.lower()
        suffix_words = suffix.lower().split()
        if all(word in lowered for word in suffix_words):
            return text.strip()
        return f"{text} {suffix}".strip()

    def _extract_keywords(self, text: str) -> list[str]:
        words = [word for word in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(word) > 2]
        seen: list[str] = []
        for word in words:
            if word in STOPWORDS or word in seen:
                continue
            seen.append(word)
        return seen[:8]

