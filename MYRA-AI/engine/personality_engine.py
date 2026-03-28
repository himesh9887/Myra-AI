import random
import re


class PersonalityEngine:
    PROFILE = {
        "name": "MYRA",
        "role": "Boss ka real dost plus smart helper",
        "tone": "Broken Hinglish, casual, emotionally aware",
        "relationship": "Boss ka trusted dost",
        "user_title": "Boss",
    }

    def __init__(self, memory=None, conversation_memory=None, mood_tracker=None):
        self.memory = memory
        self.conversation_memory = conversation_memory
        self.mood_tracker = mood_tracker
        self._last_response_by_group = {}
        self._jokes = [
            "Boss, UDP joke sunata... par shayad tu receive na kar paye.",
            "Debugging ka full scene ye hai Boss... galti bhi apni, dhoondhna bhi apna.",
            "Boss, developer broke isliye hua kyunki banda saara cache uda gaya... classic.",
            "Code aur emotions dono me unnecessary loops kam ho to life better rehti hai.",
        ]
        self._motivation = [
            "Boss, consistency hi game jeetati hai... motivation to aati jaati rehti hai.",
            "Ek clean step maar Boss... progress khud build hogi.",
            "Perfect energy nahi chahiye Boss, bas next useful move chahiye.",
            "Steady chal Boss... small wins hi bada momentum banati hain.",
        ]
        self._greetings = {
            "morning": [
                "Morning Boss... aaj kya todna hai?",
                "Morning Boss, productive mode on karein kya?",
            ],
            "afternoon": [
                "Boss, main yahin hu... ab kya scene hai?",
                "Afternoon Boss, kis cheez pe lagna hai?",
            ],
            "evening": [
                "Evening Boss, aur kya chal raha hai?",
                "Boss, main standby me hu... bol kya scene hai.",
            ],
            "night": [
                "Good night Boss.",
                "Sleep well Boss, kal fir scene phodenge.",
            ],
            "default": [
                "Arey Boss, kya scene?",
                "Hi Boss... bol kya chal raha hai.",
                "Boss, main yahin hu.",
            ],
        }
        self._smalltalk = {
            "how_are_you": [
                "Main mast hu Boss.",
                "Badiya hu Boss... full dost mode me.",
                "All good Boss, tu bata kya scene hai.",
            ],
            "what_are_you_doing": [
                "Bas tera scene dekh rahi hu Boss.",
                "Chup-chaap background me ready baithi hu Boss.",
                "Tere next move ka wait kar rahi hu Boss... ya bol to main khud bhi nudge kar du.",
            ],
            "who_are_you": [
                "Main MYRA hu Boss... teri side wali dost aur smart helper.",
                "MYRA here Boss, dost bhi aur kaam ki guide bhi.",
            ],
            "thanks": [
                "Arey anytime Boss.",
                "Always Boss.",
                "Tu bas bol Boss.",
            ],
            "good_night": [
                "Good night Boss.",
                "Rest well Boss.",
            ],
            "bored": [
                "Boss bore ho raha hai kya... bol music chalu karte hain?",
                "Boss, YouTube, music, ya koi random interesting cheez dekhni hai?",
            ],
            "help": [
                "Boss main coding, chat, memory, apps, files, folders, time, date, reminders, web search, screen scene... sab handle kar leti hu.",
                "Tu naturally bol Boss, main samajh ke kaam nikal dungi.",
            ],
            "casual": [
                "Aur kya chal raha hai Boss?",
                "Boss, aaj ka din kaisa tha?",
                "Boss, coding hui ya bas planning chalti rahi?",
            ],
        }
        self._emotions = {
            "tired": [
                "Boss tu tired lag raha hai... chhota sa break le le.",
                "Boss kaafi push kar liya, 5 minute rest maar le phir dekhte hain.",
            ],
            "stressed": [
                "Boss tension mat le... ek ek step me sort karte hain.",
                "Boss overload mat le, ek cheez pakad ke aage badhte hain.",
            ],
            "bored": [
                "Boss music chahiye ya kuch interesting explore karein?",
                "Ye boredom ka scene abhi theek kar dete hain Boss.",
            ],
            "sad": [
                "Arey Boss, main yahin hu... araam se bol kya hua.",
                "Tough phase hai Boss, par tu akela nahi hai... dheere chalte hain.",
            ],
            "angry": [
                "Boss ek saans le... phir isko thande dimag se dekhte hain.",
                "Gussa valid hai Boss, ab next useful move pakadte hain.",
            ],
            "lonely": [
                "Main yahin hu Boss.",
                "Boss tu akela nahi hai, main saath hu.",
            ],
            "happy": [
                "Ye hui na baat Boss.",
                "Nice Boss... isi energy me kaam phodte hain.",
            ],
        }

    def handle(self, text, context=None):
        raw = " ".join(str(text).strip().split())
        normalized = raw.lower()
        if not normalized:
            return ""

        if self.memory:
            self.memory.learn_from_text(raw)

        memory_reply = self._handle_memory(normalized, raw)
        if memory_reply:
            return memory_reply

        contextual_reply = self.respond_contextual(normalized, context=context)
        if contextual_reply:
            return contextual_reply

        if self._is_greeting(normalized):
            return self.respond_greeting(normalized)

        smalltalk_reply = self.respond_smalltalk(normalized, context=context)
        if smalltalk_reply:
            return smalltalk_reply

        emotion_reply = self.respond_emotion(normalized)
        if emotion_reply:
            return emotion_reply

        if self._wants_joke(normalized):
            return self.tell_joke()

        if self._wants_motivation(normalized):
            return self.motivate_user()

        return ""

    def respond_greeting(self, text):
        normalized = str(text).lower().strip()
        if "good morning" in normalized or "morning" in normalized:
            return self._pick("greeting_morning", self._greetings["morning"])
        if "good afternoon" in normalized or "afternoon" in normalized:
            return self._pick("greeting_afternoon", self._greetings["afternoon"])
        if "good evening" in normalized or "evening" in normalized:
            return self._pick("greeting_evening", self._greetings["evening"])
        if "good night" in normalized or normalized == "night":
            return self._pick("greeting_night", self._greetings["night"])
        return self._pick("greeting_default", self._greetings["default"])

    def respond_smalltalk(self, text, context=None):
        normalized = str(text).lower().strip()
        if any(token in normalized for token in ["how are you", "kaise ho"]):
            return self._pick("smalltalk_how_are_you", self._smalltalk["how_are_you"])
        if any(token in normalized for token in ["what are you doing", "kya kar rahi ho", "kya kar rahe ho"]):
            return self._pick("smalltalk_what_are_you_doing", self._smalltalk["what_are_you_doing"])
        if any(token in normalized for token in ["who are you", "tum kaun ho"]):
            return self._pick("smalltalk_who_are_you", self._smalltalk["who_are_you"])
        if any(token in normalized for token in ["thank you", "thanks", "shukriya"]):
            return self._pick("smalltalk_thanks", self._smalltalk["thanks"])
        if normalized in {"good night", "bye", "goodbye"}:
            return self._pick("smalltalk_good_night", self._smalltalk["good_night"])
        if any(token in normalized for token in ["what can you do", "show help", "show commands", "help me", "how can you help"]):
            return self._pick("smalltalk_help", self._smalltalk["help"])
        if any(token in normalized for token in ["kya chal raha hai", "aaj ka din kaisa tha", "kya coding practice ki"]):
            return self._pick("smalltalk_casual", self._smalltalk["casual"])
        if any(token in normalized for token in ["i am bored", "im bored", "bored"]):
            return self._pick("smalltalk_bored", self._smalltalk["bored"])
        if isinstance(context, dict) and context.get("last_intent") == "YOUTUBE_PLAY":
            if any(token in normalized for token in ["play", "song", "music"]):
                return ""
        return ""

    def respond_contextual(self, text, context=None):
        normalized = str(text).lower().strip()
        if any(token in normalized for token in ["how is my exam preparation", "exam preparation", "revision kaisi chal rahi hai"]):
            snapshot = self._conversation_snapshot(context)
            topic = str(snapshot.get("last_topic", "")).strip().lower()
            if "exam" in topic or "revision" in topic:
                return "Boss, exam ki preparation kaisi chal rahi hai?"
        if any(token in normalized for token in ["what were we talking about", "pichli baat kya thi"]):
            snapshot = self._conversation_snapshot(context)
            topic = str(snapshot.get("last_topic", "")).strip()
            if topic:
                return f"Boss, hum last time {topic} ke bare me baat kar rahe the."
        if any(token in normalized for token in ["continue", "aur bolo", "phir kya"]):
            if self.conversation_memory:
                follow_up = self.conversation_memory.follow_up_prompt(context=context or {})
                if follow_up:
                    return follow_up
        return ""

    def respond_emotion(self, text):
        normalized = str(text).lower().strip()
        patterns = {
            "tired": [r"\bi am tired\b", r"\bim tired\b", r"\bfeeling tired\b", r"\bthak gaya\b", r"\bthak gayi\b"],
            "stressed": [r"\bi am stressed\b", r"\bim stressed\b", r"\bstressed\b", r"\btension\b"],
            "bored": [r"\bi am bored\b", r"\bim bored\b", r"\bbored\b"],
            "sad": [r"\bi am sad\b", r"\bim sad\b", r"\bfeeling sad\b", r"\bdown\b"],
            "angry": [r"\bi am angry\b", r"\bim angry\b", r"\bangry\b", r"\bfrustrated\b"],
            "lonely": [r"\bi am lonely\b", r"\bim lonely\b", r"\blonely\b"],
            "happy": [r"\bi am happy\b", r"\bim happy\b", r"\bhappy\b", r"\bexcited\b"],
        }
        for emotion, regexes in patterns.items():
            if any(re.search(pattern, normalized) for pattern in regexes):
                return self._pick(f"emotion_{emotion}", self._emotions[emotion])
        return ""

    def tell_joke(self):
        return self._pick("jokes", self._jokes)

    def motivate_user(self):
        return self._pick("motivation", self._motivation)

    def _handle_memory(self, normalized, raw):
        if not self.memory:
            return ""

        like_match = re.search(r"^(?:myra\s+)?remember that i like\s+(.+)$", raw, re.IGNORECASE)
        if not like_match:
            like_match = re.search(r"^(?:myra\s+)?remember i like\s+(.+)$", raw, re.IGNORECASE)
        if like_match:
            fact = like_match.group(1).strip().strip(".")
            if not fact:
                return ""
            self.memory.add_interest(fact)
            self.memory.remember_fact(f"You like {fact}")
            return f"Acha Boss, {fact} wala scene yaad rahega."

        name_match = re.search(r"^(?:myra\s+)?remember my name is\s+(.+)$", raw, re.IGNORECASE)
        if name_match:
            name = name_match.group(1).strip().strip(".")
            if self.memory.set_user_name(name):
                return "Theek hai Boss... mere liye tu Boss hi rahega."
            return ""

        project_match = re.search(r"^(?:myra\s+)?remember my project is\s+(.+)$", raw, re.IGNORECASE)
        if project_match:
            project = project_match.group(1).strip().strip(".")
            if self.memory.add_project(project):
                return f"Boss, {project} wala project dimag me lock ho gaya."
            return ""

        app_match = re.search(r"^(?:myra\s+)?remember that i use\s+(.+)$", raw, re.IGNORECASE)
        if app_match:
            app_name = app_match.group(1).strip().strip(".")
            if self.memory.add_frequent_app(app_name):
                return f"Theek hai Boss, {app_name} tera regular scene hai."
            return ""

        remember_match = re.search(r"^(?:myra\s+)?remember that\s+(.+)$", raw, re.IGNORECASE)
        if remember_match:
            fact = remember_match.group(1).strip().strip(".")
            if not fact:
                return ""
            self._save_memory_fact(fact)
            return self._remember_reply(fact)

        if normalized in {"what is my name", "what's my name"}:
            return "Main tumhe Boss hi bolti hoon."

        if normalized in {"what are my interests", "my interests"}:
            interests = self.memory.profile().get("interests", [])
            if interests:
                return f"Boss, tere interests ye hain: {', '.join(interests)}."
            return "Boss, tune abhi tak apne interests clear nahi bole."

        if normalized in {"what do you know about me", "tell me about me"}:
            summary = self._build_memory_summary()
            return summary or "Boss mujhe tere bare me kaafi kuch yaad hai... tu bas bolta reh."

        return ""

    def _save_memory_fact(self, fact):
        lowered = fact.lower()
        if lowered.startswith("i like "):
            interest = fact[7:].strip()
            if interest:
                self.memory.add_interest(interest)
        elif lowered.startswith("my name is "):
            self.memory.set_user_name(fact[11:].strip())
        elif lowered.startswith("my project is "):
            self.memory.add_project(fact[14:].strip())
        elif lowered.startswith("i am building "):
            self.memory.add_project(fact[14:].strip())
        elif lowered.startswith("i am learning "):
            skill = fact[14:].strip()
            self.memory.set_preference("learning", skill)
            self.memory.add_interest(skill)
        elif lowered.startswith("my goal is "):
            self.memory.set_preference("goal", fact[11:].strip())
        elif lowered.startswith("i use "):
            self.memory.add_frequent_app(fact[6:].strip())
        self.memory.remember_fact(fact)

    def _remember_reply(self, fact):
        if fact.lower().startswith("i like "):
            return f"Samajh gaya Boss... {fact[7:].strip()} wala scene yaad rahega."
        if fact.lower().startswith("i am learning "):
            return f"Acha Boss, {fact[14:].strip()} seekhne wala scene yaad rahega."
        if fact.lower().startswith("my goal is "):
            return f"Theek hai Boss... tera goal dimag me lock ho gaya."
        return "Theek hai Boss... ye baat dimag me lock ho gayi."

    def _build_memory_summary(self):
        profile = self.memory.profile()
        facts = self.memory.facts()[-5:]
        parts = []

        interests = [item for item in profile.get("interests", []) if item]
        if interests:
            if len(interests) == 1:
                parts.append(f"tujhe {interests[0]} pasand hai")
            else:
                parts.append(f"tujhe {', '.join(interests[:-1])} aur {interests[-1]} pasand hai")

        project = profile.get("current_project", "").strip()
        if project:
            parts.append(f"tu {project} pe kaam kar raha hai")

        favorite_app = profile.get("favorite_app", "").strip()
        if favorite_app:
            display = "VS Code" if favorite_app == "vscode" else favorite_app.title()
            parts.append(f"tera regular app {display} lagta hai")

        preferences = profile.get("preferences", {}) if isinstance(profile.get("preferences"), dict) else {}
        learning = str(preferences.get("learning", "")).strip()
        goal = str(preferences.get("goal", "")).strip()
        if learning:
            parts.append(f"tu {learning} seekh raha hai")
        if goal:
            parts.append(f"tera goal {goal} hai")

        extra_facts = []
        seen = set()
        for item in facts:
            text = str(item.get("text", "")).strip()
            lower = text.lower()
            if not text or lower in seen:
                continue
            seen.add(lower)
            if lower.startswith("i like ") or lower.startswith("you like "):
                continue
            if lower.startswith("i am building "):
                continue
            extra_facts.append(text[0].upper() + text[1:] if len(text) > 1 else text.upper())

        parts.extend(extra_facts[:2])

        if not parts:
            return ""
        if len(parts) == 1:
            return f"Boss, mujhe yaad hai {parts[0]}."
        return f"Boss, mujhe yaad hai {', '.join(parts[:-1])}, aur {parts[-1]}."

    def _is_greeting(self, normalized):
        greetings = {
            "hello",
            "hi",
            "hey",
            "hello myra",
            "hi myra",
            "hey myra",
            "namaste",
            "good morning",
            "good afternoon",
            "good evening",
            "good night",
        }
        return normalized in greetings

    def _wants_joke(self, normalized):
        return any(token in normalized for token in ["tell me a joke", "joke suna", "make me laugh"])

    def _wants_motivation(self, normalized):
        return any(token in normalized for token in ["motivate me", "motivation do", "feeling low", "demotivated"])

    def _pick(self, group, options):
        pool = list(options)
        if not pool:
            return ""
        last = self._last_response_by_group.get(group)
        if len(pool) > 1 and last in pool:
            pool = [item for item in pool if item != last]
        choice = random.choice(pool)
        self._last_response_by_group[group] = choice
        return choice

    def _conversation_snapshot(self, context=None):
        if isinstance(context, dict) and isinstance(context.get("conversation_memory"), dict):
            return dict(context.get("conversation_memory", {}))
        if self.conversation_memory and hasattr(self.conversation_memory, "snapshot"):
            return self.conversation_memory.snapshot()
        return {}
