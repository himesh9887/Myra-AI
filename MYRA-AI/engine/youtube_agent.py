import re
import socket
import webbrowser
from urllib.parse import quote_plus


class YouTubeAgent:
    def handle(self, command):
        raw = str(command).strip()
        normalized = raw.lower().strip()
        query = self._extract_song_query(raw, normalized)
        if not query:
            return False, ""
        return True, self.play_song(query)

    def play_song(self, song):
        if not self._internet_available():
            return "Sir ji, internet available nahi hai. YouTube play nahi ho payega."

        try:
            import pywhatkit

            pywhatkit.playonyt(song)
            return f"Sure Boss, playing {song} on YouTube."
        except Exception:
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(song)}"
            try:
                webbrowser.open(search_url, new=0, autoraise=False)
                return f"Boss, exact video direct play nahi hua, to maine {song} ka YouTube search khol diya."
            except Exception as exc:
                return f"Boss, YouTube open nahi ho paya. {exc}"

    def _extract_song_query(self, raw_command, normalized_command):
        patterns = [
            r"play song (.+)",
            r"play music (.+)",
            r"play (.+) on youtube",
            r"youtube play (.+)",
            r"youtube par (.+) play",
            r"youtube pe (.+) play",
            r"youtube pr (.+) play",
            r"youtube par (.+) bajao",
            r"youtube pe (.+) bajao",
            r"youtube pr (.+) bajao",
            r"youtube par (.+) chalao",
            r"youtube pe (.+) chalao",
            r"youtube pr (.+) chalao",
            r"(.+) youtube par play",
            r"(.+) youtube pe play",
            r"(.+) youtube pr play",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                query = match.group(1).strip()
                query = re.sub(r"\b(song|music|video|gaana|gana)\b", " ", query, flags=re.IGNORECASE)
                return " ".join(query.split())
        if normalized_command.startswith("play "):
            fallback = re.sub(r"^play\s+", "", raw_command, flags=re.IGNORECASE).strip()
            if fallback:
                return fallback
        return ""

    def _internet_available(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2).close()
            return True
        except OSError:
            return False
