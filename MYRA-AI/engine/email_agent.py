import json
import os
import re
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


class EmailAgent:
    def __init__(self):
        self.smtp_host = os.getenv("MYRA_SMTP_HOST", "").strip()
        self.smtp_port = int(os.getenv("MYRA_SMTP_PORT", "587").strip() or "587")
        self.smtp_user = os.getenv("MYRA_SMTP_USER", "").strip()
        self.smtp_password = os.getenv("MYRA_SMTP_PASSWORD", "").strip()
        self.sender = os.getenv("MYRA_EMAIL_SENDER", "").strip() or self.smtp_user
        self.contacts = self._load_contacts()

    def handle(self, command):
        raw = str(command).strip()
        normalized = raw.lower()

        recipient, subject, body = self._extract_email_payload(raw)
        if recipient and body:
            return True, self.send_email(recipient, subject, body)

        if "check email subject" in normalized or "read email subject" in normalized:
            return True, self.read_email_subject()

        return False, ""

    def send_email(self, recipient, subject, body):
        if not self.smtp_host or not self.smtp_user or not self.smtp_password:
            return "Sir ji, email SMTP settings configured nahi hain."

        to_address = self._resolve_contact(recipient)
        if not to_address:
            return "Sir ji, email address nahi mila. MYRA_EMAIL_CONTACTS configure karo."

        message = EmailMessage()
        message["Subject"] = subject or "Message from MYRA"
        message["From"] = self.sender
        message["To"] = to_address
        message.set_content(body)

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=20) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(message)
            return "Sir ji, email send ho gaya hai."
        except Exception as exc:
            return f"Sir ji, email send nahi ho paya. {exc}"

    def read_email_subject(self):
        return "Sir ji, email subject reading ke liye IMAP integration abhi configure karni hogi."

    def _extract_email_payload(self, command):
        patterns = [
            r"send email to (.+?) about (.+?) saying (.+)$",
            r"send email to (.+?) saying (.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, command, re.IGNORECASE)
            if not match:
                continue
            if len(match.groups()) == 3:
                return match.group(1).strip(), match.group(2).strip(), match.group(3).strip()
            return match.group(1).strip(), "", match.group(2).strip()
        return "", "", ""

    def _resolve_contact(self, recipient):
        candidate = recipient.strip()
        if "@" in candidate:
            return candidate
        return self.contacts.get(candidate.lower(), "")

    def _load_contacts(self):
        raw = os.getenv("MYRA_EMAIL_CONTACTS", "").strip()
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except ValueError:
            return {}
        if not isinstance(payload, dict):
            return {}
        return {str(key).lower(): str(value).strip() for key, value in payload.items()}
