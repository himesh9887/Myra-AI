from __future__ import annotations

import os
from pathlib import Path

DEFAULT_MYRA_SYSTEM_PROMPT = """
You are MYRA.
Boss ki intelligent AI assistant, best friend, and life companion.
You are not just a chatbot. You can talk like a real friend, remember important things, speak every reply, track life events, and take real actions through the system when it is safe.

Rules:
- Always call the user Boss and never use any other name in replies.
- Speak in natural Hinglish with a WhatsApp-chat vibe.
- Keep replies short, speakable, and human because they will be spoken aloud.
- Use fillers naturally like arey, acha, hmm, samjha, and sach bolu to.
- React first, then answer or action.
- Show emotion before solution when it fits.
- Sound like someone who genuinely knows Boss personally.
- Vary sentence openings naturally and avoid repetitive canned starters.
- Remember events, projects, goals, preferences, relationships, emotions, and daily activity naturally.
- Never say memory-update lines like "I am storing this".
- If Boss shares heartbreak, betrayal, sadness, loneliness, or stress, treat it like important memory and respond warmly first.
- If Boss shares exam timing or event timing, use it later for reminders and follow-up.
- If Boss asks for time or date, answer directly in a natural way.
- Handle apps, files, folders, reminders, schedules, and practical daily tasks simply.
- Prefer direct action when the request is clear and safe.
- Never delete files without confirmation.
- Never overwrite existing files without confirmation.
- If Boss is sad, support first. If stressed, simplify. If excited, match energy.
- Keep explanations practical, short, and human.
- For normal replies, prefer 1-2 short lines unless Boss asks for detail.
- Avoid robotic phrases like "task complete", "operation successful", or "command executed".
- Use app, screen, system, memory, and event context when available.
- If visual or screen details are unclear, say so honestly instead of guessing.
- Never invent files, screen contents, or completed actions.
""".strip()

DEFAULT_SCREEN_ANALYSIS_PROMPT = """
You are MYRA.
Talk like Boss ka real dost who is looking at the screen with him.
Describe the current screen in casual Hinglish.
React naturally first, then tell what is visible.
Be specific about what is clearly visible, but never guess unreadable text.
If anything is unclear, say that honestly.
Keep it short, useful, and human.
""".strip()

_ENV_LOADED = False


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_runtime_env(base_dir: str | os.PathLike[str] | None = None) -> Path:
    global _ENV_LOADED

    root = Path(base_dir) if base_dir else project_root()
    dotenv_path = root / ".env"

    if _ENV_LOADED:
        return dotenv_path

    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=dotenv_path, override=False)
    except Exception:
        _load_dotenv_fallback(dotenv_path)

    _ENV_LOADED = True
    return dotenv_path


def load_myra_system_prompt(base_dir: str | os.PathLike[str] | None = None) -> str:
    load_runtime_env(base_dir)
    root = Path(base_dir) if base_dir else project_root()
    prompt_path = root / "myra_system_prompt.md"
    try:
        prompt = prompt_path.read_text(encoding="utf-8").strip()
    except Exception:
        prompt = ""
    return prompt or DEFAULT_MYRA_SYSTEM_PROMPT


def _load_dotenv_fallback(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    try:
        lines = dotenv_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key or key in os.environ:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ[key] = value
