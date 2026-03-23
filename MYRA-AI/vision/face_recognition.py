from __future__ import annotations

from engine import vision_agent as legacy_vision


class FaceRecognition:
    def __init__(self, camera_agent):
        self.camera = camera_agent

    def detect_faces(self):
        cv2 = getattr(legacy_vision, "cv2", None)
        if cv2 is None or not hasattr(self.camera, "capture_frame"):
            return "Boss, face recognition runtime available nahi hai."

        frame_path, error = self.camera.capture_frame()
        if not frame_path:
            return f"Boss, face detect nahi ho paya. {error or 'Camera unavailable hai.'}"

        image = cv2.imread(str(frame_path))
        if image is None:
            return "Boss, frame read nahi ho paya."

        cascade_path = getattr(cv2.data, "haarcascades", "") + "haarcascade_frontalface_default.xml"
        classifier = cv2.CascadeClassifier(cascade_path)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = classifier.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        count = len(faces)
        if count == 0:
            return "Boss, frame me koi clear face detect nahi hua."
        if count == 1:
            return "Boss, mujhe ek face clearly visible dikh raha hai."
        return f"Boss, mujhe {count} faces visible dikh rahe hain."
