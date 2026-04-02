from __future__ import annotations

import os
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False

from pathlib import Path

from .query_builder import QueryBuilder
from .summarizer import SearchSummarizer


load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


class SearchEngine:
    """Real-time search module using SerpAPI or Bing Search API."""

    SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
    BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self) -> None:
        self.query_builder = QueryBuilder()
        self.summarizer = SearchSummarizer()
        self.serpapi_key = os.getenv("SERPAPI_API_KEY", "").strip()
        self.bing_api_key = os.getenv("BING_SEARCH_API_KEY", "").strip()
        self.bing_endpoint = os.getenv("BING_SEARCH_ENDPOINT", self.BING_ENDPOINT).strip() or self.BING_ENDPOINT
        self.timeout = int(os.getenv("SEARCH_HTTP_TIMEOUT", "20") or "20")

    def search(self, query: str) -> dict[str, Any]:
        prepared = self.query_builder.build(query)
        provider = self._select_provider()

        if requests is None:
            return self._empty_response(prepared, provider, "The 'requests' package is not available.")

        try:
            if provider == "serpapi":
                raw_results = self._search_serpapi(prepared.optimized_query)
            elif provider == "bing":
                raw_results = self._search_bing(prepared.optimized_query)
            else:
                return self._empty_response(
                    prepared,
                    "unconfigured",
                    "No search provider is configured. Add SERPAPI_API_KEY or BING_SEARCH_API_KEY to use live search.",
                )
        except Exception as exc:
            return self._empty_response(prepared, provider, f"Search request failed: {exc}")

        ranked_results = self._rank_results(prepared.keywords, raw_results)
        summary = self.summarizer.summarize(prepared.raw_query, prepared.optimized_query, ranked_results)

        return {
            "query": prepared.raw_query,
            "optimized_query": prepared.optimized_query,
            "intent": prepared.intent,
            "provider": provider,
            "answer": summary["answer"],
            "highlights": summary["highlights"],
            "results": ranked_results,
            "sources": summary["sources"],
        }

    def _select_provider(self) -> str:
        if self.serpapi_key:
            return "serpapi"
        if self.bing_api_key:
            return "bing"
        return "unconfigured"

    def _search_serpapi(self, query: str) -> list[dict[str, Any]]:
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serpapi_key,
            "num": 10,
        }
        response = requests.get(self.SERPAPI_ENDPOINT, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        results: list[dict[str, Any]] = []
        for index, item in enumerate(payload.get("organic_results", []), start=1):
            title = str(item.get("title", "")).strip()
            url = str(item.get("link", "")).strip()
            snippet = str(item.get("snippet", "")).strip()
            if not title or not url:
                continue
            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source": str(item.get("source", "")).strip(),
                    "position": index,
                }
            )
        return results

    def _search_bing(self, query: str) -> list[dict[str, Any]]:
        headers = {"Ocp-Apim-Subscription-Key": self.bing_api_key}
        params = {"q": query, "count": 10, "responseFilter": "Webpages"}
        response = requests.get(self.bing_endpoint, headers=headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        results: list[dict[str, Any]] = []
        for index, item in enumerate(payload.get("webPages", {}).get("value", []), start=1):
            title = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            snippet = str(item.get("snippet", "")).strip()
            if not title or not url:
                continue
            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                    "source": str(item.get("displayUrl", "")).strip(),
                    "position": index,
                }
            )
        return results

    def _rank_results(self, query_keywords: list[str], results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique_by_url: dict[str, dict[str, Any]] = {}
        for item in results:
            url = str(item.get("url", "")).strip()
            if not url or url in unique_by_url:
                continue
            unique_by_url[url] = item

        ranked: list[dict[str, Any]] = []
        keyword_set = set(word.lower() for word in query_keywords)

        for item in unique_by_url.values():
            title = str(item.get("title", "")).lower()
            snippet = str(item.get("snippet", "")).lower()
            url = str(item.get("url", "")).lower()
            combined = f"{title} {snippet}"

            overlap = sum(1 for keyword in keyword_set if keyword in combined)
            domain_boost = 0
            if any(token in url for token in (".gov", ".edu", "wikipedia.org", "stackoverflow.com", "github.com")):
                domain_boost += 1
            if item.get("snippet"):
                domain_boost += 0.5

            position = int(item.get("position", 99) or 99)
            position_boost = max(0, 10 - position) * 0.15
            score = round(overlap * 2 + domain_boost + position_boost, 3)

            ranked.append({**item, "score": score})

        ranked.sort(key=lambda row: (row["score"], -int(row.get("position", 99) or 99)), reverse=True)
        return ranked

    def _empty_response(self, prepared, provider: str, reason: str) -> dict[str, Any]:
        return {
            "query": prepared.raw_query,
            "optimized_query": prepared.optimized_query,
            "intent": prepared.intent,
            "provider": provider,
            "answer": reason,
            "highlights": [],
            "results": [],
            "sources": [],
        }


def search(query: str) -> dict[str, Any]:
    """Public function entrypoint for existing chat systems."""

    return SearchEngine().search(query)
