from __future__ import annotations

import hashlib
import os
import queue
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import requests

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "hide")

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*args, **kwargs):
        return False


pygame = None

try:
    import pyttsx3
except Exception:  # pragma: no cover
    pyttsx3 = None

try:
    import pythoncom
except Exception:  # pragma: no cover
    pythoncom = None


@dataclass(frozen=True)
class PreparedSpeech:
    raw_text: str
    display_text: str
    spoken_text: str
    intent: str
    emotion: str


class HumanSpeechFormatter:
    def __init__(self, model_id):
        self.model_id = str(model_id or "").strip().lower()
        self._last_template_by_intent = {}
        self._templates = {
            "app_open": [
                "Alright Boss... opening {target} now.",
                "Sure Boss, launching {target}.",
                "Got it Boss, opening {target}.",
            ],
            "app_close": [
                "Alright Boss... closing {target}.",
                "Got it Boss, shutting {target} down.",
                "On it Boss, closing {target}.",
            ],
            "web_search": [
                "Give me a second Boss... checking that online.",
                "Searching that for you Boss.",
                "On it Boss... looking that up now.",
            ],
            "media_play": [
                "Nice choice Boss... playing {target} now.",
                "On it Boss, starting {target}.",
                "Got it Boss... playing {target}.",
            ],
            "listen_on": [
                "Alright Boss... I'm listening.",
                "Listening now Boss.",
                "Got it Boss, voice mode is live.",
            ],
            "listen_off": [
                "Alright Boss... I'll stay quiet for now.",
                "Okay Boss, listening is paused.",
                "Got it Boss, mic watch is off.",
            ],
            "error": [
                "Something went wrong Boss.",
                "Let me try that again Boss.",
                "Hmm... that did not go through Boss.",
            ],
            "working": [
                "Working on it Boss.",
                "Alright Boss... on it.",
                "Got it Boss.",
            ],
        }

    def prepare(self, text):
        cleaned = self._clean_text(text)
        if not cleaned:
            return PreparedSpeech("", "", "", "generic", "normal")

        intent, emotion = self._classify(cleaned)
        if self._should_rewrite(cleaned, intent):
            display_text = self._rewrite(cleaned, intent)
        else:
            display_text = self._polish_existing(cleaned, emotion)
        spoken_text = self._build_spoken_text(display_text, emotion)
        return PreparedSpeech(
            raw_text=cleaned,
            display_text=display_text,
            spoken_text=spoken_text,
            intent=intent,
            emotion=emotion,
        )

    def _classify(self, text):
        normalized = text.lower()
        if self._is_error(normalized):
            return "error", "error"
        if self._looks_supportive(normalized):
            return "generic", "supportive"
        if self._looks_cheerful(normalized):
            return "generic", "cheerful"
        if self._looks_like_greeting_reply(normalized):
            return "generic", "friendly"
        if self._is_listening_on(normalized):
            return "listen_on", "friendly"
        if self._is_listening_off(normalized):
            return "listen_off", "normal"
        if self._looks_like_web_search(normalized):
            return "web_search", "thinking"
        if self._looks_like_media(normalized):
            return "media_play", "excited"
        if self._looks_like_app_open(normalized):
            return "app_open", "friendly"
        if self._looks_like_app_close(normalized):
            return "app_close", "normal"
        if any(token in normalized for token in ["checking", "thinking", "processing", "working"]):
            return "working", "thinking"
        return "generic", "normal"

    def _should_rewrite(self, text, intent):
        if intent in {"app_open", "app_close", "web_search", "media_play", "listen_on", "listen_off"}:
            return True
        word_count = len(text.split())
        if intent == "error":
            return word_count <= 6
        robotic_patterns = [
            r"\bcommand executed\b",
            r"\bexecute ho gaya\b",
            r"\bopened in browser\b",
            r"\bopening application\b",
            r"\bclose command\b",
            r"\btoggle complete\b",
        ]
        return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in robotic_patterns)

    def _rewrite(self, text, intent):
        subject = self._extract_subject(text, intent)
        template = self._pick_template(intent, text)
        if "{target}" in template:
            target = subject or "it"
            target = self._display_target(target)
            return template.format(target=target)
        return template

    def _pick_template(self, intent, seed_text):
        options = self._templates.get(intent) or self._templates["working"]
        last = self._last_template_by_intent.get(intent)
        if len(options) > 1 and last in options:
            options = [item for item in options if item != last]
        template = random.choice(options)
        self._last_template_by_intent[intent] = template
        return template

    def _extract_subject(self, text, intent):
        patterns = {
            "app_open": [
                r"\bopening\s+(.+?)(?:\s+boss)?[.!?]?$",
                r"\blaunch(?:ing)?\s+(.+?)(?:\s+boss)?[.!?]?$",
                r"\b(.+?)\s+open ho gaya(?: hai)?[.!?]?$",
                r"\bopen\s+(?!ho\b)(.+?)(?:\s+now)?[.!?]?$",
            ],
            "app_close": [
                r"\bclosing\s+(.+?)(?:\s+boss)?[.!?]?$",
                r"\bclose\s+(.+?)(?:\s+now)?[.!?]?$",
                r"\b(.+?)\s+band(?:\s+ho gaya)?(?:\s+hai)?[.!?]?$",
            ],
            "media_play": [
                r"\bplaying\s+(.+?)(?:\s+on\s+youtube)?(?:\s+boss)?[.!?]?$",
                r"\bstarting\s+(.+?)(?:\s+boss)?[.!?]?$",
                r"\bplay\s+(.+?)(?:\s+on\s+youtube)?[.!?]?$",
            ],
            "web_search": [
                r"\bfor\s+(.+?)(?:\s+boss)?[.!?]?$",
                r"\bsearch(?:ing)?\s+(.+?)(?:\s+online)?(?:\s+boss)?[.!?]?$",
                r"\bchecking\s+(.+?)(?:\s+online)?(?:\s+boss)?[.!?]?$",
            ],
        }
        for pattern in patterns.get(intent, []):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                subject = match.group(1).strip(" .")
                subject = re.sub(r"^(?:boss[\s,.:;-]+)", "", subject, flags=re.IGNORECASE)
                subject = re.sub(r"\b(the web|google|browser)\b", "", subject, flags=re.IGNORECASE)
                subject = " ".join(subject.split()).strip(" .")
                if subject:
                    return subject
        return ""

    def _polish_existing(self, text, emotion):
        polished = str(text).strip()
        if not polished:
            return ""
        if emotion in {"thinking", "friendly", "supportive"} and "..." not in polished:
            polished = self._add_pause(polished)
        if len(polished.split()) <= 7 and "Boss" not in polished:
            polished = f"Alright Boss... {polished[0].lower() + polished[1:]}" if len(polished) > 1 else f"Alright Boss... {polished}"
        return self._clean_text(polished)

    def _build_spoken_text(self, display_text, emotion):
        spoken = self._add_pause(display_text) if emotion in {"thinking", "friendly", "supportive"} else display_text
        if re.search(r"Boss\.(?!\.)", spoken) and len(spoken.split()) <= 10:
            spoken = re.sub(r"Boss\.(?!\.)", "Boss...", spoken)
        spoken = re.sub(r"\.{3,}", " [short pause] ", spoken)
        return re.sub(r"\s+", " ", spoken).strip()

    def _add_pause(self, text):
        spoken = str(text).strip()
        if "..." in spoken:
            return spoken
        if "Boss," in spoken:
            return spoken.replace("Boss,", "Boss...", 1)
        if "Boss." in spoken:
            return spoken.replace("Boss.", "Boss...", 1)
        if "Boss" in spoken:
            return spoken.replace("Boss", "Boss...", 1)
        words = spoken.split()
        if len(words) > 4:
            return f"{' '.join(words[:3])}... {' '.join(words[3:])}"
        return spoken

    def _display_target(self, subject):
        lowered = subject.lower()
        aliases = {
            "vs code": "VS Code",
            "vscode": "VS Code",
            "youtube": "YouTube",
            "gmail": "Gmail",
            "chrome": "Chrome",
            "spotify": "Spotify",
            "whatsapp": "WhatsApp",
        }
        if lowered in aliases:
            return aliases[lowered]
        if len(subject) <= 4 and subject.isupper():
            return subject
        return subject[:1].upper() + subject[1:]

    def _clean_text(self, text):
        cleaned = str(text).strip()
        cleaned = cleaned.replace("MYRA", "Myra")
        cleaned = cleaned.replace("Sir ji", "Boss")
        cleaned = cleaned.replace("sir ji", "Boss")
        cleaned = re.sub(r"\bAI\b", "A I", cleaned)
        cleaned = re.sub(r"\bvs code\b", "VS Code", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bwhatsapp\b", "WhatsApp", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _uses_v3_model(self):
        return "v3" in self.model_id

    def _is_error(self, normalized):
        error_tokens = [
            "went wrong",
            "try that again",
            "issue aa gaya",
            "fail",
            "failed",
            "error",
            "nahi ho paya",
            "not available",
            "could not",
        ]
        return any(token in normalized for token in error_tokens)

    def _is_listening_on(self, normalized):
        return any(
            token in normalized
            for token in [
                "listening resumed",
                "continuous listening active",
                "listening active",
                "voice mode is live",
            ]
        )

    def _is_listening_off(self, normalized):
        return any(
            token in normalized
            for token in [
                "listening stopped",
                "listening is paused",
                "already stopped",
                "stay quiet",
            ]
        )

    def _looks_like_web_search(self, normalized):
        return any(token in normalized for token in ["search", "checking online", "google", "browser", "looking that up"])

    def _looks_like_media(self, normalized):
        if re.search(r"\b(open|launch|start|run)\s+(youtube|you tube|spotify|netflix)\b", normalized):
            return False
        if re.search(r"\b(youtube|you tube|spotify|netflix)\s+open\b", normalized):
            return False
        return any(
            token in normalized
            for token in [
                "play ",
                "playing ",
                "play song",
                "play music",
                "music",
                "song",
                "video",
                " on youtube",
                "youtube par",
                "youtube pe",
                "youtube pr",
            ]
        )

    def _looks_like_app_open(self, normalized):
        return any(
            token in normalized
            for token in [
                "opening ",
                "launching ",
                "open ho gaya",
                "folder open ho gaya",
                "settings open",
            ]
        )

    def _looks_like_app_close(self, normalized):
        return any(token in normalized for token in ["closing ", "close ", "band ho gaya", "shutting "])

    def _looks_supportive(self, normalized):
        supportive_tokens = [
            "take it easy",
            "take a breath",
            "take a break",
            "i m here",
            "i'm here",
            "go easy on yourself",
            "one thing at a time",
            "everything will work out",
            "we ll handle it",
            "we'll handle it",
        ]
        return any(token in normalized for token in supportive_tokens)

    def _looks_cheerful(self, normalized):
        cheerful_tokens = [
            "that s great to hear",
            "that's great to hear",
            "love that",
            "nice choice",
            "good to hear",
            "keep that energy going",
            "awesome",
        ]
        return any(token in normalized for token in cheerful_tokens)

    def _looks_like_greeting_reply(self, normalized):
        greeting_tokens = [
            "what s up",
            "what's up",
            "good to see you",
            "i m here",
            "i'm here",
            "what are we working on",
            "what are we up to",
            "what about you",
        ]
        return any(token in normalized for token in greeting_tokens)


class VoiceEngine:
    ELEVENLABS_URL_TEMPLATE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    DEFAULT_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"
    DEFAULT_MODEL_ID = "eleven_turbo_v2_5"

    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        load_dotenv(dotenv_path=self.base_dir / ".env")

        self._messages = queue.Queue()
        self.temp_dir = self.base_dir / "temp"
        self.cache_dir = self.temp_dir / "voice_cache"
        self.runtime_dir = self.temp_dir / "voice_runtime"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self._clear_runtime_files()

        self.api_key = (
            os.getenv("MYRA_ELEVENLABS_API_KEY", "").strip()
            or os.getenv("ELEVENLABS_API_KEY", "").strip()
        )
        self.voice_id = (
            os.getenv("MYRA_ELEVENLABS_VOICE_ID", "").strip()
            or os.getenv("ELEVENLABS_VOICE_ID", "").strip()
            or self.DEFAULT_VOICE_ID
        )
        self.model_id = os.getenv("MYRA_ELEVENLABS_MODEL", self.DEFAULT_MODEL_ID).strip() or self.DEFAULT_MODEL_ID
        self.output_format = os.getenv("MYRA_ELEVENLABS_OUTPUT", "mp3_44100_128").strip() or "mp3_44100_128"
        self.speed = self._clamp_float(os.getenv("MYRA_ELEVENLABS_SPEED", "0.96"), 0.9, 1.0, 0.96)
        self.stability = self._clamp_float(os.getenv("MYRA_ELEVENLABS_STABILITY", "0.36"), 0.0, 1.0, 0.36)
        self.similarity_boost = self._clamp_float(os.getenv("MYRA_ELEVENLABS_SIMILARITY", "0.82"), 0.0, 1.0, 0.82)
        self.style = self._clamp_float(os.getenv("MYRA_ELEVENLABS_STYLE", "0.22"), 0.0, 1.0, 0.22)
        self.timeout = self._clamp_float(os.getenv("MYRA_ELEVENLABS_TIMEOUT", "30"), 5.0, 120.0, 30.0)
        self.edge_voice = os.getenv("MYRA_EDGE_TTS_VOICE", "en-IN-NeerjaNeural").strip() or "en-IN-NeerjaNeural"
        self.edge_rate = os.getenv("MYRA_EDGE_TTS_RATE", "-6%").strip() or "-6%"
        self.edge_pitch = os.getenv("MYRA_EDGE_TTS_PITCH", "+0Hz").strip() or "+0Hz"
        self.edge_tts_exe = self._discover_edge_tts_exe()
        self.debug_voice = str(os.getenv("MYRA_DEBUG_VOICE", "")).strip().lower() in {"1", "true", "yes", "on"}

        self.formatter = HumanSpeechFormatter(self.model_id)
        self._fallback_speaker = None
        self._worker = threading.Thread(target=self._speech_loop, daemon=True)
        self._worker.start()

    def prepare_response(self, text):
        prepared = self.formatter.prepare(text)
        if not prepared.display_text:
            return PreparedSpeech("", "", "", "generic", "normal")
        return prepared

    def speak(self, text):
        prepared = text if isinstance(text, PreparedSpeech) else self.prepare_response(text)
        if not prepared.display_text:
            return
        if self.debug_voice:
            print("Myra:", prepared.display_text)
        self._messages.put(prepared)

    def export_audio_file(self, text, target_path):
        prepared = text if isinstance(text, PreparedSpeech) else self.prepare_response(text)
        if not prepared.display_text:
            return None

        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        actual_target = target
        try:
            if self.api_key:
                cache_id = self._cache_id(prepared)
                self._generate_audio(prepared, actual_target, cache_id)
            elif self.edge_tts_exe:
                self._generate_edge_tts_audio(prepared, actual_target)
            elif pyttsx3 is not None:
                actual_target = target.with_suffix(".wav")
                self._generate_local_audio(prepared, actual_target)
            else:
                return None
        except Exception:
            self._safe_unlink(actual_target)
            return None

        if actual_target.exists() and actual_target.stat().st_size > 0:
            return actual_target
        return None

    def _speech_loop(self):
        if pythoncom is not None:
            try:
                pythoncom.CoInitialize()
            except Exception:
                pass

        try:
            while True:
                prepared = self._messages.get()
                try:
                    self._play(prepared)
                except Exception as exc:
                    if self.debug_voice:
                        print(f"Myra voice playback failed: {exc}")
        finally:
            if pythoncom is not None:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _play(self, prepared):
        last_error = None
        if self.api_key:
            try:
                self._play_with_elevenlabs(prepared)
                return
            except Exception as exc:
                last_error = exc
        if self.edge_tts_exe:
            try:
                self._play_with_edge_tts(prepared)
                return
            except Exception as exc:
                last_error = exc
        try:
            self._play_with_fallback(prepared.spoken_text or prepared.display_text)
            return
        except Exception as exc:
            last_error = exc
        if self.debug_voice and last_error is not None:
            print(f"Myra voice playback failed: {last_error}")

    def _play_with_elevenlabs(self, prepared):
        cache_id = self._cache_id(prepared)
        cache_path = self.cache_dir / f"{cache_id}.mp3"
        if not cache_path.exists():
            self._generate_audio(prepared, cache_path, cache_id)

        playback_path = self.runtime_dir / f"myra_voice_{cache_id}_{int(time.time() * 1000)}.mp3"
        shutil.copy2(cache_path, playback_path)
        try:
            if not self._play_mp3(playback_path):
                raise RuntimeError("no mp3 playback backend available")
        finally:
            self._safe_unlink(playback_path)

    def _play_with_edge_tts(self, prepared):
        cache_id = self._cache_id(prepared)
        cache_path = self.cache_dir / f"edge_{cache_id}.mp3"
        if not cache_path.exists():
            self._generate_edge_tts_audio(prepared, cache_path)

        playback_path = self.runtime_dir / f"myra_edge_voice_{cache_id}_{int(time.time() * 1000)}.mp3"
        shutil.copy2(cache_path, playback_path)
        try:
            if not self._play_mp3(playback_path):
                raise RuntimeError("no mp3 playback backend available")
        finally:
            self._safe_unlink(playback_path)

    def _generate_audio(self, prepared, target_path, cache_id):
        url = self.ELEVENLABS_URL_TEMPLATE.format(voice_id=self.voice_id)
        params = {"output_format": self.output_format}
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        voice_settings = self._voice_settings_for(prepared.emotion)
        payload = {
            "text": prepared.spoken_text,
            "model_id": self.model_id,
            "voice_settings": {
                "stability": voice_settings["stability"],
                "similarity_boost": voice_settings["similarity_boost"],
                "style": voice_settings["style"],
                "use_speaker_boost": True,
                "speed": voice_settings["speed"],
            },
            "seed": int(cache_id[:8], 16),
        }

        response = requests.post(url, params=params, headers=headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        target_path.write_bytes(response.content)

    def _generate_edge_tts_audio(self, prepared, target_path):
        text = self._strip_pause_markup(prepared.spoken_text or prepared.display_text)
        if not text:
            raise RuntimeError("empty text for Edge TTS")
        command = [
            str(self.edge_tts_exe),
            "--voice",
            self.edge_voice,
            f"--rate={self.edge_rate}",
            f"--pitch={self.edge_pitch}",
            "--text",
            text,
            "--write-media",
            str(target_path),
        ]
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=self.timeout)
        if completed.returncode != 0 or (not target_path.exists()) or target_path.stat().st_size == 0:
            error_text = (completed.stderr or completed.stdout or "edge-tts failed").strip()
            raise RuntimeError(error_text)

    def _generate_local_audio(self, prepared, target_path):
        if pyttsx3 is None:
            raise RuntimeError("pyttsx3 unavailable")
        engine = pyttsx3.init()
        engine.setProperty("rate", 165)
        engine.save_to_file(self._strip_pause_markup(prepared.spoken_text or prepared.display_text), str(target_path))
        engine.runAndWait()
        time.sleep(0.5)
        if (not target_path.exists()) or target_path.stat().st_size == 0:
            raise RuntimeError("local tts export failed")

    def _play_mp3(self, path):
        global pygame
        if pygame is None:
            try:
                import pygame as pygame_module

                pygame = pygame_module
            except Exception:
                pygame = False
        if pygame:
            try:
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(str(path))
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    time.sleep(0.05)
                if hasattr(pygame.mixer.music, "unload"):
                    pygame.mixer.music.unload()
                return True
            except Exception as exc:
                if self.debug_voice:
                    print(f"Myra pygame playback failed: {exc}")
                try:
                    pygame.mixer.music.stop()
                    if hasattr(pygame.mixer.music, "unload"):
                        pygame.mixer.music.unload()
                except Exception:
                    pass
        return self._play_with_windows_media(path)

    def _play_with_windows_media(self, path):
        try:
            resolved = str(Path(path).resolve())
            escaped_path = resolved.replace("'", "''")
            command = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                (
                    "Add-Type -AssemblyName presentationCore; "
                    f"$path = '{escaped_path}'; "
                    "$player = New-Object System.Windows.Media.MediaPlayer; "
                    "$player.Open([uri]$path); "
                    "$player.Volume = 1.0; "
                    "$player.Play(); "
                    "Start-Sleep -Milliseconds 750; "
                    "while (-not $player.NaturalDuration.HasTimeSpan) { Start-Sleep -Milliseconds 200 }; "
                    "Start-Sleep -Milliseconds ([int]$player.NaturalDuration.TimeSpan.TotalMilliseconds + 250); "
                    "$player.Stop(); "
                    "$player.Close();"
                ),
            ]
            completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=max(15, int(self.timeout)))
            if completed.returncode != 0:
                error_text = (completed.stderr or completed.stdout or "").strip()
                if self.debug_voice and error_text:
                    print(f"Myra PowerShell playback failed: {error_text}")
                return False
            return True
        except Exception as exc:
            if self.debug_voice:
                print(f"Myra PowerShell playback failed: {exc}")
            return False

    def _play_with_fallback(self, message):
        speaker = self._ensure_fallback_speaker()
        if speaker is None:
            raise RuntimeError("no fallback speech backend available")
        speaker(message)

    def _ensure_fallback_speaker(self):
        if self._fallback_speaker is not None:
            return self._fallback_speaker
        if pyttsx3 is None:
            return None
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 155)
            engine.setProperty("volume", 1.0)

            def speak_with_pyttsx3(message):
                engine.say(self._strip_pause_markup(message))
                engine.runAndWait()

            self._fallback_speaker = speak_with_pyttsx3
            return self._fallback_speaker
        except Exception as exc:
            if self.debug_voice:
                print(f"Myra pyttsx3 init failed: {exc}")
            return None

    def _strip_pause_markup(self, text):
        cleaned = str(text).replace("[short pause]", " ")
        return re.sub(r"\s+", " ", cleaned.replace("...", ". ")).strip()

    def _clear_runtime_files(self):
        for stale_file in self.runtime_dir.glob("myra_voice_*.mp3"):
            self._safe_unlink(stale_file)

    def _safe_unlink(self, path):
        try:
            Path(path).unlink(missing_ok=True)
        except Exception:
            pass

    def _discover_edge_tts_exe(self):
        candidates = [
            self.base_dir / "venv" / "Scripts" / "edge-tts.exe",
            Path(sys.executable).resolve().parent / "Scripts" / "edge-tts.exe",
            Path(sys.executable).resolve().parent / "edge-tts.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        discovered = shutil.which("edge-tts")
        return Path(discovered) if discovered else None

    def _cache_id(self, prepared):
        digest = hashlib.sha256(
            (
                f"{prepared.display_text}|{prepared.spoken_text}|{prepared.intent}|{prepared.emotion}|"
                f"{self.voice_id}|{self.model_id}|{self.output_format}|{self.speed}|"
                f"{self.stability}|{self.similarity_boost}|{self.style}|"
                f"{self.edge_voice}|{self.edge_rate}|{self.edge_pitch}"
            ).encode("utf-8")
        ).hexdigest()
        return digest

    def _voice_settings_for(self, emotion):
        settings = {
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "speed": self.speed,
        }
        overrides = {
            "friendly": {"stability": min(1.0, self.stability + 0.06), "style": min(1.0, self.style + 0.04)},
            "thinking": {"stability": min(1.0, self.stability + 0.12), "style": max(0.0, self.style - 0.03), "speed": max(0.9, self.speed - 0.03)},
            "excited": {"stability": max(0.0, self.stability - 0.06), "style": min(1.0, self.style + 0.16), "speed": min(1.0, self.speed + 0.02)},
            "cheerful": {"stability": max(0.0, self.stability - 0.03), "style": min(1.0, self.style + 0.12), "speed": min(1.0, self.speed + 0.01)},
            "supportive": {"stability": min(1.0, self.stability + 0.18), "style": min(1.0, self.style + 0.05), "speed": max(0.9, self.speed - 0.04)},
            "error": {"stability": min(1.0, self.stability + 0.1), "style": max(0.0, self.style - 0.04)},
        }
        settings.update(overrides.get(emotion, {}))
        return settings

    def _clamp_float(self, raw_value, minimum, maximum, default):
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, value))
