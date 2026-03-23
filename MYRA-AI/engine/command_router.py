import re
from dataclasses import dataclass
from pathlib import Path

from engine.ai_brain import ask_ai
from engine.app_launcher import AppLauncher
from engine.browser_agent import BrowserAgent
from engine.conversation_engine import ConversationEngine
from engine.download_agent import DownloadAgent
from engine.file_engine import FileEngine
from engine.system_control import SystemControl
from engine.web_control import WebControl

try:
    from engine.youtube_agent import YouTubeAgent
except Exception:  # pragma: no cover
    YouTubeAgent = None

try:
    from engine.whatsapp_agent import WhatsAppAgent
except Exception:  # pragma: no cover
    WhatsAppAgent = None


GREETING = "GREETING"
SMALL_TALK = "SMALL_TALK"
SYSTEM_COMMAND = "SYSTEM_COMMAND"
APP_CONTROL = "APP_CONTROL"
WEB_SEARCH = "WEB_SEARCH"
YOUTUBE_PLAY = "YOUTUBE_PLAY"
WHATSAPP_MESSAGE = "WHATSAPP_MESSAGE"
AI_QUESTION = "AI_QUESTION"
FILE_OPERATION = "FILE_OPERATION"
MEMORY_QUERY = "MEMORY_QUERY"
GENERAL_HELP = "GENERAL_HELP"

SYSTEM_CONTROL = SYSTEM_COMMAND
FILE_ACTION = FILE_OPERATION
GENERAL_CONVERSATION = SMALL_TALK


@dataclass
class RoutedCommand:
    category: str
    normalized_text: str
    original_text: str
    payload: str = ""


class CommandRouter:
    CATEGORIES = (
        GREETING,
        SMALL_TALK,
        SYSTEM_COMMAND,
        APP_CONTROL,
        WEB_SEARCH,
        YOUTUBE_PLAY,
        WHATSAPP_MESSAGE,
        AI_QUESTION,
        FILE_OPERATION,
        MEMORY_QUERY,
        GENERAL_HELP,
    )

    def __init__(self, base_dir=None):
        root = Path(base_dir) if base_dir else Path(__file__).resolve().parent.parent
        self.base_dir = root
        self.apps = AppLauncher()
        self.browser = BrowserAgent()
        self.conversation = ConversationEngine()
        self.downloads = DownloadAgent()
        self.files = FileEngine(root)
        self.system = SystemControl(root)
        self.web = WebControl()
        self.youtube = YouTubeAgent() if YouTubeAgent else None
        self.whatsapp = WhatsAppAgent() if WhatsAppAgent else None
        self._context = {
            "last_intent": "",
            "last_subject": "",
            "youtube_opened": False,
            "web_active": False,
            "last_app": "",
        }
        self._known_sites = {
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
        }

    def classify_command(self, command):
        raw = " ".join(str(command).strip().split())
        normalized = self._normalize_text(raw)
        if not normalized:
            return RoutedCommand(SMALL_TALK, normalized, raw)

        if self.conversation.is_greeting(normalized):
            return RoutedCommand(GREETING, normalized, raw)
        if self._looks_like_help(normalized):
            return RoutedCommand(GENERAL_HELP, normalized, raw)
        if self._looks_like_memory_query(normalized):
            return RoutedCommand(MEMORY_QUERY, normalized, raw)
        if self.conversation.can_handle(normalized):
            return RoutedCommand(SMALL_TALK, normalized, raw)
        if self._is_direct_site_open(normalized):
            return RoutedCommand(APP_CONTROL, normalized, raw, self._extract_app_payload(raw, normalized))
        if self._looks_like_whatsapp(normalized):
            return RoutedCommand(WHATSAPP_MESSAGE, normalized, raw, self._extract_whatsapp_payload(raw))
        if self._looks_like_file_action(normalized):
            return RoutedCommand(FILE_OPERATION, normalized, raw)
        if self._looks_like_system_control(normalized):
            return RoutedCommand(SYSTEM_COMMAND, normalized, raw)
        if self._looks_like_youtube(normalized):
            return RoutedCommand(YOUTUBE_PLAY, normalized, raw, self._extract_youtube_query(raw, normalized))
        if self._looks_like_web_search(normalized):
            return RoutedCommand(WEB_SEARCH, normalized, raw, self._extract_search_query(raw, normalized))
        if self._looks_like_app_control(normalized):
            return RoutedCommand(APP_CONTROL, normalized, raw, self._extract_app_payload(raw, normalized))
        if self._looks_like_ai_question(normalized):
            return RoutedCommand(AI_QUESTION, normalized, raw)
        return RoutedCommand(AI_QUESTION, normalized, raw)

    def handle(self, command, profile=None):
        routed = self.classify_command(command)
        normalized = routed.normalized_text
        raw = routed.original_text

        if not normalized:
            return "Boss, command clear nahi tha."

        if routed.category == GREETING:
            reply = self.conversation.handle_greeting(normalized, context=self._conversation_context(profile))
            self._remember_context(routed.category, normalized)
            return reply

        if routed.category == GENERAL_HELP:
            self._remember_context(routed.category, normalized)
            return self.conversation.general_help()

        if routed.category == SMALL_TALK:
            reply = self.conversation.friendly_reply(normalized, context=self._conversation_context(profile))
            self._remember_context(routed.category, normalized)
            return reply

        if routed.category == MEMORY_QUERY:
            reply = self._handle_memory_query(normalized, profile)
            if reply:
                self._remember_context(routed.category, normalized)
                return reply

        if routed.category == WHATSAPP_MESSAGE:
            handled, message = self._safe_handle(self.whatsapp, raw)
            if handled:
                self._remember_context(routed.category, routed.payload or normalized)
                return self._normalize_reply(message)
            return "Boss, WhatsApp command samajh aa gaya but thoda clear format me bolo."

        if routed.category == FILE_OPERATION:
            result = self._handle_file_action(raw, normalized)
            if result:
                self._remember_context(routed.category, normalized)
                return result

        if routed.category == SYSTEM_COMMAND:
            result = self._handle_system_control(normalized)
            if result:
                self._remember_context(routed.category, normalized)
                return result

        if routed.category == YOUTUBE_PLAY:
            result = self._handle_youtube(raw, normalized, routed.payload)
            if result:
                self._remember_context(routed.category, routed.payload or normalized)
                return result

        if routed.category == WEB_SEARCH:
            result = self._handle_web(raw, normalized, routed.payload)
            if result:
                self._remember_context(routed.category, routed.payload or normalized)
                return result

        if routed.category == APP_CONTROL:
            result = self._handle_app_control(raw, normalized, routed.payload)
            if result:
                self._remember_context(routed.category, routed.payload or normalized)
                return result

        if routed.category == AI_QUESTION:
            self._remember_context(routed.category, normalized)
            return self._answer_with_ai(raw, profile=profile)

        return self._smart_fallback(raw, profile=profile)

    def _handle_app_control(self, raw, normalized, payload):
        open_match = re.search(
            r"(?:can you |could you |please |for me )*\b(?:open|launch|start|run)\b\s+(.+)$",
            normalized,
        )
        if not open_match:
            open_match = re.search(r"(.+?)\s+\bopen\b$", normalized)
        if open_match:
            app_name = payload or open_match.group(1).strip()
            folder_name = self._extract_known_folder(app_name)
            if folder_name:
                return self.system.open_known_folder(folder_name)
            if app_name in self._known_sites:
                handled, message = self.web.handle(f"open {app_name}")
                if handled:
                    return self._normalize_reply(message)
            _, message = self.apps.open_application(app_name)
            return self._normalize_reply(message)

        close_match = re.search(r"(?:please )?\b(?:close|terminate)\b\s+(.+)$", normalized)
        if not close_match:
            close_match = re.search(r"(.+?)\s+\bclose\b$", normalized)
        if close_match:
            app_name = payload or close_match.group(1).strip()
            _, message = self.apps.close_application(app_name)
            return self._normalize_reply(message)
        return ""

    def _handle_web(self, raw, normalized, payload):
        query = payload.strip()
        if query and self._looks_like_download(normalized):
            handled, message = self.downloads.handle(f"download {query}")
            if handled:
                return self._normalize_reply(message)

        handled, message = self.web.handle(raw)
        if handled:
            return self._normalize_reply(message)

        if query:
            try:
                self.browser.search(query)
                return f"Alright Boss, searching Google for {query}."
            except Exception:
                pass
        return self._smart_fallback(raw)

    def _handle_youtube(self, raw, normalized, payload):
        query = payload.strip()
        if self.youtube is not None:
            handled, message = self._safe_handle(self.youtube, raw)
            if handled:
                return self._normalize_reply(message)

        if not query:
            query = self._extract_youtube_query(raw, normalized) or self._extract_followup_media_query(normalized)
        if not query:
            return "Boss, YouTube par kya play karna hai?"

        handled, message = self.web.handle(f"youtube search {query}")
        if handled:
            return f"Playing {query} on YouTube Boss."
        return self._smart_fallback(raw)

    def _handle_system_control(self, normalized):
        volume_percent = self.system.extract_volume_percent(normalized)
        if volume_percent is not None:
            return self.system.set_volume_percent(volume_percent)

        brightness_percent = self.system.extract_brightness_percent(normalized)
        if brightness_percent is not None:
            return self.system.set_brightness_percent(brightness_percent)

        if self._contains_any(normalized, ["volume up", "increase volume", "awaz badha", "sound badha", "volume badhao", "sound badhao"]):
            return self.system.volume_up()
        if self._contains_any(normalized, ["volume down", "decrease volume", "awaz kam", "sound kam", "volume kam karo", "sound kam karo"]):
            return self.system.volume_down()
        if self._contains_any(normalized, ["mute", "silent", "chup", "awaz band"]):
            return self.system.mute_toggle()
        if self._contains_any(normalized, ["brightness up", "increase brightness", "brightness badha", "brightness badhao", "light badhao"]):
            return self.system.increase_brightness()
        if self._contains_any(normalized, ["brightness down", "decrease brightness", "brightness kam", "brightness kam karo", "light kam karo"]):
            return self.system.decrease_brightness()
        if self._contains_any(normalized, ["screenshot", "screen capture", "photo le"]):
            return self.system.take_screenshot()
        if self._contains_any(normalized, ["shutdown", "shut down", "pc band", "laptop band", "system band", "computer band"]):
            return self.system.shutdown()
        if self._contains_any(normalized, ["restart", "re start", "dobara chalu", "reboot"]):
            return self.system.restart()
        if self._contains_any(normalized, ["sleep", "sleep mode"]):
            return self.system.sleep_mode()
        if self._contains_any(normalized, ["lock", "lock screen"]):
            return self.system.lock_system()
        if "battery" in normalized:
            return self.system.battery_status()
        if self._contains_any(normalized, ["time", "samay", "date", "din", "today date", "current time"]):
            return self.system.date_time_status()
        if self._contains_any(normalized, ["wifi", "internet", "network"]):
            if "speed" in normalized:
                return self.system.internet_speed()
            return self.system.network_status()
        if self._contains_any(normalized, ["system status", "pc status", "laptop status", "status batao"]):
            return self.system.system_status()
        if "cpu" in normalized:
            return self.system.cpu_usage()
        if "ram" in normalized or "memory" in normalized:
            return self.system.ram_usage()
        if "disk" in normalized or "storage" in normalized:
            return self.system.disk_usage()
        if self._contains_any(normalized, ["task manager", "taskmanager"]):
            return self.system.open_task_manager()
        if self._contains_any(normalized, ["settings", "setting"]):
            return self.system.open_settings()
        if self._contains_any(normalized, ["switch window", "window switch", "next window"]):
            return self.system.switch_window()
        if self._contains_any(normalized, ["minimize window", "window minimize", "neeche karo"]):
            return self.system.minimize_current_window()
        if self._contains_any(normalized, ["maximize window", "window maximize", "bada karo", "full screen"]):
            return self.system.maximize_current_window()
        return ""

    def _handle_file_action(self, raw, normalized):
        if "download" in normalized:
            handled, message = self.downloads.handle(raw)
            if handled:
                return self._normalize_reply(message)

        folder_name = self._extract_known_folder(normalized)
        if folder_name and self._contains_any(normalized, ["folder", "open"]):
            return self.system.open_known_folder(folder_name)

        handled, message = self.files.handle(raw)
        if handled:
            return self._normalize_reply(message)
        return ""

    def _answer_with_ai(self, raw, profile=None):
        answer = ask_ai(raw, profile=profile)
        return self._normalize_reply(answer)

    def _smart_fallback(self, raw, profile=None):
        query = raw.strip()
        if query:
            try:
                self.browser.search(query)
                return f"Boss, exact intent clear nahi hua, isliye maine Google search khol diya for {query}."
            except Exception:
                pass
        return self._answer_with_ai(raw, profile=profile)

    def _safe_handle(self, agent, command):
        if agent is None:
            return False, ""
        try:
            return agent.handle(command)
        except Exception:
            return False, ""

    def _handle_memory_query(self, normalized, profile):
        profile = profile if isinstance(profile, dict) else {}
        name = profile.get("name", "Boss")
        course = profile.get("course", "")
        semester = profile.get("semester", "")
        field = profile.get("field", "")
        interests = ", ".join(profile.get("interests", []))
        project = profile.get("current_project", "")

        if normalized in {"what is my name", "what s my name", "my profile"}:
            return f"Your name is {name}, Boss."
        if normalized in {"what is my course", "what am i studying"}:
            return f"You are studying {course} in {semester}, Boss."
        if normalized in {"what is my field", "my field"}:
            return f"Your field is {field}, Boss."
        if normalized in {"what are my interests", "my interests"}:
            return f"Your interests are {interests}, Boss."
        if normalized in {"what is my current project", "my current project"}:
            return f"You are building {project}, Boss."
        if normalized in {"what do you know about me", "tell me about me"}:
            return (
                f"You are {name}, studying {course} in {semester}, focused on {field}, "
                f"and interested in {interests}. Current project is {project}, Boss."
            )
        return ""

    def _looks_like_greeting(self, normalized):
        return self.conversation.is_greeting(normalized)

    def _looks_like_small_talk(self, normalized):
        return self.conversation.can_handle(normalized)

    def _looks_like_help(self, normalized):
        return self._contains_any(
            normalized,
            [
                "help",
                "what can you do",
                "show commands",
                "show help",
                "how can you help",
            ],
        )

    def _looks_like_app_control(self, normalized):
        if re.search(r"\b(open|launch|start|run|close|terminate)\b", normalized):
            return True
        return self._contains_any(
            normalized,
            ["calculator", "chrome", "notepad", "settings", "task manager", "downloads", "desktop", "documents"],
        )

    def _looks_like_web_search(self, normalized):
        if self._looks_like_youtube(normalized):
            return False
        return self._contains_any(
            normalized,
            [
                "search",
                "google",
                "find",
                "browse",
                "website",
                "open site",
                "open website",
                "look up",
                "for me search",
            ],
        )

    def _looks_like_youtube(self, normalized):
        if self._is_direct_site_open(normalized):
            return False
        blocked_terms = [
            "search",
            "google",
            "find",
            "what can you do",
            "help",
            "what is",
            "who is",
            "how ",
            "why ",
            "tell me",
        ]
        if self._contains_any(normalized, blocked_terms):
            return False
        if self._contains_any(
            normalized,
            ["youtube", "play song", "play music", "play video", "song play", "gaana", "gana"],
        ):
            return True
        if normalized.startswith("play "):
            return True
        if self._context.get("last_intent") == YOUTUBE_PLAY and self._contains_any(normalized, ["play", "song", "music", "video"]):
            return True
        if (
            self._context.get("youtube_opened")
            and len(normalized.split()) <= 4
            and not self._looks_like_system_control(normalized)
            and not re.search(r"^(what|who|why|how|search|find|open|send)\b", normalized)
        ):
            return True
        return False

    def _is_direct_site_open(self, normalized):
        site_pattern = "|".join(sorted((re.escape(site) for site in self._known_sites), key=len, reverse=True))
        if not site_pattern:
            return False
        return bool(
            re.search(rf"^(?:open|launch|start|run)\s+(?:{site_pattern})$", normalized)
            or re.search(rf"^(?:{site_pattern})\s+open$", normalized)
        )

    def _looks_like_system_control(self, normalized):
        return self._contains_any(
            normalized,
            [
                "volume",
                "sound",
                "awaz",
                "brightness",
                "shutdown",
                "shut down",
                "restart",
                "lock",
                "sleep",
                "screenshot",
                "battery",
                "time",
                "samay",
                "date",
                "din",
                "internet",
                "wifi",
                "network",
                "speed",
                "status",
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
                "full screen",
            ],
        )

    def _looks_like_ai_question(self, normalized):
        if self._contains_any(
            normalized,
            ["what is", "who is", "how ", "how to", "why", "explain", "define", "tell me about", "kya hai", "kaun hai", "kaise", "samjhao"],
        ):
            return True
        return len(normalized.split()) > 4 and normalized.endswith("?")

    def _looks_like_whatsapp(self, normalized):
        return self._contains_any(
            normalized,
            [
                "whatsapp",
                "message",
                "msg",
                "call",
                "chat",
                "send image to",
                "send file to",
                "send voice message to",
                "send voice note to",
                "send document to",
            ],
        )

    def _looks_like_file_action(self, normalized):
        return self._contains_any(
            normalized,
            [
                "file",
                "folder",
                "download",
                "downloads",
                "desktop",
                "documents",
                "document",
                "pdf",
                "create file",
                "create folder",
                "open file",
                "delete file",
                "rename file",
                "organize screenshot",
                "organize screenshots",
                "screenshot folder",
            ],
        )

    def _looks_like_download(self, normalized):
        return "download" in normalized

    def _looks_like_memory_query(self, normalized):
        return normalized in {
            "what is my name",
            "what s my name",
            "my profile",
            "what is my course",
            "what am i studying",
            "what is my field",
            "my field",
            "what are my interests",
            "my interests",
            "what is my current project",
            "my current project",
            "what do you know about me",
            "tell me about me",
        }

    def _extract_app_payload(self, raw, normalized):
        patterns = [
            r"(?:can you |could you |please |for me )*\b(?:open|launch|start|run|close|terminate)\b\s+(.+)$",
            r"(.+?)\s+\b(?:open|close)\b$",
            r"\b(calculator|chrome|notepad|settings|task manager|downloads|desktop|documents)\b",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_search_query(self, raw, normalized):
        patterns = [
            r"(?:google search|search|find|browse|look up)\s+(.+)$",
            r"search\s+(.+?)\s+for me$",
            r"google\s+(?:par|pe|pr)\s+(.+?)\s+search(?:\s+karo)?$",
            r"(.+?)\s+google\s+(?:par|pe|pr)\s+search(?:\s+karo)?$",
            r"open website\s+(.+)$",
            r"open site\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw, re.IGNORECASE)
            if match:
                return self._clean_query(match.group(1))
        return ""

    def _extract_youtube_query(self, raw, normalized):
        patterns = [
            r"(?:please |can you |could you )?(?:play|play song|play music|play video)\s+(.+?)(?:\s+on youtube)?$",
            r"youtube\s+(?:par|pe|pr)\s+(.+?)\s+(?:play)(?:\s+karo)?$",
            r"youtube\s+(?:par|pe|pr)\s+(.+?)$",
            r"youtube play\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw, re.IGNORECASE)
            if match:
                return self._clean_query(match.group(1))
        return self._extract_followup_media_query(normalized)

    def _extract_followup_media_query(self, normalized):
        if normalized.startswith("play "):
            return self._clean_query(normalized[5:])
        if self._context.get("youtube_opened") and len(normalized.split()) <= 6:
            return self._clean_query(normalized)
        return ""

    def _extract_whatsapp_payload(self, raw):
        patterns = [
            r"whatsapp(?:\s+message)?\s+(.+)$",
            r"send\s+(.+?)\s+a\s+whatsapp\s+message$",
            r"message\s+(.+)$",
            r"call\s+(.+?)\s+on whatsapp$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""

    def _clean_query(self, text):
        cleaned = str(text).strip().strip('"').strip("'")
        fillers = {"karo", "krdo", "kar do", "please", "jara", "zara", "for me", "na"}
        parts = [item for item in cleaned.split() if item.lower() not in fillers]
        return " ".join(parts).strip()

    def _extract_known_folder(self, text):
        normalized = " ".join(str(text).lower().split())
        folder_aliases = {
            "download": "downloads",
            "downloads": "downloads",
            "downloads folder": "downloads",
            "download folder": "downloads",
            "desktop": "desktop",
            "desktop folder": "desktop",
            "document": "documents",
            "documents": "documents",
            "documents folder": "documents",
            "document folder": "documents",
        }
        for alias, folder_name in folder_aliases.items():
            if alias in normalized:
                return folder_name
        return ""

    def _normalize_text(self, text):
        normalized = str(text).lower().strip()
        replacements = [
            (r"\bgoogle\s+(?:pe|pr)\b", "google par"),
            (r"\byoutube\s+(?:pe|pr)\b", "youtube par"),
            (r"\bkiya\b", "kya"),
            (r"\bgya\b", "gaya"),
            (r"\bbtao\b", "batao"),
            (r"\bbadhado\b", "badhao"),
            (r"\bbadha do\b", "badhao"),
            (r"\bkam krdo\b", "kam karo"),
            (r"\bkrdo\b", "kar do"),
            (r"\bchrome kholo\b", "open chrome"),
            (r"\bcalculator kholo\b", "open calculator"),
            (r"\bcalc kholo\b", "open calculator"),
            (r"\bdownloads kholo\b", "open downloads"),
            (r"\bdownload kholo\b", "open downloads"),
            (r"\bdesktop kholo\b", "open desktop"),
            (r"\bdocuments kholo\b", "open documents"),
            (r"\btask manager kholo\b", "open task manager"),
            (r"\bscreen shot\b", "screenshot"),
            (r"\bss\b", "screenshot"),
            (r"\bbajao\b", "play"),
            (r"\bchalao\b", "play"),
            (r"\bgaana\b", "song"),
            (r"\bgana\b", "song"),
            (r"\bmsg\b", "message"),
            (r"\bplease\b", ""),
        ]
        word_replacements = [
            (r"\bkhol do\b", "open"),
            (r"\bkholo\b", "open"),
            (r"\bkhol\b", "open"),
            (r"\bband karo\b", "close"),
            (r"\bband kar\b", "close"),
        ]
        for pattern, target in replacements + word_replacements:
            normalized = re.sub(pattern, target, normalized)
        normalized = re.sub(r"[^\w\s\?]", " ", normalized)
        normalized = " ".join(normalized.split())
        normalized = re.sub(r"^(?:myra|mira|mayra|maira)\s+", "", normalized)
        normalized = re.sub(r"\bpc close\b", "pc shutdown", normalized)
        normalized = re.sub(r"\blaptop close\b", "laptop shutdown", normalized)
        normalized = re.sub(r"\bsystem close\b", "system shutdown", normalized)
        return normalized.strip()

    def _normalize_reply(self, message):
        text = str(message).strip()
        if not text:
            return "Done Boss."

        text = text.replace("LOCAL_FALLBACK::", "").strip()
        replacements = {
            "Sir ji": "Boss",
            "sir ji": "Boss",
            "Song playing on YouTube.": "Playing it on YouTube Boss.",
            "Google search opened in browser.": "Alright Boss, searching Google.",
            "Opening application.": "Opening it Boss.",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        if "Boss" not in text and not text.lower().startswith("yes boss"):
            text = text[:-1] if text.endswith(".") else text
            text = f"{text} Boss."
        return text

    def _conversation_context(self, profile=None):
        context = {}
        if isinstance(profile, dict):
            context.update(profile)
        context.update(self._context)
        return context

    def _remember_context(self, intent, subject):
        self._context["last_intent"] = str(intent)
        self._context["last_subject"] = str(subject).strip()
        self._context["youtube_opened"] = intent == YOUTUBE_PLAY or "youtube" in str(subject).lower()
        self._context["web_active"] = intent == WEB_SEARCH
        if intent == APP_CONTROL:
            self._context["last_app"] = str(subject).strip()

    def _contains_any(self, text, items):
        return any(item in text for item in items)


_DEFAULT_ROUTER = CommandRouter()


def classify_command(command):
    return _DEFAULT_ROUTER.classify_command(command).category


def route_command(command, profile=None):
    return _DEFAULT_ROUTER.handle(command, profile=profile)
