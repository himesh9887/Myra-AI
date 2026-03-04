import re
import webbrowser
from urllib.parse import quote_plus


class NetflixAgent:
    def handle(self, command):
        normalized = str(command).lower().strip()

        if "open netflix" in normalized:
            return True, self.open_netflix()

        movie = self._extract_movie_query(normalized)
        if movie:
            return True, self.search_movie(movie)

        return False, ""

    def open_netflix(self):
        try:
            webbrowser.open("https://www.netflix.com", new=0, autoraise=False)
            return "Netflix opened in browser."
        except Exception as exc:
            return f"Sir ji, Netflix open nahi ho paya. {exc}"

    def search_movie(self, movie):
        try:
            url = f"https://www.google.com/search?q={quote_plus(movie + ' site:netflix.com')}"
            webbrowser.open(url, new=0, autoraise=False)
            return "Sir ji, Netflix movie search open kar diya hai."
        except Exception as exc:
            return f"Sir ji, Netflix search open nahi ho paya. {exc}"

    def _extract_movie_query(self, command):
        patterns = [
            r"search movie on netflix (.+)",
            r"search (.+) on netflix",
            r"find movie on netflix (.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1).strip()
        if "search movie on netflix" in command:
            return "popular movies"
        return ""
