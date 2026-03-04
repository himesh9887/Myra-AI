import re
import webbrowser
from urllib.parse import quote_plus


class SpotifyAgent:
    def handle(self, command):
        normalized = str(command).lower().strip()

        if "open spotify" in normalized:
            return True, self.open_spotify()

        query = self._extract_song_query(normalized)
        if query:
            return True, self.play_song(query)

        return False, ""

    def open_spotify(self):
        try:
            webbrowser.open("https://open.spotify.com", new=0, autoraise=False)
            return "Spotify opened in browser."
        except Exception as exc:
            return f"Sir ji, Spotify open nahi ho paya. {exc}"

    def play_song(self, song):
        try:
            url = f"https://open.spotify.com/search/{quote_plus(song)}"
            webbrowser.open(url, new=0, autoraise=False)
            return "Sir ji, Spotify search open kar diya hai."
        except Exception as exc:
            return f"Sir ji, Spotify search open nahi ho paya. {exc}"

    def _extract_song_query(self, command):
        patterns = [
            r"play song on spotify (.+)",
            r"play (.+) on spotify",
            r"search song on spotify (.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1).strip()
        if "play song on spotify" in command:
            return "top hits"
        return ""
