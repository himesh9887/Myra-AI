from __future__ import annotations

import webbrowser
from dataclasses import asdict, dataclass
from typing import Callable
from urllib.parse import quote_plus

from nlp.command_parser import CommandParser, ParsedCommand

from .action_mapper import ActionMapper, MappedAction


@dataclass(slots=True)
class ExecutionResult:
    success: bool
    response: str
    commands: list[dict]
    actions: list[dict]
    step_results: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


class SequentialActionExecutor:
    """Executes mapped actions one by one without depending on existing code."""

    def __init__(
        self,
        parser: CommandParser | None = None,
        mapper: ActionMapper | None = None,
        callbacks: dict[str, Callable[..., bool | str | None]] | None = None,
    ) -> None:
        self.parser = parser or CommandParser()
        self.mapper = mapper or ActionMapper()
        self.callbacks = {
            "open_url": self._default_open_url,
            "open_target": self._default_open_target,
            "close_target": self._default_close_target,
            "unknown": self._default_unknown,
        }
        if callbacks:
            self.callbacks.update(callbacks)

    def execute_text(self, text: str) -> ExecutionResult:
        commands = self.parser.parse(text)
        actions = self.mapper.map_commands(commands)
        return self.execute_actions(commands, actions)

    def execute_actions(
        self,
        commands: list[ParsedCommand],
        actions: list[MappedAction],
    ) -> ExecutionResult:
        step_results: list[dict] = []
        overall_success = True

        for index, action in enumerate(actions, start=1):
            result = self._execute_action(action)
            step_results.append(
                {
                    "step": index,
                    "action": action.to_dict(),
                    "success": result["success"],
                    "message": result["message"],
                }
            )
            if not result["success"]:
                overall_success = False

        response = self._build_response(actions, overall_success)
        return ExecutionResult(
            success=overall_success,
            response=response,
            commands=[command.to_dict() for command in commands],
            actions=[action.to_dict() for action in actions],
            step_results=step_results,
        )

    def _execute_action(self, action: MappedAction) -> dict:
        handler = self.callbacks.get(action.handler_name, self._default_unknown)
        try:
            outcome = handler(action)
        except Exception as exc:
            return {
                "success": False,
                "message": f"{action.summary} failed: {exc}",
            }

        if outcome is False:
            return {
                "success": False,
                "message": f"{action.summary} failed.",
            }
        if isinstance(outcome, str) and outcome.strip():
            return {
                "success": True,
                "message": outcome.strip(),
            }
        return {
            "success": True,
            "message": f"{action.summary} done.",
        }

    def _build_response(self, actions: list[MappedAction], success: bool) -> str:
        if not actions:
            return "I could not understand any executable action."

        summaries = [self._to_progress_phrase(action) for action in actions if action.summary]
        if not summaries:
            return "I could not map the command into actions."

        if len(summaries) == 1:
            return f"{summaries[0]} now." if success else f"{summaries[0]} was attempted."

        normalized = [summaries[0], *[item[:1].lower() + item[1:] for item in summaries[1:]]]
        joined = ", ".join(normalized[:-1]) + f" and {normalized[-1]}"
        return f"{joined} now." if success else f"{joined} was attempted."

    def _to_progress_phrase(self, action: MappedAction) -> str:
        summary = action.summary.strip()
        if summary.startswith("Opening "):
            return summary
        if summary.startswith("Searching "):
            return summary
        if summary.startswith("Closing "):
            return summary
        if summary.startswith("Playing "):
            return summary
        return summary[:1].upper() + summary[1:]

    def _default_open_url(self, action: MappedAction) -> bool:
        webbrowser.open(action.url, new=0, autoraise=False)
        return True

    def _default_open_target(self, action: MappedAction) -> str:
        # Generic fallback keeps the module decoupled from existing app launchers.
        query = action.target.strip()
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        webbrowser.open(url, new=0, autoraise=False)
        return f"Opened a browser fallback for {query}."

    def _default_close_target(self, action: MappedAction) -> bool:
        return False

    def _default_unknown(self, action: MappedAction) -> bool:
        return False
