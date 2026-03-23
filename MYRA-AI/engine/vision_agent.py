import os
import re
import shutil
import sys
import threading
import time
from datetime import datetime
from importlib import import_module
from pathlib import Path

import requests

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

from engine.ai_brain import API_TOKEN


def _load_optional_vision_dependency(module_name):
    try:
        return import_module(module_name)
    except Exception:
        project_root = Path(__file__).resolve().parent.parent
        site_packages = project_root / "venv" / "Lib" / "site-packages"
        if site_packages.exists():
            site_packages_str = str(site_packages)
            if site_packages_str not in sys.path:
                sys.path.insert(0, site_packages_str)
            try:
                return import_module(module_name)
            except Exception:
                return None
        return None


if cv2 is None:
    cv2 = _load_optional_vision_dependency("cv2")
if np is None:
    np = _load_optional_vision_dependency("numpy")


class VisionAgent:
    CAPTION_API_URL = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-large"

    def __init__(self, base_dir):
        self.base_dir = Path(base_dir)
        self.capture_dir = self.base_dir / "captures"
        self.capture_dir.mkdir(exist_ok=True)
        self._headers = {"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {}
        self._preview_thread = None
        self._preview_stop = threading.Event()
        self._preview_lock = threading.Lock()
        self._latest_preview_path = self.capture_dir / "vision_live_latest.jpg"

    def handle(self, command):
        text = " ".join(str(command).lower().split())
        if not text:
            return False, ""
        if self.is_camera_open_command(text):
            return True, self.open_camera()
        if self.is_visual_query(text):
            return True, self.answer_visual_query(command)
        return False, ""

    def is_visual_query(self, text):
        normalized = " ".join(re.sub(r"[^a-z0-9\s]", " ", str(text).lower()).split())
        visual_tokens = (
            "camera",
            "camra",
            "carma",
            "cam",
            "kapde",
            "clothes",
            "outfit",
            "dress",
            "shirt",
            "tshirt",
            "kurta",
            "look",
            "kaise lag",
            "kese lag",
            "how do i look",
            "what am i wearing",
            "dekh",
            "dekh ke",
            "see me",
            "watch me",
        )
        return any(token in normalized for token in visual_tokens)

    def open_camera(self):
        message, _ = self.open_camera_with_frame()
        return message

    def open_camera_with_frame(self):
        if not self._camera_runtime_available():
            return "Boss, camera feature ke liye OpenCV install karna padega. Command chalao: pip install opencv-python numpy", ""
        frame_path, error = self.capture_frame(target_path=self._latest_preview_path)
        if frame_path:
            return "Boss, camera preview panel me open kar diya hai.", frame_path
        return f"Boss, camera open nahi ho paya. {error or 'Webcam unavailable hai.'}", ""

    def start_camera_preview(self, frame_callback=None):
        if not self._camera_runtime_available():
            return "Boss, camera feature ke liye OpenCV install karna padega. Command chalao: pip install opencv-python numpy", ""

        with self._preview_lock:
            if self._preview_thread is not None and self._preview_thread.is_alive():
                return "Boss, camera preview already on hai.", str(self._latest_preview_path) if self._latest_preview_path.exists() else ""

            self._preview_stop.clear()
            self._preview_thread = threading.Thread(
                target=self._preview_loop,
                args=(frame_callback,),
                daemon=True,
            )
            self._preview_thread.start()

        for _ in range(15):
            if self._latest_preview_path.exists():
                return "Boss, camera preview panel me start ho gaya hai.", str(self._latest_preview_path)
            time.sleep(0.2)
        return "Boss, camera start ho gaya hai, preview update ho raha hai.", ""

    def stop_camera_preview(self):
        with self._preview_lock:
            running = self._preview_thread is not None and self._preview_thread.is_alive()
            self._preview_stop.set()
        if running:
            return "Boss, camera preview off kar diya hai."
        return "Boss, camera already off hai."

    def is_preview_running(self):
        return self._preview_thread is not None and self._preview_thread.is_alive() and not self._preview_stop.is_set()

    def answer_visual_query(self, question):
        answer, _ = self.analyze_visual_query(question)
        return answer

    def analyze_visual_query(self, question):
        if not self._camera_runtime_available():
            return "Boss, camera analysis ke liye OpenCV install karna padega. Command chalao: pip install opencv-python numpy", ""
        frame_path, error = self._frame_for_analysis()
        if not frame_path:
            return f"Boss, camera access nahi mila. {error or 'Webcam unavailable hai.'}", ""

        caption = self._caption_image(frame_path)
        palette = self._dominant_colors(frame_path)
        question_text = str(question).lower()
        file_name = Path(frame_path).name

        if any(token in question_text for token in ["kapde", "clothes", "outfit", "dress", "shirt", "tshirt", "kurta"]):
            return self._build_outfit_reply(caption, palette, file_name), frame_path
        if any(token in question_text for token in ["how do i look", "kaise lag", "kese lag", "look"]):
            return self._build_appearance_reply(caption, palette, file_name), frame_path
        return self._build_general_visual_reply(caption, palette, file_name), frame_path

    def capture_frame(self, target_path=None):
        if not self._camera_runtime_available():
            return "", "OpenCV ya numpy installed nahi hai."
        camera = None
        try:
            camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not camera.isOpened():
                camera = cv2.VideoCapture(0)
            if not camera.isOpened():
                return "", "Webcam open nahi ho rahi."

            time.sleep(0.8)
            frame = None
            for _ in range(6):
                ok, current = camera.read()
                if ok and current is not None:
                    frame = current
                time.sleep(0.08)

            if frame is None:
                return "", "Camera frame read nahi hua."

            target = Path(target_path) if target_path else self.capture_dir / f"vision_{datetime.now():%Y%m%d_%H%M%S}.jpg"
            cv2.imwrite(str(target), frame)
            return str(target), ""
        except Exception as exc:
            return "", str(exc)
        finally:
            if camera is not None:
                camera.release()

    def _frame_for_analysis(self):
        if self.is_preview_running() and self._latest_preview_path.exists():
            target = self.capture_dir / f"vision_{datetime.now():%Y%m%d_%H%M%S}.jpg"
            try:
                shutil.copyfile(self._latest_preview_path, target)
                return str(target), ""
            except Exception:
                pass
        return self.capture_frame()

    def _caption_image(self, image_path):
        if not self._headers:
            return ""
        try:
            with open(image_path, "rb") as image_file:
                response = requests.post(
                    self.CAPTION_API_URL,
                    headers=self._headers,
                    data=image_file.read(),
                    timeout=25,
                )
            payload = response.json()
            if isinstance(payload, list) and payload:
                return str(payload[0].get("generated_text", "")).strip()
        except Exception:
            return ""
        return ""

    def _dominant_colors(self, image_path):
        if not self._camera_runtime_available():
            return []
        image = cv2.imread(str(image_path))
        if image is None:
            return []

        height, width = image.shape[:2]
        crop = image[int(height * 0.15) : int(height * 0.85), int(width * 0.2) : int(width * 0.8)]
        if crop.size == 0:
            crop = image

        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        pixels = rgb.reshape((-1, 3)).astype(np.float32)
        if len(pixels) > 8000:
            indices = np.random.choice(len(pixels), 8000, replace=False)
            pixels = pixels[indices]

        try:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 12, 1.0)
            _, labels, centers = cv2.kmeans(pixels, 3, None, criteria, 4, cv2.KMEANS_RANDOM_CENTERS)
            counts = np.bincount(labels.flatten())
            ordered = [centers[index] for index in counts.argsort()[::-1]]
        except Exception:
            ordered = [pixels.mean(axis=0)]

        names = []
        for color in ordered:
            name = self._closest_color_name(color)
            if name not in names:
                names.append(name)
        return names[:3]

    def _closest_color_name(self, rgb):
        palette = {
            "black": (25, 25, 25),
            "white": (235, 235, 235),
            "gray": (128, 128, 128),
            "navy": (30, 52, 92),
            "blue": (55, 120, 210),
            "sky blue": (110, 190, 245),
            "green": (62, 150, 95),
            "olive": (110, 120, 55),
            "yellow": (225, 200, 70),
            "orange": (225, 140, 60),
            "red": (200, 65, 65),
            "pink": (220, 120, 170),
            "purple": (135, 90, 170),
            "brown": (120, 80, 55),
            "beige": (205, 190, 150),
        }
        rgb = np.array(rgb, dtype=np.float32)
        best_name = "neutral"
        best_distance = float("inf")
        for name, sample in palette.items():
            distance = float(np.linalg.norm(rgb - np.array(sample, dtype=np.float32)))
            if distance < best_distance:
                best_distance = distance
                best_name = name
        return best_name

    def _build_outfit_reply(self, caption, colors, file_name):
        color_text = ", ".join(colors[:2]) if colors else "neutral"
        if caption:
            return (
                f"Boss, camera on karke jo frame mila usme {caption}. "
                f"Overall tones {color_text} side par lag rahe hain, to outfit clean aur noticeable lag raha hai. "
                f"Reference frame {file_name} me save hai."
            )
        return (
            f"Boss, camera on karke maine frame dekha. Exact outfit detail perfect clear nahi aayi, lekin {color_text} tones dominate kar rahe hain. "
            f"Look simple aur balanced lag raha hai. Reference frame {file_name} me save kar diya hai."
        )

    def _build_appearance_reply(self, caption, colors, file_name):
        color_text = ", ".join(colors[:2]) if colors else "balanced"
        if caption:
            return (
                f"Boss, camera khol ke jo dikh raha hai uske hisaab se {caption}. "
                f"Overall presentation {color_text} tone ki wajah se neat lag rahi hai. "
                f"Agar chaho to main specifically kapde, color combo ya background par bhi bata sakti hoon. "
                f"Frame {file_name} me save hai."
            )
        return (
            f"Boss, camera frame ke hisaab se aap presentable lag rahe ho. "
            f"Dominant tones {color_text} side par hain. Agar chaho to closer outfit check bhi kar sakti hoon. "
            f"Frame {file_name} me save hai."
        )

    def _build_general_visual_reply(self, caption, colors, file_name):
        color_text = ", ".join(colors[:2]) if colors else "balanced"
        if caption:
            return (
                f"Boss, camera ne jo dekha uske hisaab se {caption}. "
                f"Dominant tones {color_text} hain. Frame {file_name} me save hai."
            )
        return (
            f"Boss, camera frame capture ho gaya hai. Exact scene detail clear nahi mili, "
            f"lekin dominant tones {color_text} dikh rahe hain. Frame {file_name} me save hai."
        )

    def is_camera_open_command(self, text):
        return any(
            token in text
            for token in (
                "open camera",
                "camera open",
                "camra open",
                "carma open",
                "open cam",
                "start camera",
                "camera chalu karo",
                "camera kholo",
            )
        )

    def is_camera_off_command(self, text):
        normalized = " ".join(str(text).lower().split())
        return normalized in {
            "camera off",
            "camera band",
            "camera band karo",
            "close camera",
            "stop camera",
            "cam off",
        }

    def _preview_loop(self, frame_callback=None):
        camera = None
        try:
            camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not camera.isOpened():
                camera = cv2.VideoCapture(0)
            if not camera.isOpened():
                return

            while not self._preview_stop.is_set():
                ok, frame = camera.read()
                if not ok or frame is None:
                    time.sleep(0.1)
                    continue
                cv2.imwrite(str(self._latest_preview_path), frame)
                if frame_callback is not None:
                    try:
                        frame_callback(str(self._latest_preview_path), "Boss, live camera preview chal raha hai.")
                    except Exception:
                        pass
                time.sleep(0.35)
        finally:
            if camera is not None:
                camera.release()
            with self._preview_lock:
                self._preview_thread = None

    def _camera_runtime_available(self):
        return cv2 is not None and np is not None
