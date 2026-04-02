import json
import os
import re
import socket
import subprocess
import time
import webbrowser
from collections import deque
from pathlib import Path
from urllib.parse import quote

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False

try:
    import pyautogui
except Exception:  # pragma: no cover
    pyautogui = None

try:
    import pyperclip
except Exception:  # pragma: no cover
    pyperclip = None

try:
    import pyttsx3
except Exception:  # pragma: no cover
    pyttsx3 = None

try:
    import psutil
except Exception:  # pragma: no cover
    psutil = None

try:
    import win32process
except Exception:  # pragma: no cover
    win32process = None

try:
    from pywinauto import Desktop
except Exception:  # pragma: no cover
    Desktop = None

from engine.voice_engine import VoiceEngine
from engine.app_launcher import AppLauncher
try:
    from automation.whatsapp_controller import WhatsAppController
except Exception:  # pragma: no cover
    WhatsAppController = None

try:
    from selenium import webdriver
    from selenium.webdriver import ChromeOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
except Exception:  # pragma: no cover
    webdriver = None
    ChromeOptions = None
    By = None
    Keys = None
    EC = None
    WebDriverWait = None


load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


class WhatsAppAgent:
    DEFAULT_WHATSAPP_APP_ID = "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"

    def __init__(self):
        self.workspace_dir = Path(__file__).resolve().parent.parent
        self.contacts_file = self.workspace_dir / "myra_contacts.json"
        self.temp_dir = self.workspace_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.contacts = self._load_contacts()
        self._driver = None
        self._voice_renderer = None
        self._advanced_controller = None
        self._pending_contact_action = None
        self.apps = AppLauncher()
        self.desktop_app_id = os.getenv("MYRA_WHATSAPP_APP_ID", self.DEFAULT_WHATSAPP_APP_ID).strip()

    def handle(self, command):
        text = " ".join(str(command).strip().split())
        normalized = text.lower()

        if self._pending_contact_action and self._is_confirmation_reply(normalized):
            return True, self._handle_pending_contact_action(normalized)

        block_target = self._extract_block_target(text)
        if block_target:
            return True, self.block_contact(block_target)

        unblock_target = self._extract_unblock_target(text)
        if unblock_target:
            return True, self.unblock_contact(unblock_target)

        if self._should_delegate_to_advanced_controller(normalized):
            controller = self._advanced_controller_instance()
            if controller is not None:
                return True, controller.handle(text)

        contact_name, phone_number = self._extract_add_contact_payload(text)
        if contact_name and phone_number:
            return True, self.add_contact(contact_name, phone_number)

        if self._is_list_contacts_command(normalized):
            return True, self.list_contacts()

        chat_target = self._extract_open_chat_target(text)
        if chat_target:
            return True, self.open_chat(chat_target)

        if self._is_open_whatsapp_web_command(normalized):
            return True, self.open_whatsapp_web()

        if self._is_open_whatsapp_command(normalized):
            return True, self.open_whatsapp()

        action = self._detect_action(normalized)
        if not action:
            return False, ""

        if action == "message":
            target, message = self._extract_message_payload(text, normalized)
            if not target or not message:
                return True, self._format_help("message")
            return True, self.send_message(target, message)

        if action == "call":
            target = self._extract_call_target(text)
            if not target:
                return True, self._format_help("call")
            return True, self.call_contact(target)

        if action == "image":
            target, file_hint = self._extract_file_payload(text, action)
            if not target or not file_hint:
                return True, self._format_help("image")
            return True, self.send_image(target, file_hint)

        if action == "file":
            target, file_hint = self._extract_file_payload(text, action)
            if not target or not file_hint:
                return True, self._format_help("file")
            return True, self.send_file(target, file_hint)

        if action == "voice":
            target, message = self._extract_voice_payload(text)
            if not target or not message:
                return True, self._format_help("voice")
            return True, self.send_voice(target, message)

        return False, ""

    def can_claim_followup(self, text):
        if self._pending_contact_action is not None:
            normalized = " ".join(str(text).strip().lower().split())
            return normalized in {"haan", "han", "yes", "y", "confirm", "ok", "okay", "nahi", "nah", "no", "cancel", "stop"}
        controller = self._advanced_controller_instance()
        if controller is None or getattr(controller, "pending_confirmation", None) is None:
            return False
        normalized = " ".join(str(text).strip().lower().split())
        return normalized in {"haan", "han", "yes", "y", "confirm", "ok", "okay", "nahi", "nah", "no", "cancel", "stop"}

    def _should_delegate_to_advanced_controller(self, normalized):
        text = " ".join(str(normalized).strip().lower().split())
        if not text:
            return False
        controller = self._advanced_controller_instance()
        if controller is not None and getattr(controller, "pending_confirmation", None) is not None and self.can_claim_followup(text):
            return True

        patterns = (
            r"^.+?\sko\s+(?:message|msg)\s+(?:bhej|send)(?:\s+do|\s+de|\s+kar do|\s+kar)?\s+.+$",
            r"^(?:send|bhej)\s+(?:message|msg)\s+to\s+.+?\s+.+$",
        )
        return any(re.match(pattern, text, flags=re.IGNORECASE) for pattern in patterns)

    def _is_confirmation_reply(self, normalized):
        return normalized in {"haan", "han", "yes", "y", "confirm", "ok", "okay", "nahi", "nah", "no", "cancel", "stop"}

    def _handle_pending_contact_action(self, normalized):
        pending = dict(self._pending_contact_action or {})
        if not pending:
            return "Boss, koi pending WhatsApp action nahi hai."
        if normalized in {"nahi", "nah", "no", "cancel", "stop"}:
            self._pending_contact_action = None
            return f"Theek hai Boss, {pending.get('contact', '').title()} wala action cancel kar diya."

        self._pending_contact_action = None
        action = str(pending.get("action", "")).strip().lower()
        contact = str(pending.get("contact", "")).strip()
        if action == "block":
            return self.block_contact(contact, confirmed=True)
        if action == "unblock":
            return self.unblock_contact(contact, confirmed=True)
        return "Boss, pending WhatsApp action valid nahi tha."

    def _extract_block_target(self, raw_command):
        patterns = [
            r"^(.+?)\s+ko\s+block(?:\s+kar|\s+kar do|\s+karna|\s+do)?$",
            r"^block\s+(.+)$",
            r"^(.+?)\s+block$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                target = self._clean_target(match.group(1))
                if target:
                    return target
        return ""

    def _extract_unblock_target(self, raw_command):
        patterns = [
            r"^(.+?)\s+ko\s+unblock(?:\s+kar|\s+kar do|\s+karna|\s+do)?$",
            r"^unblock\s+(.+)$",
            r"^(.+?)\s+unblock$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                target = self._clean_target(match.group(1))
                if target:
                    return target
        return ""

    def _advanced_controller_instance(self):
        if self._advanced_controller is not None:
            return self._advanced_controller
        if WhatsAppController is None:
            return None
        try:
            self._advanced_controller = WhatsAppController(contacts_file=self.contacts_file)
        except Exception:
            self._advanced_controller = None
        return self._advanced_controller

    def add_contact(self, name, phone_number):
        normalized_name = " ".join(str(name).strip().split())
        normalized_number = re.sub(r"[^\d+]", "", str(phone_number).strip())
        if not normalized_name:
            return "Boss, contact name clear nahi hai."
        if not re.fullmatch(r"\+?\d{10,15}", normalized_number):
            return "Boss, phone number valid format me do. Example: add whatsapp contact Rahul 9876543210"

        stored_number = normalized_number if normalized_number.startswith("+") else f"+{normalized_number}"
        self.contacts[normalized_name.lower()] = stored_number
        self._save_contacts()
        return f"Boss, WhatsApp contact {normalized_name} save ho gaya hai."

    def list_contacts(self):
        if not self.contacts:
            return "Boss, abhi WhatsApp contacts empty hain. Use karo: add whatsapp contact Rahul 9876543210"
        names = ", ".join(sorted(name.title() for name in self.contacts))
        return f"Boss, saved WhatsApp contacts ye hain: {names}."

    def block_contact(self, target, confirmed=False):
        return self._change_contact_state("block", target, confirmed=confirmed)

    def unblock_contact(self, target, confirmed=False):
        return self._change_contact_state("unblock", target, confirmed=confirmed)

    def _change_contact_state(self, action, target, confirmed=False):
        contact_name = self._clean_target(target)
        action_word = "block" if action == "block" else "unblock"
        pretty_name = self._format_contact_name(contact_name)

        if not contact_name:
            return f"Boss, kis contact ko {action_word} karna hai wo clear nahi hai."

        if not confirmed:
            self._pending_contact_action = {"action": action, "contact": contact_name}
            return f"Boss, kya tum '{pretty_name}' contact ko {action_word} karna chahte ho?"

        try:
            if not self._open_target_chat_desktop(contact_name):
                return f"Mujhe '{pretty_name}' naam ka contact nahi mila"
            if not self._open_contact_info_desktop(contact_name):
                return "Boss, desktop WhatsApp me contact info open nahi ho pa raha."
            if not self._click_contact_action_desktop(action, contact_name):
                return f"Boss, desktop WhatsApp me '{pretty_name}' ko {action_word} option nahi mila."

            if action == "block":
                return f"'{pretty_name}' contact ko block kar diya 👍"
            return f"'{pretty_name}' contact ab unblock ho gaya ✅"
        except Exception as exc:
            return f"Boss, {action_word} karte waqt desktop WhatsApp me issue aa gaya. {exc}"

    def open_whatsapp(self):
        try:
            ok, message = self.apps.open_application("whatsapp")
            normalized_message = str(message).lower()
            if ok and "google" not in normalized_message and "search" not in normalized_message:
                return "Boss, desktop WhatsApp open kar diya hai."
        except Exception:
            pass

        if self._open_whatsapp_shell_app():
            return "Boss, desktop WhatsApp open kar diya hai."

        try:
            ok, _ = self.apps.windows_search("WhatsApp")
            if ok:
                return "Boss, desktop WhatsApp open kar diya hai."
        except Exception:
            pass

        return "Boss, desktop WhatsApp open nahi ho pa raha."

    def open_whatsapp_web(self):
        return self.open_whatsapp()

    def open_chat(self, target):
        try:
            if self._open_target_chat_desktop(target):
                return f"Boss, {target} ki WhatsApp chat open kar di hai."
            return f"Boss, {target} ki WhatsApp chat open nahi ho pa rahi."
        except Exception as exc:
            return f"Boss, {target} ki WhatsApp chat open nahi ho payi. {exc}"

    def send_message(self, target, message):
        try:
            if self._looks_like_phone_number(target) and self._send_message_via_protocol(target, message):
                return "Message sent Boss."
            if self._open_target_chat_desktop(target):
                if self._send_text_to_current_chat(message, target=target):
                    return "Message sent Boss."
                if self._internet_available() and self._send_message_via_web(target, message):
                    return "Message sent Boss."
            if not self._looks_like_phone_number(target) and self._send_message_via_protocol(target, message):
                return "Message sent Boss."
            return f"Boss, {target} ki chat khol di hai, lekin auto-send complete nahi ho paya."
        except Exception as exc:
            return f"Boss, WhatsApp message bhejte time issue aa gaya. {exc}"

    def send_image(self, target, file_hint):
        return self._send_attachment(target, file_hint, asset_type="image")

    def send_file(self, target, file_hint):
        return self._send_attachment(target, file_hint, asset_type="file")

    def send_voice(self, target, message):
        audio_path = self._synthesize_voice_message(message)
        if audio_path is None:
            return "Boss, voice message generate nahi ho paya."

        return self._send_attachment(target, str(audio_path), asset_type="voice")

    def send_voice_message(self, target, message):
        return self.send_voice(target, message)

    def call_contact(self, target):
        try:
            if self._call_via_protocol(target):
                return f"Calling {target} on WhatsApp Boss."
            if self._open_target_chat_desktop(target):
                if self._click_call_button() or self._trigger_toolbar_action("call"):
                    return f"Calling {target} on WhatsApp Boss."
                if self._internet_available() and self._call_via_selenium(target):
                    return f"Calling {target} on WhatsApp Boss."
            return f"Boss, {target} ki chat open ho gayi hai, lekin auto-call start nahi ho payi."
        except Exception as exc:
            return f"Boss, WhatsApp call open karte waqt issue aa gaya. {exc}"

    def make_call(self, target):
        return self.call_contact(target)

    def _send_attachment(self, target, file_hint, asset_type="file"):
        file_path = self._resolve_path(file_hint)
        if not file_path:
            return f"Boss, mujhe `{file_hint}` file nahi mili."

        try:
            if self._open_target_chat_desktop(target) and self._send_attachment_to_current_chat(file_path, asset_type):
                return self._attachment_success_message(asset_type)
            if self._internet_available() and self._send_attachment_via_selenium(target, file_path, asset_type=asset_type):
                return self._attachment_success_message(asset_type)
            return f"Boss, {target} ki chat khul gayi, lekin {asset_type} desktop WhatsApp se send nahi ho paya."
        except Exception as exc:
            return f"Boss, WhatsApp {asset_type} bhejte waqt issue aa gaya. {exc}"

    def _send_attachment_to_current_chat(self, file_path, asset_type="file"):
        self._focus_desktop_window()

        if self._trigger_attachment_flow(file_path, asset_type=asset_type):
            return True

        if self._launch_file_to_current_chat(file_path):
            return self._confirm_attachment_send_desktop(timeout_seconds=8)

        return False

    def _detect_action(self, normalized):
        if "whatsapp" not in normalized and not any(
            token in normalized for token in ["send message", "send image", "send file", "send voice", "call "]
        ):
            return ""
        if any(token in normalized for token in ["voice message", "voice msg", "voice note", "audio message", "audio msg"]):
            return "voice"
        if any(token in normalized for token in ["send image", "whatsapp image", "send photo", "send pic"]):
            return "image"
        if any(token in normalized for token in ["send file", "send document", "send pdf", "whatsapp file"]):
            return "file"
        if any(token in normalized for token in ["whatsapp call", "call on whatsapp", "call "]):
            return "call"
        if "message" in normalized:
            return "message"
        return ""

    def _extract_add_contact_payload(self, raw_command):
        patterns = [
            r"add whatsapp contact\s+(.+?)\s+(\+?\d{10,15})$",
            r"save whatsapp contact\s+(.+?)\s+(\+?\d{10,15})$",
            r"whatsapp contact add\s+(.+?)\s+(\+?\d{10,15})$",
            r"add contact\s+(.+?)\s+(\+?\d{10,15})$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                return match.group(1).strip(), match.group(2).strip()
        return "", ""

    def _is_list_contacts_command(self, normalized):
        phrases = (
            "list whatsapp contacts",
            "show whatsapp contacts",
            "my whatsapp contacts",
            "saved whatsapp contacts",
        )
        return any(phrase in normalized for phrase in phrases)

    def _is_open_whatsapp_command(self, normalized):
        return normalized in {"open whatsapp", "start whatsapp", "launch whatsapp"}

    def _is_open_whatsapp_web_command(self, normalized):
        return normalized in {"open whatsapp web", "start whatsapp web", "launch whatsapp web"}

    def _extract_open_chat_target(self, raw_command):
        patterns = [
            r"open whatsapp chat\s+(.+)$",
            r"open chat\s+(.+?)\s+on whatsapp$",
            r"whatsapp chat\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                return self._clean_target(match.group(1))
        return ""

    def _extract_message_payload(self, raw_command, normalized_command):
        prefix_patterns = [
            r"open whatsapp message to\s+(.+)$",
            r"send whatsapp message to\s+(.+)$",
            r"whatsapp message to\s+(.+)$",
            r"open message to\s+(.+)$",
            r"send message to\s+(.+)$",
        ]
        for pattern in prefix_patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                target, message = self._split_target_and_message(match.group(1).strip())
                if target and message:
                    return target, message

        patterns = [
            r"open whatsapp message to\s+(.+?)\s+(.+)$",
            r"send whatsapp message to\s+(.+?)\s+(.+)$",
            r"send whatsapp message\s+(.+?)\s+(.+)$",
            r"whatsapp message to\s+(.+?)\s+(?:saying\s+)?(.+)$",
            r"open message to\s+(.+?)\s+(.+)$",
            r"send message to\s+(.+?)\s+(?:saying\s+)?(.+)$",
            r"send message\s+(.+?)\s+(.+)$",
            r"(.+?)\s+ko\s+whatsapp\s+message\s+(?:send|bhej)(?:\s+kar|\s+kr)?(?:\s+do)?\s+(.+)$",
            r"whatsapp\s+(?:par|pe|pr)\s+(.+?)\s+ko\s+message\s+(?:send|bhej)(?:\s+kar|\s+kr)?(?:\s+do)?\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                return self._clean_target(match.group(1)), self._clean_message(match.group(2))

        if "message" in normalized_command:
            compact = re.search(r"message\s+to\s+(.+?)\s+(.+)$", raw_command, re.IGNORECASE)
            if compact:
                return self._clean_target(compact.group(1)), self._clean_message(compact.group(2))

        return "", ""

    def _extract_call_target(self, raw_command):
        patterns = [
            r"open whatsapp call to\s+(.+)$",
            r"open whatsapp call\s+(.+)$",
            r"make whatsapp call\s+(.+)$",
            r"call\s+(.+?)\s+on whatsapp$",
            r"whatsapp call\s+(.+)$",
            r"call\s+(.+)$",
            r"(.+?)\s+ko\s+whatsapp\s+call$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                return self._clean_target(match.group(1))
        return ""

    def _extract_file_payload(self, raw_command, action):
        kind = "image" if action == "image" else "(?:file|document|pdf|audio|voice message)"
        patterns = [
            rf"send {kind} to\s+(.+?)\s+(.+)$",
            rf"send whatsapp {kind} to\s+(.+?)\s+(.+)$",
            rf"send whatsapp {kind}\s+(.+?)\s+(.+)$",
            rf"whatsapp {kind}\s+(.+?)\s+(.+)$",
            rf"(.+?)\s+ko\s+whatsapp\s+{kind}\s+(?:send|bhej)(?:\s+kar|\s+kr)?(?:\s+do)?\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                return self._clean_target(match.group(1)), match.group(2).strip()
        return "", ""

    def _extract_voice_payload(self, raw_command):
        patterns = [
            r"send voice message to\s+(.+?)\s+(.+)$",
            r"send voice msg to\s+(.+?)\s+(.+)$",
            r"send whatsapp voice message to\s+(.+?)\s+(.+)$",
            r"send whatsapp voice msg to\s+(.+?)\s+(.+)$",
            r"send whatsapp voice message\s+(.+?)\s+(.+)$",
            r"send whatsapp voice msg\s+(.+?)\s+(.+)$",
            r"send whatsapp voice note\s+(.+?)\s+(.+)$",
            r"(.+?)\s+ko\s+whatsapp\s+voice\s+message\s+(?:send|bhej)(?:\s+kar|\s+kr)?(?:\s+do)?\s+(.+)$",
            r"(.+?)\s+ko\s+whatsapp\s+voice\s+msg\s+(?:send|bhej)(?:\s+kar|\s+kr)?(?:\s+do)?\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_command, re.IGNORECASE)
            if match:
                return self._clean_target(match.group(1)), self._clean_message(match.group(2))
        return "", ""

    def _clean_target(self, value):
        target = str(value).strip().strip(",").strip(".")
        target = re.sub(
            r"\b(to|ko|whatsapp|message|call|image|file|document|voice|note|send|on|open)\b",
            " ",
            target,
            flags=re.IGNORECASE,
        )
        return " ".join(target.split())

    def _clean_message(self, value):
        message = str(value).strip().strip('"').strip("'")
        message = re.sub(
            r"^(?:message|msg|send|bhej|send kr|send kar|kar do|kr do|bolo|ki)\s+",
            "",
            message,
            flags=re.IGNORECASE,
        )
        return " ".join(message.split())

    def _split_target_and_message(self, payload):
        words = " ".join(str(payload).split()).split()
        if len(words) < 2:
            return "", ""

        max_prefix = min(5, len(words) - 1)
        for size in range(max_prefix, 0, -1):
            candidate = " ".join(words[:size]).lower()
            if candidate in self.contacts:
                return " ".join(words[:size]), " ".join(words[size:])

        lowered = [item.lower() for item in words]
        if "group" in lowered[:-1]:
            group_index = max(index for index, item in enumerate(lowered[:-1]) if item == "group")
            target = " ".join(words[: group_index + 1])
            message = " ".join(words[group_index + 1 :])
            if target and message:
                return target, message

        return words[0], " ".join(words[1:])

    def _open_phone_chat(self, target, message=""):
        phone_number = self._resolve_contact(target)
        if not phone_number:
            raise ValueError("contact number nahi mila")
        url = f"whatsapp://send?phone={quote(phone_number)}"
        if message:
            url += f"&text={quote(message)}"
        if not self._open_uri(url):
            raise RuntimeError("desktop WhatsApp protocol open nahi ho paya")

    def _send_message_via_protocol(self, target, message):
        if not self._resolve_contact(target):
            return False
        try:
            self._open_phone_chat(target, message=message)
        except Exception:
            return False
        return self._confirm_prefilled_send()

    def _call_via_protocol(self, target):
        if not self._resolve_contact(target):
            return False
        try:
            self._open_phone_chat(target)
        except Exception:
            return False
        return self._trigger_toolbar_action("call")

    def _open_named_chat(self, target):
        if self._open_named_chat_desktop(target):
            return
        raise RuntimeError("desktop WhatsApp me named chat nahi mili")

    def _open_target_chat_desktop(self, target):
        target_name = " ".join(str(target).strip().split())
        if not target_name:
            return False

        self.open_whatsapp()
        if self._looks_like_phone_number(target_name):
            self._open_phone_chat(target_name)
            return self._wait_for_chat_ready(target_name)
        if self._open_named_chat_desktop(target_name):
            return True
        if self._resolve_contact(target_name):
            self._open_phone_chat(target_name)
            return self._wait_for_chat_ready(target_name)
        return False

    def _open_named_chat_desktop(self, target):
        document = self._desktop_document(wait_seconds=12)
        if document is None:
            return False

        search_box = self._find_first_node(
            lambda node: self._node_type(node) == "Edit"
            and "search input textbox" in self._node_name(node).lower(),
            root=document,
            depth=10,
        )
        if search_box is None:
            return False

        try:
            search_box.click_input()
        except Exception:
            return False

        time.sleep(0.3)
        self._replace_focused_text(target)
        time.sleep(1.0)

        chat_item = self._find_chat_item(target, document=document)
        if chat_item is None:
            return False

        try:
            chat_item.click_input()
        except Exception:
            return False
        return self._wait_for_chat_ready(target)

    def _send_text_to_current_chat(self, message, target=""):
        self._focus_desktop_window()
        composer = self._wait_for_composer_desktop(target=target)
        if composer is None:
            return self._send_text_via_window_geometry(message)

        try:
            composer.click_input()
        except Exception:
            return self._send_text_via_window_geometry(message)

        time.sleep(0.2)
        if not self._replace_composer_text(composer, message):
            return self._send_text_via_window_geometry(message)
        time.sleep(0.35)
        if self._click_send_button_desktop(timeout_seconds=2.5):
            return True
        if self._click_send_button_near_composer(composer):
            return True
        if self._press_enter_and_verify_send(composer):
            return True
        return self._send_text_via_window_geometry(message)

    def _click_call_button(self):
        self._focus_desktop_window()
        document = self._desktop_document(wait_seconds=8)
        if document is None:
            return False

        preferred_fragments = (
            "voice call",
            "audio call",
            "start voice call",
            "call",
        )
        for fragment in preferred_fragments:
            button = self._find_toolbar_button(document, fragment, timeout_seconds=1.5)
            if button is None:
                continue
            try:
                button.click_input()
                return True
            except Exception:
                continue
        return False

    def _click_send_button_desktop(self, timeout_seconds=3):
        button = self._find_send_button_desktop(timeout_seconds=timeout_seconds)
        if button is None:
            return False
        try:
            button.click_input()
            time.sleep(0.4)
            return True
        except Exception:
            return False

    def _find_send_button_desktop(self, timeout_seconds=3):
        document = self._desktop_document(wait_seconds=max(timeout_seconds, 1))
        if document is None:
            return None

        fragments = ("send", "send message", "send now", "submit")
        deadline = time.time() + max(timeout_seconds, 1)
        while time.time() < deadline:
            for node in self._desktop_nodes(document, depth=12):
                if self._node_type(node) not in {"Button", "Hyperlink"}:
                    continue
                node_name = self._node_name(node).strip().lower()
                if not node_name:
                    continue
                if any(fragment == node_name or fragment in node_name for fragment in fragments):
                    return node
            time.sleep(0.2)
            document = self._desktop_document(wait_seconds=1)
            if document is None:
                break
        return None

    def _send_text_via_window_geometry(self, message, use_existing_text=False):
        if pyautogui is None:
            return False
        window = self._desktop_window(wait_seconds=3)
        if window is None:
            return False
        try:
            window.set_focus()
        except Exception:
            pass
        try:
            rect = window.rectangle()
        except Exception:
            return False

        input_points = [
            (int((rect.left + rect.right) / 2), max(rect.top + 80, rect.bottom - 72)),
            (int((rect.left + rect.right) / 2), max(rect.top + 80, rect.bottom - 92)),
            (int((rect.left + rect.right) / 2), max(rect.top + 80, rect.bottom - 112)),
        ]
        send_points = [
            (max(rect.left + 90, rect.right - 60), max(rect.top + 80, rect.bottom - 72)),
            (max(rect.left + 90, rect.right - 82), max(rect.top + 80, rect.bottom - 72)),
            (max(rect.left + 90, rect.right - 60), max(rect.top + 80, rect.bottom - 96)),
        ]

        for input_x, input_y in input_points:
            try:
                pyautogui.click(input_x, input_y)
                time.sleep(0.2)
                if not use_existing_text:
                    pyautogui.hotkey("ctrl", "a")
                    time.sleep(0.1)
                    pyautogui.press("backspace")
                    time.sleep(0.1)
                    self._paste_text(message)
                    time.sleep(0.35)
                for send_x, send_y in send_points:
                    pyautogui.click(send_x, send_y)
                    time.sleep(0.35)
                    if self._find_send_button_desktop(timeout_seconds=0.6) is None:
                        return True
                pyautogui.press("enter")
                time.sleep(0.4)
                if self._find_send_button_desktop(timeout_seconds=0.6) is None:
                    return True
            except Exception:
                continue
        return False

    def _launch_file_to_current_chat(self, file_path):
        executable = self._find_desktop_executable()
        if executable is None:
            return False

        window = self._desktop_window(wait_seconds=5)
        if window is not None:
            try:
                window.set_focus()
            except Exception:
                pass
            time.sleep(0.4)

        try:
            subprocess.Popen([str(executable), str(file_path)], shell=False)
            time.sleep(2.5)
            return True
        except Exception:
            return False

    def _confirm_attachment_send_desktop(self, timeout_seconds=8):
        deadline = time.time() + max(timeout_seconds, 2)
        while time.time() < deadline:
            self._focus_desktop_window()

            if self._click_send_button_desktop(timeout_seconds=1.2):
                time.sleep(0.7)
                if self._find_send_button_desktop(timeout_seconds=0.8) is None:
                    return True

            composer = self._wait_for_composer_desktop(timeout_seconds=1.0)
            if composer is not None:
                if self._click_send_button_near_composer(composer):
                    return True
                if self._press_enter_and_verify_send(composer):
                    return True

            if pyautogui is not None:
                try:
                    pyautogui.press("enter")
                    time.sleep(0.6)
                    if self._find_send_button_desktop(timeout_seconds=0.6) is None:
                        return True
                except Exception:
                    pass

            time.sleep(0.35)
        return False

    def _find_desktop_executable(self):
        configured_raw = os.getenv("MYRA_WHATSAPP_EXE", "").strip()
        if configured_raw:
            configured = Path(configured_raw)
        else:
            configured = None
        if configured is not None and configured.exists():
            return configured

        running = self._find_running_desktop_executable()
        if running is not None:
            return running

        windows_apps = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "WindowsApps"
        patterns = [
            "5319275A.WhatsAppDesktop_*__cv1g1gvanyjgm/WhatsApp.Root.exe",
            "5319275A.WhatsAppDesktop_*__cv1g1gvanyjgm\\WhatsApp.Root.exe",
        ]
        for pattern in patterns:
            matches = sorted(windows_apps.glob(pattern), reverse=True)
            if matches:
                return matches[0]
        return None

    def _find_running_desktop_executable(self):
        if psutil is None:
            return None
        for process in psutil.process_iter(["name", "exe"]):
            try:
                name = str(process.info.get("name", "")).lower()
                exe = str(process.info.get("exe", "")).strip()
                if name == "whatsapp.root.exe" and exe:
                    candidate = Path(exe)
                    if candidate.exists():
                        return candidate
            except Exception:
                continue
        return None

    def _desktop_window(self, wait_seconds=8):
        if Desktop is None:
            return None

        deadline = time.time() + max(wait_seconds, 1)
        while time.time() < deadline:
            try:
                for window in Desktop(backend="uia").windows():
                    if window.window_text().strip().lower() != "whatsapp":
                        continue
                    if self._is_desktop_app_window(window):
                        return window
            except Exception:
                pass
            time.sleep(0.4)
        return None

    def _is_desktop_app_window(self, window):
        if win32process is None or psutil is None:
            return True
        try:
            _, pid = win32process.GetWindowThreadProcessId(window.handle)
            process = psutil.Process(pid)
            return process.name().lower() == "whatsapp.root.exe"
        except Exception:
            return True

    def _desktop_document(self, wait_seconds=8):
        deadline = time.time() + max(wait_seconds, 1)
        while time.time() < deadline:
            window = self._desktop_window(wait_seconds=2)
            if window is None:
                time.sleep(0.3)
                continue
            for node in self._desktop_nodes(window, depth=12):
                try:
                    if self._node_type(node) == "Document" and "whatsapp" in node.window_text().lower():
                        return node
                except Exception:
                    continue
            time.sleep(0.3)
        return None

    def _desktop_nodes(self, root, depth=10):
        queue = deque([(root, 0)])
        while queue:
            node, current_depth = queue.popleft()
            yield node
            if current_depth >= depth:
                continue
            try:
                children = node.children()
            except Exception:
                children = []
            for child in children[:100]:
                queue.append((child, current_depth + 1))

    def _find_first_node(self, predicate, root=None, depth=10):
        search_root = root or self._desktop_document(wait_seconds=6)
        if search_root is None:
            return None
        for node in self._desktop_nodes(search_root, depth=depth):
            try:
                if predicate(node):
                    return node
            except Exception:
                continue
        return None

    def _find_chat_item(self, target, document=None):
        target_name = " ".join(str(target).strip().lower().split())
        if not target_name:
            return None

        document = document or self._desktop_document(wait_seconds=6)
        if document is None:
            return None

        exact_match = None
        partial_match = None
        for node in self._desktop_nodes(document, depth=12):
            if self._node_type(node) not in {"DataItem", "ListItem"}:
                continue
            node_name = self._node_name(node).strip().lower()
            if not node_name:
                continue
            if node_name == target_name or node_name.startswith(target_name + " ") or node_name.startswith(target_name):
                exact_match = node
                break
            if target_name in node_name and partial_match is None:
                partial_match = node
        return exact_match or partial_match

    def _wait_for_chat_ready(self, target=""):
        deadline = time.time() + 10
        target_name = " ".join(str(target).strip().lower().split())
        while time.time() < deadline:
            composer = self._wait_for_composer_desktop(target=target_name, timeout_seconds=1.5)
            if composer is not None:
                return True
            time.sleep(0.3)
        return False

    def _open_contact_info_desktop(self, contact=""):
        self._focus_desktop_window()
        window = self._desktop_window(wait_seconds=6)
        if window is None:
            return False

        direct_fragments = (
            "conversation info",
            "contact info",
            "group info",
            "view contact",
            "profile details",
            "chat info",
        )
        node = self._find_desktop_node_by_name(
            direct_fragments,
            root=window,
            control_types={"Button", "Hyperlink", "MenuItem", "ListItem"},
            depth=14,
        )
        if node is not None and self._click_desktop_node(node):
            time.sleep(0.8)
            return True

        menu_button = self._find_desktop_node_by_name(
            ("more options", "more", "menu"),
            root=window,
            control_types={"Button", "Hyperlink"},
            depth=12,
        )
        if menu_button is not None and self._click_desktop_node(menu_button):
            time.sleep(0.4)
            node = self._find_desktop_node_by_name(
                ("contact info", "view contact", "group info", "profile", "conversation info"),
                root=window,
                control_types={"MenuItem", "Button", "Hyperlink", "ListItem"},
                depth=14,
            )
            if node is not None and self._click_desktop_node(node):
                time.sleep(0.8)
                return True

        header_node = self._find_contact_header_node(contact, window=window)
        if header_node is not None and self._click_desktop_node(header_node):
            time.sleep(0.8)
            return True

        return False

    def _click_contact_action_desktop(self, action, contact=""):
        window = self._desktop_window(wait_seconds=6)
        if window is None:
            return False

        fragments = self._contact_action_fragments(action, contact)
        control_types = {"Button", "Hyperlink", "MenuItem", "ListItem", "Text"}
        node = self._find_desktop_node_by_name(fragments, root=window, control_types=control_types, depth=15)
        if node is None:
            self._scroll_contact_panel_desktop(direction="down", steps=5)
            window = self._desktop_window(wait_seconds=3)
            if window is None:
                return False
            node = self._find_desktop_node_by_name(fragments, root=window, control_types=control_types, depth=16)
        if node is None:
            return False

        if not self._click_desktop_node(node):
            return False

        time.sleep(0.6)
        self._confirm_contact_action_dialog(action, contact=contact)
        return True

    def _confirm_contact_action_dialog(self, action, contact=""):
        window = self._desktop_window(wait_seconds=3)
        if window is None:
            return False

        fragments = self._contact_action_fragments(action, contact)
        confirm_node = self._find_desktop_node_by_name(
            fragments,
            root=window,
            control_types={"Button", "Hyperlink", "MenuItem"},
            depth=14,
        )
        if confirm_node is None:
            return False
        return self._click_desktop_node(confirm_node)

    def _scroll_contact_panel_desktop(self, direction="down", steps=4):
        if pyautogui is None:
            return False

        window = self._desktop_window(wait_seconds=3)
        if window is None:
            return False

        try:
            rect = window.rectangle()
            x = max(rect.left + 180, rect.right - 140)
            y = int((rect.top + rect.bottom) / 2)
            pyautogui.click(x, y)
            time.sleep(0.2)
            delta = -800 if direction == "down" else 800
            for _ in range(max(steps, 1)):
                pyautogui.scroll(delta)
                time.sleep(0.3)
            return True
        except Exception:
            return False

    def _find_contact_header_node(self, contact, window=None):
        contact_name = " ".join(str(contact).strip().lower().split())
        if not contact_name:
            return None

        window = window or self._desktop_window(wait_seconds=4)
        if window is None:
            return None

        try:
            window_rect = window.rectangle()
        except Exception:
            window_rect = None

        candidates = []
        for node in self._desktop_nodes(window, depth=14):
            node_type = self._node_type(node)
            if node_type not in {"Button", "Hyperlink", "Text", "ListItem"}:
                continue
            node_name = " ".join(self._node_name(node).strip().lower().split())
            if not node_name or contact_name not in node_name:
                continue
            score = 0
            if window_rect is not None:
                try:
                    rect = node.rectangle()
                    if rect.left >= window_rect.left + 220:
                        score += 2
                    if rect.top <= window_rect.top + max(220, int((window_rect.bottom - window_rect.top) * 0.32)):
                        score += 2
                except Exception:
                    pass
            candidates.append((score, node))

        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    def _find_desktop_node_by_name(self, fragments, root=None, control_types=None, depth=12):
        if isinstance(fragments, str):
            fragments = (fragments,)
        normalized_fragments = tuple(" ".join(str(item).strip().lower().split()) for item in fragments if str(item).strip())
        if not normalized_fragments:
            return None

        search_root = root or self._desktop_window(wait_seconds=4)
        if search_root is None:
            return None

        best_node = None
        best_score = -1
        for node in self._desktop_nodes(search_root, depth=depth):
            node_type = self._node_type(node)
            if control_types and node_type not in control_types:
                continue
            node_name = " ".join(self._node_name(node).strip().lower().split())
            if not node_name:
                continue
            for fragment in normalized_fragments:
                if fragment == node_name:
                    score = 4
                elif node_name.startswith(fragment):
                    score = 3
                elif fragment in node_name:
                    score = 2
                else:
                    continue
                if score > best_score:
                    best_node = node
                    best_score = score
        return best_node

    def _click_desktop_node(self, node):
        if node is None:
            return False

        attempts = []
        try:
            attempts.append(node.click_input)
        except Exception:
            pass
        try:
            attempts.append(node.invoke)
        except Exception:
            pass

        for action in attempts:
            try:
                action()
                return True
            except Exception:
                continue

        current = node
        for _ in range(3):
            try:
                current = current.parent()
            except Exception:
                current = None
            if current is None:
                break
            try:
                current.click_input()
                return True
            except Exception:
                try:
                    current.invoke()
                    return True
                except Exception:
                    continue
        return False

    def _contact_action_fragments(self, action, contact=""):
        contact_name = " ".join(str(contact).strip().lower().split())
        if action == "block":
            fragments = ["block"]
            if contact_name:
                fragments.extend(
                    [
                        f"block {contact_name}",
                        f"block {contact_name} contact",
                    ]
                )
            return tuple(fragments)

        fragments = ["unblock"]
        if contact_name:
            fragments.extend(
                [
                    f"unblock {contact_name}",
                    f"unblock {contact_name} contact",
                ]
            )
        return tuple(fragments)

    def _format_contact_name(self, contact):
        words = [part for part in str(contact).strip().split() if part]
        if not words:
            return ""
        return " ".join(word[:1].upper() + word[1:] for word in words)

    def _wait_for_composer_desktop(self, target="", timeout_seconds=6):
        deadline = time.time() + max(timeout_seconds, 1)
        target_name = " ".join(str(target).strip().lower().split())
        while time.time() < deadline:
            document = self._desktop_document(wait_seconds=2)
            if document is None:
                time.sleep(0.3)
                continue
            generic_match = None
            for node in self._desktop_nodes(document, depth=12):
                if self._node_type(node) != "Edit":
                    continue
                node_name = self._node_name(node).strip().lower()
                if not (
                    node_name.startswith("type a message")
                    or node_name.startswith("message")
                    or "type a message" in node_name
                ):
                    continue
                if target_name and target_name in node_name:
                    return node
                if generic_match is None:
                    generic_match = node
            if generic_match is not None:
                return generic_match
            time.sleep(0.3)
        return None

    def _find_toolbar_button(self, document, name_fragment, timeout_seconds=3):
        fragment = str(name_fragment).strip().lower()
        deadline = time.time() + max(timeout_seconds, 1)
        while time.time() < deadline:
            for node in self._desktop_nodes(document, depth=12):
                if self._node_type(node) not in {"Button", "Hyperlink"}:
                    continue
                node_name = self._node_name(node).strip().lower()
                if not node_name:
                    continue
                if node_name == fragment or fragment in node_name:
                    return node
            time.sleep(0.2)
            document = self._desktop_document(wait_seconds=1)
            if document is None:
                break
        return None

    def _open_attachment_picker_desktop(self, timeout_seconds=4):
        document = self._desktop_document(wait_seconds=3)
        if document is not None:
            for fragment in ("attach", "attachment", "add attachment", "plus", "clip"):
                button = self._find_toolbar_button(document, fragment, timeout_seconds=0.8)
                if button is None:
                    continue
                try:
                    button.click_input()
                    if self._wait_for_file_dialog(timeout_seconds=timeout_seconds) is not None:
                        return True
                except Exception:
                    continue

        if pyautogui is None:
            return False

        for shortcut in (("ctrl", "shift", "u"), ("ctrl", "u"), ("ctrl", "o")):
            try:
                pyautogui.hotkey(*shortcut)
            except Exception:
                continue
            if Desktop is None:
                time.sleep(1.0)
                return True
            if self._wait_for_file_dialog(timeout_seconds=timeout_seconds) is not None:
                return True
        return False

    def _wait_for_file_dialog(self, timeout_seconds=4):
        if Desktop is None:
            return None

        deadline = time.time() + max(timeout_seconds, 1)
        while time.time() < deadline:
            try:
                for window in Desktop(backend="uia").windows():
                    title = (window.window_text() or "").strip().lower()
                    class_name = str(getattr(window.element_info, "class_name", "") or "").strip().lower()
                    if self._looks_like_file_dialog(title, class_name):
                        return window
            except Exception:
                pass
            time.sleep(0.2)
        return None

    def _looks_like_file_dialog(self, title, class_name):
        if class_name != "#32770":
            return False
        return title in {"open", "attach", "select", "choose file to send"} or any(
            fragment in title for fragment in ("open", "attach", "choose", "select")
        )

    def _focus_desktop_window(self):
        window = self._desktop_window(wait_seconds=3)
        if window is None:
            return False
        try:
            window.set_focus()
            time.sleep(0.2)
            return True
        except Exception:
            return False

    def _replace_focused_text(self, value):
        text = str(value)
        if pyautogui is not None:
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.1)
            pyautogui.press("backspace")
        else:
            return
        self._paste_text(text)

    def _replace_composer_text(self, composer, value):
        text = str(value)
        if pyautogui is not None:
            self._replace_focused_text(text)
            return True
        try:
            composer.type_keys("^a{BACKSPACE}", with_spaces=True)
            time.sleep(0.1)
            composer.type_keys(text, with_spaces=True)
            return True
        except Exception:
            return False

    def _paste_text(self, value):
        text = str(value)
        if pyperclip is not None and pyautogui is not None:
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            return
        if pyautogui is not None:
            pyautogui.write(text, interval=0.01)

    def _node_name(self, node):
        return getattr(node.element_info, "name", "") or node.window_text()

    def _node_type(self, node):
        return getattr(node.element_info, "control_type", "")

    def _send_message_via_web(self, target, message):
        if not self._ensure_driver():
            return False
        driver = self._driver
        self._open_chat_via_selenium(target)
        composer = self._wait_for_composer(driver)
        composer.click()
        composer.send_keys(message)
        composer.send_keys(Keys.ENTER)
        return True

    def _send_attachment_via_selenium(self, target, file_path, asset_type="file"):
        if not self._ensure_driver():
            return False
        driver = self._driver
        if self._resolve_contact(target):
            self._open_phone_chat_via_selenium(target)
        else:
            self._open_chat_via_selenium(target)
        attach_button = self._wait_for_attach_button(driver)
        if attach_button is None:
            return False
        attach_button.click()
        file_input = self._wait_for_attachment_input(driver, asset_type)
        if file_input is None:
            return False
        file_input.send_keys(str(file_path))
        time.sleep(2.0)
        return self._click_send_button(driver, prefer_attachment=True)

    def _call_via_selenium(self, target):
        if not self._ensure_driver():
            return False
        driver = self._driver
        self._open_chat_via_selenium(target)
        selectors = [
            "//button[@title='Voice call']",
            "//button[@aria-label='Voice call']",
            "//button[contains(@aria-label, 'voice call')]",
            "//button[contains(@title, 'Voice call')]",
            "//button[contains(@aria-label, 'Start voice call')]",
            "//span[@data-icon='call']/ancestor::button[1]",
        ]
        for selector in selectors:
            try:
                button = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                button.click()
                return True
            except Exception:
                continue
        return False

    def _open_chat_via_selenium(self, target):
        driver = self._driver
        driver.get("https://web.whatsapp.com")
        search_box = self._wait_for_search_box(driver)
        search_box.click()
        search_box.send_keys(Keys.CONTROL, "a")
        search_box.send_keys(target)

        title_selectors = [
            f"//span[@title={self._xpath_literal(target)}]",
            f"//div[@title={self._xpath_literal(target)}]",
        ]
        for selector in title_selectors:
            try:
                chat = WebDriverWait(driver, 12).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                chat.click()
                return True
            except Exception:
                continue
        raise RuntimeError(f"{target} chat WhatsApp Web me nahi mili")

    def _open_phone_chat_via_selenium(self, target):
        phone_number = self._resolve_contact(target)
        if not phone_number:
            raise RuntimeError("contact number nahi mila")
        self._driver.get(f"https://web.whatsapp.com/send?phone={quote(phone_number)}")
        self._wait_for_composer(self._driver)
        return True

    def _open_whatsapp_shell_app(self):
        app_id = str(self.desktop_app_id).strip()
        if not app_id:
            return False
        try:
            import subprocess

            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app_id}"], shell=False)
            return True
        except Exception:
            return False

    def _open_uri(self, uri):
        target = str(uri).strip()
        if not target:
            return False
        try:
            os.startfile(target)
            return True
        except Exception:
            pass
        try:
            import subprocess

            subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)
            return True
        except Exception:
            return False

    def _wait_for_search_box(self, driver):
        selectors = [
            "//div[@contenteditable='true' and @data-tab='3']",
            "//div[@contenteditable='true' and @role='textbox']",
            "//div[@title='Search input textbox']",
        ]
        for selector in selectors:
            try:
                return WebDriverWait(driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
            except Exception:
                continue
        raise RuntimeError("WhatsApp search box nahi mila")

    def _wait_for_composer(self, driver):
        selectors = [
            "//footer//div[@contenteditable='true']",
            "//div[@contenteditable='true' and @data-tab='10']",
            "//div[@title='Type a message']",
        ]
        for selector in selectors:
            try:
                return WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
            except Exception:
                continue
        raise RuntimeError("WhatsApp message composer nahi mila")

    def _click_send_button(self, driver, prefer_attachment=False):
        selectors = [
            "//span[@data-icon='send']/ancestor::button[1]",
            "//span[@data-icon='send']/ancestor::*[@role='button'][1]",
            "//button[@aria-label='Send']",
            "//button[@title='Send']",
        ]
        for selector in selectors:
            try:
                button = WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
                button.click()
                time.sleep(1.0)
                return True
            except Exception:
                continue
        if prefer_attachment:
            return False
        composer = self._wait_for_composer(driver)
        composer.send_keys(Keys.ENTER)
        return True

    def _ensure_driver(self):
        if webdriver is None or ChromeOptions is None:
            return False
        if self._driver is not None:
            return True
        try:
            options = ChromeOptions()
            options.add_experimental_option("detach", True)
            options.add_argument("--disable-notifications")
            profile_dir = os.getenv("MYRA_CHROME_PROFILE_DIR", "").strip()
            profile_name = os.getenv("MYRA_CHROME_PROFILE_NAME", "").strip()
            if profile_dir:
                options.add_argument("--user-data-dir=" + profile_dir)
                if profile_name:
                    options.add_argument("--profile-directory=" + profile_name)
            else:
                options.add_argument("--user-data-dir=" + str(self.workspace_dir / ".myra_chrome"))
            self._driver = webdriver.Chrome(options=options)
            return True
        except Exception:
            self._driver = None
            return False

    def _press_enter_after_load(self):
        if pyautogui is None:
            return False
        time.sleep(12)
        pyautogui.press("enter")
        return True

    def _confirm_prefilled_send(self):
        # WhatsApp desktop can take a few seconds to foreground the chat opened
        # by the protocol handler. Retry a few send strategies and only
        # report success when one of them actually triggers.
        for delay in (4.0, 2.5, 2.5):
            time.sleep(delay)
            self._focus_desktop_window()
            if self._click_send_button_desktop(timeout_seconds=1.4):
                return True
            composer = self._wait_for_composer_desktop(timeout_seconds=1.4)
            if composer is None:
                if self._send_text_via_window_geometry("", use_existing_text=True):
                    return True
                continue
            if self._click_send_button_near_composer(composer):
                return True
            if self._press_enter_and_verify_send(composer):
                return True
        return False

    def _click_send_button_near_composer(self, composer):
        if pyautogui is None:
            return False
        try:
            rect = composer.rectangle()
            window = self._desktop_window(wait_seconds=2)
            window_rect = window.rectangle() if window is not None else rect
            x_positions = [
                min(rect.right + 22, window_rect.right - 36),
                min(rect.right + 36, window_rect.right - 36),
                min(rect.right + 52, window_rect.right - 36),
            ]
            y = int((rect.top + rect.bottom) / 2)
            for x in x_positions:
                pyautogui.click(x, y)
                time.sleep(0.35)
                if self._find_send_button_desktop(timeout_seconds=0.6) is None:
                    return True
            return False
        except Exception:
            return False

    def _press_enter_and_verify_send(self, composer):
        had_send_button = self._find_send_button_desktop(timeout_seconds=0.8) is not None
        try:
            if pyautogui is not None:
                pyautogui.press("enter")
            else:
                composer.type_keys("{ENTER}", with_spaces=True)
        except Exception:
            return False
        time.sleep(0.45)
        if not had_send_button:
            return True
        return self._find_send_button_desktop(timeout_seconds=0.8) is None

    def _trigger_toolbar_action(self, action):
        if pyautogui is None:
            return False
        time.sleep(10)
        try:
            pyautogui.press("esc")
            time.sleep(0.2)
            pyautogui.click()
            time.sleep(0.2)
        except Exception:
            pass

        if action != "call":
            return False

        # When chat opens via the whatsapp:// protocol, focus can land in different
        # places depending on desktop app state. Try several keyboard paths so the
        # voice-call button can still be triggered without UIA/Selenium support.
        navigation_attempts = [
            ("shift+tab", 2),
            ("shift+tab", 3),
            ("shift+tab", 4),
            ("shift+tab", 5),
            ("shift+tab", 6),
            ("tab", 6),
            ("tab", 8),
            ("tab", 10),
            ("tab", 12),
            ("tab", 14),
        ]
        for key, count in navigation_attempts:
            try:
                pyautogui.press("esc")
                time.sleep(0.15)
                if key == "tab":
                    for _ in range(count):
                        pyautogui.press("tab")
                        time.sleep(0.12)
                else:
                    for _ in range(count):
                        pyautogui.hotkey("shift", "tab")
                        time.sleep(0.12)
                pyautogui.press("enter")
                time.sleep(1.0)
                return True
            except Exception:
                continue
        return False

    def _trigger_attachment_flow(self, file_path, asset_type="file"):
        if pyautogui is None:
            return False

        self._focus_desktop_window()
        if not self._open_attachment_picker_desktop(timeout_seconds=4):
            return False

        dialog = self._wait_for_file_dialog(timeout_seconds=2.5)
        if dialog is not None:
            try:
                dialog.set_focus()
            except Exception:
                pass

        time.sleep(0.6)
        if pyperclip is not None:
            pyperclip.copy(str(file_path))
        if pyperclip is not None:
            pyautogui.hotkey("ctrl", "v")
        else:
            pyautogui.write(str(file_path), interval=0.01)
        time.sleep(0.6)
        pyautogui.press("enter")
        time.sleep(1.4)
        return self._confirm_attachment_send_desktop(timeout_seconds=8)

    def _synthesize_voice_message(self, message):
        safe_name = re.sub(r"[^a-z0-9]+", "_", message.lower())[:32].strip("_") or "voice_note"
        target = self.temp_dir / f"{safe_name}_{int(time.time())}.mp3"
        renderer = self._voice_renderer_instance()
        if renderer is not None and hasattr(renderer, "export_audio_file"):
            prepared = renderer.prepare_response(message) if hasattr(renderer, "prepare_response") else message
            exported = renderer.export_audio_file(prepared, target)
            if exported is not None:
                return Path(exported)

        if pyttsx3 is None:
            return None
        try:
            fallback_target = target.with_suffix(".wav")
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)
            engine.save_to_file(message, str(fallback_target))
            engine.runAndWait()
            time.sleep(0.5)
            if fallback_target.exists() and fallback_target.stat().st_size > 0:
                return fallback_target
        except Exception:
            return None
        return None

    def _attachment_success_message(self, asset_type):
        if asset_type == "image":
            return "Image sent successfully Boss."
        if asset_type == "voice":
            return "Voice message sent Boss."
        return "File sent successfully Boss."

    def _voice_renderer_instance(self):
        if self._voice_renderer is not None:
            return self._voice_renderer
        try:
            self._voice_renderer = VoiceEngine()
        except Exception:
            self._voice_renderer = None
        return self._voice_renderer

    def _wait_for_attach_button(self, driver):
        selectors = [
            "//button[@title='Attach' or @aria-label='Attach']",
            "//span[@data-icon='plus-rounded']/ancestor::*[@role='button'][1]",
            "//span[@data-icon='clip']/ancestor::*[@role='button'][1]",
        ]
        for selector in selectors:
            try:
                return WebDriverWait(driver, 12).until(
                    EC.element_to_be_clickable((By.XPATH, selector))
                )
            except Exception:
                continue
        return None

    def _wait_for_attachment_input(self, driver, asset_type="file"):
        selectors = []
        if asset_type == "image":
            selectors.extend(
                [
                    "//input[@type='file' and contains(@accept, 'image')]",
                    "//input[contains(@accept, 'image')]",
                ]
            )
        elif asset_type == "voice":
            selectors.extend(
                [
                    "//input[@type='file' and contains(@accept, 'audio')]",
                    "//input[contains(@accept, 'audio')]",
                    "//input[@type='file']",
                ]
            )
        else:
            selectors.extend(
                [
                    "//input[@type='file']",
                    "//input[contains(@accept, '*')]",
                ]
            )

        for selector in selectors:
            try:
                return WebDriverWait(driver, 12).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
            except Exception:
                continue
        return None

    def _resolve_contact(self, target):
        candidate = " ".join(str(target).strip().split())
        compact = candidate.replace(" ", "")
        if re.fullmatch(r"\+?\d{10,15}", compact):
            return compact if compact.startswith("+") else f"+{compact}"
        return self.contacts.get(candidate.lower(), "")

    def _looks_like_phone_number(self, value):
        compact = re.sub(r"\s+", "", str(value).strip())
        return bool(re.fullmatch(r"\+?\d{10,15}", compact))

    def _resolve_path(self, value):
        candidate = Path(str(value).strip().strip('"').strip("'"))
        search_paths = []
        if candidate.is_absolute():
            search_paths.append(candidate)
        else:
            search_paths.append(Path.cwd() / candidate)
            search_paths.append(self.workspace_dir / candidate)

        for path in search_paths:
            if path.exists() and path.is_file():
                return path.resolve()
        return None

    def _format_help(self, action):
        examples = {
            "message": "send message to Rahul hello bhai",
            "call": "call Rahul on whatsapp",
            "image": "send image to Rahul C:/images/photo.jpg",
            "file": "send file to Rahul C:/files/document.pdf",
            "voice": "send voice message to Rahul hello bhai kal milte hai",
        }
        return f"Boss, format try karo: {examples.get(action, 'send message to Rahul hello')}"

    def _load_contacts(self):
        contacts = {}
        raw = os.getenv("MYRA_CONTACTS", "").strip()
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            payload = {}
        if isinstance(payload, dict):
            for key, value in payload.items():
                number = str(value).strip()
                if number:
                    contacts[str(key).lower()] = number

        if self.contacts_file.exists():
            try:
                file_payload = json.loads(self.contacts_file.read_text(encoding="utf-8"))
            except Exception:
                file_payload = {}
            if isinstance(file_payload, dict):
                for key, value in file_payload.items():
                    number = str(value).strip()
                    if number:
                        contacts[str(key).lower()] = number
        else:
            self.contacts_file.write_text("{}", encoding="utf-8")

        return contacts

    def _save_contacts(self):
        payload = {name: number for name, number in sorted(self.contacts.items())}
        self.contacts_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _internet_available(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2).close()
            return True
        except OSError:
            return False

    def _xpath_literal(self, value):
        text = str(value)
        if "'" not in text:
            return f"'{text}'"
        if '"' not in text:
            return f'"{text}"'
        parts = text.split("'")
        return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"
