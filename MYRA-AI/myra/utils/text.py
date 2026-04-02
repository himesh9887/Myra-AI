from __future__ import annotations

import re
from collections import Counter


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "for",
    "from",
    "hai",
    "ho",
    "hu",
    "i",
    "is",
    "kal",
    "ki",
    "main",
    "mera",
    "meri",
    "mujhe",
    "my",
    "of",
    "on",
    "se",
    "tera",
    "the",
    "to",
    "tomorrow",
    "today",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def extract_keywords(text: str, limit: int = 8) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9']+", normalize_text(text))
    ranked = Counter(token for token in tokens if token not in STOPWORDS and len(token) > 2)
    return [word for word, _ in ranked.most_common(limit)]


def keyword_overlap_score(query_keywords: list[str], candidate_keywords: list[str]) -> float:
    if not query_keywords or not candidate_keywords:
        return 0.0
    overlap = set(query_keywords) & set(candidate_keywords)
    return len(overlap) / max(len(set(query_keywords)), 1)


def compact_text(text: str, max_length: int = 140) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."
