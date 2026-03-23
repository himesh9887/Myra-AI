from __future__ import annotations

import os

import requests


class HuggingFaceBrain:
    def __init__(self, token: str | None = None, api_url: str | None = None, timeout: float = 25.0):
        self.token = str(token or os.getenv("MYRA_HF_API_TOKEN") or os.getenv("HUGGINGFACE_API_TOKEN", "")).strip()
        self.api_url = str(
            api_url
            or os.getenv(
                "MYRA_HF_API_URL",
                "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2",
            )
        ).strip()
        self.timeout = float(timeout)

    @property
    def name(self) -> str:
        return "huggingface"

    def available(self) -> bool:
        return bool(self.token and self.api_url)

    def ask(self, prompt: str, system_prompt: str = "", context: str = "") -> str:
        if not self.available():
            return ""

        final_prompt = "\n".join(item.strip() for item in (system_prompt, context, prompt) if str(item).strip())
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        payload = {"inputs": final_prompt}
        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=self.timeout)
            data = response.json()
        except Exception:
            return ""

        if isinstance(data, dict) and data.get("error"):
            return ""
        try:
            text = str(data[0]["generated_text"]).strip()
        except Exception:
            return ""
        return " ".join(text.split())
