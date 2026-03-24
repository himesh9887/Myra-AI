import os
import re
import random
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from engine.runtime_config import load_runtime_env

load_runtime_env(Path(__file__).resolve().parent)

os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "0")

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

from brain.ai_router import AIRouter, decide_action
from brain.task_planner import TaskPlanner
from voice.emotion_voice_engine import EmotionVoiceEngine
from voice.voice_listener import VoiceListener
from vision.camera_agent import CameraAgent
from vision.face_recognition import FaceRecognition
from vision.object_detector import ObjectDetector
from automation.automation_agent import AutomationController

from engine.ai_brain import is_failsafe_response
from engine.agent_manager import AgentManager
from engine.activity_monitor import ActivityMonitor
from engine.app_launcher import AppLauncher
from engine.behavior_engine import BehaviorEngine
from engine.browser_agent import BrowserAgent
from engine.brightness_control import BrightnessControl
from engine.command_router import CommandRouter
from engine.conversation_engine import ConversationEngine
from engine.conversation_memory import ConversationMemory
from engine.download_agent import DownloadAgent
from engine.email_agent import EmailAgent
from engine.emotion_engine import EmotionEngine
from engine.file_engine import FileEngine
from engine.internet_agent import InternetAgent
from engine.memory_engine import MemoryEngine
from engine.mood_tracker import MoodTracker
from engine.netflix_agent import NetflixAgent
from engine.personality_engine import PersonalityEngine
from engine.planner_ai import PlannerAI
from engine.reminder_engine import ReminderEngine
from engine.research_agent import ResearchAgent
from engine.screen_awareness import ScreenAwareness
from engine.scheduler import SchedulerEngine
from engine.spotify_agent import SpotifyAgent
from engine.system_control import SystemControl
from engine.web_control import WebControl
from engine.whatsapp_agent import WhatsAppAgent
from engine.youtube_agent import YouTubeAgent
from ui.main_window import MainWindow


class AssistantController(QObject):
    history = pyqtSignal(str)
    status = pyqtSignal(str)
    notification = pyqtSignal(str, str)
    dashboard_action = pyqtSignal(str)
    camera_frame = pyqtSignal(str, str)
    core_snapshot = pyqtSignal(object)

    DEFAULT_PROFILE = {
        "name": "Himesh Rajput",
        "course": "BCA",
        "semester": "4nd",
        "field": "Software Engineering",
        "interests": ["Python", "AI development", "automation"],
        "current_project": "MYRA AI assistant",
        "exam_date": "2026-03-25",
        "subject": "Data Structure",
        "study_goal_hours": 3,
        "study_progress": 1,
        "behavior_profile": {
            "preferred_study_time": "",
            "coding_schedule": "",
            "sleep_time": "",
            "frequent_apps": [],
        },
    }

    def __init__(self, base_dir):
        super().__init__()
        self.base_dir = Path(base_dir)

        self.emotion = EmotionEngine()
        self.voice = EmotionVoiceEngine(emotion_engine=self.emotion)
        self.listener = VoiceListener(language="en-IN")
        self.memory = MemoryEngine(self.base_dir / "memory")
        self.conversation_memory = ConversationMemory(self.base_dir / "memory", memory=self.memory)
        self.mood_tracker = MoodTracker(self.memory, emotion_engine=self.emotion)
        self.ai_router = AIRouter(memory=self.memory)
        self._seed_user_profile()
        self.behavior = BehaviorEngine(self.memory)
        self.planner_ai = PlannerAI(self.memory, behavior_engine=self.behavior)
        self.reminders = ReminderEngine(self.memory, behavior_engine=self.behavior)
        self.activity_monitor = ActivityMonitor(self.memory, behavior_engine=self.behavior)
        self.screen_awareness = ScreenAwareness(self.base_dir, activity_monitor=self.activity_monitor)
        self.conversation = ConversationEngine(self.emotion)
        self.personality = PersonalityEngine(
            memory=self.memory,
            conversation_memory=self.conversation_memory,
            mood_tracker=self.mood_tracker,
        )

        self.files = FileEngine(self.base_dir)
        self.apps = AppLauncher()
        self.automation = AutomationController()
        self.browser = BrowserAgent()
        self.brightness = BrightnessControl()
        self.command_brain = CommandRouter(self.base_dir)
        self.downloads = DownloadAgent()
        self.email = EmailAgent()
        self.netflix = NetflixAgent()
        self.internet = InternetAgent()
        self.research = ResearchAgent()
        self.system = SystemControl(self.base_dir)
        self.spotify = SpotifyAgent()
        self.vision = CameraAgent(self.base_dir)
        self.object_detector = ObjectDetector(self.vision)
        self.face_recognition = FaceRecognition(self.vision)
        self.web = WebControl()
        self.whatsapp = WhatsAppAgent()
        self.youtube = YouTubeAgent()
        self.agent_manager = AgentManager(
            self.base_dir,
            automation=self.automation,
            apps=self.apps,
            browser=self.browser,
            download=self.downloads,
            files=self.files,
            research=self.research,
            system=self.system,
            web=self.web,
            whatsapp=self.whatsapp,
            youtube=self.youtube,
        )
        self.task_planner = TaskPlanner(self.base_dir, agent_manager=self.agent_manager, memory=self.memory)
        self.scheduler = SchedulerEngine(self.memory)
        self.task_planner.configure_agents(
            automation=self.automation,
            apps=self.apps,
            browser=self.browser,
            download=self.downloads,
            files=self.files,
            research=getattr(self, "research", None),
            system=self.system,
            web=self.web,
            whatsapp=self.whatsapp,
            youtube=self.youtube,
        )

        self._continuous_listening = False
        self._listening_paused = False
        self._listener_thread = None
        self._listener_lock = threading.Lock()
        self._last_spoken_message = ""
        self._last_spoken_at = 0.0
        self._proactive_cooldowns = {}
        self._companion_running = True
        self._companion_thread = None

        threading.Thread(target=self.apps.refresh_index, daemon=True).start()
        self.scheduler.start(self._run_scheduled_command)
        self._start_companion_loop()

    def startup(self):
        self.status.emit("Online")
        self.planner_ai.generate_schedule(force=False)
        self._emit_core_snapshot("Standing by", "system")
        self._respond(self.conversation.startup_message(context=self._conversation_context()))
        self.request_listen(startup=True)

    def _seed_user_profile(self):
        merged = self.memory.profile()
        merged.update(self.DEFAULT_PROFILE)
        if not merged.get("projects"):
            merged["projects"] = [self.DEFAULT_PROFILE["current_project"]]
        merged.setdefault("preferences", {})
        merged["preferences"].setdefault("music", "lofi")
        merged["preferences"].setdefault("coding_editor", "vscode")
        self.memory.set_profile(merged)
        self.memory.set_user_name(self.DEFAULT_PROFILE["name"])
        self.memory.set_exam_details(
            exam_date=merged.get("exam_date", self.DEFAULT_PROFILE["exam_date"]),
            subject=merged.get("subject", self.DEFAULT_PROFILE["subject"]),
        )
        self.memory.set_study_goal(merged.get("study_goal_hours", self.DEFAULT_PROFILE["study_goal_hours"]))
        if not self.memory.daily_memory().get("study_progress"):
            self.memory.set_study_progress(merged.get("study_progress", self.DEFAULT_PROFILE["study_progress"]))

    def _start_companion_loop(self):
        if self._companion_thread and self._companion_thread.is_alive():
            return
        self._companion_thread = threading.Thread(target=self._companion_loop, daemon=True)
        self._companion_thread.start()

    def _companion_loop(self):
        while self._companion_running:
            try:
                snapshot = self.activity_monitor.poll()
                payload = snapshot.as_dict()
                self.memory.record_activity_snapshot(payload)
                self.behavior.record_activity(payload)
                context = self._conversation_context()
                message = self.activity_monitor.build_intervention(context=context, snapshot=snapshot)
                if message:
                    self._push_proactive_message(message, "activity", cooldown_seconds=20 * 60)
                else:
                    reminder = self.reminders.proactive_prompt(context=context, snapshot=payload)
                    if reminder:
                        self._push_proactive_message(reminder, "reminder", cooldown_seconds=35 * 60)
            except Exception:
                pass
            time.sleep(60)

    def _push_proactive_message(self, message, channel, cooldown_seconds):
        now = time.monotonic()
        last_sent = float(self._proactive_cooldowns.get(channel, 0.0))
        if (now - last_sent) < cooldown_seconds:
            return False
        self._proactive_cooldowns[channel] = now
        self.status.emit("Speaking")
        self._respond(message)
        if self._continuous_listening and not self._listening_paused:
            self.status.emit("Listening")
        else:
            self.status.emit("Online")
        return True

    def request_listen(self, startup=False):
        with self._listener_lock:
            if self._continuous_listening:
                if self._listening_paused:
                    self._listening_paused = False
                    self.status.emit("Listening")
                    self._respond("Listening resumed Boss.")
                elif not startup:
                    self._respond("Boss, continuous listening already on hai.")
                return
            self._continuous_listening = True
            self._listening_paused = False
            self._listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._listener_thread.start()
        self.status.emit("Listening")
        if not startup:
            self._respond("Listening resumed Boss.")

    def stop_listen(self):
        with self._listener_lock:
            was_active = self._continuous_listening and not self._listening_paused
            self._listening_paused = True
        self.status.emit("Online")
        if was_active:
            return "Okay Boss. Listening stopped."
        return "Boss, listening already stopped hai."

    def _listen_loop(self):
        while self._continuous_listening:
            command, error = self.listener.listen_once()

            if error:
                self.status.emit("Error")
                self.notification.emit(error, "error")
                self._respond(error)
                if not self._listening_paused:
                    self.status.emit("Listening")
                continue

            if not command:
                continue

            spoken = " ".join(str(command).strip().split())

            if self._listening_paused:
                if self._is_resume_listen_command(spoken):
                    self.history.emit(f"You: {spoken}")
                    self.request_listen()
                    continue
                continue

            if self._is_stop_listen_command(spoken):
                self.history.emit(f"You: {spoken}")
                self.status.emit("Speaking")
                self._respond(self.stop_listen())
                continue

            self.history.emit(f"You: {spoken}")
            self.process_command(spoken, from_voice=True)

    def submit_text(self, command):
        text = str(command).strip()
        if not text:
            return
        self.history.emit(f"You: {text}")
        self.process_command(text)

    def process_command(self, command, from_voice=False):
        raw = " ".join(str(command).split())
        normalized = raw.lower()
        if not normalized:
            return False

        if self._is_stop_listen_command(normalized):
            self.status.emit("Speaking")
            self._respond(self.stop_listen())
            return True

        if self._is_resume_listen_command(normalized):
            self.request_listen()
            return True

        if from_voice and self._is_unclear_voice_command(normalized):
            self.status.emit("Speaking")
            self._respond("Thoda unclear tha Boss, ek baar phir se bolo.")
            self.status.emit("Listening")
            return False

        self.status.emit("Processing")
        routed = self.command_brain.classify_command(raw)
        routed_agent, _ = self.agent_manager.route(raw)
        self.memory.track_command(raw, routed.category)
        try:
            result = self._route_command(normalized, raw)
        except Exception as exc:
            result = f"Boss, is command me thoda issue aa gaya. {exc}"

        self.memory.learn_from_text(raw)
        self._learn_from_execution(raw, routed)
        suggestion = self.memory.suggestion()
        if suggestion and suggestion.lower() not in str(result).lower():
            result = f"{result} {suggestion}".strip()
        self.memory.log_conversation(raw, result)
        self.conversation_memory.remember_turn(
            raw,
            result,
            emotion=self.memory.latest_mood().get("emotion", ""),
        )
        planner_snapshot = self.task_planner.latest_snapshot() if hasattr(self.task_planner, "latest_snapshot") else {}
        active_agent = planner_snapshot.get("agent") or routed_agent or "brain"
        self._emit_core_snapshot(raw, active_agent)

        self.status.emit("Speaking")
        self._respond(result, user_text=raw)

        if not from_voice and self._continuous_listening:
            self.status.emit("Listening")
        elif not self._continuous_listening:
            self.status.emit("Online")
        return True

    def _route_command(self, command, raw):
        panel_result = self._handle_dashboard_panel_command(command)
        if panel_result:
            return panel_result

        if self.vision.is_camera_off_command(command):
            self.camera_frame.emit("", "Boss, camera preview off hai.")
            return self.vision.stop_camera_preview()

        if self.vision.is_camera_open_command(command):
            message, frame_path = self.vision.start_camera_preview(frame_callback=self.camera_frame.emit)
            if frame_path:
                self.camera_frame.emit(frame_path, "Boss, live camera preview update ho gaya hai.")
            return message

        handled, message = self.screen_awareness.handle(raw)
        if handled:
            return message

        handled, message = self.scheduler.handle(raw)
        if handled:
            return message

        handled, message = self.task_planner.handle(raw)
        if handled:
            return message

        companion_result = self._handle_companion_command(raw)
        if companion_result:
            return companion_result

        emotion_result = self._handle_emotion(raw)
        if emotion_result:
            return emotion_result

        memory_result = self._handle_memory_command(raw)
        if memory_result:
            return memory_result

        conversation_result = self._handle_conversation(raw)
        if conversation_result:
            return conversation_result

        handled, message = self.agent_manager.handle(raw)
        if handled:
            return message

        lowered_raw = raw.lower()
        if any(token in lowered_raw for token in ["identify this object", "what do you see", "object in front"]):
            return self.object_detector.detect(raw)
        if any(token in lowered_raw for token in ["detect face", "face detect", "who is in front", "how many faces"]):
            return self.face_recognition.detect_faces()

        if self._is_visual_query(command):
            message, frame_path = self.vision.analyze_visual_query(raw)
            if frame_path:
                self.camera_frame.emit(frame_path, message)
            return message

        if self.internet.needs_latest_info(raw):
            return self._perform_latest_info_lookup(raw)

        result = self.command_brain.handle(raw, profile=self._brain_profile())
        if result:
            return result

        action = decide_action(command)
        if action == "google" and len(command.split()) >= 2:
            return self._perform_web_search(raw)
        if len(command.split()) >= 2:
            return self._ask_brain(raw)
        return self._friendly_fallback(raw)

    def _learn_from_execution(self, raw, routed):
        if not routed:
            return

        category = getattr(routed, "category", "")
        payload = str(getattr(routed, "payload", "") or "").strip()
        normalized = str(getattr(routed, "normalized_text", "") or raw).lower()

        if category == "APP_CONTROL":
            app_name = payload or self._extract_open_target(raw)
            if app_name:
                self.memory.track_app_usage(app_name)
                if app_name.lower() in {"vscode", "vs code", "code", "visual studio code"}:
                    self.memory.set_preference("coding_editor", "vscode")
        elif category == "YOUTUBE_PLAY":
            self.memory.track_app_usage("youtube")
        elif category == "WEB_SEARCH":
            self.memory.track_app_usage("browser")
        elif "vscode" in normalized or "vs code" in normalized or re.search(r"\bopen code\b", normalized):
            self.memory.track_app_usage("vscode")
            self.memory.set_preference("coding_editor", "vscode")

    def _extract_open_target(self, raw):
        match = re.search(r"\b(?:open|launch|start|run)\b\s+(.+)$", str(raw), re.IGNORECASE)
        if not match:
            return ""
        target = match.group(1).strip()
        return re.sub(r"\bfor me\b$", "", target, flags=re.IGNORECASE).strip()

    def _safe_handle(self, agent, command):
        if agent is None:
            return False, ""
        try:
            return agent.handle(command)
        except Exception:
            return False, ""

    def _extract_search_query(self, command, raw):
        if command.startswith("google search "):
            return raw[len("google search ") :].strip()
        if command.startswith("search "):
            return raw[len("search ") :].strip()
        if command.startswith("find "):
            return raw[len("find ") :].strip()
        return ""

    def _handle_application(self, command):
        open_match = re.search(r"open\s+(.+)", command)
        if open_match:
            app_name = open_match.group(1).strip()
            _, message = self.apps.open_application(app_name)
            return message

        close_match = re.search(r"close\s+(.+)", command)
        if close_match:
            app_name = close_match.group(1).strip()
            _, message = self.apps.close_application(app_name)
            return message
        return ""

    def _handle_system(self, command):
        volume_percent = self.system.extract_volume_percent(command)
        if volume_percent is not None:
            return self.system.set_volume_percent(volume_percent)

        brightness_percent = self.system.extract_brightness_percent(command)
        if brightness_percent is not None:
            return self.system.set_brightness_percent(brightness_percent)

        if "volume up" in command:
            return self.system.volume_up()
        if "volume down" in command:
            return self.system.volume_down()
        if "mute" in command:
            return self.system.mute_toggle()
        if "increase brightness" in command or "brightness up" in command:
            return self.system.increase_brightness()
        if "decrease brightness" in command or "brightness down" in command:
            return self.system.decrease_brightness()
        if "lock screen" in command:
            return self.system.lock_system()
        if "shutdown" in command:
            return self.system.shutdown()
        if "restart" in command:
            return self.system.restart()
        if "sleep" in command:
            return self.system.sleep_mode()
        if "screenshot" in command:
            return self.system.take_screenshot()
        if "battery" in command:
            return self.system.battery_status()
        if "cpu" in command:
            return self.system.cpu_usage()
        if "ram" in command:
            return self.system.ram_usage()
        if "switch window" in command:
            return self.system.switch_window()
        if "minimize window" in command:
            return self.system.minimize_current_window()
        if "maximize window" in command:
            return self.system.maximize_current_window()
        return ""

    def _handle_conversation(self, command):
        normalized = str(command).lower().strip()
        context = self._conversation_context()
        if self.conversation.can_handle(normalized):
            return self.conversation.friendly_reply(normalized, context=context)
        personality_reply = self.personality.handle(normalized, context=context)
        if personality_reply:
            return personality_reply
        return ""

    def _handle_companion_command(self, command):
        for engine in (self.planner_ai, self.reminders, self.activity_monitor):
            handled, message = engine.handle(command)
            if handled:
                return message
        return ""

    def _handle_emotion(self, command):
        detected = self.mood_tracker.track(command, source="conversation")
        if not detected.is_emotional:
            return ""
        return self.conversation.emotion_response(command, detected=detected, context=self._conversation_context())

    def _handle_dashboard_panel_command(self, command):
        normalized = " ".join(str(command).lower().split())
        radar_phrases = {
            "show radar status",
            "radar status dikhao",
            "target radar dikhao",
            "radar scan dikhao",
        }
        body_scan_phrases = {
            "show body scan",
            "body scan dikhao",
            "system body scan dikhao",
            "scan panel dikhao",
        }
        system_scan_phrases = {
            "scan system now",
            "system scan karo",
            "full system scan karo",
            "diagnostic scan karo",
        }

        if normalized in radar_phrases:
            self.dashboard_action.emit("radar_status")
            return "Radar status open kar diya Boss."
        if normalized in body_scan_phrases:
            self.dashboard_action.emit("body_scan")
            return "Body scan highlight kar diya Boss."
        if normalized in system_scan_phrases:
            self.dashboard_action.emit("system_scan")
            return "System scan chala diya Boss."
        return ""

    def _is_visual_query(self, command):
        return self.vision.is_visual_query(command)

    def _handle_memory_command(self, raw_command):
        normalized = str(raw_command).lower().strip()
        profile = self.memory.profile()
        daily = self.memory.daily_memory()

        if normalized in {"what is my name", "what's my name", "my profile"}:
            return "Main tumhe Boss hi bolti hoon."

        if normalized in {"what is my exam date", "when is my exam", "exam date"}:
            exam_date = profile.get("exam_date") or daily.get("exam_date") or "not set yet"
            subject = profile.get("subject") or daily.get("subject") or "your subject"
            return f"{subject} ka exam {exam_date} pe set hai."

        if normalized in {"what is my subject", "which subject am i studying", "my subject"}:
            return f"Abhi tum {profile.get('subject', 'Data Structure')} pe focus kar rahe ho."

        if normalized in {"study progress", "how much did i study", "what is my study progress"}:
            return (
                f"Aaj tumne {daily.get('study_progress', 0):g} out of "
                f"{daily.get('study_goal_hours', 0):g} study hours complete kiye hain."
            )

        if normalized in {"what is my course", "what am i studying"}:
            return (
                f"You are studying {profile.get('course', 'BCA')} in "
                f"{profile.get('semester', '2nd')} semester, Boss."
            )

        if normalized in {"what is my field", "my field"}:
            return f"Your field is {profile.get('field', 'Software Engineering')}, Boss."

        if normalized in {"what are my interests", "my interests"}:
            interests = ", ".join(profile.get("interests", [])) or "Python, AI development, automation"
            return f"Your interests are {interests}, Boss."

        if normalized in {"what is my current project", "my current project"}:
            return f"You are building {profile.get('current_project', 'MYRA AI assistant')}, Boss."

        if normalized in {"what do you know about me", "tell me about me"}:
            facts = [item.get("text", "") for item in self.memory.facts() if isinstance(item, dict)]
            facts_text = ""
            if facts:
                facts_text = " I also remember " + ", ".join(facts[:3]) + "."
            interests = ", ".join(profile.get("interests", [])) or "AI development"
            return (
                f"Boss, tum {profile.get('course', 'BCA')} "
                f"ke {profile.get('semester', '2nd')} semester me ho, "
                f"{profile.get('field', 'Software Engineering')} pe focused ho, "
                f"{interests} me interest rakhte ho, aur "
                f"{profile.get('subject', 'Data Structure')} ke liye "
                f"{daily.get('study_goal_hours', 0):g} hour daily goal ke saath prepare kar rahe ho.{facts_text}"
            )

        remember_exam = re.search(r"(?:myra\s+)?(?:remember|set)\s+(?:my\s+)?exam(?: date)?(?: is| to)?\s+(\d{4}-\d{2}-\d{2})", raw_command, re.IGNORECASE)
        if remember_exam:
            exam_date = remember_exam.group(1).strip()
            if self.memory.set_exam_details(exam_date=exam_date):
                self.planner_ai.generate_schedule(force=True)
                return f"Exam date {exam_date} save kar di. Main plan bhi update kar dungi."

        remember_subject = re.search(r"(?:myra\s+)?(?:remember|set)\s+(?:my\s+)?subject(?: is| to)?\s+(.+)", raw_command, re.IGNORECASE)
        if remember_subject:
            subject = remember_subject.group(1).strip().strip(".")
            if self.memory.set_exam_details(subject=subject):
                self.planner_ai.generate_schedule(force=True)
                return f"Subject {subject} yaad rakh liya."

        remember_goal = re.search(r"(?:myra\s+)?(?:remember|set)\s+(?:my\s+)?study goal(?: is| to)?\s+(\d+(?:\.\d+)?)", raw_command, re.IGNORECASE)
        if remember_goal:
            goal = float(remember_goal.group(1))
            if self.memory.set_study_goal(goal):
                self.planner_ai.generate_schedule(force=True)
                return f"Daily study goal {goal:g} hours set kar diya."

        remember_interest = re.search(r"(?:myra\s+)?remember(?: that)? i like\s+(.+)", raw_command, re.IGNORECASE)
        if remember_interest:
            interest = remember_interest.group(1).strip().strip(".")
            if self.memory.add_interest(interest):
                return f"Noted, Boss. I will remember that you like {interest}."
            return "I could not save that interest, Boss."

        remember_name = re.search(r"(?:myra\s+)?remember my name is\s+(.+)", raw_command, re.IGNORECASE)
        if remember_name:
            name = remember_name.group(1).strip().strip(".")
            if self.memory.set_user_name(name):
                return "Done Boss. Noted. Main tumhe Boss hi bulaungi."
            return "Boss, name save nahi ho paya."

        remember_project = re.search(r"(?:myra\s+)?remember my project is\s+(.+)", raw_command, re.IGNORECASE)
        if remember_project:
            project = remember_project.group(1).strip().strip(".")
            if self.memory.add_project(project):
                return f"Got it Boss. Current project saved as {project}."
            return "Boss, project save nahi ho paya."

        remember_use = re.search(r"(?:myra\s+)?remember that i use\s+(.+)", raw_command, re.IGNORECASE)
        if remember_use:
            app_name = remember_use.group(1).strip().strip(".")
            if self.memory.add_frequent_app(app_name):
                return f"Done Boss. I'll remember that you use {app_name}."
            return "Boss, wo preference save nahi ho payi."

        remember_fact = re.search(r"(?:myra\s+)?remember\s+(.+)", raw_command, re.IGNORECASE)
        if remember_fact:
            fact = remember_fact.group(1).strip().strip(".")
            if fact and self.memory.remember_fact(fact):
                return f"Noted Boss. I'll remember that."

        return ""

    def _respond(self, message, user_text=""):
        text = self._normalize_persona_text(message)
        if not text:
            return
        prepared = self.voice.prepare_response(text, user_text=user_text)
        display_text = prepared.display_text
        if not display_text:
            return
        now = time.monotonic()
        if display_text == self._last_spoken_message and (now - self._last_spoken_at) < 1.0:
            return
        self._last_spoken_message = display_text
        self._last_spoken_at = now
        self.history.emit(f"Myra: {display_text}")
        self.voice.speak(prepared)

    def _is_unclear_voice_command(self, command):
        fillers = {"hmm", "haan", "han", "okay", "ok", "yes", "no", "huh", "hmmm"}
        tokens = command.split()
        if not tokens:
            return True
        if len(tokens) == 1 and tokens[0] in fillers:
            return True
        if len(tokens) == 1 and tokens[0] not in {"stop", "mute", "shutdown", "restart", "sleep"}:
            return True
        return False

    def _is_stop_listen_command(self, command):
        normalized = " ".join(str(command).lower().split())
        phrases = {
            "stop listening",
            "stop myra",
            "mute assistant",
            "mic off",
            "listening off",
            "stop",
        }
        return normalized in phrases

    def _is_resume_listen_command(self, command):
        normalized = " ".join(str(command).lower().split())
        phrases = {
            "start listening",
            "resume assistant",
            "myra start",
            "resume listening",
            "start myra",
        }
        return normalized in phrases

    def _normalize_persona_text(self, message):
        text = str(message).strip()
        if not text:
            return ""
        if is_failsafe_response(text):
            text = text.replace("LOCAL_FALLBACK::", "", 1).strip()
        replacements = {
            "Sir ji": "Boss",
            "sir ji": "Boss",
            "Sir": "Boss",
            "Message sent on WhatsApp.": "Ho gaya Boss, WhatsApp message send kar diya.",
            "Speech recognition service is unavailable.": "Boss, speech service abhi respond nahi kar rahi.",
        }
        for source, target in replacements.items():
            text = text.replace(source, target)
        text = self._humanize_response(text)
        return text

    def _humanize_response(self, text):
        normalized = text.lower().strip()
        if normalized.startswith("searching the internet for "):
            query = text[len("Searching the internet for ") :].strip().rstrip(".")
            return f"Ek second Boss, maine {query} ke liye web search khol diya hai."
        if normalized.startswith("i could not process that command"):
            return "Boss, ye command execute nahi ho payi. Ek baar thoda alag tareeke se bolo."
        if normalized == "continuous listening is already active, boss.":
            return "Boss, continuous listening already on hai."
        if normalized == "listening was already off, boss.":
            return "Boss, listening already stopped hai."
        if normalized == "listening has been stopped, boss.":
            return "Okay Boss. Listening stopped."
        if normalized == "google search opened in browser.":
            return "Boss, maine browser me search khol diya hai."
        return text

    def _conversation_context(self):
        context = dict(self.memory.profile())
        context.update(getattr(self.command_brain, "_context", {}))
        context["daily_memory"] = self.memory.daily_memory()
        context["latest_mood"] = self.memory.latest_mood()
        context["mood_history"] = self.memory.mood_history(limit=None) if hasattr(self.memory, "mood_history") else {}
        context["emotion_history"] = self.memory.emotion_history() if hasattr(self.memory, "emotion_history") else {}
        context["conversation_memory"] = self.conversation_memory.snapshot()
        context["behavior_profile"] = self.behavior.summary()
        context["pending_tasks"] = self.memory.pending_tasks()
        snapshot = self.activity_monitor.last_snapshot()
        if snapshot:
            context["activity_snapshot"] = snapshot.as_dict()
        screen_snapshot = self.screen_awareness.status_snapshot() if hasattr(self, "screen_awareness") else {}
        if screen_snapshot.get("last_summary"):
            context["screen_summary"] = screen_snapshot.get("last_summary")
        if screen_snapshot.get("last_capture"):
            context["screen_capture"] = screen_snapshot.get("last_capture")
        return context

    def _brain_profile(self):
        profile = dict(self.memory.profile())
        snapshot = self.activity_monitor.last_snapshot()
        if snapshot:
            profile["activity_snapshot"] = snapshot.as_dict()
        screen_snapshot = self.screen_awareness.status_snapshot() if hasattr(self, "screen_awareness") else {}
        if screen_snapshot.get("last_summary"):
            profile["screen_summary"] = screen_snapshot.get("last_summary")
        if screen_snapshot.get("last_capture"):
            profile["screen_capture"] = screen_snapshot.get("last_capture")
        return profile

    def _emit_core_snapshot(self, task="", agent=""):
        brain_snapshot = self.ai_router.status_snapshot() if hasattr(self, "ai_router") else {}
        memory_snapshot = self.memory.dashboard_snapshot() if hasattr(self.memory, "dashboard_snapshot") else {}
        voice_snapshot = self.voice.status_snapshot() if hasattr(self.voice, "status_snapshot") else {}
        payload = {
            "active_model": brain_snapshot.get("active_model", "local"),
            "route": brain_snapshot.get("route", "offline-safe"),
            "task_status": str(task or "Standby"),
            "active_agent": str(agent or "brain"),
            "memory_status": memory_snapshot.get("memory_status", "SYNCED"),
            "voice_status": voice_snapshot.get("provider", "READY"),
            "emotion_voice": voice_snapshot.get("emotion_voice", "neutral"),
        }
        self.core_snapshot.emit(payload)

    def _looks_like_message_intent(self, command):
        text = str(command).lower()
        if "whatsapp" in text and ("message" in text or "msg" in text or "call" in text):
            return True
        if "send message" in text:
            return True
        return False

    def _classify_command(self, command):
        text = str(command).lower().strip()
        normalized_text = " ".join(re.sub(r"[^a-z0-9\s]", " ", text).split())
        conversation_patterns = {
            "hello",
            "hi",
            "hey",
            "hello myra",
            "hi myra",
            "hey myra",
            "kaise ho",
            "kya kar rahi ho",
            "kya kar rahe ho",
            "how are you",
            "what are you doing",
        }
        if text in conversation_patterns or "thanks" in text or "thank you" in text:
            return "conversation"
        if any(token in text for token in ["whatsapp", "message", "call", "voice message", "email"]):
            return "communication"
        if text.startswith("open ") or text.startswith("close "):
            return "app_control"
        if any(token in text for token in ["play song", "play music", "youtube", "spotify", "netflix", "video"]):
            return "media_control"
        if any(
            token in text
            for token in [
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
                "window",
            ]
        ):
            return "system_control"
        if self._is_visual_query(text):
            return "visual_question"
        if any(
            token in text
            for token in ["what is", "who is", "explain", "tell me about", "how", "why", "define", "kya hai", "kiya hai"]
        ):
            return "ai_question"
        if any(token in normalized_text for token in ["explen", "explane", "explain", "full explain", "full explen"]):
            return "ai_question"
        if any(token in normalized_text for token in ["ai kya hai", "ai kiya hai", "python kya hai", "python kiya hai"]):
            return "ai_question"
        if text.startswith(("search ", "google search ", "find ")) or any(
            token in text for token in ["tutorial", "news", "latest", "guide"]
        ):
            return "internet_search"
        return "general"

    def _ask_brain(self, raw):
        prefaces = [
            "Sochne do Boss, isko simple way me batata hoon.",
            "Ek second Boss, isko tod ke samjhata hoon.",
            "Boss, iska clear answer deta hoon.",
        ]
        answer = self.ai_router.ask(raw, profile=self._brain_profile())
        if not answer:
            return "Boss, main abhi is query ka solid answer generate nahi kar paayi."
        return f"{random.choice(prefaces)} {answer}".strip()

    def _perform_web_search(self, query):
        self.browser.search(query)
        return random.choice(
            [
                f"Ek second Boss, maine {query} ke liye web search khol diya hai.",
                f"Boss, {query} check karne ke liye browser open kar diya hai.",
                f"Abhi dekhta hoon Boss, {query} ka result khol diya hai.",
            ]
        )

    def _perform_latest_info_lookup(self, query):
        lowered = str(query).lower()
        if any(token in lowered for token in ["news", "headline", "headlines"]):
            results = self.internet.fetch_latest_news(query)
            return self.internet.summarize_results(query, results)
        return self.internet.get_latest_info(query)

    def _friendly_fallback(self, raw):
        return random.choice(
            [
                f"Boss, {raw} ko main thoda aur clearly samajhna chahti hoon. Dobara bolo?",
                f"Thoda sa ambiguous tha Boss. {raw} se exactly kya karwana hai?",
                "Boss, isko ya to command ki tarah bolo ya question ki tarah, fir main better handle kar loongi.",
            ]
        )

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

    controller = AssistantController(base_dir)
    window.command_submitted.connect(controller.submit_text)
    window.listen_requested.connect(controller.request_listen)
    controller.history.connect(window.add_history)
    controller.status.connect(window.set_status)
    controller.notification.connect(window.show_notification)
    controller.dashboard_action.connect(window.handle_dashboard_action)
    controller.camera_frame.connect(window.update_camera_frame)
    controller.core_snapshot.connect(window.update_core_snapshot)

    window.show()
    controller.startup()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
