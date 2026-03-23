from __future__ import annotations

from dataclasses import dataclass

from engine.runtime_config import load_myra_system_prompt

from .gemini_brain import GeminiBrain
from .huggingface_brain import HuggingFaceBrain
from .local_brain import LocalBrain
from .openrouter_brain import OpenRouterBrain


@dataclass(frozen=True)
class BrainReply:
    model: str
    response: str
    route: str


class AIRouter:
    def __init__(self, memory=None):
        self.memory = memory
        self.openrouter = OpenRouterBrain()
        self.gemini = GeminiBrain()
        self.huggingface = HuggingFaceBrain()
        self.local = LocalBrain(memory=memory)
        self._last_model = "local"
        self._last_route = "offline-safe"

    def available_models(self) -> list[str]:
        models = []
        if self.openrouter.available():
            models.append("openrouter")
        if self.gemini.available():
            models.append("gemini")
        if self.huggingface.available():
            models.append("huggingface")
        models.append("local")
        return models

    def last_selected_model(self) -> str:
        return self._last_model

    def status_snapshot(self) -> dict:
        return {
            "active_model": self._last_model,
            "route": self._last_route,
            "available_models": self.available_models(),
            "mode": "god-mode",
        }

    def ask(self, prompt: str, profile: dict | None = None) -> str:
        profile = profile if isinstance(profile, dict) else {}
        system_prompt = load_myra_system_prompt()
        context = self._build_context(profile)
        route = self.route_query(prompt)
        providers = self._providers_for_route(route)

        for provider in providers:
            response = self._ask_provider(provider, prompt, system_prompt, context, profile)
            if response:
                self._last_model = provider.name
                self._last_route = route
                return response

        self._last_model = "local"
        self._last_route = "offline-safe"
        return self.local.ask(prompt, system_prompt=system_prompt, context=context, profile=profile)

    def route_query(self, prompt: str) -> str:
        text = " ".join(str(prompt).lower().split())
        if not text:
            return "offline-safe"

        if self._looks_like_operational_command(text):
            return "fast-command"
        if self._looks_like_research_query(text):
            return "deep-research"
        if self._looks_like_personal_memory_query(text):
            return "memory-aware"
        return "general-reasoning"

    def _providers_for_route(self, route: str):
        if route == "deep-research":
            return [self.openrouter, self.gemini, self.huggingface, self.local]
        if route == "general-reasoning":
            return [self.openrouter, self.gemini, self.huggingface, self.local]
        if route == "memory-aware":
            return [self.openrouter, self.gemini, self.local]
        return [self.local, self.openrouter, self.gemini, self.huggingface]

    def _ask_provider(self, provider, prompt: str, system_prompt: str, context: str, profile: dict) -> str:
        if not provider.available():
            return ""
        if provider.name == "local":
            return provider.ask(prompt, system_prompt=system_prompt, context=context, profile=profile)
        return provider.ask(prompt, system_prompt=system_prompt, context=context)

    def _build_context(self, profile: dict) -> str:
        context_chunks = []
        if profile:
            interests = ", ".join(profile.get("interests", []))
            projects = ", ".join(profile.get("projects", [])[:3]) if profile.get("projects") else ""
            preferences = profile.get("preferences", {}) if isinstance(profile.get("preferences"), dict) else {}
            preference_text = ", ".join(
                f"{key}={value}" for key, value in list(preferences.items())[:5] if str(value).strip()
            )
            context_chunks.append(
                "User profile: "
                "preferred_address=Boss, "
                f"course={profile.get('course', '')}, "
                f"field={profile.get('field', '')}, "
                f"current_project={profile.get('current_project', '')}, "
                f"projects={projects}, "
                f"interests={interests}, "
                f"preferences={preference_text}."
            )
            screen_summary = str(profile.get("screen_summary", "")).strip()
            if screen_summary:
                context_chunks.append(f"Latest screen summary: {screen_summary}")
            activity_snapshot = profile.get("activity_snapshot")
            if isinstance(activity_snapshot, dict):
                open_apps = ", ".join(activity_snapshot.get("open_apps", [])[:5]) if activity_snapshot.get("open_apps") else ""
                context_chunks.append(
                    "Current device state: "
                    f"active_app={activity_snapshot.get('active_app', '')}, "
                    f"active_window={activity_snapshot.get('active_title', '')}, "
                    f"open_apps={open_apps}, "
                    f"focus_minutes={activity_snapshot.get('minutes_in_focus', '')}."
                )
        if self.memory and hasattr(self.memory, "recent_conversations"):
            recent = self.memory.recent_conversations(limit=4)
            if recent:
                snippets = []
                for item in recent:
                    user_text = str(item.get("user", "")).strip()
                    assistant_text = str(item.get("assistant", "")).strip()
                    if user_text or assistant_text:
                        snippets.append(f"user={user_text}; assistant={assistant_text}")
                if snippets:
                    context_chunks.append("Recent conversation memory: " + " | ".join(snippets))
        return " ".join(chunk for chunk in context_chunks if chunk).strip()

    def _looks_like_operational_command(self, text: str) -> bool:
        return any(
            text.startswith(prefix)
            for prefix in (
                "open ",
                "close ",
                "launch ",
                "start ",
                "run ",
                "play ",
                "download ",
                "send ",
                "search ",
                "take ",
                "mute ",
                "lock ",
                "restart ",
                "shutdown ",
                "press ",
                "type ",
                "move mouse ",
                "scroll ",
            )
        )

    def _looks_like_research_query(self, text: str) -> bool:
        tokens = (
            "research ",
            "compare ",
            "best ",
            "latest ",
            "analyze ",
            "summary of ",
            "tell me about ",
            "what is ",
            "who is ",
            "why ",
            "how ",
        )
        return any(token in text for token in tokens)

    def _looks_like_personal_memory_query(self, text: str) -> bool:
        tokens = (
            "my name",
            "my profile",
            "what do you know about me",
            "my interests",
            "my project",
            "my course",
        )
        return any(token in text for token in tokens)


def decide_action(command: str) -> str:
    text = " ".join(str(command).lower().split())
    if not text:
        return "ai_answer"

    if any(token in text for token in ["camera", "identify this object", "what do you see", "face"]):
        return "vision"
    if any(token in text for token in ["move mouse", "click", "drag", "type text", "press hotkey", "macro"]):
        return "automation"
    if any(token in text for token in ["youtube", "play song", "play music", "video"]):
        return "youtube"
    if text.startswith("open ") or text.startswith("close "):
        return "open_app"
    if any(
        token in text
        for token in [
            "volume",
            "brightness",
            "mute",
            "lock",
            "shutdown",
            "restart",
            "sleep",
            "screenshot",
            "battery",
            "cpu",
            "ram",
            "window",
        ]
    ):
        return "system"
    if text.startswith("search ") or text.startswith("google search ") or "tutorial" in text:
        return "google"
    return "ai_answer"
