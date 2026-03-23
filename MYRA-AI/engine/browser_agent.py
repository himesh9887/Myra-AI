import re
import webbrowser
from urllib.parse import quote_plus

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
except Exception:  # pragma: no cover
    webdriver = None
    Options = None


class BrowserAgent:
    SITES = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "gmail": "https://mail.google.com",
        "github": "https://github.com",
        "instagram": "https://www.instagram.com",
        "facebook": "https://www.facebook.com",
        "netflix": "https://www.netflix.com",
        "spotify": "https://open.spotify.com",
    }

    def handle(self, command):
        normalized = str(command).lower().strip()

        search_query = self._extract_search_query(normalized)
        if search_query:
            return True, self.search(search_query)

        site = self._extract_site(normalized)
        if site:
            return True, self.open_site(site)

        return False, ""

    def search(self, query):
        try:
            self._open_url(f"https://www.google.com/search?q={quote_plus(query)}")
            return "Google search opened in browser."
        except Exception as exc:
            return f"Sir ji, browser search open nahi ho paya. {exc}"

    def open_site(self, site_name):
        url = self.SITES.get(site_name)
        if not url:
            return f"Sir ji, {site_name} site supported nahi hai."
        try:
            self._open_url(url)
            return f"{site_name.title()} opened in browser."
        except Exception as exc:
            return f"Sir ji, {site_name} open nahi ho paya. {exc}"

    def _extract_search_query(self, command):
        patterns = [
            r"search (.+)",
            r"google search (.+)",
            r"browse (.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, command)
            if match:
                query = match.group(1).strip()
                blocked = ("youtube", "song", "music")
                if any(token in query for token in blocked):
                    return ""
                return query
        return ""

    def _extract_site(self, command):
        if not command.startswith("open "):
            return ""
        target = command[5:].strip()
        return target if target in self.SITES else ""

    def _open_url(self, url):
        if webdriver is not None and Options is not None:
            try:
                options = Options()
                options.add_experimental_option("detach", True)
                driver = webdriver.Chrome(options=options)
                driver.get(url)
                return
            except Exception:
                pass
        webbrowser.open(url, new=0, autoraise=False)
