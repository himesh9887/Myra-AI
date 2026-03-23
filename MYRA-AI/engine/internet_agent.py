import html
import re
import webbrowser
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None


class InternetAgent:
    def __init__(self):
        self._last_results = []

    def needs_latest_info(self, query):
        text = str(query).lower().strip()
        return any(
            token in text
            for token in [
                "latest",
                "today",
                "recent",
                "news",
                "current",
                "trending",
                "update",
                "headlines",
                "new launch",
                "new feature",
            ]
        )

    def search_google(self, query):
        cleaned = self._clean_query(query)
        if not cleaned:
            return []

        browser_url = f"https://www.google.com/search?q={quote_plus(cleaned)}"
        try:
            webbrowser.open(browser_url, new=0, autoraise=False)
        except Exception:
            pass

        if requests is None:
            self._last_results = [{"title": cleaned, "url": browser_url, "snippet": ""}]
            return self._last_results

        results = self._search_duckduckgo(cleaned)
        if not results and self.needs_latest_info(cleaned):
            results = self._search_news_rss(cleaned)
        if not results:
            results = [{"title": cleaned, "url": browser_url, "snippet": "Google search opened in browser."}]
        self._last_results = results
        return results

    def get_latest_info(self, query):
        cleaned = self._clean_query(query)
        if not cleaned:
            return "Boss, latest info ke liye topic missing hai."

        if requests is None:
            self.search_google(cleaned)
            return f"Give me a second Boss, maine {cleaned} ke liye browser search khol diya hai."

        results = self._search_news_rss(cleaned)
        if not results:
            results = self.search_google(cleaned)
        self._last_results = results
        return self.summarize_results(cleaned, results)

    def fetch_latest_news(self, query):
        cleaned = self._clean_query(query)
        if not cleaned:
            return []
        results = self._search_news_rss(cleaned) if requests is not None else []
        self._last_results = results
        try:
            webbrowser.open(
                f"https://news.google.com/search?q={quote_plus(cleaned)}",
                new=0,
                autoraise=False,
            )
        except Exception:
            pass
        return results

    def summarize_results(self, query=None, results=None):
        active_query = self._clean_query(query) if query else ""
        active_results = results if results is not None else self._last_results
        if not active_results:
            topic = active_query or "that topic"
            return f"Boss, mujhe {topic} ke liye solid live results nahi mile."

        lines = []
        for item in active_results[:3]:
            title = str(item.get("title", "")).strip()
            snippet = str(item.get("snippet", "")).strip()
            source = str(item.get("source", "")).strip()
            if source:
                lines.append(f"{title} ({source}) - {snippet}".strip(" -"))
            else:
                lines.append(f"{title} - {snippet}".strip(" -"))

        topic = active_query or "your topic"
        intro = f"Boss, here's the latest information I found about {topic}."
        return f"{intro} " + " ".join(lines)

    def _search_news_rss(self, query):
        url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-IN&gl=IN&ceid=IN:en"
        try:
            response = requests.get(url, timeout=8)
            response.raise_for_status()
            root = ET.fromstring(response.text)
        except Exception:
            return []

        results = []
        for item in root.findall(".//item")[:5]:
            title = html.unescape(item.findtext("title", default="")).strip()
            link = item.findtext("link", default="").strip()
            source = html.unescape(item.findtext("source", default="")).strip()
            description = self._strip_html(item.findtext("description", default=""))
            results.append(
                {
                    "title": title,
                    "url": link,
                    "snippet": description[:220].strip(),
                    "source": source,
                }
            )
        return results

    def _search_duckduckgo(self, query):
        url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            response = requests.get(url, headers=headers, timeout=8)
            response.raise_for_status()
            body = response.text
        except Exception:
            return []

        results = []
        pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
            r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
            re.IGNORECASE | re.DOTALL,
        )
        for match in pattern.finditer(body):
            title = self._strip_html(match.group("title"))
            snippet = self._strip_html(match.group("snippet"))
            url_value = html.unescape(match.group("url")).strip()
            if title and url_value:
                results.append({"title": title, "url": url_value, "snippet": snippet, "source": "web"})
            if len(results) == 5:
                break
        return results

    def _clean_query(self, query):
        text = " ".join(str(query).split()).strip()
        text = re.sub(
            r"^(what s|what is|who is|tell me|give me|show me|search|find|latest|current|recent)\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return text.strip(" ?.")

    def _strip_html(self, text):
        cleaned = re.sub(r"<[^>]+>", " ", str(text))
        cleaned = html.unescape(cleaned)
        return " ".join(cleaned.split()).strip()
