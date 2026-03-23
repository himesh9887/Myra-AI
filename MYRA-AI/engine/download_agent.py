import re
from pathlib import Path
from urllib.parse import urlparse

import requests


class DownloadAgent:
    def __init__(self):
        self.download_dir = Path.home() / "Downloads"

    def handle(self, command):
        raw = str(command).strip()
        normalized = raw.lower()

        url = self._extract_url(raw)
        if url:
            return True, self.download_url(url)

        if normalized.startswith("download "):
            topic = raw[9:].strip()
            return True, self.search_download(topic)

        return False, ""

    def download_url(self, url):
        self.download_dir.mkdir(parents=True, exist_ok=True)
        file_name = self._infer_filename(url)
        target = self.download_dir / file_name

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            target.write_bytes(response.content)
            return f"Boss, file download ho gayi hai as {target.name}."
        except Exception as exc:
            return f"Boss, file download nahi ho payi. {exc}"

    def search_download(self, topic):
        query = topic.strip()
        if not query:
            return "Boss, download query clear nahi hai."
        try:
            import webbrowser
            from urllib.parse import quote_plus

            webbrowser.open(
                f"https://www.google.com/search?q={quote_plus(query + ' filetype:pdf OR filetype:zip')}",
                new=0,
                autoraise=False,
            )
            return f"Boss, {query} ke download results open kar diye hain."
        except Exception as exc:
            return f"Boss, download search open nahi ho paya. {exc}"

    def _extract_url(self, text):
        match = re.search(r"(https?://[^\s]+)", text)
        if match:
            return match.group(1)
        return ""

    def _infer_filename(self, url):
        parsed = urlparse(url)
        name = Path(parsed.path).name
        return name or "downloaded_file"
