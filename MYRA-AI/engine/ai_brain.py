import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from google import genai


load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


class AIBrain:
    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        self.gemini_model = os.getenv("GEMINI_MODEL", "").strip() or "gemini-2.5-flash"
        self.groq_key = os.getenv("GROQ_API_KEY", "").strip()
        self.groq_model = os.getenv("GROQ_MODEL", "").strip() or "llama-3.1-8b-instant"
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.openrouter_model = (
            os.getenv("OPENROUTER_MODEL", "").strip() or "openai/gpt-4o-mini"
        )
        self.openrouter_site = os.getenv("OPENROUTER_SITE_URL", "").strip() or "http://localhost"
        self.openrouter_title = os.getenv("OPENROUTER_APP_NAME", "").strip() or "MYRA"

        self._gemini_client = None
        if self.gemini_key:
            self._gemini_client = genai.Client(api_key=self.gemini_key)

    def ask_ai(self, prompt):
        text = str(prompt).strip()
        if not text:
            return "AI error: empty prompt."

        providers = (
            self._ask_gemini,
            self._ask_groq,
            self._ask_openrouter,
        )

        last_error = ""
        for provider in providers:
            answer, error = provider(text)
            if answer:
                return answer
            if error:
                last_error = error

        if last_error:
            return f"AI service temporarily unavailable. {last_error}"
        return "AI service temporarily unavailable, please try again later."

    def _ask_gemini(self, prompt):
        if self._gemini_client is None:
            return "", "Gemini not configured."

        model_candidates = [self.gemini_model, "gemini-2.0-flash"]
        last_error = ""

        for model_name in model_candidates:
            if not model_name:
                continue
            try:
                response = self._gemini_client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                text = getattr(response, "text", None)
                if text:
                    return text, ""
                return "", "Gemini returned an empty response."
            except Exception as exc:
                message = str(exc)
                lowered = message.lower()
                if any(token in lowered for token in ("404", "not found", "unsupported", "model")):
                    last_error = message
                    continue
                return "", f"Gemini failed: {message}"

        return "", f"Gemini failed: {last_error or 'no valid model available.'}"

    def _ask_groq(self, prompt):
        if not self.groq_key:
            return "", "Groq not configured."

        payload = {
            "model": self.groq_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return "", f"Groq failed: {exc}"

        content = self._extract_chat_content(data)
        if content:
            return content, ""
        return "", "Groq returned an empty response."

    def _ask_openrouter(self, prompt):
        if not self.openrouter_key:
            return "", "OpenRouter not configured."

        payload = {
            "model": self.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "Authorization": f"Bearer {self.openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.openrouter_site,
            "X-Title": self.openrouter_title,
        }

        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=20,
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            return "", f"OpenRouter failed: {exc}"

        content = self._extract_chat_content(data)
        if content:
            return content, ""
        return "", "OpenRouter returned an empty response."

    def _extract_chat_content(self, payload):
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        return str(message.get("content") or "").strip()


_AI_BRAIN = AIBrain()


def ask_ai(prompt: str) -> str:
    return _AI_BRAIN.ask_ai(prompt)
