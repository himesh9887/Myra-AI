from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False

from .text_normalizer import TextNormalizer


load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


APP_ALIASES: dict[str, tuple[str, ...]] = {
    "whatsapp": ("whatsapp", "whatsap", "watsapp"),
    "chrome": ("chrome", "browser", "google chrome"),
    "chatgpt": ("chatgpt", "chat gpt"),
    "gmail": ("gmail", "mail"),
    "youtube": ("youtube", "you tube"),
}

SYSTEM_KEYWORDS: dict[str, tuple[str, ...]] = {
    "laptop": ("laptop", "pc", "computer", "desktop", "system"),
    "screen": ("screen", "display", "monitor"),
    "windows": ("windows", "window"),
    "device": ("device", "machine"),
}

ACTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "block": ("block",),
    "unblock": ("unblock",),
    "lock": ("lock",),
    "unlock": ("unlock",),
    "open": ("open", "launch", "start", "khol"),
    "close": ("close", "band", "stop", "exit"),
    "message": ("message", "msg", "send", "bhej"),
    "delete": ("delete", "remove", "hatao"),
    "search": ("search", "find", "dhoondo"),
}

CONTACT_HINT_PATTERNS: tuple[str, ...] = (
    r"^(?P<name>.+?)\s+ko\b",
    r"\bto\s+(?P<name>[a-z0-9][a-z0-9\s]{0,40})\b",
    r"\bwith\s+(?P<name>[a-z0-9][a-z0-9\s]{0,40})\b",
)


@dataclass(slots=True)
class ExtractedEntities:
    raw_text: str
    normalized_text: str
    contact: str | None = None
    app: str | None = None
    system: str | None = None
    message: str | None = None
    target: str | None = None
    action_words: list[str] = field(default_factory=list)
    contact_candidates: list[str] = field(default_factory=list)
    app_candidates: list[str] = field(default_factory=list)
    system_candidates: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class EntityExtractor:
    """Extracts contacts, apps, system targets, and message content from text."""

    def __init__(
        self,
        *,
        contacts_file: str | Path | None = None,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.contacts_file = Path(contacts_file) if contacts_file else self.base_dir / "myra_contacts.json"
        self.normalizer = normalizer or TextNormalizer()
        self.known_contacts = self._load_contacts()

    def extract(self, text: str) -> ExtractedEntities:
        normalized = self.normalizer.normalize(text)
        action_words = self._extract_action_words(normalized)
        contact_candidates = self._extract_contact_candidates(normalized)
        app_candidates = self._extract_apps(normalized)
        system_candidates = self._extract_system_targets(normalized)
        message = self._extract_message_text(normalized)

        contact = self._choose_contact(contact_candidates)
        app = app_candidates[0] if app_candidates else None
        system = system_candidates[0] if system_candidates else None

        if app is None and contact and any(action in action_words for action in ("block", "unblock", "message")):
            app = "whatsapp"

        target = contact or app or system

        return ExtractedEntities(
            raw_text=str(text or "").strip(),
            normalized_text=normalized,
            contact=contact,
            app=app,
            system=system,
            message=message,
            target=target,
            action_words=action_words,
            contact_candidates=contact_candidates,
            app_candidates=app_candidates,
            system_candidates=system_candidates,
        )

    def _extract_action_words(self, text: str) -> list[str]:
        found: list[str] = []
        for action, variants in ACTION_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(variant)}\b", text, flags=re.IGNORECASE) for variant in variants):
                found.append(action)
        return found

    def _extract_contact_candidates(self, text: str) -> list[str]:
        candidates: list[str] = []

        for name in self.known_contacts:
            if re.search(rf"\b{re.escape(name)}\b", text, flags=re.IGNORECASE):
                candidates.append(name)

        for pattern in CONTACT_HINT_PATTERNS:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = self._clean_name(match.group("name"))
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        message_patterns = (
            r"^(?P<name>.+?)\s+ko\s+(?:message|msg)\b",
            r"(?:message|msg)\s+to\s+(?P<name>.+?)\b",
            r"(?:send|bhej)\s+(?:message|msg)\s+to\s+(?P<name>.+?)\b",
        )
        for pattern in message_patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            candidate = self._clean_name(match.group("name"))
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        return candidates

    def _extract_apps(self, text: str) -> list[str]:
        found: list[str] = []
        for app_name, aliases in APP_ALIASES.items():
            if any(re.search(rf"\b{re.escape(alias)}\b", text, flags=re.IGNORECASE) for alias in aliases):
                found.append(app_name)
        return found

    def _extract_system_targets(self, text: str) -> list[str]:
        found: list[str] = []
        for target_name, aliases in SYSTEM_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(alias)}\b", text, flags=re.IGNORECASE) for alias in aliases):
                found.append(target_name)
        return found

    def _extract_message_text(self, text: str) -> str | None:
        patterns = (
            r"^(?P<contact>.+?)\s+ko\s+(?:message|msg)\s+(?:bhej|send)(?:\s+do|\s+de|\s+kar do|\s+kar)?\s+(?P<message>.+)$",
            r"^(?:send|bhej)\s+(?:message|msg)\s+to\s+(?P<contact>.+?)\s+(?P<message>.+)$",
            r"^(?:whatsapp\s+)?message\s+to\s+(?P<contact>.+?)\s+(?P<message>.+)$",
        )
        for pattern in patterns:
            match = re.match(pattern, text, flags=re.IGNORECASE)
            if match:
                return self._clean_message(match.group("message"))
        return None

    def _choose_contact(self, candidates: list[str]) -> str | None:
        if not candidates:
            return None

        reserved_terms = {
            *APP_ALIASES.keys(),
            *SYSTEM_KEYWORDS.keys(),
            *(alias for aliases in APP_ALIASES.values() for alias in aliases),
            *(alias for aliases in SYSTEM_KEYWORDS.values() for alias in aliases),
        }

        for candidate in candidates:
            if candidate in self.known_contacts:
                return candidate
        for candidate in candidates:
            if candidate not in reserved_terms:
                return candidate
        return None

    def _load_contacts(self) -> list[str]:
        contacts: list[str] = []

        raw = os.getenv("MYRA_CONTACTS", "").strip()
        if raw:
            try:
                payload = json.loads(raw)
            except ValueError:
                payload = {}
            if isinstance(payload, dict):
                contacts.extend(self._clean_name(name) for name in payload.keys())

        if self.contacts_file.exists():
            try:
                payload = json.loads(self.contacts_file.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            if isinstance(payload, dict):
                contacts.extend(self._clean_name(name) for name in payload.keys())

        unique: list[str] = []
        for contact in contacts:
            if contact and contact not in unique:
                unique.append(contact)
        return unique

    def _clean_name(self, value: str) -> str:
        cleaned = str(value or "").strip(" .")
        cleaned = re.sub(
            r"\b(whatsapp|message|msg|send|bhej|block|unblock|lock|unlock|open|close|please|kar|karo|karna|do|de)\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
        return cleaned

    def _clean_message(self, value: str) -> str:
        cleaned = str(value or "").strip(" .")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned
