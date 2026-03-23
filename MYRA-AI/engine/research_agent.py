import re
import webbrowser
from urllib.parse import quote_plus

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

from engine.ai_brain import ask_ai


class ResearchAgent:
    def handle(self, command):
        normalized = str(command).lower().strip()

        news_topic = self._extract_news_topic(normalized)
        if news_topic:
            return True, self._open_news_search(news_topic)

        page_topic = self._extract_page_summary_target(normalized)
        if page_topic:
            return True, self._summarize_topic(page_topic)

        topic = self._extract_topic(normalized)
        if not topic:
            return False, ""

        summary = self._research_topic(topic)
        return True, summary

    def _extract_topic(self, command):
        patterns = [
            r"research\s+(.+)",
            r"research about\s+(.+)",
            r"find information about\s+(.+)",
            r"latest trends in\s+(.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_news_topic(self, command):
        patterns = [
            r"news about\s+(.+)",
            r"latest news on\s+(.+)",
            r"show news for\s+(.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_page_summary_target(self, command):
        patterns = [
            r"summarize\s+(.+)",
            r"summary of\s+(.+)",
            r"summarize page\s+(.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1).strip()
        return ""

    def _research_topic(self, topic):
        browser_url = f"https://www.google.com/search?q={quote_plus(topic)}"
        webbrowser.open(browser_url, new=0, autoraise=False)

        if requests is None:
            return (
                f"Sir ji, maine Google results open kar diye hain for {topic}, "
                "lekin detailed research summary ke liye requests install karna padega."
            )

        parts = []

        wiki = self._fetch_wikipedia_summary(topic)
        if wiki:
            parts.append(wiki)

        instant = self._fetch_instant_answer(topic)
        if instant and instant not in parts:
            parts.append(instant)

        top_results = self._extract_top_results(topic)
        if top_results:
            parts.append("Top results: " + " | ".join(top_results))

        if not parts:
            return (
                f"Sir ji, maine Google results open kar diye hain for {topic}. "
                "Abhi live summary fetch nahi ho pa rahi."
            )

        summary = self._summarize_research(topic, parts)
        return f"Sir ji, research summary for {topic}: {summary}"

    def _fetch_wikipedia_summary(self, topic):
        title = topic.strip().replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote_plus(title)}"

        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                return ""
            payload = response.json()
        except Exception:
            return ""

        return str(payload.get("extract", "")).strip()

    def _fetch_instant_answer(self, topic):
        url = "https://api.duckduckgo.com/"
        params = {
            "q": topic,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }

        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return ""

        abstract = str(payload.get("AbstractText", "")).strip()
        if abstract:
            return abstract

        related = payload.get("RelatedTopics", [])
        for item in related:
            if isinstance(item, dict) and item.get("Text"):
                return str(item["Text"]).strip()
        return ""

    def _open_news_search(self, topic):
        url = f"https://news.google.com/search?q={quote_plus(topic)}"
        webbrowser.open(url, new=0, autoraise=False)
        return f"Sir ji, maine latest news search open kar di hai for {topic}."

    def _summarize_topic(self, topic):
        parts = []

        wiki = self._fetch_wikipedia_summary(topic) if requests is not None else ""
        if wiki:
            parts.append(wiki)

        instant = self._fetch_instant_answer(topic) if requests is not None else ""
        if instant and instant not in parts:
            parts.append(instant)

        if not parts:
            webbrowser.open(
                f"https://www.google.com/search?q={quote_plus(topic)}",
                new=0,
                autoraise=False,
            )
            return (
                f"Sir ji, maine web search open kar diya hai for {topic}, "
                "lekin abhi summary fetch nahi ho pa rahi."
            )

        return f"Sir ji, summary for {topic}: {' '.join(parts)}"

    def _extract_top_results(self, topic):
        url = "https://api.duckduckgo.com/"
        params = {
            "q": topic,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }

        try:
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return []

        results = []
        for item in payload.get("RelatedTopics", []):
            if not isinstance(item, dict):
                continue
            text = str(item.get("Text", "")).strip()
            if text:
                results.append(text)
            elif isinstance(item.get("Topics"), list):
                for nested in item["Topics"]:
                    nested_text = str(nested.get("Text", "")).strip()
                    if nested_text:
                        results.append(nested_text)
                    if len(results) == 3:
                        return results
            if len(results) == 3:
                return results
        return results

    def _summarize_research(self, topic, parts):
        joined = " ".join(parts)
        prompt = (
            "Summarize this research in 4 short casual Hinglish sentences for Boss. "
            "Sound natural, helpful, and non-robotic. "
            f"Topic: {topic}. Research notes: {joined}"
        )
        summary = ask_ai(prompt)
        if summary.lower().startswith("ai service temporarily unavailable") or summary.lower().startswith("ai error"):
            return joined
        return summary
