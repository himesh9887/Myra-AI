from __future__ import annotations

import re


class LocalBrain:
    def __init__(self, memory=None):
        self.memory = memory

    @property
    def name(self) -> str:
        return "local"

    def available(self) -> bool:
        return True

    def ask(self, prompt: str, system_prompt: str = "", context: str = "", profile: dict | None = None) -> str:
        text = " ".join(str(prompt).strip().split())
        normalized = text.lower()
        profile = profile if isinstance(profile, dict) else {}

        course = profile.get("course") or "your course"
        semester = profile.get("semester") or ""
        field = profile.get("field") or "your field"
        project = profile.get("current_project") or "MYRA"
        interests = ", ".join(profile.get("interests", []))

        if normalized in {"hi", "hello", "hey", "hello myra", "hey myra"}:
            return "Arey Boss, kya scene?"
        if normalized in {"how are you", "how are you myra"}:
            return "Haan mast hu Boss... tu bata, aaj coding mode me hai ya chill mode?"
        if normalized in {"what are you doing", "what are you doing myra"}:
            return "Hmm bas yahin hu Boss... tera scene dekh raha hu."

        if any(token in normalized for token in ["tired", "sleepy", "exhausted", "drained"]):
            return "Arey Boss, tu kaafi tired lag raha hai... chhota break maar le, fir dekhte hain."
        if any(token in normalized for token in ["stressed", "anxious", "overwhelmed"]):
            return "Haan samajh rha hu Boss... scene thoda tight hai. Ruk isko simple steps me todte hain."
        if any(token in normalized for token in ["bored", "boring"]):
            return "Achaaa Boss, bore ho raha hai? Bol na... music chala du ya kuch mast nikaale?"
        if any(token in normalized for token in ["happy", "excited", "glad"]):
            return "Arey wah Boss 🔥 ye hui na baat... energy mast lag rahi."
        if any(token in normalized for token in ["sad", "down", "upset"]):
            return "Arey kya hua Boss... sab theek? bol na, saath me dekhte hain."

        if normalized in {"what is my name", "what's my name"}:
            return "Tu mere liye hamesha Boss hi hai."
        if normalized in {"what am i studying", "what is my course"}:
            semester_text = f" in {semester} semester" if semester else ""
            return f"Hmm Boss, tu {course}{semester_text} kar raha hai."
        if normalized in {"what is my field", "my field"}:
            return f"Boss, tera field {field} hai... yaad hai mujhe."
        if normalized in {"what is my current project", "my current project"}:
            return f"Boss tu abhi {project} build kar raha hai na... wahi scene chal raha."
        if normalized in {"what are my interests", "my interests"} and interests:
            return f"Boss, tujhe {interests} wala scene pasand hai."

        if re.search(r"\b(ai|artificial intelligence)\b", normalized) and re.search(
            r"\bwhat|explain|define|kya\b",
            normalized,
        ):
            return (
                "Acha sun Boss... AI ka matlab simple me ye hai ki machine thodi smart ho jaye, "
                "patterns samjhe aur kaam thoda human jaisa handle kare."
            )

        if re.search(r"\bpython\b", normalized) and re.search(r"\bwhat|explain|define|kya\b", normalized):
            return (
                "Hmm Boss, Python ek easy aur kaafi useful language hai... "
                "automation, web, AI, scripting sab me kaam aati hai."
            )

        if normalized.startswith(("what is ", "who is ", "how ", "why ", "explain ", "define ")):
            return (
                "Haan Boss, ruk simple me samjhata hu... bas topic thoda specific bol de."
            )

        return (
            "Hmm Boss, scene samajh aa raha hai... bas thoda aur seedha bol, fir sahi se batata hu."
        )
