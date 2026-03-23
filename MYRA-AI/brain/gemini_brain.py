from __future__ import annotations

import os

import requests


class GeminiBrain:
    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 20.0):
        self.api_key = str(api_key or os.getenv("GEMINI_API_KEY", "")).strip()
        self.model = str(model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")).strip() or "gemini-1.5-flash"
        self.timeout = float(timeout)

    @property
    def name(self) -> str:
        return "gemini"

    def available(self) -> bool:
        return bool(self.api_key)

    def ask(self, prompt: str, system_prompt: str = "", context: str = "") -> str:
        if not self.available():
            return ""

        segments = [item.strip() for item in (system_prompt, context, f"User: {prompt}") if str(item).strip()]
        final_prompt = "\n".join(segments)
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": final_prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 600,
            },
        }
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                return ""
            parts = candidates[0].get("content", {}).get("parts", [])
            text = " ".join(str(part.get("text", "")).strip() for part in parts if isinstance(part, dict)).strip()
            return " ".join(text.split())
        except Exception:
            return ""
