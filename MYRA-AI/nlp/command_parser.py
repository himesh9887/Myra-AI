from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .hinglish_converter import HinglishConverter
from .text_normalizer import TextNormalizer


@dataclass(slots=True)
class ParsedCommand:
    type: str
    raw_segment: str
    normalized_segment: str
    target: str = ""
    query: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class CommandParser:
    """Splits human text into sequential actionable commands."""

    def __init__(
        self,
        normalizer: TextNormalizer | None = None,
        converter: HinglishConverter | None = None,
    ) -> None:
        self.normalizer = normalizer or TextNormalizer()
        self.converter = converter or HinglishConverter()

    def parse(self, text: str) -> list[ParsedCommand]:
        normalized = self.normalizer.normalize(text)
        converted = self.converter.convert(normalized)
        raw_segments = self._split_segments(converted)

        commands: list[ParsedCommand] = []
        for segment in raw_segments:
            parsed = self._parse_segment(segment)
            if parsed is not None:
                commands.append(parsed)
        return commands

    def parse_to_actions(self, text: str) -> dict:
        commands = self.parse(text)
        return {
            "actions": [self._command_to_action_text(command) for command in commands],
            "commands": [command.to_dict() for command in commands],
        }

    def _split_segments(self, text: str) -> list[str]:
        return [part.strip(" ,.") for part in re.split(r"\b(?:and|then)\b", text) if part.strip(" ,.")]

    def _parse_segment(self, segment: str) -> ParsedCommand | None:
        cleaned = segment.strip()
        if not cleaned:
            return None

        url_match = re.search(r"((?:https?://)?[a-z0-9.-]+\.[a-z]{2,}(?:/[^\s]*)?)", cleaned, flags=re.IGNORECASE)
        if re.match(r"^(open|go to)\b", cleaned) and url_match:
            url = url_match.group(1)
            if not url.startswith("http"):
                url = f"https://{url}"
            return ParsedCommand("open_url", cleaned, cleaned, url=url)

        action_patterns = (
            ("open", r"^(?:open|launch|start|go to)\s+(?P<value>.+)$"),
            ("search", r"^(?:search|find|google)\s+(?P<value>.+)$"),
            ("close", r"^(?:close|stop|exit)\s+(?P<value>.+)$"),
            ("play", r"^(?:play)\s+(?P<value>.+)$"),
        )

        for action_type, pattern in action_patterns:
            match = re.match(pattern, cleaned, flags=re.IGNORECASE)
            if not match:
                continue
            value = self._clean_value(match.group("value"))
            if action_type == "search":
                return ParsedCommand("search", cleaned, cleaned, query=value)
            return ParsedCommand(action_type, cleaned, cleaned, target=value)

        return ParsedCommand("unknown", cleaned, cleaned, target=cleaned)

    def _clean_value(self, value: str) -> str:
        cleaned = value.strip(" .")
        cleaned = re.sub(r"\b(on google|in google|on browser|in browser)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _command_to_action_text(self, command: ParsedCommand) -> str:
        if command.type == "search":
            return f"search {command.query}".strip()
        if command.type == "open_url":
            return f"open {command.url}".strip()
        return f"{command.type} {command.target}".strip()

