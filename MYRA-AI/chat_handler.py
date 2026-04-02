from __future__ import annotations

import random
import re
from dataclasses import asdict, dataclass
from datetime import datetime


@dataclass(slots=True)
class ChatReply:
    text: str
    mood: str
    topic: str
    follow_up: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


class ChatHandler:
    """Standalone human-like chat layer for MYRA.

    This module is intentionally decoupled from the existing command system.
    It only handles casual conversation and leaves command execution to the
    existing pipeline.
    """

    def __init__(self, persona_name: str = "MYRA", address_style: str = "bhai") -> None:
        self.persona_name = persona_name
        self.address_style = address_style
        self._last_reply_by_topic: dict[str, str] = {}
        self._fallbacks = [
            "Haan bhai, main yahi hoon. Tu bata kya scene hai?",
            "Sun rahi hoon bhai. Bol kya chal raha hai?",
            "Main yahin hoon bhai, araam se bol.",
        ]

    def can_handle(self, text: str) -> bool:
        normalized = self._normalize(text)
        if not normalized:
            return False
        if self._looks_like_command(normalized):
            return False
        return self._is_chat_message(normalized)

    def respond(self, text: str, context: dict | None = None) -> str:
        reply = self.build_reply(text, context=context)
        return reply.text

    def build_reply(self, text: str, context: dict | None = None) -> ChatReply:
        normalized = self._normalize(text)
        context = context or {}

        if not normalized:
            return ChatReply(
                text=self._pick("fallback", self._fallbacks),
                mood="neutral",
                topic="fallback",
            )

        for handler in (
            self._handle_schedule_talk,
            self._handle_greeting,
            self._handle_how_are_you,
            self._handle_what_are_you_doing,
            self._handle_bye,
            self._handle_thanks,
            self._handle_support,
            self._handle_casual_future_talk,
            self._handle_casual_status,
            self._handle_identity,
        ):
            reply = handler(normalized, context)
            if reply is not None:
                return reply

        return ChatReply(
            text=self._pick("fallback", self._fallbacks),
            mood="friendly",
            topic="fallback",
        )

    def _handle_schedule_talk(self, text: str, context: dict) -> ChatReply | None:
        if "kal baat karte" in text or "kal baat karenge" in text or "talk tomorrow" in text:
            options = [
                "Theek hai bhai, kal baat karte hain. Main yahin hoon.",
                "Done bhai, kal aaraam se baat karenge.",
                "Theek hai, kal connect karte hain bhai.",
            ]
            return ChatReply(text=self._pick("tomorrow_talk", options), mood="warm", topic="future_talk")
        return None

    def _handle_greeting(self, text: str, context: dict) -> ChatReply | None:
        greetings = {
            "hi",
            "hello",
            "hey",
            "hello myra",
            "hi myra",
            "hey myra",
            "namaste",
        }
        if text in greetings:
            hour = datetime.now().hour
            if hour < 12:
                options = [
                    "Good morning bhai, kya scene hai aaj?",
                    "Morning bhai, bata aaj kya chal raha hai?",
                ]
            elif hour < 18:
                options = [
                    "Haan bhai, bata kya chal raha hai?",
                    "Hey bhai, kya scene hai?",
                ]
            else:
                options = [
                    "Evening bhai, sab theek?",
                    "Haan bhai, shaam kaisi ja rahi hai?",
                ]
            return ChatReply(text=self._pick("greeting", options), mood="friendly", topic="greeting")
        return None

    def _handle_how_are_you(self, text: str, context: dict) -> ChatReply | None:
        tokens = ("kaise ho", "how are you", "how s it going", "sab theek", "kya haal")
        if any(token in text for token in tokens):
            options = [
                "Main badhiya hoon bhai, tu bata tera mood kaisa hai?",
                "Sab mast hai idhar bhai. Tu suna kya haal hai?",
                "Main theek hoon bhai, bas tere saath vibe kar rahi hoon. Tu bata?",
            ]
            return ChatReply(text=self._pick("how_are_you", options), mood="friendly", topic="check_in")
        return None

    def _handle_what_are_you_doing(self, text: str, context: dict) -> ChatReply | None:
        tokens = ("kya kar raha hai", "kya kar rahi ho", "what are you doing", "what are you up to")
        if any(token in text for token in tokens):
            options = [
                "Bas yahi hoon bhai, tu bata kya scene hai?",
                "Bas standby pe hoon bhai, tera wait kar rahi thi.",
                "Yahin hoon bhai, chill mode me. Tu bol kya karna hai ya bas baat karein?",
            ]
            return ChatReply(text=self._pick("what_doing", options), mood="chill", topic="status")
        return None

    def _handle_bye(self, text: str, context: dict) -> ChatReply | None:
        if text in {"bye", "goodbye", "see you", "milte hain", "chalta hu", "chalta hoon"}:
            options = [
                "Theek hai bhai, baad me baat karte hain.",
                "Milte hain bhai, take care.",
                "Theek hai, jab mann kare ping kar dena bhai.",
            ]
            return ChatReply(text=self._pick("bye", options), mood="warm", topic="goodbye")
        return None

    def _handle_thanks(self, text: str, context: dict) -> ChatReply | None:
        if any(token in text for token in ("thanks", "thank you", "shukriya", "thnx")):
            options = [
                "Arey koi baat nahi bhai.",
                "Anytime bhai, tu bas bol.",
                "Hamesha bhai, tension mat le.",
            ]
            return ChatReply(text=self._pick("thanks", options), mood="supportive", topic="gratitude")
        return None

    def _handle_support(self, text: str, context: dict) -> ChatReply | None:
        supportive_tokens = (
            "sad",
            "tired",
            "stress",
            "stressed",
            "bura lag raha",
            "mann nahi lag raha",
            "thak gaya",
            "thak gayi",
            "low feel",
            "acha nahi lag raha",
        )
        if any(token in text for token in supportive_tokens):
            options = [
                "Aaja bhai, thoda aaraam se lete hain. Jo bolna hai bol.",
                "Samajh sakti hoon bhai. Ek ek step lete hain, sab ho jayega.",
                "Koi nahi bhai, aaj halka sa slow ho ja. Main yahin hoon.",
            ]
            return ChatReply(text=self._pick("support", options), mood="supportive", topic="support")
        return None

    def _handle_casual_future_talk(self, text: str, context: dict) -> ChatReply | None:
        if any(token in text for token in ("baad me baat", "phir baat", "later baat", "later talk")):
            options = [
                "Bilkul bhai, jab free ho tab baat kar lena.",
                "Theek hai bhai, later catch up karte hain.",
                "Done bhai, baad me baat kar lenge.",
            ]
            return ChatReply(text=self._pick("later_talk", options), mood="warm", topic="future_talk")
        return None

    def _handle_casual_status(self, text: str, context: dict) -> ChatReply | None:
        tokens = ("kya chal raha hai", "kya scene hai", "aur bata", "aur sunao", "kya haal chal")
        if any(token in text for token in tokens):
            options = [
                "Sab smooth hai bhai. Tu suna tere side kya chal raha hai?",
                "Yahin usual scene hai bhai. Tu bata aaj kya mood hai?",
                "Bas chill chal raha hai bhai. Tu kya kar raha hai?",
            ]
            return ChatReply(text=self._pick("casual_status", options), mood="friendly", topic="casual_status")
        return None

    def _handle_identity(self, text: str, context: dict) -> ChatReply | None:
        if any(token in text for token in ("tum kaun ho", "who are you", "what is your name")):
            options = [
                f"Main {self.persona_name} hoon bhai, teri dost aur assistant dono.",
                f"{self.persona_name} hoon bhai, kaam bhi karungi aur baat bhi.",
            ]
            return ChatReply(text=self._pick("identity", options), mood="friendly", topic="identity")
        return None

    def _normalize(self, text: str) -> str:
        normalized = str(text or "").lower().strip()
        normalized = normalized.replace("what's", "what s")
        normalized = normalized.replace("how's", "how s")
        normalized = re.sub(r"[^\w\s']", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    def _is_chat_message(self, normalized: str) -> bool:
        chat_tokens = (
            "kal baat karte",
            "kal baat karenge",
            "kya kar raha hai",
            "kya kar rahi ho",
            "kya scene hai",
            "aur bata",
            "aur sunao",
            "kaise ho",
            "how are you",
            "what are you doing",
            "what are you up to",
            "thanks",
            "thank you",
            "shukriya",
            "bye",
            "milte hain",
            "see you",
            "tum kaun ho",
            "who are you",
            "sad",
            "stress",
            "thak gaya",
            "thak gayi",
        )
        return any(token in normalized for token in chat_tokens)

    def _looks_like_command(self, normalized: str) -> bool:
        command_starters = (
            "open ",
            "close ",
            "start ",
            "launch ",
            "run ",
            "play ",
            "search ",
            "find ",
            "download ",
            "send ",
            "call ",
            "message ",
            "whatsapp ",
            "block ",
            "unblock ",
            "lock ",
            "shutdown ",
            "restart ",
            "delete ",
            "create ",
        )
        if normalized.startswith(command_starters):
            return True

        command_tokens = (
            " ko block ",
            " ko unblock ",
            " ko message ",
            " bhej ",
            " search kar ",
            " open kar ",
            " lock kar ",
            " unlock kar ",
        )
        return any(token in f" {normalized} " for token in command_tokens)

    def _pick(self, topic: str, options: list[str]) -> str:
        pool = [item for item in options if item]
        if not pool:
            return ""
        last = self._last_reply_by_topic.get(topic)
        if len(pool) > 1 and last in pool:
            pool = [item for item in pool if item != last]
        choice = random.choice(pool)
        self._last_reply_by_topic[topic] = choice
        return choice
