from __future__ import annotations

import json
import os
import re
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False

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


@dataclass(slots=True)
class WhatsAppCommand:
    app: str
    action: str
    contact: str = ""
    message: str = ""
    requires_confirmation: bool = False
    raw_text: str = ""


@dataclass(slots=True)
class PendingConfirmation:
    action: str
    contact: str
    message: str = ""


class WhatsAppController:
    """Standalone WhatsApp Web controller for MYRA.

    Supports:
    - open WhatsApp
    - send message
    - block contact
    - unblock contact

    The module is intentionally self-contained so it can be plugged into
    an existing command system without modifying old code.
    """

    WEB_URL = "https://web.whatsapp.com"

    def __init__(
        self,
        contacts_file: str | Path | None = None,
        chrome_user_data_dir: str | Path | None = None,
        chrome_profile_name: str | None = None,
        headless: bool = False,
    ) -> None:
        self.base_dir = Path(__file__).resolve().parent.parent
        self.contacts_file = Path(contacts_file) if contacts_file else self.base_dir / "myra_contacts.json"
        self.chrome_user_data_dir = (
            Path(chrome_user_data_dir)
            if chrome_user_data_dir
            else Path(os.getenv("MYRA_CHROME_PROFILE_DIR", "").strip() or self.base_dir / ".myra_chrome")
        )
        self.chrome_profile_name = chrome_profile_name or os.getenv("MYRA_CHROME_PROFILE_NAME", "").strip()
        self.headless = headless
        self.contacts = self._load_contacts()
        self.driver = None
        self.pending_confirmation: PendingConfirmation | None = None

    def handle(self, text: str) -> str:
        normalized = self._normalize_text(text)
        if not normalized:
            return "Boss, WhatsApp command clear nahi tha."

        if self.pending_confirmation and self._is_confirmation_reply(normalized):
            return self._handle_confirmation(normalized)

        command = self.parse_command(normalized)
        if command is None:
            return "Boss, WhatsApp wala action samajh nahi aaya."

        if command.action in {"block", "unblock"} and command.requires_confirmation:
            self.pending_confirmation = PendingConfirmation(
                action=command.action,
                contact=command.contact,
                message=command.message,
            )
            action_word = "block" if command.action == "block" else "unblock"
            return f"Boss, kya tum '{self._display_contact(command.contact)}' ko {action_word} karna chahte ho?"

        return self.execute_command(command)

    def parse_command(self, text: str) -> WhatsAppCommand | None:
        cleaned = self._normalize_text(text)

        open_patterns = (
            r"^open whatsapp$",
            r"^whatsapp open$",
            r"^whatsapp open kar$",
            r"^whatsapp open karo$",
            r"^whatsapp kholo$",
            r"^whatsapp khol do$",
            r"^whatsapp khol de$",
        )
        if any(re.match(pattern, cleaned, flags=re.IGNORECASE) for pattern in open_patterns):
            return WhatsAppCommand(app="whatsapp", action="open", raw_text=text)

        message_patterns = (
            r"^(?P<contact>.+?)\s+ko\s+(?:message|msg)\s+(?:bhej|send)(?:\s+do|\s+de|\s+kar do|\s+kar)?\s+(?P<message>.+)$",
            r"^(?:send|bhej)\s+(?:message|msg)\s+to\s+(?P<contact>.+?)\s+(?P<message>.+)$",
            r"^(?:whatsapp\s+)?message\s+to\s+(?P<contact>.+?)\s+(?P<message>.+)$",
        )
        for pattern in message_patterns:
            match = re.match(pattern, cleaned, flags=re.IGNORECASE)
            if match:
                contact = self._clean_contact(match.group("contact"))
                message = self._clean_message(match.group("message"))
                return WhatsAppCommand(
                    app="whatsapp",
                    action="message",
                    contact=contact,
                    message=message,
                    raw_text=text,
                )

        unblock_patterns = (
            r"^(?P<contact>.+?)\s+ko\s+unblock(?:\s+kar|\s+kar do|\s+karna)?$",
            r"^unblock\s+(?P<contact>.+)$",
            r"^(?P<contact>.+?)\s+unblock$",
        )
        for pattern in unblock_patterns:
            match = re.match(pattern, cleaned, flags=re.IGNORECASE)
            if match:
                return WhatsAppCommand(
                    app="whatsapp",
                    action="unblock",
                    contact=self._clean_contact(match.group("contact")),
                    requires_confirmation=True,
                    raw_text=text,
                )

        block_patterns = (
            r"^(?P<contact>.+?)\s+ko\s+block(?:\s+kar|\s+kar do|\s+karna)?$",
            r"^block\s+(?P<contact>.+)$",
            r"^(?P<contact>.+?)\s+block$",
        )
        for pattern in block_patterns:
            match = re.match(pattern, cleaned, flags=re.IGNORECASE)
            if match:
                return WhatsAppCommand(
                    app="whatsapp",
                    action="block",
                    contact=self._clean_contact(match.group("contact")),
                    requires_confirmation=True,
                    raw_text=text,
                )

        if "whatsapp" in cleaned:
            return WhatsAppCommand(app="whatsapp", action="open", raw_text=text)
        return None

    def execute_command(self, command: WhatsAppCommand) -> str:
        if command.action == "open":
            return self.open_whatsapp()
        if command.action == "message":
            return self.send_message(command.contact, command.message)
        if command.action == "block":
            return self.block_contact(command.contact, confirmed=True)
        if command.action == "unblock":
            return self.unblock_contact(command.contact, confirmed=True)
        return "Boss, WhatsApp action supported nahi hai."

    def open_whatsapp(self) -> str:
        try:
            if self._open_whatsapp_home(wait_for_ready=False):
                return "WhatsApp open kar rahi hoon 🚀"
        except Exception:
            pass

        webbrowser.open(self.WEB_URL, new=0, autoraise=False)
        return "WhatsApp open kar rahi hoon 🚀"

    def send_message(self, contact: str, message: str) -> str:
        contact_name = self._clean_contact(contact)
        message_text = self._clean_message(message)
        if not contact_name or not message_text:
            return "Boss, contact aur message dono clear hone chahiye."

        if webdriver is None or ChromeOptions is None:
            phone = self._resolve_contact_number(contact_name)
            if not phone:
                return f"Mujhe '{self._display_contact(contact_name)}' naam ka contact nahi mila"
            url = f"{self.WEB_URL}/send?phone={quote_plus(phone)}&text={quote_plus(message_text)}"
            webbrowser.open(url, new=0, autoraise=False)
            return f"{self._display_contact(contact_name)} ko message ready kar diya. Send ke liye WhatsApp Web khul gaya."

        try:
            if not self._open_whatsapp_home(wait_for_ready=True):
                return "Pehle WhatsApp open karna padega"

            if not self._open_chat(contact_name):
                return f"Mujhe '{self._display_contact(contact_name)}' naam ka contact nahi mila"

            composer = self._wait_for_composer()
            if composer is None:
                return "Message box nahi mila. WhatsApp Web ready hone do."

            composer.click()
            composer.send_keys(message_text)
            composer.send_keys(Keys.ENTER)
            return f"{self._display_contact(contact_name)} ko message bhej diya 👍"
        except Exception as exc:
            return f"Boss, message bhejte waqt issue aa gaya. {exc}"

    def block_contact(self, contact: str, confirmed: bool = False) -> str:
        contact_name = self._clean_contact(contact)
        if not contact_name:
            return "Boss, kis contact ko block karna hai wo clear nahi hai."
        if not confirmed:
            self.pending_confirmation = PendingConfirmation(action="block", contact=contact_name)
            return f"Boss, kya tum '{self._display_contact(contact_name)}' ko block karna chahte ho?"
        if webdriver is None or ChromeOptions is None:
            return "Block karne ke liye Selenium setup chahiye."

        try:
            if not self._open_whatsapp_home(wait_for_ready=True):
                return "Pehle WhatsApp open karna padega"
            if not self._open_chat(contact_name):
                return f"Mujhe '{self._display_contact(contact_name)}' naam ka contact nahi mila"
            if not self._open_contact_info():
                return "Boss, contact info panel open nahi ho pa raha."
            if not self._click_contact_action("block"):
                return f"Boss, '{self._display_contact(contact_name)}' ko block option nahi mila."
            self.pending_confirmation = None
            return f"{self._display_contact(contact_name)} ko block kar diya 👍"
        except Exception as exc:
            return f"Boss, block karte waqt issue aa gaya. {exc}"

    def unblock_contact(self, contact: str, confirmed: bool = False) -> str:
        contact_name = self._clean_contact(contact)
        if not contact_name:
            return "Boss, kis contact ko unblock karna hai wo clear nahi hai."
        if not confirmed:
            self.pending_confirmation = PendingConfirmation(action="unblock", contact=contact_name)
            return f"Boss, kya tum '{self._display_contact(contact_name)}' ko unblock karna chahte ho?"
        if webdriver is None or ChromeOptions is None:
            return "Unblock karne ke liye Selenium setup chahiye."

        try:
            if not self._open_whatsapp_home(wait_for_ready=True):
                return "Pehle WhatsApp open karna padega"
            if not self._open_chat(contact_name):
                return f"Mujhe '{self._display_contact(contact_name)}' naam ka contact nahi mila"
            if not self._open_contact_info():
                return "Boss, contact info panel open nahi ho pa raha."
            if not self._click_contact_action("unblock"):
                return f"Boss, '{self._display_contact(contact_name)}' ko unblock option nahi mila."
            self.pending_confirmation = None
            return f"{self._display_contact(contact_name)} ab unblock ho gaya ✅"
        except Exception as exc:
            return f"Boss, unblock karte waqt issue aa gaya. {exc}"

    def status(self) -> dict:
        return {
            "contacts_loaded": len(self.contacts),
            "pending_confirmation": bool(self.pending_confirmation),
            "selenium_available": webdriver is not None,
        }

    def _handle_confirmation(self, text: str) -> str:
        if self.pending_confirmation is None:
            return "Boss, koi pending confirmation nahi hai."

        if text in {"haan", "han", "yes", "y", "confirm", "ok", "okay"}:
            pending = self.pending_confirmation
            self.pending_confirmation = None
            if pending.action == "block":
                return self.block_contact(pending.contact, confirmed=True)
            if pending.action == "unblock":
                return self.unblock_contact(pending.contact, confirmed=True)
            return "Boss, pending action valid nahi tha."

        if text in {"nahi", "nah", "no", "cancel", "stop"}:
            contact_name = self._display_contact(self.pending_confirmation.contact)
            self.pending_confirmation = None
            return f"Theek hai Boss, '{contact_name}' wala action cancel kar diya."

        return "Boss, confirmation ke liye haan ya nahi bolo."

    def _normalize_text(self, text: str) -> str:
        cleaned = str(text or "").strip().lower()
        cleaned = cleaned.replace("&", " and ")
        cleaned = re.sub(r"[^\w\s:/.?+-]", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        replacements = (
            (r"\bwhatsap\b", "whatsapp"),
            (r"\bwatsapp\b", "whatsapp"),
            (r"\bopen karo\b", "open"),
            (r"\bopen kar\b", "open"),
            (r"\bkhol do\b", "open"),
            (r"\bkhol de\b", "open"),
            (r"\bkholo\b", "open"),
            (r"\bbhej do\b", "bhej"),
            (r"\bbhej de\b", "bhej"),
            (r"\bmsg\b", "message"),
        )
        for pattern, replacement in replacements:
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)

        return re.sub(r"\s+", " ", cleaned).strip()

    def _clean_contact(self, value: str) -> str:
        cleaned = str(value or "").strip(" .")
        cleaned = re.sub(r"\b(whatsapp|message|msg|send|bhej|block|unblock|open)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _clean_message(self, value: str) -> str:
        cleaned = str(value or "").strip(" .")
        return re.sub(r"\s+", " ", cleaned).strip()

    def _display_contact(self, contact: str) -> str:
        return str(contact or "").strip().title()

    def _is_confirmation_reply(self, text: str) -> bool:
        return text in {"haan", "han", "yes", "y", "confirm", "ok", "okay", "nahi", "nah", "no", "cancel", "stop"}

    def _load_contacts(self) -> dict[str, str]:
        contacts: dict[str, str] = {}

        raw_contacts = os.getenv("MYRA_CONTACTS", "").strip()
        if raw_contacts:
            try:
                payload = json.loads(raw_contacts)
            except ValueError:
                payload = {}
            if isinstance(payload, dict):
                for name, number in payload.items():
                    normalized_name = self._clean_contact(name).lower()
                    if normalized_name:
                        contacts[normalized_name] = str(number).strip()

        if self.contacts_file.exists():
            try:
                payload = json.loads(self.contacts_file.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
            if isinstance(payload, dict):
                for name, number in payload.items():
                    normalized_name = self._clean_contact(name).lower()
                    if normalized_name:
                        contacts[normalized_name] = str(number).strip()

        return contacts

    def _resolve_contact_number(self, contact: str) -> str:
        candidate = self._clean_contact(contact).lower()
        if re.fullmatch(r"\+?\d{10,15}", candidate):
            return candidate if candidate.startswith("+") else f"+{candidate}"
        return self.contacts.get(candidate, "")

    def _ensure_driver(self):
        if self.driver is not None:
            return self.driver
        if webdriver is None or ChromeOptions is None:
            raise RuntimeError("selenium is not available")

        options = ChromeOptions()
        options.add_experimental_option("detach", True)
        options.add_argument("--disable-notifications")
        options.add_argument("--start-maximized")
        options.add_argument(f"--user-data-dir={self.chrome_user_data_dir}")
        if self.chrome_profile_name:
            options.add_argument(f"--profile-directory={self.chrome_profile_name}")
        if self.headless:
            options.add_argument("--headless=new")

        self.driver = webdriver.Chrome(options=options)
        return self.driver

    def _open_whatsapp_home(self, wait_for_ready: bool = True) -> bool:
        driver = self._ensure_driver()
        driver.get(self.WEB_URL)
        if not wait_for_ready:
            return True
        return self._wait_for_whatsapp_ready()

    def _wait_for_whatsapp_ready(self, timeout: int = 25) -> bool:
        if By is None or WebDriverWait is None or EC is None:
            return False

        search_selectors = [
            "//div[@contenteditable='true' and @role='textbox']",
            "//div[@title='Search input textbox']",
            "//div[@contenteditable='true' and @data-tab='3']",
        ]
        for selector in search_selectors:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                return True
            except Exception:
                continue
        return False

    def _open_chat(self, contact: str) -> bool:
        driver = self._ensure_driver()
        phone = self._resolve_contact_number(contact)
        if phone:
            driver.get(f"{self.WEB_URL}/send?phone={quote_plus(phone)}")
            return self._wait_for_composer() is not None

        search_box = self._wait_for_search_box()
        if search_box is None:
            return False

        search_box.click()
        search_box.send_keys(Keys.CONTROL, "a")
        search_box.send_keys(contact)
        time.sleep(1.2)

        contact_literal = self._xpath_literal(self._display_contact(contact))
        search_selectors = [
            f"//span[@title={contact_literal}]",
            f"//div[@title={contact_literal}]",
            f"//span[contains(@title, {contact_literal})]",
            f"//div[contains(@title, {contact_literal})]",
        ]
        for selector in search_selectors:
            node = self._wait_for_clickable(selector, timeout=5)
            if node is None:
                continue
            node.click()
            return self._wait_for_composer() is not None
        return False

    def _wait_for_search_box(self):
        selectors = [
            "//div[@contenteditable='true' and @role='textbox']",
            "//div[@title='Search input textbox']",
            "//div[@contenteditable='true' and @data-tab='3']",
        ]
        return self._wait_for_first(selectors, timeout=20)

    def _wait_for_composer(self):
        selectors = [
            "//footer//div[@contenteditable='true']",
            "//div[@title='Type a message']",
            "//div[@contenteditable='true' and @role='textbox']",
        ]
        return self._wait_for_first(selectors, timeout=20)

    def _open_contact_info(self) -> bool:
        selectors = [
            "//header//*[@role='button'][.//span[@title]]",
            "//header//span[@title]/ancestor::*[@role='button'][1]",
            "//header//div[@role='button'][.//*[@title]]",
        ]
        for selector in selectors:
            node = self._wait_for_clickable(selector, timeout=5)
            if node is None:
                continue
            node.click()
            time.sleep(1.0)
            return True
        return False

    def _click_contact_action(self, action: str) -> bool:
        label = "Unblock" if action == "unblock" else "Block"
        self._scroll_side_panel_to_bottom()

        selectors = [
            f"//div[@role='button'][.//*[contains(normalize-space(), '{label}')]]",
            f"//button[.//*[contains(normalize-space(), '{label}')]]",
            f"//*[self::div or self::button][contains(@aria-label, '{label}')]",
            f"//*[contains(text(), '{label}')]",
        ]
        button = self._wait_for_clickable_from_many(selectors, timeout=6)
        if button is None:
            return False
        button.click()
        time.sleep(0.8)

        confirm_selectors = [
            f"//div[@role='button'][.//*[contains(normalize-space(), '{label}')]]",
            f"//button[.//*[contains(normalize-space(), '{label}')]]",
            f"//*[self::div or self::button][contains(@aria-label, '{label}')]",
        ]
        confirm = self._wait_for_clickable_from_many(confirm_selectors, timeout=4)
        if confirm is not None:
            confirm.click()
            time.sleep(1.0)
        return True

    def _scroll_side_panel_to_bottom(self) -> None:
        if self.driver is None:
            return

        candidates = [
            "//div[@data-testid='drawer-right']",
            "//div[@role='dialog']",
            "//div[contains(@class, 'copyable-area')]",
        ]
        for selector in candidates:
            panel = self._wait_for_first([selector], timeout=2)
            if panel is None:
                continue
            try:
                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight;", panel)
                time.sleep(0.5)
                return
            except Exception:
                continue

        try:
            body = self.driver.find_element(By.TAG_NAME, "body")
            for _ in range(5):
                body.send_keys(Keys.END)
                time.sleep(0.2)
        except Exception:
            pass

    def _wait_for_first(self, selectors: list[str], timeout: int = 15):
        if self.driver is None or By is None or WebDriverWait is None or EC is None:
            return None
        for selector in selectors:
            try:
                return WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
            except Exception:
                continue
        return None

    def _wait_for_clickable(self, selector: str, timeout: int = 8):
        if self.driver is None or By is None or WebDriverWait is None or EC is None:
            return None
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((By.XPATH, selector))
            )
        except Exception:
            return None

    def _wait_for_clickable_from_many(self, selectors: list[str], timeout: int = 8):
        for selector in selectors:
            node = self._wait_for_clickable(selector, timeout=timeout)
            if node is not None:
                return node
        return None

    def _xpath_literal(self, value: str) -> str:
        text = str(value)
        if "'" not in text:
            return f"'{text}'"
        if '"' not in text:
            return f'"{text}"'
        parts = text.split("'")
        return "concat(" + ", \"'\", ".join(f"'{part}'" for part in parts) + ")"
