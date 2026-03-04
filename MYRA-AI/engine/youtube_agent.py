import re
import socket
import webbrowser
from urllib.parse import quote_plus

import pywhatkit


class YouTubeAgent:
    def handle(self, command):
        normalized = str(command).lower().strip()
        query = self._extract_song_query(normalized)
        if not query:
            return False, ""
        return True, self.play_song(query)

    def play_song(self, song):
        if not self._internet_available():
            return "Sir ji, internet available nahi hai. YouTube play nahi ho payega."

        try:
            pywhatkit.playonyt(song)
            return "Song playing on YouTube."
        except Exception:
            search_url = f"https://www.youtube.com/results?search_query={quote_plus(song)}"
            try:
                webbrowser.open(search_url, new=0, autoraise=False)
                return "Sir ji, exact song play nahi hua. YouTube search open kar diya hai."
            except Exception as exc:
                return f"Sir ji, YouTube open nahi ho paya. {exc}"

    def _extract_song_query(self, command):
        patterns = [
            r"play song (.+)",
            r"play music (.+)",
            r"play (.+) on youtube",
            r"youtube play (.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                return match.group(1).strip()
        return ""

    def _internet_available(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2).close()
            return True
        except OSError:
            return False
