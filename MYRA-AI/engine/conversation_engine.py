from __future__ import annotations

import random
import re
from datetime import datetime

from help_command import get_netcontrol_help

from engine.emotion_engine import EmotionEngine, EmotionSignal
from engine.emotion_reply_engine import EmotionReplyEngine


class ConversationEngine:
    def __init__(self, emotion_engine: EmotionEngine | None = None, emotion_reply_engine: EmotionReplyEngine | None = None) -> None:
        self.emotion_engine = emotion_engine or EmotionEngine()
        self.emotion_reply_engine = emotion_reply_engine or EmotionReplyEngine()
        self._last_response_by_group = {}
        self._fallbacks = [
            "Arey Boss, kya scene?",
            "Haan Boss... bol kya karna hai.",
            "Boss bata na, aaj kya sort karna hai?",
        ]
        self._jokes = [
            "Boss, debugging ka matlab... dard bhi apna, bug bhi apna, aur jeet bhi apni.",
            "Programmer ka heartbreak bhi commit jaisa hota hai Boss... feelings fix, bugs add.",
            "Code aur chai dono thande ho gaye to samajh ja scene serious hai.",
        ]
        self._motivation = [
            "Boss perfect mood ka wait mat kar... next step maar.",
            "Tu progress kar raha hai Boss, flow mat tod bas.",
            "Aaj thoda sa bhi kaam hua na Boss... wo bhi win hai.",
        ]

    def startup_message(self, context: dict | None = None) -> str:
        context = context or {}
        greeting = self._startup_greeting()
        exam_prompt = self._exam_event_prompt(context)
        contextual_prompt = self._context_follow_up(context)

        if exam_prompt:
            return f"{greeting}... {exam_prompt}"

        if contextual_prompt:
            return f"{greeting}... {contextual_prompt}"

        if "morning" in greeting.lower():
            schedule_text = self._schedule_preview(context)
            if schedule_text:
                return f"{greeting}... aaj ka scene ye hai: {schedule_text}"
            return f"{greeting}... uth gaya kya?"

        if "afternoon" in greeting.lower():
            exam_nudge = self._exam_nudge(context)
            return f"{greeting}... {exam_nudge}" if exam_nudge else f"{greeting}... aaj ka scene kya hai?"

        return f"{greeting}... aaj productive day tha ya chill?"

    def friendly_reply(self, text: str, context: dict | None = None) -> str:
        normalized = self._normalize(text)
        if not normalized:
            return self._pick("fallback", self._fallbacks)

        if self.is_greeting(normalized):
            return self.handle_greeting(normalized, context=context)

        smalltalk_reply = self.handle_smalltalk(normalized, context=context)
        if smalltalk_reply:
            return smalltalk_reply

        emotion_reply = self.emotion_response(normalized, context=context)
        if emotion_reply:
            return emotion_reply

        if self._wants_help(normalized):
            return self.general_help()

        return self._pick("fallback", self._fallbacks)

    def can_handle(self, text: str) -> bool:
        normalized = self._normalize(text)
        if self._contains_action_intent(normalized):
            if not any(token in normalized for token in ("tell me a joke", "make me laugh", "motivate me", "cheer me up")):
                return False
        return self.is_greeting(normalized) or self._matches_smalltalk(normalized) or self.emotion_engine.has_emotion(normalized)

    def handle_greeting(self, text: str, context: dict | None = None) -> str:
        normalized = self._normalize(text)
        context = context or {}
        if any(token in normalized for token in ("good morning", "morning")):
            contextual_prompt = self._context_follow_up(context)
            if contextual_prompt:
                return contextual_prompt
            schedule_text = self._schedule_preview(context)
            if schedule_text:
                return f"Morning Boss, aaj ka schedule ready hai: {schedule_text}"
            exam_nudge = self._exam_nudge(context)
            return exam_nudge or "Morning Boss, kya scene hai?"

        if any(token in normalized for token in ("good night", "night")):
            return "Good night Boss. Aaj ka stress yahin park kar dete hain."

        exam_nudge = self._exam_nudge(context)
        if exam_nudge and random.random() > 0.35:
            return exam_nudge
        return self._pick(
            "greeting",
            [
                "Arey Boss, kya scene?",
                "Aur kya chal raha hai Boss?",
                "Boss... aaj coding mode ya chill mode?",
            ],
        )

    def handle_smalltalk(self, text: str, context: dict | None = None) -> str:
        normalized = self._normalize(text)
        context = context or {}
        if any(token in normalized for token in ("how are you", "how s it going", "kaise ho")):
            return self._pick(
                "smalltalk_how_are_you",
                [
                    "Main mast hu Boss... tu bata, mood kaisa chal raha?",
                    "All good idhar Boss. Tu kaisa feel kar raha... sach bolu to?",
                    "Haan ready hu Boss, tu bata energy kitni bachi hai?",
                ],
            )

        if any(token in normalized for token in ("what are you doing", "what are you up to", "kya kar rahi ho", "kya kar rahe ho")):
            return self._pick(
                "smalltalk_what_are_you_doing",
                [
                    "Bas tera flow dekh rahi hu Boss... ready baithi hu.",
                    "Hmm system, schedule aur mood pe nazar hai Boss... kuch chahiye to bol.",
                    "Main standby me hu Boss, bol kya chahiye.",
                ],
            )

        if any(token in normalized for token in ("who are you", "what is your name", "tum kaun ho")):
            return "Arey Boss, main MYRA hu... teri side wali dost bhi aur smart helper bhi, samjha?"

        if "do you know me" in normalized:
            return self._do_you_know_me_reply(context=context)

        if any(token in normalized for token in ("aaj ka din kaisa tha", "kya chal raha hai", "kya coding practice ki")):
            contextual_prompt = self._context_follow_up(context)
            if contextual_prompt:
                return contextual_prompt
            return self._pick(
                "smalltalk_casual",
                [
                    "Boss, aaj ka din kaisa gaya re?",
                    "Boss, coding hui ya bas planning hi chalti rahi?",
                    "Aur kya chal raha hai Boss?",
                ],
            )

        if any(token in normalized for token in ("thank you", "thanks", "shukriya")):
            return self._pick("thanks", ["Arey anytime Boss.", "Hamesha Boss.", "Tu bas bol Boss."])

        if any(token in normalized for token in ("tell me a joke", "make me laugh", "joke suna")):
            return self.tell_joke()

        if any(token in normalized for token in ("motivate me", "motivation do", "cheer me up")):
            return self.motivate_user()

        if normalized in {"bye", "goodbye", "see you"}:
            return self._pick("goodbye", ["Theek hai Boss, milte hain.", "Jab chaho bula lena Boss.", "Main yahin hu Boss."])

        return ""

    def tell_joke(self) -> str:
        return self._pick("joke", self._jokes)

    def motivate_user(self) -> str:
        return self._pick("motivation", self._motivation)

    def emotion_response(
        self,
        text: str,
        detected: EmotionSignal | None = None,
        context: dict | None = None,
    ) -> str:
        signal = detected if isinstance(detected, EmotionSignal) else self.emotion_engine.detect(text)
        if not signal.is_emotional:
            return ""
        return self.emotion_reply_engine.build_reply(signal, context=context or {})

    def casual_chat(self, text: str, context: dict | None = None) -> str:
        return self.friendly_reply(text, context=context)

    def handle_small_talk(self, text: str, context: dict | None = None) -> str:
        return self.handle_smalltalk(text, context=context)

    def respond_greeting(self, text: str) -> str:
        return self.handle_greeting(text)

    def general_help(self) -> str:
        summary = (
            "Arey Boss, coding, debugging, apps, files, folders, time, date, reminders, memory, schedule, screen scene, aur NetControl se network status, WiFi scan, blocked sites, focus dashboard aur study mode sab handle kar lunga. "
            "Tu bol next kya build karna hai?"
        )
        try:
            return f"{summary}\n\n{get_netcontrol_help()}"
        except Exception:
            return summary

    def is_greeting(self, text: str) -> bool:
        normalized = self._normalize(text)
        return normalized in {
            "hello",
            "hi",
            "hey",
            "hello myra",
            "hi myra",
            "hey myra",
            "good morning",
            "good afternoon",
            "good evening",
            "good night",
            "namaste",
        }

    def _matches_smalltalk(self, normalized: str) -> bool:
        if not normalized:
            return False
        smalltalk_tokens = (
            "how are you",
            "how s it going",
            "kaise ho",
            "what are you doing",
            "what are you up to",
            "kya kar rahi ho",
            "kya kar rahe ho",
            "who are you",
            "what is your name",
            "do you know me",
            "thank you",
            "thanks",
            "shukriya",
            "tell me a joke",
            "make me laugh",
            "joke suna",
            "motivate me",
            "motivation do",
            "cheer me up",
            "what can you do",
            "help me",
            "how can you help",
            "bye",
            "goodbye",
            "see you",
        )
        return any(token in normalized for token in smalltalk_tokens)

    def _contains_action_intent(self, normalized: str) -> bool:
        action_starters = (
            "open ",
            "close ",
            "launch ",
            "start ",
            "run ",
            "play ",
            "search ",
            "find ",
            "google ",
            "download ",
            "send ",
            "call ",
            "set ",
            "increase ",
            "decrease ",
            "mute ",
            "restart ",
            "shutdown ",
            "lock ",
            "plan ",
            "schedule ",
            "remind ",
        )
        return any(normalized.startswith(starter) for starter in action_starters)

    def _do_you_know_me_reply(self, context: dict | None = None) -> str:
        context = context or {}
        name = self._name(context)
        subject = self._subject(context)
        goal = self._daily_value(context, "study_goal_hours", default=0)
        parts = [f"Of course {name}."]
        parts = ["Of course Boss."]
        if subject:
            parts.append(f"Tu abhi {subject} pe focus kar raha hai.")
        if goal:
            parts.append(f"Aaj ka study goal {goal:g} hours hai.")
        return " ".join(parts)

    def _wants_help(self, normalized: str) -> bool:
        return any(token in normalized for token in ("help me", "what can you do", "how can you help", "show help"))

    def _schedule_preview(self, context: dict | None = None) -> str:
        context = context or {}
        schedule = list((context.get("daily_memory") or {}).get("schedule", []))[:3]
        if not schedule:
            return ""
        lines = []
        for item in schedule:
            slot = str(item.get("time", "")).strip()
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            lines.append(f"{slot} - {title}" if slot else title)
        return " | ".join(lines)

    def _startup_greeting(self) -> str:
        hour = datetime.now().hour
        if hour < 12:
            return "Good Morning Boss"
        if hour < 18:
            return "Good Afternoon Boss"
        return "Good Evening Boss"

    def _exam_event_prompt(self, context: dict | None = None) -> str:
        context = context or {}
        daily = context.get("daily_memory") or {}
        exam_date = str(daily.get("exam_date") or context.get("exam_date") or "").strip()
        subject = str(daily.get("subject") or context.get("subject") or "exam").strip()
        subject_label = f"{subject} " if subject and subject.lower() != "exam" else ""
        exam_start = str(daily.get("exam_start") or "").strip()
        exam_end = str(daily.get("exam_end") or "").strip()
        exam_feedback = str(daily.get("exam_feedback") or "").strip()
        today_key = str(datetime.now().date())

        if exam_date != today_key:
            return ""

        if exam_start and exam_end:
            start_dt = self._time_for_today(exam_start)
            end_dt = self._time_for_today(exam_end)
            if start_dt and end_dt:
                now = datetime.now()
                if now < start_dt:
                    return f"yaad hai na... aaj {exam_start} se {exam_end} tera {subject_label}exam hai."
                if start_dt <= now <= end_dt:
                    return "abhi tera exam chal raha hoga... focus kar."
                if now > end_dt and not exam_feedback:
                    return "exam ho gaya? kaisa gaya?"

        if not exam_feedback:
            return f"yaad hai na... aaj tera {subject_label}exam hai."
        return ""

    def _context_follow_up(self, context: dict | None = None) -> str:
        context = context or {}
        snapshot = context.get("conversation_memory") or {}
        topic = str(snapshot.get("last_topic", "")).strip().lower()
        latest_mood = str((context.get("latest_mood") or {}).get("emotion", "")).strip().lower()
        subject = self._subject(context)
        if "exam" in topic or "revision" in topic:
            if subject:
                return f"Hmm Boss, {subject} revision start kiya kya?"
            return "Boss, exam ka scene kaisa chal raha?"
        if "coding" in topic or "project" in topic:
            return "Acha Boss, coding practice kaisi chal rahi?"
        if latest_mood in {"stressed", "sad", "tired"}:
            return "Boss... ab thoda better feel kar raha hai kya?"
        return ""

    def _exam_nudge(self, context: dict | None = None) -> str:
        context = context or {}
        subject = self._subject(context)
        days_left = self._days_until_exam(context)
        if days_left != 1 or not subject:
            return ""
        return f"Boss, kal {subject} ka exam hai na... revision start kiya kya?"

    def _days_until_exam(self, context: dict | None = None):
        context = context or {}
        exam_date = str(
            context.get("exam_date")
            or (context.get("daily_memory") or {}).get("exam_date")
            or ""
        ).strip()
        if not exam_date:
            return None
        try:
            target = datetime.fromisoformat(exam_date).date()
        except ValueError:
            return None
        return (target - datetime.now().date()).days

    def _time_for_today(self, time_text: str):
        try:
            parsed = datetime.strptime(time_text, "%H:%M").time()
        except ValueError:
            return None
        return datetime.combine(datetime.now().date(), parsed)

    def _daily_value(self, context: dict, key: str, default=0):
        daily = context.get("daily_memory") or {}
        return daily.get(key, context.get(key, default))

    def _subject(self, context: dict | None = None) -> str:
        context = context or {}
        return str(context.get("subject") or (context.get("daily_memory") or {}).get("subject") or "").strip()

    def _name(self, context: dict | None = None) -> str:
        return "Boss"

    def _normalize(self, text: str) -> str:
        normalized = str(text).lower().strip()
        normalized = re.sub(r"[^\w\s']", " ", normalized)
        normalized = normalized.replace("what's", "what s")
        normalized = normalized.replace("how's", "how s")
        normalized = normalized.replace("i'm", "im")
        return " ".join(normalized.split())

    def _pick(self, group: str, options: list[str]) -> str:
        pool = [item for item in options if item]
        if not pool:
            return ""
        last = self._last_response_by_group.get(group)
        if len(pool) > 1 and last in pool:
            pool = [item for item in pool if item != last]
        choice = random.choice(pool)
        self._last_response_by_group[group] = choice
        return choice
