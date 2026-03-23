from __future__ import annotations

import os

from engine.openrouter_client import OpenRouterClient
from engine.runtime_config import load_runtime_env

load_runtime_env()

try:
    from engine.ai_brain import LEGACY_OPENROUTER_API_KEY, OPENROUTER_API_KEY as ENGINE_OPENROUTER_API_KEY, OPENROUTER_MODEL as ENGINE_OPENROUTER_MODEL
except Exception:
    LEGACY_OPENROUTER_API_KEY = ""
    ENGINE_OPENROUTER_API_KEY = ""
    ENGINE_OPENROUTER_MODEL = "openai/gpt-4o-mini"


class OpenRouterBrain:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 20.0):
        resolved_api_key = str(
            api_key
            or os.getenv("OPENROUTER_API_KEY", "")
            or ENGINE_OPENROUTER_API_KEY
            or LEGACY_OPENROUTER_API_KEY
        ).strip()
        resolved_model = str(
            model
            or os.getenv("OPENROUTER_MODEL", "")
            or ENGINE_OPENROUTER_MODEL
            or "openai/gpt-4o-mini"
        ).strip() or "openai/gpt-4o-mini"

        if resolved_api_key and not os.getenv("OPENROUTER_API_KEY"):
            os.environ.setdefault("OPENROUTER_API_KEY", resolved_api_key)
        if resolved_model and not os.getenv("OPENROUTER_MODEL"):
            os.environ.setdefault("OPENROUTER_MODEL", resolved_model)

        self.client = OpenRouterClient(api_key=resolved_api_key, model=resolved_model, timeout=timeout)

    @property
    def name(self) -> str:
        return "openrouter"

    def available(self) -> bool:
        return self.client.available()

    def ask(self, prompt: str, system_prompt: str = "", context: str = "") -> str:
        if not self.available():
            return ""

        user_prompt = "\n".join(
            item.strip()
            for item in (context, f"User: {prompt}", "MYRA:")
            if str(item).strip()
        )
        payload = self.client.chat(
            [
                {"role": "system", "content": str(system_prompt).strip()},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=600,
        )
        text = self.client.extract_text(payload)
        return " ".join(text.split())
