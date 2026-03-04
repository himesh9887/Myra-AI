import json
import os
import re
import socket
from pathlib import Path

from dotenv import load_dotenv
import pywhatkit


load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


class WhatsAppAgent:
    def __init__(self):
        self.contacts = self._load_contacts()

    def handle(self, command):
        text = str(command).strip()
        normalized = text.lower()
        target, message = self._extract_message_payload(text, normalized)
        if not target or not message:
            return False, ""
        return True, self.send_message(target, message)

    def send_message(self, target, message):
        if not self._internet_available():
            return "Sir ji, internet available nahi hai. WhatsApp message send nahi hoga."

        phone_number = self._resolve_contact(target)
        if not phone_number:
            return (
                "Sir ji, contact number nahi mila. "
                "Number ke saath bolo ya MYRA_CONTACTS configure karo."
            )

        try:
            pywhatkit.sendwhatmsg_instantly(
                phone_no=phone_number,
                message=message,
                wait_time=15,
                tab_close=False,
                close_time=3,
            )
            return "Message sent on WhatsApp."
        except Exception as exc:
            return (
                "Sir ji, WhatsApp message send nahi ho paya. "
                f"Check karo WhatsApp Web login hai ya nahi. {exc}"
            )

    def _extract_message_payload(self, raw_command, normalized_command):
        patterns = [
            r"send message to (.+?) (?:saying |that |message )?(.+)$",
            r"whatsapp message to (.+?) (?:saying |that |message )?(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                return match.group(1).strip(), match.group(2).strip()
        return "", ""

    def _resolve_contact(self, target):
        candidate = target.strip()
        compact = candidate.replace(" ", "")
        if re.fullmatch(r"\+?\d{10,15}", compact):
            return compact if compact.startswith("+") else f"+{compact}"
        return self.contacts.get(candidate.lower(), "")

    def _load_contacts(self):
        raw = os.getenv("MYRA_CONTACTS", "").strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except ValueError:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(key).lower(): str(value).strip() for key, value in payload.items()}

    def _internet_available(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2).close()
            return True
        except OSError:
            return False
