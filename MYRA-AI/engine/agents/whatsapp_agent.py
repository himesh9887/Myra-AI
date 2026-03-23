from __future__ import annotations

from engine.whatsapp_agent import WhatsAppAgent as LegacyWhatsAppAgent

from .base_agent import BaseAgent


class WhatsAppAgent(BaseAgent):
    name = "whatsapp"

    def __init__(self, whatsapp=None):
        self.whatsapp = whatsapp or LegacyWhatsAppAgent()

    def handle(self, command: str):
        return self.whatsapp.handle(command)

    def execute(self, task):
        task = self.normalize_task(task)
        action = task.action.lower()
        payload = task.payload
        meta = task.meta

        if action == "send_message":
            return self.whatsapp.send_message(meta.get("contact", ""), meta.get("text", payload))
        if action == "call_contact":
            return self.whatsapp.call_contact(meta.get("contact", payload))
        if action == "send_file":
            return self.whatsapp.send_file(meta.get("contact", ""), meta.get("file", payload))
        if action == "send_voice":
            return self.whatsapp.send_voice(meta.get("contact", ""), meta.get("text", payload))
        if action == "open_whatsapp":
            return self.whatsapp.open_whatsapp()

        handled, message = self.handle(payload)
        return message if handled else ""
