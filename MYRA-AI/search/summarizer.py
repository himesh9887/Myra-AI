from __future__ import annotations

import re
from typing import Any


class SearchSummarizer:
    """Builds a readable summary from ranked search results."""

    def summarize(self, raw_query: str, optimized_query: str, results: list[dict[str, Any]]) -> dict[str, Any]:
        if not results:
            return {
                "answer": (
                    "No live search results were found. "
                    "Check provider configuration or try a more specific query."
                ),
                "highlights": [],
                "sources": [],
            }

        top_results = results[:3]
        highlights: list[str] = []
        sources: list[dict[str, str]] = []

        for item in top_results:
            snippet = self._clean_text(item.get("snippet", ""))
            title = self._clean_text(item.get("title", ""))
            if snippet:
                highlights.append(snippet)
            elif title:
                highlights.append(title)

            url = str(item.get("url", "")).strip()
            if title and url:
                sources.append({"title": title, "url": url})

        answer = self._compose_answer(raw_query, optimized_query, highlights)
        return {
            "answer": answer,
            "highlights": highlights,
            "sources": sources,
        }

    def _compose_answer(self, raw_query: str, optimized_query: str, highlights: list[str]) -> str:
        if not highlights:
            return f"Search completed for '{raw_query}', but there was not enough content to summarize."

        lead = highlights[0]
        if len(highlights) == 1:
            return f"Here is the quick summary for '{raw_query}': {lead}"

        second = highlights[1]
        tail = f" The search was optimized as '{optimized_query}'."
        return f"Here is the quick summary for '{raw_query}': {lead} {second}{tail}"

    def _clean_text(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(value)).strip()
        cleaned = re.sub(r"\s+([,.!?])", r"\1", cleaned)
        return cleaned

