import re
import sys
import threading
from datetime import datetime
from datetime import timedelta
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from engine.app_launcher import AppLauncher
from engine.ai_brain import ask_ai
from engine.automation import DesktopAutomation
from engine.browser_agent import BrowserAgent
from engine.brightness_control import BrightnessControl
from engine.download_agent import DownloadAgent
from engine.email_agent import EmailAgent
from engine.file_engine import FileEngine
from engine.listener import VoiceListener
from engine.memory_engine import MemoryEngine
from engine.netflix_agent import NetflixAgent
from engine.productivity_engine import ProductivityEngine
from engine.research_agent import ResearchAgent
from engine.scheduler import SchedulerEngine
from engine.spotify_agent import SpotifyAgent
from engine.system_control import SystemControl
from engine.task_planner import TaskPlanner
from engine.voice_engine import VoiceEngine
from engine.web_control import WebControl
from engine.whatsapp_agent import WhatsAppAgent
from engine.youtube_agent import YouTubeAgent
from ui.main_window import MainWindow


class AssistantController(QObject):
    WAKE_WORD_ALIASES = (
        "myra",
        "mira",
        "mera",
        "mayra",
        "maira",
        "miara",
        "nayara",
        "nyara",
        "niyara",
        "niara",
    )

    AI_TRIGGERS = (
        "explain",
        "question",
        "what is",
        "who is",
        "define",
        "tell me about",
        "how does",
    )

    history = pyqtSignal(str)
    status = pyqtSignal(str)
    notification = pyqtSignal(str, str)

    def __init__(self, base_dir):
        super().__init__()

        self.base_dir = Path(base_dir)
        self.voice = VoiceEngine()
        self.listener = VoiceListener(language="en-US")
        self.memory = MemoryEngine(self.base_dir / "memory.json")
        self.productivity = ProductivityEngine(self.base_dir, self.memory)
        self.files = FileEngine(self.base_dir)
        self.apps = AppLauncher()
        self.automation = DesktopAutomation()
        self.browser = BrowserAgent()
        self.brightness = BrightnessControl()
        self.downloads = DownloadAgent()
        self.email = EmailAgent()
        self.netflix = NetflixAgent()
        self.research = ResearchAgent()
        self.system = SystemControl(self.base_dir)
        self.spotify = SpotifyAgent()
        self.task_planner = TaskPlanner()
        self.web = WebControl()
        self.whatsapp = WhatsAppAgent()
        self.youtube = YouTubeAgent()
        self.scheduler = SchedulerEngine(self.memory)

        self._continuous_listening = False
        self._listener_thread = None
        self._listener_lock = threading.Lock()

        threading.Thread(target=self.apps.refresh_index, daemon=True).start()
        self.scheduler.start(self._run_scheduled_command)

    def startup(self):
        self.status.emit("Online")
        self._respond(f"{self._time_based_greeting()}, Sir ji. Myra dashboard is online.")

        for item in self.memory.due_today():
            self._respond(f"Sir ji reminder: {item['text']}")

    def request_listen(self):
        with self._listener_lock:
            if self._continuous_listening:
                self._respond("Sir ji, listening already on hai.")
                return

            self._continuous_listening = True
            self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._listener_thread.start()

        self.status.emit("Listening")
        self._respond("Sir ji listening start ho gaya hai. Ab boliye.")

    def stop_listen(self):
        with self._listener_lock:
            was_listening = self._continuous_listening
            self._continuous_listening = False
            self._listener_thread = None

        self.status.emit("Online")
        if was_listening:
            return "Sir ji, listening stop kar diya hai."
        return "Sir ji, listening already band hai."

    def submit_text(self, command):
        text = str(command).strip()
        if not text:
            return
        self.history.emit(f"You: {text}")
        self.process_command(text)

    def _listen_loop(self):
        while self._continuous_listening:
            self.status.emit("Listening")
            command, error = self.listener.listen_once()

            if error:
                self.status.emit("Error")
                self.notification.emit(error, "error")
                self._respond(error)
                continue

            if not command:
                continue

            if not self._should_process_voice_command(command):
                continue

            self.history.emit(f"You: {command}")
            self.process_command(command)

    def process_command(self, command):
        raw_command = " ".join(str(command).split())
        raw_without_wake = self._strip_wake_words(raw_command)
        normalized = raw_without_wake.lower()

        if not normalized:
            self._respond("Sir ji command bolo.")
            if not self._continuous_listening:
                self.status.emit("Online")
            return

        if self._is_stop_command(normalized):
            self.status.emit("Speaking")
            self._respond(self.stop_listen())
            return

        self.status.emit("Processing")
        result = self._route_command(normalized, raw_without_wake)
        self.status.emit("Speaking")
        self._respond(result)

        if self._continuous_listening:
            self.status.emit("Listening")
        else:
            self.status.emit("Online")

    def _route_command(self, command, raw_command):
        handled, message = self.scheduler.handle(raw_command)
        if handled:
            return message

        handled, message = self.productivity.handle(raw_command)
        if handled:
            return message

        handled, message = self.files.handle(raw_command)
        if handled:
            return message

        handled, message = self.task_planner.handle(raw_command)
        if handled:
            return message

        handled, message = self.youtube.handle(raw_command)
        if handled:
            return message

        handled, message = self.spotify.handle(raw_command)
        if handled:
            return message

        handled, message = self.netflix.handle(raw_command)
        if handled:
            return message

        handled, message = self.whatsapp.handle(raw_command)
        if handled:
            return message

        handled, message = self.email.handle(raw_command)
        if handled:
            return message

        handled, message = self.downloads.handle(raw_command)
        if handled:
            return message

        handled, message = self.brightness.handle(raw_command)
        if handled:
            return message

        handled, message = self.browser.handle(raw_command)
        if handled:
            return message

        handled, message = self.research.handle(raw_command)
        if handled:
            return message

        handled, message = self.automation.handle(raw_command)
        if handled:
            return message

        handled, message = self.web.handle(command)
        if handled:
            return message

        app_result = self._handle_application_command(command)
        if app_result:
            return app_result

        system_result = self._handle_system_command(command)
        if system_result:
            return system_result

        memory_result = self._handle_memory_command(raw_command)
        if memory_result:
            return memory_result

        conversation = self._handle_conversation(command)
        if conversation:
            return conversation

        if any(trigger in command for trigger in self.AI_TRIGGERS):
            return ask_ai(raw_command)

        return f"Sir ji maine '{raw_command}' suna lekin command supported nahi hai."

    def _handle_application_command(self, command):
        if re.search(r"open\s+(desktop|downloads|documents)\b", command):
            return ""

        if command.startswith("search ") or command.startswith("find "):
            return self.browser.search(command.split(" ", 1)[1].strip())

        open_match = re.search(r"open\s+(.+)", command)
        if open_match:
            app_name = self._normalize_app_name(open_match.group(1).strip())
            ok, message = self.apps.open_application(app_name)
            return message

        close_match = re.search(r"close\s+(.+)", command)
        if close_match:
            app_name = self._normalize_app_name(close_match.group(1).strip())
            ok, message = self.apps.close_application(app_name)
            return message

        if "refresh apps" in command or "scan apps" in command:
            self.apps.refresh_index()
            total = len(self.apps.available_apps())
            return f"Sir ji, app index refresh ho gaya. {total} apps detect hui hain."

        return ""

    def _handle_system_command(self, command):
        volume_percent = self.system.extract_volume_percent(command)
        if volume_percent is not None:
            return self.system.set_volume_percent(volume_percent)

        if "volume up" in command:
            return self.system.volume_up()
        if "volume down" in command:
            return self.system.volume_down()
        if "mute" in command:
            return self.system.mute_toggle()
        if "take screenshot" in command or "screenshot" in command:
            return self.system.take_screenshot()
        if "lock screen" in command or "lock system" in command:
            return self.system.lock_system()
        if "shutdown" in command:
            return self.system.shutdown()
        if "restart" in command:
            return self.system.restart()
        if "sleep mode" in command or command == "sleep":
            return self.system.sleep_mode()
        if "battery" in command:
            return self.system.battery_status()
        if "internet speed" in command or "speed test" in command:
            return self.system.internet_speed()
        if "show system status" in command or "system status" in command:
            return self.system.system_status()
        if "wifi" in command or "internet status" in command:
            return self.system.network_status()
        if "cpu" in command:
            return self.system.cpu_usage()
        if "ram" in command or "memory usage" in command:
            return self.system.ram_usage()
        if "disk" in command:
            return self.system.disk_usage()
        if "time" in command or "date" in command:
            return self.system.date_time_status()
        if "task manager" in command:
            return self.system.open_task_manager()
        if "open settings" in command:
            return self.system.open_settings()
        if "switch window" in command:
            return self.system.switch_window()
        if "minimize window" in command:
            return self.system.minimize_current_window()
        if "maximize window" in command:
            return self.system.maximize_current_window()

        folder_match = re.search(r"open\s+(desktop|downloads|documents)\b", command)
        if folder_match:
            return self.system.open_known_folder(folder_match.group(1))

        return ""

    def _handle_memory_command(self, command):
        normalized = command.lower().strip()

        if normalized.startswith("my name is"):
            name = command[10:].strip()
            self.memory.set_user_name(name)
            return f"Sir ji maine aapka naam {name} save kar liya."

        if "what is my name" in normalized:
            return f"Sir ji aapka naam {self.memory.user_name()} hai."

        remember_match = re.search(r"(?:remember|save reminder)\s+(.+)", command, re.IGNORECASE)
        if remember_match:
            text = remember_match.group(1).strip()
            due_on = self._extract_due_date(normalized)
            if due_on:
                self.memory.add_reminder(text, due_on=due_on)
                return f"Sir ji, reminder save ho gaya for {due_on}."
            self.memory.remember_fact(text)
            return "Sir ji, maine yeh memory me save kar liya hai."

        if "show reminders" in normalized or "my reminders" in normalized:
            reminders = self.memory.reminders()
            if not reminders:
                return "Sir ji, abhi koi reminders saved nahi hain."
            preview = ", ".join(item.get("text", "") for item in reminders[:3])
            return f"Sir ji, reminders: {preview}"

        if "what do you remember" in normalized or "show memory" in normalized:
            facts = self.memory.facts()
            if not facts:
                return "Sir ji, abhi personal memory me kuch saved nahi hai."
            preview = ", ".join(item.get("text", "") for item in facts[:3])
            return f"Sir ji, mujhe yeh yaad hai: {preview}"

        return ""

    def _handle_conversation(self, command):
        if "hello" in command or "hi" == command:
            return "Hello Sir ji, Myra ready hai."
        if "how are you" in command:
            return "Sir ji main fully operational hoon."
        if "who are you" in command:
            return "Sir ji, main Myra hoon. Aapka personal desktop AI assistant."
        if "motivate me" in command:
            return "Sir ji discipline hi success ka shortcut hai."
        if "thank you" in command or "thanks" in command:
            return "Always ready, Sir ji."
        return ""

    def _is_stop_command(self, command):
        return command in {
            "stop",
            "stop listening",
            "stop myra",
            "stop now",
            "band ho jao",
            "sunna band karo",
            "listening band karo",
            "mute listening",
        }

    def _should_process_voice_command(self, command):
        if self._is_stop_command(self._strip_wake_words(command).lower()):
            return True
        return self.listener.heard_wake_word(command)

    def _strip_wake_words(self, text):
        cleaned = str(text).strip()
        if not cleaned:
            return ""

        pattern = r"\b(?:%s)\b" % "|".join(re.escape(alias) for alias in self.WAKE_WORD_ALIASES)
        cleaned = re.sub(pattern, " ", cleaned, flags=re.IGNORECASE)
        return " ".join(cleaned.split())

    def _extract_due_date(self, command):
        if "tomorrow" in command:
            return str(datetime.now().date() + timedelta(days=1))
        if "today" in command:
            return str(datetime.now().date())
        return None

    def _normalize_app_name(self, app_name):
        aliases = {
            "vs code": "code",
            "vscode": "code",
            "visual studio code": "code",
            "chrome browser": "chrome",
        }
        return aliases.get(app_name.lower(), app_name)

    def _respond(self, message):
        text = str(message)
        self.history.emit(f"Myra: {text}")
        self.voice.speak(text)

    def _time_based_greeting(self):
        hour = datetime.now().hour
        if hour < 12:
            return "Good morning"
        if hour < 18:
            return "Good afternoon"
        return "Good evening"

    def _run_scheduled_command(self, command):
        self.process_command(command)


def main():
    app = QApplication(sys.argv)
    base_dir = Path(__file__).resolve().parent

    window = MainWindow()
    window.load_theme()
    window.keep_dashboard_on_top(True)

    controller = AssistantController(base_dir)
    window.command_submitted.connect(controller.submit_text)
    window.listen_requested.connect(controller.request_listen)
    controller.history.connect(window.add_history)
    controller.status.connect(window.set_status)
    controller.notification.connect(window.show_notification)

    window.show()
    controller.startup()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
