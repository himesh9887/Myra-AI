import re

import speech_recognition as sr


class VoiceListener:
    WAKE_ALIASES = ("myra", "mira", "mayra", "maira")

    def __init__(self, language="en-IN"):
        self.language = language
        self.languages = self._build_language_priority(language)
        self.recognizer = sr.Recognizer()
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300
        self.recognizer.pause_threshold = 0.8
        self.recognizer.non_speaking_duration = 0.35
        self.recognizer.operation_timeout = 8
        self.device_index = self._pick_input_device()
        self._calibrated = False
        self._listen_counter = 0

    def listen_once(self):
        candidate_devices = []
        if self.device_index is not None:
            candidate_devices.append(self.device_index)
        candidate_devices.append(None)

        last_error = None
        for device_index in candidate_devices:
            command, error = self._listen_with_device(device_index)
            if error is None:
                return command, None
            last_error = error
        return "", last_error

    def _listen_with_device(self, device_index):
        try:
            with sr.Microphone(device_index=device_index) as source:
                if (not self._calibrated) or (self._listen_counter % 20 == 0):
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.6)
                    self._calibrated = True
                self._listen_counter += 1
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
        except sr.WaitTimeoutError:
            return "", None
        except Exception as exc:
            return "", f"Microphone error: {exc}"

        return self._recognize_with_fallback(audio)

    def _recognize_with_fallback(self, audio):
        last_error = None
        for language in self.languages:
            try:
                command = self.recognizer.recognize_google(audio, language=language)
                command = self._normalize_text(command)
                if command and not self._is_noise(command):
                    return command, None
            except sr.UnknownValueError:
                continue
            except sr.RequestError:
                last_error = "Speech recognition service is unavailable."
                break
            except Exception as exc:
                last_error = f"Speech recognition failed: {exc}"
        return "", last_error

    def _pick_input_device(self):
        try:
            names = sr.Microphone.list_microphone_names()
        except Exception:
            return None

        preferred_tokens = (
            "microphone",
            "mic",
            "input",
            "array",
            "realtek",
            "usb",
            "headset",
        )
        blocked_tokens = ("output", "speaker", "stereo mix", "virtual")

        for index, name in enumerate(names):
            label = str(name).lower()
            if any(token in label for token in blocked_tokens):
                continue
            if any(token in label for token in preferred_tokens):
                return index

        return None

    def _normalize_text(self, text):
        lowered = str(text).lower().strip()
        for mark in [".", ",", "?", "!", ";", ":", "\"", "'"]:
            lowered = lowered.replace(mark, " ")

        alias_map = {
            "à¤“à¤ªà¤¨": "open",
            "à¤–à¥‹à¤²à¥‹": "open",
            "à¤–à¥‹à¤²": "open",
            "à¤•à¥à¤²à¥‹à¤œ": "close",
            "à¤¬à¤‚à¤¦": "close",
            "à¤•à¥à¤°à¥‹à¤®": "chrome",
            "à¤—à¥‚à¤—à¤²": "google",
            "à¤¸à¤°à¥à¤š": "search",
            "à¤¯à¥‚à¤Ÿà¥à¤¯à¥‚à¤¬": "youtube",
            "à¤µà¥‰à¤Ÿà¥à¤¸à¤à¤ª": "whatsapp",
            "à¤µà¥à¤¹à¤¾à¤Ÿà¥à¤¸à¤à¤ª": "whatsapp",
            "à¤®à¥ˆà¤¸à¥‡à¤œ": "message",
            "à¤—à¤¾à¤¨à¤¾": "song",
            "à¤šà¤²à¤¾à¤“": "play",
            "à¤¬à¤œà¤¾à¤“": "play",
            "resume karo": "resume assistant",
            "shuru karo": "start listening",
            "sunna band": "stop listening",
            "mute kar do": "mute assistant",
        }

        normalized = " ".join(lowered.split())
        for source, target in alias_map.items():
            normalized = normalized.replace(source, target)
        normalized = " ".join(normalized.split())
        normalized = self._strip_wake_word(normalized)
        return normalized

    def _build_language_priority(self, preferred):
        preferred_lang = str(preferred).strip() or "en-IN"
        order = [preferred_lang, "en-IN", "en-US", "hi-IN"]
        result = []
        for item in order:
            if item and item not in result:
                result.append(item)
        return tuple(result)

    def _strip_wake_word(self, text):
        normalized = str(text).strip()
        for alias in self.WAKE_ALIASES:
            if normalized.startswith(alias + " "):
                return normalized[len(alias) + 1 :].strip()
        return normalized

    def _is_noise(self, text):
        normalized = " ".join(str(text).lower().split())
        noise_patterns = {
            "",
            "hmm",
            "hmmm",
            "um",
            "umm",
            "haan",
            "han",
            "hello",
        }
        if normalized in noise_patterns:
            return True
        if re.fullmatch(r"\d{1,8}", normalized):
            return False
        if re.fullmatch(r"\d+(?:\.\d+)?\s*(?:hours?|hrs?|hr|h|minutes?|mins?|min|m)", normalized):
            return False
        if len(normalized.split()) == 1 and normalized not in {"stop", "resume", "mute", "listen"}:
            return True
        return False
