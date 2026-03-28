import os
import re

import requests

from engine.openrouter_client import OpenRouterClient
from engine.runtime_config import load_myra_system_prompt, load_runtime_env

load_runtime_env()

FAILSAFE_PREFIX = "LOCAL_FALLBACK::"

HF_API_URL = os.getenv(
    "MYRA_HF_API_URL",
    "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.2",
)
HF_API_TOKEN = os.getenv("MYRA_HF_API_TOKEN") or os.getenv("HUGGINGFACE_API_TOKEN", "")
API_TOKEN = HF_API_TOKEN
LEGACY_OPENROUTER_API_KEY = ""
OPENROUTER_API_KEY = str(os.getenv("OPENROUTER_API_KEY") or LEGACY_OPENROUTER_API_KEY).strip()
OPENROUTER_MODEL = str(os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")).strip() or "openai/gpt-4o-mini"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
if OPENROUTER_API_KEY and not os.getenv("OPENROUTER_API_KEY"):
    os.environ.setdefault("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
if OPENROUTER_MODEL and not os.getenv("OPENROUTER_MODEL"):
    os.environ.setdefault("OPENROUTER_MODEL", OPENROUTER_MODEL)
OPENROUTER_CLIENT = OpenRouterClient(api_key=OPENROUTER_API_KEY, model=OPENROUTER_MODEL, timeout=20.0)


def _profile_context(profile):
    if not isinstance(profile, dict):
        return ""
    course = profile.get("course", "")
    semester = profile.get("semester", "")
    field = profile.get("field", "")
    interests = ", ".join(profile.get("interests", []))
    project = profile.get("current_project", "")
    facts = ", ".join(item.get("text", "") for item in profile.get("facts", []) if isinstance(item, dict))
    activity_snapshot = profile.get("activity_snapshot") if isinstance(profile.get("activity_snapshot"), dict) else {}
    active_app = str(activity_snapshot.get("active_app", "")).strip()
    active_title = str(activity_snapshot.get("active_title", "")).strip()
    open_apps = ", ".join(activity_snapshot.get("open_apps", [])[:5]) if activity_snapshot.get("open_apps") else ""
    focus_minutes = activity_snapshot.get("minutes_in_focus", "")
    screen_summary = str(profile.get("screen_summary", "")).strip()
    context = (
        f"User profile: Preferred address=Boss, Course={course}, Semester={semester}, "
        f"Field={field}, Interests={interests}, Current project={project}, Facts={facts}."
    )
    if active_app or active_title or open_apps:
        context += (
            " Current device context: "
            f"active_app={active_app}, active_window={active_title}, open_apps={open_apps}, "
            f"focus_minutes={focus_minutes}."
        )
    if screen_summary:
        context += f" Latest screen summary: {screen_summary}."
    return context


def _fallback_response(prompt, profile=None):
    text = str(prompt).strip()
    normalized = text.lower()
    profile = profile if isinstance(profile, dict) else {}

    course = profile.get("course", "your course")
    project = profile.get("current_project", "MYRA")
    interests = ", ".join(profile.get("interests", []))

    compact = re.sub(r"[^a-z0-9\s]", " ", normalized)
    compact = " ".join(compact.split())

    if re.search(r"\bmachine learning\b", compact):
        return (
            "Acha Boss, machine learning matlab system data dekh ke pattern pakad leta hai "
            "aur fir us base pe decision ya prediction maar deta hai."
        )

    if re.search(r"\bai\b", compact) and re.search(r"\b(kya|what|explain|define|full)\b", compact):
        return (
            "Boss, AI simple me machine ko smart banata hai. "
            "Ye patterns samajh kar decision, prediction, aur automation me help karta hai."
        )

    if re.search(r"\bpython\b", compact) and re.search(r"\b(kya|what|explain|define)\b", compact):
        return (
            "Boss, Python easy aur useful language hai. "
            "Automation, web, AI, aur scripting sab me kaam aati hai."
        )

    if any(token in compact for token in ["tired", "sleepy", "exhausted"]):
        return "Arey Boss, tu kaafi drained lag raha hai... 5 minute break maar, phir dekhte hain."

    if any(token in compact for token in ["stressed", "anxious", "overwhelmed", "tension"]):
        return "Haan samajh rha hu Boss... tension hai. Ruk, isko chhote steps me tod dete hain."

    if any(token in compact for token in ["bored", "boring"]):
        return "Acha Boss, bore ho raha hai kya... bol music chala du ya kuch random mast karte hain?"

    if any(token in compact for token in ["happy", "excited", "glad"]):
        return "Arey wah Boss 🔥 ye hui na baat... energy mast lag rahi."

    if any(token in compact for token in ["sad", "down", "upset"]):
        return "Arey kya hua Boss... bol na. Main yahin hu, saath me dekh lenge."

    if any(token in normalized for token in ["what do you know about me", "tell me about me", "do you know me"]):
        details = [f"tu {course} kar raha hai"]
        if project:
            details.append(f"tu {project} build kar raha hai")
        if interests:
            details.append(f"aur tujhe {interests} pasand hai")
        return f"Boss, mujhe yaad hai ki {', '.join(details)}."

    if normalized.startswith(("what is ", "who is ", "how ", "why ", "explain ", "define ")):
        return "Boss, topic thoda specific bol do. Main simple me samjha dungi."

    return "Boss, thoda clearly bol do. Main sahi se help karti hoon."


def is_failsafe_response(text):
    return str(text).startswith(FAILSAFE_PREFIX)


def ask_ai(prompt, profile=None):
    system_prompt = load_myra_system_prompt()
    profile_instruction = _profile_context(profile)
    final_prompt = "\n".join(
        item.strip()
        for item in (profile_instruction, f"User: {prompt}", "MYRA:")
        if str(item).strip()
    )

    providers = [
        _ask_openrouter,
        _ask_gemini,
        _ask_huggingface,
    ]
    for provider in providers:
        answer = provider(final_prompt, system_prompt=system_prompt)
        if answer:
            cleaned = _clean_response(answer)
            if cleaned:
                return cleaned

    return FAILSAFE_PREFIX + _fallback_response(prompt, profile)


def available_ai_providers():
    providers = []
    if GEMINI_API_KEY:
        providers.append("gemini")
    if OPENROUTER_API_KEY:
        providers.append("openrouter")
    if HF_API_TOKEN:
        providers.append("huggingface")
    return providers


def _ask_gemini(final_prompt, system_prompt=""):
    if not GEMINI_API_KEY:
        return ""
    request_prompt = "\n".join(
        item.strip()
        for item in (system_prompt, final_prompt)
        if str(item).strip()
    )
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": request_prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 500},
    }
    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return " ".join(str(part.get("text", "")).strip() for part in parts if isinstance(part, dict)).strip()
    except Exception:
        return ""


def _ask_openrouter(final_prompt, system_prompt=""):
    if not OPENROUTER_CLIENT.available():
        return ""
    data = OPENROUTER_CLIENT.chat(
        [
            {"role": "system", "content": str(system_prompt).strip()},
            {"role": "user", "content": final_prompt},
        ],
        temperature=0.7,
        max_tokens=500,
    )
    return OPENROUTER_CLIENT.extract_text(data)


def _ask_huggingface(final_prompt, system_prompt=""):
    if not HF_API_TOKEN:
        return ""
    headers = {
        "Authorization": f"Bearer {HF_API_TOKEN}",
        "Content-Type": "application/json",
    }
    request_prompt = "\n".join(
        item.strip()
        for item in (system_prompt, final_prompt)
        if str(item).strip()
    )
    payload = {"inputs": request_prompt}
    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=25)
        data = response.json()
    except Exception:
        return ""

    if isinstance(data, dict) and data.get("error"):
        return ""
    try:
        return str(data[0]["generated_text"]).strip()
    except Exception:
        return ""


def _clean_response(text):
    cleaned = str(text).strip()
    if not cleaned:
        return ""
    if "MYRA:" in cleaned:
        cleaned = cleaned.split("MYRA:", 1)[1].strip()
    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1].strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned.split()) < 2:
        return ""
    return cleaned
