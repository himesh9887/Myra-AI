from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSequentialAnimationGroup
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QWidget


def apply_glow(widget, color="#2ea8ff", blur_radius=32):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setColor(QColor(color))
    effect.setOffset(0, 0)
    widget.setGraphicsEffect(effect)
    return effect


def update_glow(effect, color, blur_radius):
    if effect is None:
        return
    effect.setColor(QColor(color))
    effect.setBlurRadius(blur_radius)


def slide_in(widget, start_point, end_point, duration=280):
    animation = QPropertyAnimation(widget, b"pos")
    animation.setStartValue(QPoint(*start_point))
    animation.setEndValue(QPoint(*end_point))
    animation.setDuration(duration)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    return animation


def ping(widget, points):
    group = QSequentialAnimationGroup(widget)
    for start_point, end_point in points:
        group.addAnimation(slide_in(widget, start_point, end_point))
    return group


def fade_in(widget, duration=220):
    if not isinstance(widget, QWidget):
        return None

    animation = QPropertyAnimation(widget, b"windowOpacity")
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setDuration(duration)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)
    return animation
