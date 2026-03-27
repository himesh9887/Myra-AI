from __future__ import annotations

import threading

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

try:
    import sounddevice as sd
except Exception:  # pragma: no cover
    sd = None


class NoiseDetector:
    def __init__(self, config=None):
        self.config = dict(config or {})
        self.sample_rate = int(self.config.get("sampleRate", 16000))
        self.block_size = int(self.config.get("blockSize", 1024))
        self.threshold = float(self.config.get("noiseThreshold", 0.055))
        self.available = np is not None and sd is not None
        self._stream = None
        self._lock = threading.Lock()
        self._level = 0.0
        self._error = ""

    def start(self):
        if not self.available:
            return {
                "available": False,
                "started": False,
                "error": "sounddevice unavailable",
            }

        if self._stream is not None:
            return {
                "available": True,
                "started": True,
                "error": "",
            }

        try:
            self._stream = sd.InputStream(
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                callback=self._audio_callback,
            )
            self._stream.start()
            self._error = ""
            return {
                "available": True,
                "started": True,
                "error": "",
            }
        except Exception as exc:
            self._stream = None
            self._error = str(exc)
            return {
                "available": True,
                "started": False,
                "error": self._error,
            }

    def snapshot(self):
        with self._lock:
            level = float(self._level)
            error = str(self._error)
        return {
            "available": self.available,
            "started": self._stream is not None,
            "level": level,
            "alert": level >= self.threshold,
            "threshold": self.threshold,
            "error": error,
        }

    def stop(self):
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def _audio_callback(self, indata, frames, time_info, status):  # pragma: no cover
        if np is None:
            return
        try:
            samples = np.asarray(indata, dtype=np.float32)
            level = float(np.sqrt(np.mean(np.square(samples))))
            with self._lock:
                self._level = (self._level * 0.72) + (level * 0.28)
                self._error = ""
        except Exception as exc:
            with self._lock:
                self._error = str(exc)
