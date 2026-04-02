from __future__ import annotations

from dataclasses import asdict, dataclass

from .entity_extractor import EntityExtractor, ExtractedEntities
from .text_normalizer import TextNormalizer


CRITICAL_ACTIONS = {"block_contact", "unblock_contact", "lock_system", "delete_target"}


@dataclass(slots=True)
class ResolvedAction:
    action_type: str
    handler_name: str
    domain: str
    target: str = ""
    contact: str = ""
    app: str = ""
    system: str = ""
    message: str = ""
    requires_confirmation: bool = False
    requires_clarification: bool = False
    clarification_prompt: str = ""
    summary: str = ""
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class ActionResolver:
    """Resolves ambiguous command language into a context-aware action."""

    def __init__(
        self,
        *,
        extractor: EntityExtractor | None = None,
        normalizer: TextNormalizer | None = None,
    ) -> None:
        self.normalizer = normalizer or TextNormalizer()
        self.extractor = extractor or EntityExtractor(normalizer=self.normalizer)

    def resolve(self, text: str) -> ResolvedAction:
        normalized = self.normalizer.normalize(text)
        entities = self.extractor.extract(normalized)
        return self.resolve_from_entities(entities)

    def resolve_from_entities(self, entities: ExtractedEntities) -> ResolvedAction:
        actions = entities.action_words
        contact = entities.contact or ""
        app = entities.app or ""
        system = entities.system or ""
        message = entities.message or ""

        if "unblock" in actions:
            if contact:
                return self._resolved(
                    "unblock_contact",
                    "unblock_contact",
                    "whatsapp",
                    contact=contact,
                    app=app or "whatsapp",
                    requires_confirmation=True,
                    summary=f"Unblocking {self._display_contact(contact)} contact",
                    confidence=0.97,
                )
            return self._clarify("Kisko unblock karna hai?", domain="whatsapp")

        if "block" in actions:
            if contact:
                return self._resolved(
                    "block_contact",
                    "block_contact",
                    "whatsapp",
                    contact=contact,
                    app=app or "whatsapp",
                    requires_confirmation=True,
                    summary=f"Blocking {self._display_contact(contact)} contact",
                    confidence=0.98,
                )
            if system:
                return self._resolved(
                    "lock_system",
                    "lock_system",
                    "system",
                    system=system,
                    target=system,
                    requires_confirmation=True,
                    summary=f"Locking {system}",
                    confidence=0.8,
                )
            return self._clarify("Kisko block karna hai?", domain="unknown")

        if "lock" in actions:
            if system:
                return self._resolved(
                    "lock_system",
                    "lock_system",
                    "system",
                    system=system,
                    target=system,
                    requires_confirmation=True,
                    summary=f"Locking {system}",
                    confidence=0.98,
                )
            if contact:
                return self._clarify(
                    f"Kya tum {self._display_contact(contact)} contact ko block karna chahte ho ya system ko lock?",
                    domain="unknown",
                )
            return self._clarify("Kya lock karna hai? Laptop ya screen?", domain="system")

        if "message" in actions:
            if contact and message:
                return self._resolved(
                    "send_message",
                    "send_message",
                    "whatsapp",
                    contact=contact,
                    app=app or "whatsapp",
                    message=message,
                    summary=f"Sending message to {self._display_contact(contact)}",
                    confidence=0.99,
                )
            if contact and not message:
                return self._clarify(
                    f"{self._display_contact(contact)} ko kya message bhejna hai?",
                    domain="whatsapp",
                )
            return self._clarify("Kisko message bhejna hai?", domain="whatsapp")

        if "open" in actions:
            if app == "whatsapp":
                return self._resolved(
                    "open_whatsapp",
                    "open_whatsapp",
                    "whatsapp",
                    app="whatsapp",
                    target="whatsapp",
                    summary="Opening WhatsApp",
                    confidence=0.97,
                )
            if app:
                return self._resolved(
                    "open_application",
                    "open_application",
                    "app",
                    app=app,
                    target=app,
                    summary=f"Opening {app}",
                    confidence=0.92,
                )
            if contact:
                return self._resolved(
                    "open_contact_chat",
                    "open_contact_chat",
                    "whatsapp",
                    contact=contact,
                    app="whatsapp",
                    summary=f"Opening chat with {self._display_contact(contact)}",
                    confidence=0.84,
                )
            return self._clarify("Kya open karna hai?", domain="app")

        if "close" in actions:
            if app:
                return self._resolved(
                    "close_application",
                    "close_application",
                    "app",
                    app=app,
                    target=app,
                    summary=f"Closing {app}",
                    confidence=0.9,
                )
            return self._clarify("Kya close karna hai?", domain="app")

        if "delete" in actions:
            if contact:
                return self._resolved(
                    "delete_contact",
                    "delete_contact",
                    "contact",
                    contact=contact,
                    requires_confirmation=True,
                    summary=f"Deleting {self._display_contact(contact)} contact",
                    confidence=0.82,
                )
            if app or system or entities.target:
                target = app or system or (entities.target or "")
                return self._resolved(
                    "delete_target",
                    "delete_target",
                    "system",
                    target=target,
                    app=app,
                    system=system,
                    requires_confirmation=True,
                    summary=f"Deleting {target}",
                    confidence=0.72,
                )
            return self._clarify("Kya delete karna hai?", domain="system")

        return self._clarify("Command thoda ambiguous hai. Thoda aur clearly bolo.", domain="unknown")

    def needs_confirmation(self, action: ResolvedAction) -> bool:
        return action.requires_confirmation or action.action_type in CRITICAL_ACTIONS

    def _resolved(
        self,
        action_type: str,
        handler_name: str,
        domain: str,
        *,
        target: str = "",
        contact: str = "",
        app: str = "",
        system: str = "",
        message: str = "",
        requires_confirmation: bool = False,
        summary: str = "",
        confidence: float = 0.0,
    ) -> ResolvedAction:
        return ResolvedAction(
            action_type=action_type,
            handler_name=handler_name,
            domain=domain,
            target=target or contact or app or system,
            contact=contact,
            app=app,
            system=system,
            message=message,
            requires_confirmation=requires_confirmation,
            requires_clarification=False,
            clarification_prompt="",
            summary=summary,
            confidence=confidence,
        )

    def _clarify(self, prompt: str, *, domain: str) -> ResolvedAction:
        return ResolvedAction(
            action_type="clarify",
            handler_name="clarify",
            domain=domain,
            requires_confirmation=False,
            requires_clarification=True,
            clarification_prompt=prompt,
            summary=prompt,
            confidence=0.2,
        )

    def _display_contact(self, value: str) -> str:
        return str(value or "").strip().title()
