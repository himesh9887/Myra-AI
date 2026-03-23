from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path

import requests

from engine.runtime_config import load_runtime_env

load_runtime_env()


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 25.0,
        site_url: str | None = None,
        app_name: str | None = None,
    ) -> None:
        self.api_key = str(api_key or os.getenv("OPENROUTER_API_KEY", "")).strip()
        self.model = str(model or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")).strip() or "openai/gpt-4o-mini"
        self.timeout = float(timeout)
        self.site_url = str(site_url or os.getenv("OPENROUTER_SITE_URL", "https://myra.local")).strip() or "https://myra.local"
        self.app_name = str(app_name or os.getenv("OPENROUTER_APP_NAME", "MYRA")).strip() or "MYRA"

    def available(self) -> bool:
        return bool(self.api_key)

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        extra_payload: dict | None = None,
    ) -> dict:
        if not self.available():
            return {}

        payload = {
            "model": str(model or self.model).strip() or self.model,
            "messages": list(messages),
            "temperature": float(temperature),
        }
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        if isinstance(extra_payload, dict):
            payload.update(extra_payload)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.site_url,
            "X-Title": self.app_name,
        }

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception:
            return {}

    def chat_with_image(
        self,
        text_prompt: str,
        image_path: str | os.PathLike[str],
        system_prompt: str = "",
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 250,
    ) -> dict:
        image_data_url = self._image_as_data_url(image_path)
        if not image_data_url:
            return {}

        messages = []
        if str(system_prompt).strip():
            messages.append({"role": "system", "content": str(system_prompt).strip()})

        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": str(text_prompt).strip()},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        )
        return self.chat(messages, model=model, temperature=temperature, max_tokens=max_tokens)

    def extract_text(self, payload: dict) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except Exception:
            return ""

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    cleaned = item.strip()
                    if cleaned:
                        parts.append(cleaned)
                    continue
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text":
                    cleaned = str(item.get("text", "")).strip()
                    if cleaned:
                        parts.append(cleaned)
            return " ".join(parts).strip()

        return str(content).strip()

    def _image_as_data_url(self, image_path: str | os.PathLike[str]) -> str:
        path = Path(image_path)
        if not path.exists():
            return ""

        try:
            raw = path.read_bytes()
        except Exception:
            return ""

        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(raw).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"
