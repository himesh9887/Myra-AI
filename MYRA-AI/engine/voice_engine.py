import queue
import threading

import pythoncom

try:
    import win32com.client
except Exception:  # pragma: no cover
    win32com = None

try:
    import pyttsx3
except Exception:  # pragma: no cover
    pyttsx3 = None


class VoiceEngine:
    def __init__(self):
        self._messages = queue.Queue()
        self._worker = threading.Thread(target=self._speech_loop, daemon=True)
        self._worker.start()

    def speak(self, text):
        message = str(text).strip()
        if not message:
            return
        print("Myra:", message)
        self._messages.put(message)

    def _speech_loop(self):
        pythoncom.CoInitialize()
        speaker = self._create_speaker()
        if speaker is None:
            print("Myra voice init failed: no speech backend available")
            pythoncom.CoUninitialize()
            return

        try:
            while True:
                message = self._messages.get()
                try:
                    speaker(message)
                except Exception as exc:
                    print(f"Myra voice playback failed: {exc}")
        finally:
            pythoncom.CoUninitialize()

    def _create_speaker(self):
        if win32com is not None:
            try:
                sapi = win32com.client.Dispatch("SAPI.SpVoice")
                sapi.Rate = 1

                def speak_with_sapi(message):
                    sapi.Speak(message)

                return speak_with_sapi
            except Exception as exc:
                print(f"Myra SAPI init failed: {exc}")

        if pyttsx3 is not None:
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", 170)

                def speak_with_pyttsx3(message):
                    engine.say(message)
                    engine.runAndWait()

                return speak_with_pyttsx3
            except Exception as exc:
                print(f"Myra pyttsx3 init failed: {exc}")

        return None
