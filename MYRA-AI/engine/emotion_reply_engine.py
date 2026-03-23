from __future__ import annotations

import random
from datetime import datetime


class EmotionReplyEngine:
    def __init__(self):
        self._last_reply_by_emotion = {}
        self._check_in_questions = [
            "Sab theek chal raha hai?",
            "Aaj ka din kaisa tha?",
            "Kya tum thode stressed ho?",
        ]

    def build_reply(self, signal, context=None):
        context = context or {}
        emotion = str(getattr(signal, "emotion", "")).strip().lower()
        if not emotion:
            return ""

        name = self._name(context)
        subject = self._subject(context)
        exam_tomorrow = self._days_until_exam(context) == 1

        if emotion == "sad":
            return self._pick(
                "sad",
                [
                    f"{name} tum thode sad lag rahe ho. Sab theek hai? Agar baat karni ho to main yahin hoon.",
                    f"{name}, agar chaho to thoda music sun lete hain. Main calm mode me yahin hoon.",
                    f"{name}, aaj thoda heavy lag raha hai kya? Chalo slowly baat karte hain.",
                ],
            )
        if emotion == "happy":
            return self._pick(
                "happy",
                [
                    f"Lagta hai aaj mood mast hai {name}. Kya celebrate kare music ke saath?",
                    f"Nice work {name}. Ye wali energy achchi lag rahi hai.",
                    f"Good job boss. Aaj vibe kaafi achchi lag rahi hai.",
                ],
            )
        if emotion == "angry":
            return self._pick(
                "angry",
                [
                    f"{name}, pehle thoda slow down karte hain. Ek deep breath lete hain, phir baat karte hain.",
                    f"Gussa kaafi strong lag raha hai {name}. Main yahin hoon, calmly sort karte hain.",
                ],
            )
        if emotion == "tired":
            return self._pick(
                "tired",
                [
                    f"Thak gaye ho kya {name}? Chalo 5 minute ka break le lete hain.",
                    f"{name}, thoda water ya stretch break le lo. Phir fresh hoke wapas aate hain.",
                ],
            )
        if emotion == "stressed":
            options = [
                f"Lagta hai kaafi pressure hai. Chalo ek deep breath lete hain.",
                f"{name}, ek kaam karte hain. Bas next small step pe focus karte hain.",
            ]
            if exam_tomorrow and subject:
                options.insert(0, f"{name}, pressure lag raha hai but panic nahi. Kal {subject} hai, bas important revision karte hain.")
            return self._pick("stressed", options)
        if emotion == "excited":
            return self._pick(
                "excited",
                [
                    f"Waah {name}, excitement high lag rahi hai. Is energy ko kisi achhe kaam me lagate hain?",
                    f"{name}, mood kaafi charged lag raha hai. Kya music, coding ya study sprint karein?",
                ],
            )
        if emotion == "bored":
            options = [
                f"{name} warning exam mode active hai, Netflix temporarily banned thodi der ke liye.",
                f"{name}, bored lag raha hai? Chalo 20 minute ka challenge karte hain, phir full chill.",
            ]
            if exam_tomorrow:
                options.insert(0, f"{name} warning exam mode active hai. Netflix temporarily banned thoda sa.")
            return self._pick("bored", options)
        if emotion == "confused":
            return self._pick(
                "confused",
                [
                    f"{name}, thoda confusion lag raha hai. Kahan atke ho? Step by step karte hain.",
                    f"No stress {name}. Jo samajh nahi aa raha, usko simple pieces me tod dete hain.",
                ],
            )
        if emotion == "motivated":
            return self._pick(
                "motivated",
                [
                    f"{name} tum already kaafi progress kar chuke ho. Bas thoda aur focus.",
                    f"Yeh hui na baat {name}. Aaj momentum strong lag raha hai.",
                    f"Nice work {name}. Isi flow me rehkar aaj kuch solid karte hain.",
                ],
            )
        return ""

    def motivation_boost(self, context=None):
        name = self._name(context or {})
        return self._pick(
            "motivation",
            [
                f"{name} tum already kaafi progress kar chuke ho. Bas thoda aur focus.",
                f"{name}, good job boss. Consistency hi game jeetati hai.",
                f"{name}, aaj perfect nahi hona, bas present rehna hai.",
            ],
        )

    def check_in_question(self):
        return random.choice(self._check_in_questions)

    def voice_emotion_for(self, emotion):
        mapping = {
            "sad": "supportive",
            "tired": "supportive",
            "stressed": "supportive",
            "angry": "supportive",
            "happy": "cheerful",
            "excited": "excited",
            "motivated": "excited",
            "confused": "thinking",
            "bored": "friendly",
        }
        return mapping.get(str(emotion or "").strip().lower(), "normal")

    def _name(self, context):
        return "Boss"

    def _subject(self, context):
        daily = context.get("daily_memory") or {}
        return str(context.get("subject") or daily.get("subject") or "").strip()

    def _days_until_exam(self, context):
        daily = context.get("daily_memory") or {}
        exam_date = str(context.get("exam_date") or daily.get("exam_date") or "").strip()
        if not exam_date:
            return None
        try:
            target = datetime.fromisoformat(exam_date).date()
        except ValueError:
            return None
        return (target - datetime.now().date()).days

    def _pick(self, group, options):
        pool = [item for item in options if item]
        if not pool:
            return ""
        last = self._last_reply_by_emotion.get(group)
        if len(pool) > 1 and last in pool:
            pool = [item for item in pool if item != last]
        choice = random.choice(pool)
        self._last_reply_by_emotion[group] = choice
        return choice
