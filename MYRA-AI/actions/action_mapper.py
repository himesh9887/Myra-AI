from __future__ import annotations

from dataclasses import asdict, dataclass
from urllib.parse import quote_plus

from nlp.command_parser import ParsedCommand


OPEN_TARGET_URLS = {
    "chatgpt": "https://chat.openai.com",
    "google": "https://www.google.com",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "youtube": "https://www.youtube.com",
    "whatsapp": "https://web.whatsapp.com",
    "news": "https://news.google.com",
}


@dataclass(slots=True)
class MappedAction:
    action_type: str
    handler_name: str
    target: str = ""
    url: str = ""
    query: str = ""
    summary: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class ActionMapper:
    """Maps parsed commands to executable action definitions."""

    def map_command(self, command: ParsedCommand) -> MappedAction:
        if command.type == "open_url":
            return MappedAction(
                action_type="open_url",
                handler_name="open_url",
                url=command.url,
                summary=f"Opening {command.url}",
            )

        if command.type == "open":
            url = OPEN_TARGET_URLS.get(command.target.lower(), "")
            if url:
                return MappedAction(
                    action_type="open_site",
                    handler_name="open_url",
                    target=command.target,
                    url=url,
                    summary=f"Opening {self._display_name(command.target)}",
                )
            return MappedAction(
                action_type="open_target",
                handler_name="open_target",
                target=command.target,
                summary=f"Opening {self._display_name(command.target)}",
            )

        if command.type == "search":
            url = f"https://www.google.com/search?q={quote_plus(command.query)}"
            return MappedAction(
                action_type="search_web",
                handler_name="open_url",
                query=command.query,
                url=url,
                summary=f"Searching {command.query}",
            )

        if command.type == "close":
            return MappedAction(
                action_type="close_target",
                handler_name="close_target",
                target=command.target,
                summary=f"Closing {self._display_name(command.target)}",
            )

        if command.type == "play":
            query = command.target
            url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
            return MappedAction(
                action_type="play_media",
                handler_name="open_url",
                target=query,
                url=url,
                summary=f"Playing {query}",
            )

        return MappedAction(
            action_type="unknown",
            handler_name="unknown",
            target=command.target or command.normalized_segment,
            summary=f"Could not map {command.normalized_segment}",
        )

    def map_commands(self, commands: list[ParsedCommand]) -> list[MappedAction]:
        return [self.map_command(command) for command in commands]

    def _display_name(self, value: str) -> str:
        aliases = {
            "chatgpt": "ChatGPT",
            "gmail": "Gmail",
            "github": "GitHub",
            "youtube": "YouTube",
            "whatsapp": "WhatsApp",
        }
        lowered = str(value).lower()
        return aliases.get(lowered, str(value).strip().title())

