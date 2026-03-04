import re
import webbrowser
from urllib.parse import quote_plus


class WebControl:
    def __init__(self):
        self.direct_sites = {
            "youtube": "https://www.youtube.com",
            "you tube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "wikipedia": "https://www.wikipedia.org",
            "whatsapp": "https://web.whatsapp.com",
            "whatsapp web": "https://web.whatsapp.com",
            "instagram": "https://www.instagram.com",
            "facebook": "https://www.facebook.com",
            "gmail": "https://mail.google.com",
            "github": "https://github.com",
            "linkedin": "https://www.linkedin.com",
            "chatgpt": "https://chatgpt.com",
            "weather": "https://www.google.com/search?q=weather",
            "news": "https://news.google.com",
        }

    def handle(self, command):
        normalized = command.lower().strip()

        wiki_summary_query = self._extract_wikipedia_summary_query(normalized)
        if wiki_summary_query:
            return True, self._wikipedia_summary(wiki_summary_query)

        youtube_query = self._extract_youtube_query(normalized)
        if youtube_query:
            return self._open(
                f"https://www.youtube.com/results?search_query={quote_plus(youtube_query)}",
                "Boss, YouTube search complete ho gaya hai.",
            )

        direct_site = self._match_direct_site(normalized)
        if direct_site:
            site_name, url = direct_site
            return self._open(url, f"Boss, {site_name.title()} open ho gaya hai.")

        google_query = self._extract_google_query(normalized)
        if google_query:
            return self._open(
                f"https://www.google.com/search?q={quote_plus(google_query)}",
                "Boss, Google search complete ho gaya hai.",
            )

        wikipedia_query = self._extract_wikipedia_query(normalized)
        if wikipedia_query:
            return self._open(
                f"https://en.wikipedia.org/wiki/Special:Search?search={quote_plus(wikipedia_query)}",
                "Boss, Wikipedia search complete ho gaya hai.",
            )

        direct_url = self._extract_direct_url(normalized)
        if direct_url:
            return self._open(direct_url, "Boss, link open ho gaya hai.")

        return False, ""

    def _match_direct_site(self, command):
        open_terms = [
            "open",
            "launch",
            "start",
            "khol",
            "kholo",
            "karo",
            "open karo",
            "open karna",
        ]
        if not any(term in command for term in open_terms):
            return None

        for site_name, url in self.direct_sites.items():
            if site_name in command:
                return site_name, url
        return None

    def _extract_youtube_query(self, command):
        patterns = [
            r"search youtube (.+)",
            r"youtube search (.+)",
            r"youtube par (.+) search",
            r"youtube pe (.+) search",
            r"youtube pr (.+) search",
            r"youtube par (.+) dhoondo",
            r"youtube pe (.+) dhoondo",
            r"youtube pr (.+) dhoondo",
            r"youtube par (.+) play",
            r"youtube pe (.+) play",
            r"youtube pr (.+) play",
            r"youtube par (.+) bajao",
            r"youtube pe (.+) bajao",
            r"youtube pr (.+) bajao",
            r"(.+) youtube par search",
            r"(.+) youtube pe search",
            r"(.+) youtube pr search",
            r"(.+) on youtube",
        ]
        return self._first_match(command, patterns)

    def _extract_google_query(self, command):
        patterns = [
            r"search (.+)",
            r"google search (.+)",
            r"google par (.+) search",
            r"google pe (.+) search",
            r"google pr (.+) search",
            r"(.+) search karo",
        ]
        query = self._first_match(command, patterns)
        if not query:
            return ""

        blocked_terms = ["youtube", "wikipedia", "whatsapp", "open", "launch", "start"]
        if any(term in query for term in blocked_terms):
            return ""
        return query

    def _extract_wikipedia_query(self, command):
        patterns = [
            r"wikipedia (.+)",
            r"wikipedia par (.+)",
            r"wikipedia pe (.+)",
            r"wikipedia pr (.+)",
        ]
        return self._first_match(command, patterns)

    def _extract_wikipedia_summary_query(self, command):
        patterns = [
            r"wikipedia summary (.+)",
            r"summary of (.+)",
            r"wiki summary (.+)",
        ]
        return self._first_match(command, patterns)

    def _extract_direct_url(self, command):
        if "link" in command or "website" in command or "." in command:
            match = re.search(r"((?:https?://)?[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s]*)?)", command)
            if match:
                url = match.group(1)
                if not url.startswith("http"):
                    url = f"https://{url}"
                return url
        return ""

    def _first_match(self, command, patterns):
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return self._clean_query(match.group(1))
        return ""

    def _clean_query(self, query):
        cleaned = query.strip()
        fillers = [
            "karo",
            "karo na",
            "please",
            "jara",
            "zara",
            "open",
        ]
        words = [word for word in cleaned.split() if word not in fillers]
        normalized = " ".join(words).strip()

        leading_noise = [
            "song ",
            "gaana ",
            "gana ",
            "video ",
            "music ",
            "youtube ",
        ]
        trailing_noise = [
            " play karo",
            " play",
            " bajao",
            " chalao",
            " search",
        ]

        changed = True
        while changed and normalized:
            changed = False
            for prefix in leading_noise:
                if normalized.startswith(prefix):
                    normalized = normalized[len(prefix):].strip()
                    changed = True
            for suffix in trailing_noise:
                if normalized.endswith(suffix):
                    normalized = normalized[: -len(suffix)].strip()
                    changed = True

        return normalized

    def _open(self, url, message):
        webbrowser.open(url, new=0, autoraise=False)
        return True, message

    def _wikipedia_summary(self, topic):
        try:
            import requests
        except ImportError:
            return "Sir ji, Wikipedia summary ke liye requests install karna padega."

        title = topic.strip().replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote_plus(title)}"

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return "Sir ji, Wikipedia summary abhi fetch nahi ho pa rahi."

        extract = str(data.get("extract", "")).strip()
        if not extract:
            return "Sir ji, is topic ka summary nahi mila."
        return extract
