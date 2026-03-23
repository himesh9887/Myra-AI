import math

from PyQt6.QtCore import QEasingCurve, QPropertyAnimation, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class ChatBubble(QWidget):
    def __init__(self, role, message, timestamp):
        super().__init__()
        self.role = role

        root = QHBoxLayout(self)
        root.setContentsMargins(4, 6, 4, 6)
        root.setSpacing(0)

        left_spacer = QWidget()
        left_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        right_spacer = QWidget()
        right_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        container = QFrame()
        container.setObjectName("UserBubble" if role == "user" else "AssistantBubble")
        container.setMinimumWidth(0)
        container.setMaximumWidth(560)
        container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel("YOU" if role == "user" else "MYRA")
        title.setObjectName("BubbleTitle")

        body = QLabel(message)
        body.setWordWrap(True)
        body.setObjectName("BubbleBody")
        body.setMinimumWidth(0)
        body.setMaximumWidth(520)
        body.setTextFormat(Qt.TextFormat.PlainText)

        time_label = QLabel(timestamp)
        time_label.setObjectName("BubbleTime")
        time_label.setAlignment(
            Qt.AlignmentFlag.AlignRight if role == "user" else Qt.AlignmentFlag.AlignLeft
        )

        layout.addWidget(title)
        layout.addWidget(body)
        layout.addWidget(time_label)

        if role == "user":
            root.addWidget(left_spacer)
            root.addWidget(container, 0, Qt.AlignmentFlag.AlignRight)
            root.addSpacing(18)
            root.setStretch(0, 1)
        else:
            root.addSpacing(18)
            root.addWidget(container, 0, Qt.AlignmentFlag.AlignLeft)
            root.addWidget(right_spacer)
            root.setStretch(2, 1)


class QuickActionButton(QPushButton):
    def __init__(self, icon_text, title, command, tooltip):
        super().__init__()
        self.command = command
        self.setObjectName("QuickActionButton")
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(54)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(3)

        icon = QLabel(icon_text)
        icon.setObjectName("QuickActionIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        text = QLabel(title)
        text.setObjectName("QuickActionText")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(icon)
        layout.addWidget(text)

        self._height_anim = QPropertyAnimation(self, b"minimumHeight", self)
        self._height_anim.setDuration(150)
        self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def enterEvent(self, event):
        self.setProperty("hovered", True)
        self.style().unpolish(self)
        self.style().polish(self)
        self._height_anim.stop()
        self._height_anim.setStartValue(self.minimumHeight())
        self._height_anim.setEndValue(58)
        self._height_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        self._height_anim.stop()
        self._height_anim.setStartValue(self.minimumHeight())
        self._height_anim.setEndValue(54)
        self._height_anim.start()
        super().leaveEvent(event)


class StatusPanel(QFrame):
    def __init__(self, title, value):
        super().__init__()
        self.setObjectName("StatCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("StatTitle")

        self.value_label = QLabel(value)
        self.value_label.setObjectName("StatValue")

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value):
        self.value_label.setText(value)


class CameraFeedWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InnerPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.title_label = QLabel("VISION CAMERA")
        self.title_label.setObjectName("SectionMiniTitle")

        self.preview_label = QLabel("Camera standby")
        self.preview_label.setObjectName("CameraPreview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(190)

        self.status_label = QLabel("Boss, camera preview yahan dikhega.")
        self.status_label.setWordWrap(True)
        self.status_label.setObjectName("CameraStatus")

        layout.addWidget(self.title_label)
        layout.addWidget(self.preview_label, 1)
        layout.addWidget(self.status_label)

    def set_frame(self, image_path="", status_text=""):
        path = str(image_path).strip()
        if path and QPixmap(path).isNull() is False:
            pixmap = QPixmap(path)
            scaled = pixmap.scaled(
                self.preview_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(scaled)
            self.preview_label.setText("")
        else:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("Camera off")
        if status_text:
            self.status_label.setText(str(status_text).strip())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        current = self.preview_label.pixmap()
        if current is not None and not current.isNull():
            self.preview_label.setPixmap(
                current.scaled(
                    self.preview_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )


class RadarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0
        self._state = "online"
        self._activity = "Standby"
        self._pulse_frames = 0
        self._targets = [
            {"angle": 42, "distance": 0.48, "strength": 0.9},
        ]
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(40)

    def set_state(self, state):
        self._state = str(state).lower()
        self._targets = self._build_targets_for_state(self._state)
        self.update()

    def set_activity(self, activity):
        text = str(activity).strip()
        if text:
            self._activity = text
        self.update()

    def update_targets(self, targets, activity=""):
        payload = []
        for item in targets or []:
            try:
                payload.append(
                    {
                        "angle": int(item.get("angle", 0)) % 360,
                        "distance": max(0.1, min(1.0, float(item.get("distance", 0.5)))),
                        "strength": max(0.1, min(1.0, float(item.get("strength", 0.6)))),
                    }
                )
            except Exception:
                continue
        if payload:
            self._targets = payload
        if activity:
            self._activity = str(activity).strip()
        self._pulse_frames = 10
        self.update()

    def pulse_ping(self, activity=""):
        if activity:
            self._activity = str(activity).strip()
        self._pulse_frames = 10
        self.update()

    def _tick(self):
        self._angle = (self._angle + 3) % 360
        if self._pulse_frames > 0:
            self._pulse_frames -= 1
        self.update()

    def _accent(self):
        return {
            "online": QColor(95, 245, 255, 220),
            "listening": QColor(94, 255, 246, 240),
            "processing": QColor(150, 170, 255, 240),
            "speaking": QColor(120, 255, 214, 240),
            "error": QColor(255, 108, 130, 240),
        }.get(self._state, QColor(95, 245, 255, 220))

    def _build_targets_for_state(self, state):
        patterns = {
            "online": [{"angle": 42, "distance": 0.48, "strength": 0.55}],
            "listening": [
                {"angle": 38, "distance": 0.46, "strength": 0.95},
                {"angle": 114, "distance": 0.72, "strength": 0.4},
            ],
            "processing": [
                {"angle": 60, "distance": 0.36, "strength": 0.92},
                {"angle": 198, "distance": 0.64, "strength": 0.5},
                {"angle": 312, "distance": 0.58, "strength": 0.42},
            ],
            "speaking": [
                {"angle": 28, "distance": 0.4, "strength": 0.82},
                {"angle": 144, "distance": 0.62, "strength": 0.38},
            ],
            "error": [{"angle": 0, "distance": 0.28, "strength": 1.0}],
        }
        return patterns.get(state, patterns["online"])

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

        rect = self.rect().adjusted(10, 10, -10, -10)
        side = min(rect.width(), rect.height())
        box = QRectF(
            rect.center().x() - side / 2,
            rect.center().y() - side / 2,
            side,
            side,
        )
        center = box.center()

        accent = self._accent()
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 120), 1))
        for ratio in (0.25, 0.5, 0.75, 1.0):
            radius = (side / 2) * ratio
            painter.drawEllipse(center, radius, radius)

        painter.drawLine(
            QPointF(center.x() - side / 2, center.y()),
            QPointF(center.x() + side / 2, center.y()),
        )
        painter.drawLine(
            QPointF(center.x(), center.y() - side / 2),
            QPointF(center.x(), center.y() + side / 2),
        )

        sweep_path = QPainterPath()
        sweep_path.moveTo(center)
        for offset in range(0, 45, 3):
            angle = math.radians(self._angle - offset)
            point = QPointF(
                center.x() + math.cos(angle) * side / 2,
                center.y() - math.sin(angle) * side / 2,
            )
            sweep_path.lineTo(point)
        sweep_path.closeSubpath()
        painter.fillPath(sweep_path, QColor(accent.red(), accent.green(), accent.blue(), 45))

        pen = QPen(accent, 2)
        painter.setPen(pen)
        angle = math.radians(self._angle)
        painter.drawLine(
            center,
            QPointF(
                center.x() + math.cos(angle) * side / 2,
                center.y() - math.sin(angle) * side / 2,
            ),
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 230))
        painter.drawEllipse(center, 5, 5)

        for target in self._targets:
            target_angle = math.radians(target["angle"])
            radius = (side / 2) * float(target["distance"])
            point = QPointF(
                center.x() + math.cos(target_angle) * radius,
                center.y() - math.sin(target_angle) * radius,
            )
            boost = 25 if self._pulse_frames > 0 else 0
            alpha = int(110 + 120 * float(target["strength"])) + boost
            painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), alpha))
            size = 4 + 2 * float(target["strength"]) + (1 if self._pulse_frames > 0 else 0)
            painter.drawEllipse(point, size, size)

        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 180), 1))
        painter.drawText(self.rect().adjusted(12, 8, -12, -8), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight, self._activity.upper())


class JarvisCoreWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._angle = 0.0
        self._pulse = 0.0
        self._state = "online"
        self._accent = QColor("#55dfff")

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_state(self, state):
        self._state = str(state).lower()
        self._accent = {
            "online": QColor("#55dfff"),
            "listening": QColor("#6cfbff"),
            "processing": QColor("#8ea2ff"),
            "speaking": QColor("#74ffd9"),
            "error": QColor("#ff6d85"),
        }.get(self._state, QColor("#55dfff"))
        self.update()

    def _tick(self):
        speed = {
            "online": 1.6,
            "listening": 2.8,
            "processing": 2.1,
            "speaking": 3.0,
            "error": 1.2,
        }.get(self._state, 1.6)
        self._angle = (self._angle + speed) % 360
        self._pulse += 0.08
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(12, 12, -12, -12)
        center = rect.center()
        side = min(rect.width(), rect.height())
        radius = side / 2

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(3, 13, 24, 220))
        painter.drawEllipse(rect)

        for ratio, alpha in ((0.95, 70), (0.78, 110), (0.56, 150)):
            painter.setPen(QPen(QColor(self._accent.red(), self._accent.green(), self._accent.blue(), alpha), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, radius * ratio, radius * ratio)

        for offset in (0, 120, 240):
            painter.drawArc(
                QRectF(center.x() - radius * 0.9, center.y() - radius * 0.9, radius * 1.8, radius * 1.8),
                int((self._angle + offset) * 16),
                int(52 * 16),
            )

        pulse_radius = radius * (0.18 + 0.02 * math.sin(self._pulse))
        painter.setBrush(QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 210))
        painter.setPen(QPen(QColor(230, 250, 255, 180), 1.5))
        painter.drawEllipse(center, pulse_radius, pulse_radius)

        painter.setPen(QPen(QColor(self._accent.red(), self._accent.green(), self._accent.blue(), 180), 1))
        for index in range(8):
            angle = math.radians(self._angle + index * 45)
            inner = QPointF(
                center.x() + math.cos(angle) * radius * 0.26,
                center.y() + math.sin(angle) * radius * 0.26,
            )
            outer = QPointF(
                center.x() + math.cos(angle) * radius * 0.46,
                center.y() + math.sin(angle) * radius * 0.46,
            )
            painter.drawLine(inner, outer)


class HudFaceWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._state = "online"
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(45)

    def set_state(self, state):
        self._state = str(state).lower()
        self.update()

    def _tick(self):
        self._pulse += 0.08
        self.update()

    def _accent(self):
        return {
            "online": QColor("#4de0ff"),
            "listening": QColor("#68f7ff"),
            "processing": QColor("#95a4ff"),
            "speaking": QColor("#75ffde"),
            "error": QColor("#ff7088"),
        }.get(self._state, QColor("#4de0ff"))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

        accent = self._accent()
        glow_alpha = 65 + int(20 * math.sin(self._pulse))

        rect = self.rect().adjusted(20, 8, -20, -8)
        width = rect.width()
        height = rect.height()
        cx = rect.center().x()
        top = rect.top()

        outline = QPolygonF(
            [
                QPointF(cx - width * 0.17, top + height * 0.06),
                QPointF(cx + width * 0.17, top + height * 0.06),
                QPointF(cx + width * 0.23, top + height * 0.18),
                QPointF(cx + width * 0.19, top + height * 0.42),
                QPointF(cx + width * 0.12, top + height * 0.58),
                QPointF(cx + width * 0.1, top + height * 0.72),
                QPointF(cx + width * 0.04, top + height * 0.88),
                QPointF(cx - width * 0.04, top + height * 0.88),
                QPointF(cx - width * 0.1, top + height * 0.72),
                QPointF(cx - width * 0.12, top + height * 0.58),
                QPointF(cx - width * 0.19, top + height * 0.42),
                QPointF(cx - width * 0.23, top + height * 0.18),
            ]
        )

        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), glow_alpha), 3))
        painter.setBrush(QColor(7, 18, 34, 80))
        painter.drawPolygon(outline)

        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 170), 2))
        painter.drawLine(
            QPointF(cx - width * 0.12, top + height * 0.22),
            QPointF(cx + width * 0.12, top + height * 0.22),
        )
        painter.drawLine(
            QPointF(cx - width * 0.1, top + height * 0.22),
            QPointF(cx - width * 0.18, top + height * 0.35),
        )
        painter.drawLine(
            QPointF(cx + width * 0.1, top + height * 0.22),
            QPointF(cx + width * 0.18, top + height * 0.35),
        )
        painter.drawLine(
            QPointF(cx - width * 0.08, top + height * 0.52),
            QPointF(cx + width * 0.08, top + height * 0.52),
        )

        left_eye = QPolygonF(
            [
                QPointF(cx - width * 0.15, top + height * 0.36),
                QPointF(cx - width * 0.03, top + height * 0.34),
                QPointF(cx - width * 0.06, top + height * 0.4),
                QPointF(cx - width * 0.17, top + height * 0.4),
            ]
        )
        right_eye = QPolygonF(
            [
                QPointF(cx + width * 0.15, top + height * 0.36),
                QPointF(cx + width * 0.03, top + height * 0.34),
                QPointF(cx + width * 0.06, top + height * 0.4),
                QPointF(cx + width * 0.17, top + height * 0.4),
            ]
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(accent.red(), accent.green(), accent.blue(), 210))
        painter.drawPolygon(left_eye)
        painter.drawPolygon(right_eye)

        painter.setPen(QPen(QColor(255, 96, 130, 180), 2))
        painter.drawLine(
            QPointF(cx - width * 0.09, top + height * 0.61),
            QPointF(cx - width * 0.04, top + height * 0.68),
        )
        painter.drawLine(
            QPointF(cx + width * 0.09, top + height * 0.61),
            QPointF(cx + width * 0.04, top + height * 0.68),
        )
        painter.drawLine(
            QPointF(cx - width * 0.04, top + height * 0.68),
            QPointF(cx + width * 0.04, top + height * 0.68),
        )


class BodyScanWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scan_y = 0.0
        self._state = "online"
        self._focus_metric = "cpu"
        self._summary = "System nominal"
        self._metrics = {
            "cpu": 0,
            "ram": 0,
            "disk": 0,
            "battery": 0,
        }
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(55)

    def set_state(self, state):
        self._state = str(state).lower()
        self.update()

    def update_metrics(self, cpu=0, ram=0, disk=0, battery=0):
        self._metrics = {
            "cpu": max(0, min(100, int(cpu))),
            "ram": max(0, min(100, int(ram))),
            "disk": max(0, min(100, int(disk))),
            "battery": max(0, min(100, int(battery))),
        }
        self.update()

    def set_focus_metric(self, metric_name):
        metric = str(metric_name).lower().strip()
        if metric in {"cpu", "ram", "disk", "battery"}:
            self._focus_metric = metric
            self.update()

    def set_summary(self, summary):
        text = str(summary).strip()
        if text:
            self._summary = text
            self.update()

    def _tick(self):
        self._scan_y = (self._scan_y + 0.03) % 1.0
        self.update()

    def _accent(self):
        return {
            "online": QColor("#7de7ff"),
            "listening": QColor("#75fff0"),
            "processing": QColor("#98a5ff"),
            "speaking": QColor("#7cffd8"),
            "error": QColor("#ff748d"),
        }.get(self._state, QColor("#7de7ff"))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

        w = self.width()
        h = self.height()
        accent = self._accent()
        pen = QPen(QColor(230, 240, 255, 110), 1)
        painter.setPen(pen)
        metrics_floor = h * 0.78
        footer_top = h * 0.82

        columns = (
            (w * 0.2, "CPU", self._metrics["cpu"]),
            (w * 0.5, "RAM", self._metrics["ram"]),
            (w * 0.8, "BAT", self._metrics["battery"]),
        )
        for center_x, label, value in columns:
            head = QRectF(center_x - 15, h * 0.08, 30, 30)
            body = QRectF(center_x - 16, h * 0.22, 32, h * 0.4)
            painter.drawEllipse(head)
            painter.drawRect(body)
            painter.drawLine(QPointF(center_x - 28, h * 0.33), QPointF(center_x + 28, h * 0.33))
            painter.drawLine(QPointF(center_x, h * 0.62), QPointF(center_x - 22, metrics_floor))
            painter.drawLine(QPointF(center_x, h * 0.62), QPointF(center_x + 22, metrics_floor))

            fill_height = body.height() * (value / 100.0)
            fill_rect = QRectF(body.left() + 2, body.bottom() - fill_height - 2, body.width() - 4, fill_height)
            is_focus = self._focus_metric == label.lower() or (self._focus_metric == "battery" and label == "BAT")
            fill_alpha = 70 + int(value * 1.2) + (35 if is_focus else 0)
            painter.fillRect(fill_rect, QColor(accent.red(), accent.green(), accent.blue(), fill_alpha))
            painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 220 if is_focus else 180), 1.4 if is_focus else 1))
            if is_focus:
                painter.drawRoundedRect(body.adjusted(-3, -3, 3, 3), 5, 5)
            painter.drawText(
                QRectF(center_x - 34, h * 0.86, 68, 18),
                Qt.AlignmentFlag.AlignCenter,
                f"{label} {value}%",
            )

        scan_y = h * self._scan_y
        painter.fillRect(QRectF(0, min(scan_y, footer_top - 10), w, 8), QColor(accent.red(), accent.green(), accent.blue(), 38))

        footer_rect = QRectF(6, footer_top, w - 12, h - footer_top - 6)
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 65), 1))
        painter.drawRoundedRect(footer_rect, 8, 8)

        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 180), 1))
        painter.drawText(
            QRectF(w * 0.58, footer_top + 4, w * 0.36, 18),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"DISK {self._metrics['disk']}%",
        )
        painter.drawText(
            QRectF(14, footer_top + 4, w * 0.5, 18),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self._summary.upper(),
        )
