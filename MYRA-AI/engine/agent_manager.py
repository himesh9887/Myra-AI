from __future__ import annotations

import re
from pathlib import Path

from agents import (
    AppAgent,
    AutomationAgent,
    BrowserAgent,
    DownloadAgent,
    FileAgent,
    NetControlAgent,
    ResearchAgent,
    SystemAgent,
    WhatsAppAgent,
    YouTubeAgent,
)


class AgentManager:
    def __init__(self, base_dir=None, **dependencies):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
        self._browser_sites = {
            "youtube",
            "you tube",
            "google",
            "gmail",
            "github",
            "instagram",
            "facebook",
            "linkedin",
            "netflix",
            "spotify",
            "chatgpt",
            "news",
            "weather",
            "wikipedia",
        }
        self._agents = {}
        self.configure_agents(**dependencies)

    def configure_agents(self, **dependencies):
        self._agents = {
            "browser": BrowserAgent(browser=dependencies.get("browser"), web=dependencies.get("web")),
            "research": ResearchAgent(research=dependencies.get("research")),
            "system": SystemAgent(self.base_dir, system=dependencies.get("system"), apps=dependencies.get("apps")),
            "automation": AutomationAgent(controller=dependencies.get("automation")),
            "youtube": YouTubeAgent(youtube=dependencies.get("youtube"), web=dependencies.get("web")),
            "whatsapp": WhatsAppAgent(whatsapp=dependencies.get("whatsapp")),
            "download": DownloadAgent(download=dependencies.get("download")),
            "file": FileAgent(self.base_dir, files=dependencies.get("files")),
            "netcontrol": NetControlAgent(self.base_dir, bridge=dependencies.get("netcontrol")),
            "app": AppAgent(apps=dependencies.get("apps")),
        }
        return self

    def get_agent(self, name: str):
        return self._agents.get(str(name).strip().lower())

    def list_agents(self):
        return tuple(self._agents)

    def route(self, command: str):
        normalized = " ".join(str(command).lower().split())
        if not normalized:
            return "", None

        netcontrol_agent = self._agents.get("netcontrol")
        if netcontrol_agent is not None and hasattr(netcontrol_agent, "should_claim_input"):
            if netcontrol_agent.should_claim_input(normalized):
                return "netcontrol", netcontrol_agent

        whatsapp_agent = self._agents.get("whatsapp")
        if whatsapp_agent is not None and hasattr(whatsapp_agent, "whatsapp"):
            inner = getattr(whatsapp_agent, "whatsapp", None)
            if inner is not None and hasattr(inner, "can_claim_followup") and inner.can_claim_followup(normalized):
                return "whatsapp", whatsapp_agent

        if self._looks_like_research(normalized):
            return "research", self._agents["research"]
        if self._looks_like_whatsapp(normalized):
            return "whatsapp", self._agents["whatsapp"]
        if self._looks_like_download(normalized):
            return "download", self._agents["download"]
        if self._looks_like_file(normalized):
            return "file", self._agents["file"]
        if self._looks_like_netcontrol(normalized):
            return "netcontrol", self._agents["netcontrol"]
        if self._looks_like_automation(normalized):
            return "automation", self._agents["automation"]
        if self._looks_like_system(normalized):
            return "system", self._agents["system"]
        if self._looks_like_browser(normalized):
            return "browser", self._agents["browser"]
        if self._looks_like_youtube(normalized):
            return "youtube", self._agents["youtube"]
        if self._looks_like_app(normalized):
            return "app", self._agents["app"]
        return "", None

    def handle(self, command: str):
        agent_name, agent = self.route(command)
        if not agent:
            return False, ""

        handled, message = agent.handle(command)
        if handled:
            return True, message

        for fallback_name in self._fallback_agent_names(agent_name):
            fallback = self._agents.get(fallback_name)
            if not fallback:
                continue
            handled, message = fallback.handle(command)
            if handled:
                return True, message
        return False, ""

    def execute(self, task):
        if isinstance(task, dict):
            agent_name = str(task.get("agent", "")).strip().lower()
            agent = self.get_agent(agent_name) if agent_name else None
            if agent is None:
                agent_name, agent = self.route(task.get("payload", "") or task.get("goal", ""))
            if not agent:
                return ""
            return agent.execute(task)

        agent_name, agent = self.route(task)
        if not agent:
            return ""
        return agent.execute(task)

    def _fallback_agent_names(self, primary: str):
        fallback_map = {
            "app": ("system", "browser"),
            "system": ("app",),
            "browser": ("research", "app"),
            "youtube": ("browser",),
            "research": ("browser",),
            "download": ("browser",),
            "automation": ("system", "app"),
            "netcontrol": ("system", "browser"),
        }
        return fallback_map.get(primary, ())

    def _looks_like_browser(self, normalized: str):
        if self._looks_like_direct_site_open(normalized):
            return True
        browser_tokens = [
            "search ",
            "google search",
            "browse ",
            "look up ",
            "open website",
            "open site",
            "website ",
            "news ",
            "weather",
            "wikipedia",
        ]
        return any(token in normalized for token in browser_tokens)

    def _looks_like_research(self, normalized: str):
        research_tokens = [
            "research ",
            "research about",
            "best ai",
            "best python",
            "compare ",
            "analyze ",
            "analysis ",
            "find information",
            "summarize ",
            "summary of",
        ]
        return any(token in normalized for token in research_tokens)

    def _looks_like_system(self, normalized: str):
        system_tokens = [
            "volume",
            "brightness",
            "mute",
            "lock",
            "shutdown",
            "restart",
            "sleep",
            "screenshot",
            "battery",
            "cpu",
            "ram",
            "memory",
            "disk",
            "storage",
            "task manager",
            "settings",
            "switch window",
            "minimize window",
            "maximize window",
        ]
        return self._matches_any(normalized, system_tokens)

    def _looks_like_automation(self, normalized: str):
        automation_tokens = [
            "move mouse",
            "mouse to",
            "drag mouse",
            "drag to",
            "scroll ",
            "press hotkey",
            "press shortcut",
            "shortcut ",
            "press key",
            "type text",
            "right click",
            "double click",
            "left click",
            "copy that",
            "paste here",
            "mouse position",
            "cursor position",
            "activate window",
            "focus window",
            "resize window",
            "macro",
        ]
        return any(token in normalized for token in automation_tokens)

    def _looks_like_youtube(self, normalized: str):
        if self._looks_like_direct_site_open(normalized):
            return False
        media_tokens = [
            "play ",
            "play song",
            "play music",
            "play video",
            "youtube search",
            " on youtube",
            "youtube par",
            "youtube pe",
            "youtube pr",
            "song ",
            "music ",
            "video ",
        ]
        return any(token in normalized for token in media_tokens)

    def _looks_like_whatsapp(self, normalized: str):
        tokens = [
            "whatsapp",
            "send message",
            "send image",
            "send file",
            "send voice",
            "voice message",
            "voice note",
            "call ",
            "chat ",
        ]
        if self._matches_any(normalized, tokens):
            return True
        patterns = (
            r"^.+?\sko\s+block(?:\s+kar|\s+kar do|\s+karna|\s+do)?$",
            r"^.+?\sko\s+unblock(?:\s+kar|\s+kar do|\s+karna|\s+do)?$",
            r"^block\s+.+$",
            r"^unblock\s+.+$",
            r"^.+?\sko\s+(?:message|msg)\s+(?:bhej|send)(?:\s+do|\s+de|\s+kar do|\s+kar)?\s+.+$",
            r"^(?:send|bhej)\s+(?:message|msg)\s+to\s+.+?\s+.+$",
        )
        return any(re.match(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    def _looks_like_download(self, normalized: str):
        return normalized.startswith("download ") or "download file" in normalized or "download from" in normalized

    def _looks_like_file(self, normalized: str):
        file_tokens = [
            "file ",
            "folder ",
            "create file",
            "create folder",
            "delete file",
            "rename file",
            "find file",
            "search file",
            "open file",
        ]
        return any(token in normalized for token in file_tokens)

    def _looks_like_netcontrol(self, normalized: str):
        if normalized == "show logs":
            return True
        if normalized.startswith("block site "):
            return True
        if "focus mode" in normalized:
            return True
        if "vision monitor" in normalized or "vision monitoring" in normalized:
            return True
        if "study mode" in normalized or "study mood" in normalized:
            return True
        if "netcontrol" in normalized:
            return True
        if normalized in {"internet on", "internet off"}:
            return True
        return any(
            token in normalized
            for token in (
                "check network",
                "network status",
                "internet status",
                "internet speed",
                "wifi status",
                "scan wifi",
                "wifi scan",
                "network ping",
            )
        )

    def _looks_like_app(self, normalized: str):
        if self._looks_like_direct_site_open(normalized):
            return False
        return bool(
            re.search(r"^(?:open|launch|start|run|close|terminate)\s+.+$", normalized)
            or re.search(r"^.+\s+(?:open|close)$", normalized)
        )

    def _matches_any(self, normalized: str, tokens):
        text = str(normalized).lower()
        for token in tokens:
            value = str(token).strip().lower()
            if not value:
                continue
            pattern = r"(?<!\w)" + re.escape(value).replace(r"\ ", r"\s+") + r"(?!\w)"
            if re.search(pattern, text, flags=re.IGNORECASE):
                return True
        return False

    def _looks_like_direct_site_open(self, normalized: str):
        site_pattern = "|".join(sorted((re.escape(site) for site in self._browser_sites), key=len, reverse=True))
        if not site_pattern:
            return False
        return bool(
            re.search(rf"^(?:open|launch|start|run)\s+(?:{site_pattern})$", normalized)
            or re.search(rf"^(?:{site_pattern})\s+open$", normalized)
        )
