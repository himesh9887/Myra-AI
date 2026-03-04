import speech_recognition as sr


class VoiceListener:
    WAKE_WORD_ALIASES = (
        "myra",
        "mira",
        "mera",
        "mayra",
        "maira",
        "miara",
        "nayara",
        "nyara",
        "niyara",
        "niara",
    )

    def __init__(self, language="en-US"):
        self.language = language
        self.recognizer = sr.Recognizer()
        self.device_index = self._pick_input_device()

    def listen_once(self):
        try:
            with sr.Microphone(device_index=self.device_index) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
        except sr.WaitTimeoutError:
            return "", None
        except Exception as exc:
            return "", f"Microphone error: {exc}"

        try:
            command = self.recognizer.recognize_google(audio, language=self.language)
            return command.strip(), None
        except sr.UnknownValueError:
            return "", None
        except sr.RequestError:
            return "", "Speech recognition service is unavailable."
        except Exception as exc:
            return "", f"Speech recognition failed: {exc}"

    def _pick_input_device(self):
        try:
            names = sr.Microphone.list_microphone_names()
        except Exception:
            return None

        preferred_tokens = ("microphone", "mic", "input", "array")
        blocked_tokens = ("output", "speaker", "headphone")

        for index, name in enumerate(names):
            label = str(name).lower()
            if any(token in label for token in blocked_tokens):
                continue
            if any(token in label for token in preferred_tokens):
                return index

        return None

    def heard_wake_word(self, text):
        spoken = str(text).lower().strip()
        if not spoken:
            return False
        return any(alias in spoken.split() for alias in self.WAKE_WORD_ALIASES)
